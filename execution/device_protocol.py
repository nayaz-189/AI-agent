"""Cross-device contract and bounded in-memory receiver; no network listener.

AuthenticatedTransport is a trusted adapter boundary, NOT authentication supplied
by a model or JSON flag. The only production adapter denies all delivery. A real
adapter needs pairing, peer authentication, durable replay storage and OS review.
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

    Peer registration is supplied by a future authenticated pairing store. No
    registration endpoint exists. Records are bounded, process-local and never
    evicted to make room; this is not restart-safe production replay protection.
    """
    def __init__(self, transport=None, *, registered_peers=(), clock=time):
        self._transport = transport if transport is not None else UnavailableTransport()
        if not isinstance(self._transport, AuthenticatedTransport):
            raise TypeError("A trusted transport adapter is required.")
        self._peers = frozenset(_uuid(peer) for peer in registered_peers)
        self._clock = clock
        self._records = {}
        self._lock = RLock()

    @staticmethod
    def _denial(task_id=None, code=ErrorCode.PERMISSION_DENIED):
        return {"task_id": task_id, "status": "failed", "verified": False, "error_code": code.value}

    @staticmethod
    def _ack(record):
        return {"task_id": record["task"].task_id, "status": record["status"].value,
                "verified": record["status"] == DeliveryStatus.COMPLETED,
                "error_code": record["error"]}

    def receive(self):
        with self._lock:
            try:
                delivery = self._transport.receive_verified()
                if type(delivery) is not VerifiedDelivery or delivery.peer_id not in self._peers:
                    return self._denial()
                task, hold = DeviceTask.parse(delivery.body, delivery.peer_id, self._clock())
                if task.target_device != "windows":
                    return self._denial(task.task_id, ErrorCode.BACKEND_UNAVAILABLE)
                key = (delivery.peer_id, task.task_id)
                prior = self._records.get(key)
                if prior is not None:
                    if prior["task"].fingerprint != task.fingerprint:
                        return self._denial(task.task_id)
                    return self._ack(prior)  # A duplicate never dispatches again.
                if len(self._records) >= 128:
                    return self._denial(task.task_id, ErrorCode.BACKEND_UNAVAILABLE)
                self._records[key] = {"task": task, "status": DeliveryStatus.WAITING if hold else DeliveryStatus.QUEUED,
                                      "error": None}
                return self._ack(self._records[key])
            except Exception:
                return self._denial()

    def dispatch_pending(self, *, online=False):
        """Local scheduler only. Untrusted JSON cannot dispatch or release holds."""
        with self._lock:
            for record in self._records.values():
                if record["status"] not in {DeliveryStatus.QUEUED, DeliveryStatus.WAITING}:
                    continue
                if self._clock() >= record["task"].expires_at:
                    record.update(status=DeliveryStatus.FAILED, error=ErrorCode.PRECONDITION_FAILED.value)
                elif online is True and record["status"] == DeliveryStatus.QUEUED:
                    record["status"] = DeliveryStatus.RUNNING
                    try:
                        outcome = _execute_calculator()
                        verified = type(outcome) is VerifiedOutcome and outcome.verified is True
                    except Exception:
                        verified = False
                    record.update(status=DeliveryStatus.COMPLETED if verified else DeliveryStatus.FAILED,
                                  error=None if verified else ErrorCode.VERIFICATION_FAILED.value)
            return [self._ack(r) for r in self._records.values()]

    def history(self):
        with self._lock:
            return [self._ack(r) for r in self._records.values()]
