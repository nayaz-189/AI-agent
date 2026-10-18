"""Cross-device contract and journal-backed receiver; no implicit network listener.

AuthenticatedTransport is a trusted adapter boundary, NOT authentication supplied
by a model or JSON flag. The default adapter denies all delivery. The optional
TLS adapter must be explicitly composed by the local device_server command.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from threading import RLock
from time import time
from uuid import UUID

from execution.safe_failure import ErrorCode
from execution.replay_journal import ReplayJournal, JournalError


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError("Invalid identifier.")
    return value


@dataclass(frozen=True)
class VerifiedDelivery:
    """Constructed only by a trusted transport after channel authentication."""
    peer_id: str
    body: bytes


class AuthenticatedTransport(ABC):
    def authorize_dispatch(self, peer_id):
        """Recheck live authorization immediately before claiming/executing."""
        return False

    @abstractmethod
    def receive_verified(self):
        """Return VerifiedDelivery or None, never caller-asserted identity."""
        raise NotImplementedError


class UnavailableTransport(AuthenticatedTransport):
    def receive_verified(self):
        return None


@dataclass(frozen=True)
class DeviceTask:
    task_id: str
    source_device: str
    target_device: str
    operation: str
    expires_at: float
    fingerprint: str

    @classmethod
    def parse(cls, body, peer_id, now):
        if type(body) is not bytes or not 0 < len(body) <= 8192:
            raise ValueError("Invalid request.")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate field.")
                result[key] = value
            return result

        data = json.loads(body.decode("utf-8"), object_pairs_hook=unique)
        fields = {"protocol_version", "task_id", "source_device", "target_device",
                  "operation", "arguments", "expires_at", "requires_approval"}
        if type(data) is not dict or set(data) != fields:
            raise ValueError("Invalid request.")
        if (type(data["protocol_version"]) is not int or data["protocol_version"] != 1
                or _uuid(data["source_device"]) != _uuid(peer_id)
                or data["target_device"] not in {"windows", "android"}
                or type(data["operation"]) is not str
                or data["operation"] != "open_calculator"
                or type(data["arguments"]) is not dict or data["arguments"] != {}
                or type(data["requires_approval"]) is not bool):
            raise ValueError("Invalid request.")
        # Remote modifications are unavailable. The flag grants no authorization;
        # true imposes an additional hold, never an automatic approval.
        if type(data["expires_at"]) is not str:
            raise ValueError("Invalid expiry.")
        expiry = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        if not now < expiry <= now + 300:
            raise ValueError("Expired or excessive request lifetime.")
        return cls(_uuid(data["task_id"]), peer_id, data["target_device"],
                   data["operation"], expiry,
                   sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()), data["requires_approval"]


@dataclass(frozen=True)
class VerifiedOutcome:
    verified: bool


def _execute_calculator():
    """Reuse validation/routing, then observe independently again before ack."""
    from execution.runtime import execute_plan
    from desktop.application_observer import observe_calculator
    task = execute_plan("Open Calculator", {"tool": "open_calculator", "arguments": {}})
    return VerifiedOutcome(task.status.value == "completed" and
                           observe_calculator().get("calculator_open") is True)


class DeviceReceiver:
    """Trusted composition API, never installed in the planner tool registry.

    Peer registration and a journal must be explicitly supplied by trusted local
    composition. No registration endpoint exists. No database is opened/created
    by default. Persisted
    queued tasks require authenticated redelivery after restart; storage is not
    authority to execute. The default transport remains unavailable.
    """
    def __init__(self, transport=None, *, registered_peers=(), clock=time, journal=None):
        self._transport = transport if transport is not None else UnavailableTransport()
        if not isinstance(self._transport, AuthenticatedTransport):
            raise TypeError("A trusted transport adapter is required.")
        self._peers = frozenset(_uuid(peer) for peer in registered_peers)
        self._clock = clock
        if journal is not None and type(journal) is not ReplayJournal:
            raise TypeError("A trusted replay journal is required.")
        self._journal = journal
        self._journal_failed = False
        self._pending = {}  # Only requests received through this live transport.
        self._lock = RLock()

    @staticmethod
    def _denial(task_id=None, code=ErrorCode.PERMISSION_DENIED):
        return {"task_id": task_id, "status": "failed", "verified": False, "error_code": code.value}

    def receive(self):
        with self._lock:
            try:
                delivery = self._transport.receive_verified()
                if type(delivery) is not VerifiedDelivery or delivery.peer_id not in self._peers:
                    return self._denial()
                task, hold = DeviceTask.parse(delivery.body, delivery.peer_id, self._clock())
                if task.target_device != "windows":
                    return self._denial(task.task_id, ErrorCode.BACKEND_UNAVAILABLE)
                if self._journal is None or self._journal_failed:
                    return self._denial(task.task_id, ErrorCode.BACKEND_UNAVAILABLE)
                key = (delivery.peer_id, task.task_id)
                receipt = self._journal.accept(task, hold, self._clock())
                if receipt is None:
                    return self._denial(task.task_id)
                if receipt["status"] in {"queued", "waiting"}:
                    self._pending[key] = task.fingerprint
                return receipt
            except JournalError:
                self._journal_failed = True
                return self._denial(code=ErrorCode.BACKEND_UNAVAILABLE)
            except Exception:
                return self._denial()

    def dispatch_pending(self, *, online=False):
        """Trusted scheduler; no message-based approval release."""
        with self._lock:
            if self._journal_failed:
                return [self._denial(code=ErrorCode.BACKEND_UNAVAILABLE)]
            if self._journal is None:
                return []
            try:
                if online is True:
                    for (peer, task_id), fingerprint in list(self._pending.items()):
                        if self._transport.authorize_dispatch(peer) is not True:
                            return [self._denial(task_id)]
                        claim = self._journal.claim(peer, task_id, fingerprint, self._clock())
                        if claim is None:
                            continue
                        # The claim transaction has COMMITTED before any action.
                        # Process death (including BaseException) leaves a durable,
                        # non-retryable claim; no finally block resets it to queued.
                        try:
                            if self._transport.authorize_dispatch(peer) is not True:
                                raise PermissionError()
                            outcome = _execute_calculator()
                            verified = type(outcome) is VerifiedOutcome and outcome.verified is True
                        except Exception:
                            verified = False
                        self._journal.finish(peer, task_id, claim, verified)
                        self._pending.pop((peer, task_id), None)
                return self._journal.receipts(self._peers, self._clock())
            except JournalError:
                self._journal_failed = True
                return [self._denial(code=ErrorCode.BACKEND_UNAVAILABLE)]

    def history(self):
        with self._lock:
            if self._journal_failed:
                return [self._denial(code=ErrorCode.BACKEND_UNAVAILABLE)]
            if self._journal is None:
                return []
            try:
                return self._journal.receipts(self._peers, self._clock())
            except JournalError:
                self._journal_failed = True
                return [self._denial(code=ErrorCode.BACKEND_UNAVAILABLE)]
