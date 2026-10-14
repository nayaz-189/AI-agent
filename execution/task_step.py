from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from execution.task_state import StepStatus


def generate_step_id() -> str:
    return f"step_{uuid4().hex[:12]}"


@dataclass
class TaskStep:
    action: str
    agent: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    postconditions: List[Dict[str, Any]] = field(default_factory=list)

    requires_confirmation: bool = False

    step_id: str = field(default_factory=generate_step_id)
    status: StepStatus = StepStatus.PENDING

    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:

        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError(
                "Task step action must be a non-empty string."
            )

        self.action = self.action.strip()

        if self.agent is not None:
            if not isinstance(self.agent, str) or not self.agent.strip():
                raise ValueError(
                    "Task step agent must be None or a non-empty string."
                )

            self.agent = self.agent.strip()

        if not isinstance(self.arguments, dict):
            raise TypeError(
                "Task step arguments must be a dictionary."
            )

        if not isinstance(self.preconditions, list):
            raise TypeError(
                "Task step preconditions must be a list."
            )

        if not isinstance(self.postconditions, list):
            raise TypeError(
                "Task step postconditions must be a list."
            )

        if not isinstance(self.requires_confirmation, bool):
            raise TypeError(
                "requires_confirmation must be boolean."
            )

    def mark_running(self) -> None:

        if self.status not in {
            StepStatus.PENDING,
            StepStatus.WAITING_FOR_USER,
        }:
            raise RuntimeError(
                "Only a pending or waiting step can start running."
            )

        self.status = StepStatus.RUNNING
        self.error = None

    def mark_waiting_for_user(
        self,
        reason: str,
    ) -> None:

        if self.status != StepStatus.PENDING:
            raise RuntimeError(
                "Only a pending step can wait for user confirmation."
            )

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "Waiting state requires a reason."
            )

        self.status = StepStatus.WAITING_FOR_USER
        self.error = reason.strip()

    def mark_completed(
        self,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:

        if self.status != StepStatus.RUNNING:
            raise RuntimeError(
                "Only a running step can complete."
            )

        self.status = StepStatus.COMPLETED
        self.result = result
        self.error = None

    def mark_failed(
        self,
        error: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:

        if self.status not in {
            StepStatus.PENDING,
            StepStatus.RUNNING,
            StepStatus.WAITING_FOR_USER,
        }:
            raise RuntimeError(
                "Only a pending, running, or waiting step can fail."
            )

        if not isinstance(error, str) or not error.strip():
            raise ValueError(
                "A failed step must include a non-empty error message."
            )

        self.status = StepStatus.FAILED
        self.error = error.strip()
        self.result = result

    def mark_skipped(
        self,
        reason: str,
    ) -> None:

        if self.status != StepStatus.PENDING:
            raise RuntimeError(
                "Only a pending step can be skipped."
            )

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "A skipped step must include a reason."
            )

        self.status = StepStatus.SKIPPED
        self.error = reason.strip()

    def is_terminal(self) -> bool:

        return self.status in {
            StepStatus.COMPLETED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        }

    def to_dict(self) -> Dict[str, Any]:

        return {
            "step_id": self.step_id,
            "agent": self.agent,
            "action": self.action,
            "arguments": self.arguments,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }