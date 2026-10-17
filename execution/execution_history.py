from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
import hashlib
import json
import weakref
from execution.audit_schema import EVENTS, event_details, safe_action, safe_agent, safe_id


REDACTED = "[REDACTED]"


SENSITIVE_KEYS = {
    # Runtime intent and tool values can contain personal data even when the
    # caller does not label them as credentials. Keep structural evidence only.
    "goal",
    "url",
    "target",
    "launch_target",
    "text",
    "new_text",
    "new_value",
    "expected_before",
    "confirmation_token",
    "password",
    "passwd",
    "passcode",
    "pin",
    "secret",
    "api_key",
    "apikey",
    "api-key",
    "access_token",
    "access-token",
    "refresh_token",
    "refresh-token",
    "auth_token",
    "auth-token",
    "authorization",
    "bearer",
    "private_key",
    "private-key",
    "recovery_code",
    "recovery-code",
    "recovery_codes",
    "recovery-codes",
    "otp",
    "totp",
}


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower()


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalize_key(key)

    if normalized in SENSITIVE_KEYS:
        return True

    normalized_with_underscores = (
        normalized
        .replace("-", "_")
        .replace(" ", "_")
    )

    return normalized_with_underscores in SENSITIVE_KEYS


def sanitize_for_history(
    value: Any,
) -> Any:
    """
    Legacy key redactor retained for callers; NOT an audit/export boundary.

    Key-based secret redaction is deliberately conservative.

    Important:
    This is not yet a complete secret-detection system.
    ExecutionEvent enforces audit_schema independently; use that for audit data.
    """

    if isinstance(value, dict):
        sanitized: Dict[Any, Any] = {}

        for key, item in value.items():

            if _is_sensitive_key(key):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = sanitize_for_history(
                    item
                )

        return sanitized

    if isinstance(value, list):
        return [
            sanitize_for_history(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            sanitize_for_history(item)
            for item in value
        )

    if isinstance(value, set):
        return {
            sanitize_for_history(item)
            for item in value
        }

    return deepcopy(value)


def generate_event_id() -> str:
    return f"event_{uuid4().hex[:16]}"


def utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_timestamp(value) -> str:
    """Retain evidence time across copies, accepting only canonical UTC times."""
    if isinstance(value, str) and len(value) <= 32:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.utcoffset() == timezone.utc.utcoffset(None):
                return parsed.isoformat()
        except ValueError:
            pass
    return utc_timestamp()


@dataclass(frozen=True)
class ExecutionEvent:
    event_type: str
    task_id: str

    step_id: Optional[str] = None
    agent: Optional[str] = None
    action: Optional[str] = None

    details: Dict[str, Any] = field(
        default_factory=dict
    )

    event_id: str = field(
        default_factory=generate_event_id
    )

    timestamp: str = field(
        default_factory=utc_timestamp
    )

    def __post_init__(self) -> None:

        if (
            not isinstance(self.event_type, str)
            or not self.event_type.strip()
        ):
            raise ValueError(
                "Execution event requires a non-empty event_type."
            )

        if (
            not isinstance(self.task_id, str)
            or not self.task_id.strip()
        ):
            raise ValueError(
                "Execution event requires a non-empty task_id."
            )

        if not isinstance(self.details, dict):
            raise TypeError(
                "Execution event details must be a dictionary."
            )

        object.__setattr__(
            self,
            "event_type",
            self.event_type.strip() if self.event_type.strip() in EVENTS else "unknown_event",
        )

        object.__setattr__(
            self,
            "task_id",
            safe_id(self.task_id.strip()),
        )

        object.__setattr__(
            self,
            "details",
            event_details(self.event_type, self.details),
        )
        object.__setattr__(self, "step_id", safe_id(self.step_id))
        object.__setattr__(self, "event_id", safe_id(self.event_id))
        object.__setattr__(self, "agent", safe_agent(self.agent))
        object.__setattr__(self, "action", safe_action(self.action))
        object.__setattr__(self, "timestamp", safe_timestamp(self.timestamp))

    def to_dict(self) -> Dict[str, Any]:

        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "agent": self.agent,
            "action": self.action,
            "details": event_details(self.event_type, self.details),
        }


