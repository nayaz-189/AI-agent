from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


REDACTED = "[REDACTED]"


SENSITIVE_KEYS = {
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
    Create a sanitized copy of execution data before it enters history.

    Key-based secret redaction is deliberately conservative.

    Important:
    This is not yet a complete secret-detection system.
    Schema-aware sensitivity metadata will be added later.
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
            self.event_type.strip(),
        )

        object.__setattr__(
            self,
            "task_id",
            self.task_id.strip(),
        )

        object.__setattr__(
            self,
            "details",
            sanitize_for_history(
                self.details
            ),
        )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "agent": self.agent,
            "action": self.action,
            "details": sanitize_for_history(
                self.details
            ),
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
            details=sanitize_for_history(
                event.details
            ),
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
            if event.task_id == task_id
        ]

    def events_for_step(
        self,
        step_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            event.to_dict()
            for event in self._events
            if event.step_id == step_id
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