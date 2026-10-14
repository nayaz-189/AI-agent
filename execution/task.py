from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from execution.task_state import (
    StepStatus,
    TaskStatus,
)
from execution.task_step import TaskStep


def generate_task_id() -> str:
    return f"task_{uuid4().hex[:12]}"


@dataclass
class Task:
    goal: str

    steps: List[TaskStep] = field(
        default_factory=list
    )

    task_id: str = field(
        default_factory=generate_task_id
    )

    status: TaskStatus = TaskStatus.PENDING

    current_step_index: int = 0

    result: Optional[Dict[str, Any]] = None

    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError(
                "Task goal must be a non-empty string."
            )

        self.goal = self.goal.strip()

        if not isinstance(self.steps, list):
            raise TypeError(
                "Task steps must be provided as a list."
            )

        for step in self.steps:
            if not isinstance(step, TaskStep):
                raise TypeError(
                    "Every task step must be a TaskStep instance."
                )

    def add_step(
        self,
        step: TaskStep,
    ) -> None:
        if not isinstance(step, TaskStep):
            raise TypeError(
                "Only TaskStep instances can be added to a task."
            )

        if self.status != TaskStatus.PENDING:
            raise RuntimeError(
                "Steps cannot be added after task execution has started."
            )

        self.steps.append(step)

    def mark_running(self) -> None:
        if self.status != TaskStatus.PENDING:
            raise RuntimeError(
                "Only a pending task can start running."
            )

        self.status = TaskStatus.RUNNING
        self.error = None

    def mark_waiting_for_user(
        self,
        reason: str,
    ) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "Waiting state requires a reason."
            )

        self.status = TaskStatus.WAITING_FOR_USER
        self.error = reason.strip()

    def resume(self) -> None:
        if self.status != TaskStatus.WAITING_FOR_USER:
            raise RuntimeError(
                "Only a task waiting for the user can resume."
            )

        self.status = TaskStatus.RUNNING
        self.error = None

    def mark_completed(
        self,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        failed_steps = [
            step
            for step in self.steps
            if step.status == StepStatus.FAILED
        ]

        incomplete_steps = [
            step
            for step in self.steps
            if step.status not in {
                StepStatus.COMPLETED,
                StepStatus.SKIPPED,
            }
        ]

        if failed_steps:
            raise RuntimeError(
                "Task cannot complete while a step has failed."
            )

        if incomplete_steps:
            raise RuntimeError(
                "Task cannot complete while steps remain unfinished."
            )

        self.status = TaskStatus.COMPLETED
        self.result = result
        self.error = None

    def mark_failed(
        self,
        error: str,
    ) -> None:
        if not isinstance(error, str) or not error.strip():
            raise ValueError(
                "A failed task must include a non-empty error message."
            )

        self.status = TaskStatus.FAILED
        self.error = error.strip()

    def get_current_step(self) -> Optional[TaskStep]:
        if self.current_step_index >= len(self.steps):
            return None

        return self.steps[self.current_step_index]

    def advance_step(self) -> None:
        current_step = self.get_current_step()

        if current_step is None:
            raise RuntimeError(
                "Task has no current step to advance from."
            )

        if current_step.status not in {
            StepStatus.COMPLETED,
            StepStatus.SKIPPED,
        }:
            raise RuntimeError(
                "Cannot advance from an unfinished or failed step."
            )

        self.current_step_index += 1

    def has_remaining_steps(self) -> bool:
        return self.current_step_index < len(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
            "result": self.result,
            "error": self.error,
        }