class ExecutionHistory:
    """
    In-memory structured execution history.

    History receives already-structured events and stores only
    sanitized copies.

    It has no authority to execute or approve actions.
    """

    def __init__(self) -> None:
        self._events: List[
            ExecutionEvent
        ] = []
        # Private observation provenance, never reconstructed from event JSON.
        # Weak references and digests avoid retaining task goals/argument values.
        self._verification_records = {}

    @staticmethod
    def _verification_binding(task):
        definition = {"task_id": task.task_id, "steps": [
            {"step_id": step.step_id, "agent": step.agent, "action": step.action,
             "arguments": step.arguments, "preconditions": step.preconditions,
             "postconditions": step.postconditions,
             "requires_confirmation": step.requires_confirmation}
            for step in task.steps]}
        encoded = json.dumps(definition, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).digest()

    def _record_verification(self, task, kind, passed):
        """Trusted observer/composition API; never expose as a model tool.

        Called during the final running step after independent observation. This
        records evidence only, grants no execution authority, and is not an OS or
        cryptographic boundary against malicious Python inside this process.
        """
        from execution.task import Task
        from execution.task_state import TaskStatus, StepStatus
        if (type(task) is not Task or task.status != TaskStatus.RUNNING
                or not task.steps or task.get_current_step() is not task.steps[-1]
                or task.steps[-1].status != StepStatus.RUNNING
                or kind not in {"calculator", "document_export", "research_report"}
                or type(passed) is not bool):
            return
        key = id(task)
        # Invalidate earlier evidence even if binding the new observation fails.
        self._verification_records.pop(key, None)
        try:
            binding = self._verification_binding(task)
        except (TypeError, ValueError):
            return

        def discard(reference):
            current = self._verification_records.get(key)
            if current is not None and current[0] is reference:
                self._verification_records.pop(key, None)

        self._verification_records[key] = (weakref.ref(task, discard), binding, kind, passed)

    def has_verification(self, task, kind):
        """Read a bound receipt, not a status/condition declaration or audit claim."""
        from execution.task import Task
        from execution.task_state import TaskStatus, StepStatus
        if (type(task) is not Task or task.status != TaskStatus.COMPLETED or task.error
                or not task.steps or any(s.status != StepStatus.COMPLETED or s.error for s in task.steps)):
            return False
        record = self._verification_records.get(id(task))
        try:
            return bool(record is not None and record[0]() is task and record[2] == kind
                        and record[3] is True and record[1] == self._verification_binding(task))
        except (TypeError, ValueError):
            return False

    def record(
        self,
        event: ExecutionEvent,
    ) -> None:

        if not isinstance(
            event,
            ExecutionEvent,
        ):
            raise TypeError(
                "ExecutionHistory can only record ExecutionEvent objects."
            )

        safe_event = ExecutionEvent(
            event_type=event.event_type,
            task_id=event.task_id,
            step_id=event.step_id,
            agent=event.agent,
            action=event.action,
            details=event_details(event.event_type, event.details),
            event_id=event.event_id,
            timestamp=event.timestamp,
        )

        self._events.append(
            safe_event
        )

    def all_events(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            event.to_dict()
            for event in self._events
        ]

    def events_for_task(
        self,
        task_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            event.to_dict()
            for event in self._events
            if event.task_id == safe_id(task_id)
        ]

    def events_for_step(
        self,
        step_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            event.to_dict()
            for event in self._events
            if event.step_id == safe_id(step_id)
        ]

    def count(
        self,
    ) -> int:

        return len(
            self._events
        )

    def clear(
        self,
    ) -> None:

        self._events.clear()
        self._verification_records.clear()
