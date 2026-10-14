from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from execution.condition_evaluator import ConditionEvaluator
from execution.execution_history import ExecutionEvent, ExecutionHistory
from execution.execution_router import ExecutionRouter
from execution.task import Task
from execution.task_state import StepStatus, TaskStatus
from execution.task_step import TaskStep


ActionHandler = Callable[
    [Dict[str, Any]],
    Dict[str, Any],
]

StateProvider = Callable[
    [],
    Dict[str, Any],
]


@dataclass(frozen=True)
class StepExecutionResult:
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskExecutor:
    """
    Controlled sequential task executor.

    Responsibilities:
    - sequencing,
    - precondition checking,
    - routing,
    - confirmation pauses,
    - postcondition verification,
    - fail-closed execution,
    - sanitized execution evidence.

    ExecutionHistory is observational only.
    It cannot approve, route, or execute actions.

    approved_step_id remains temporary Day 13 workflow evidence.
    It is NOT a security credential.
    """

    def __init__(
        self,
        state_provider: Optional[StateProvider] = None,
        execution_router: Optional[ExecutionRouter] = None,
        execution_history: Optional[ExecutionHistory] = None,
    ) -> None:

        self._action_handlers: Dict[str, ActionHandler] = {}

        self._state_provider = state_provider
        self._execution_router = execution_router

        self._condition_evaluator = ConditionEvaluator()

        self._execution_history = (
            execution_history
            if execution_history is not None
            else ExecutionHistory()
        )

    @property
    def execution_history(self) -> ExecutionHistory:
        return self._execution_history

    def _record_event(
        self,
        event_type: str,
        task: Task,
        step: Optional[TaskStep] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:

        safe_details = (
            details
            if isinstance(details, dict)
            else {}
        )

        event = ExecutionEvent(
            event_type=event_type,
            task_id=task.task_id,
            step_id=(
                step.step_id
                if step is not None
                else None
            ),
            agent=(
                step.agent
                if step is not None
                else None
            ),
            action=(
                step.action
                if step is not None
                else None
            ),
            details=safe_details,
        )

        self._execution_history.record(event)

    def register_action(
        self,
        action: str,
        handler: ActionHandler,
    ) -> None:

        if not isinstance(action, str) or not action.strip():
            raise ValueError(
                "Action name must be a non-empty string."
            )

        if not callable(handler):
            raise TypeError(
                "Action handler must be callable."
            )

        normalized_action = action.strip()

        if normalized_action in self._action_handlers:
            raise ValueError(
                f"Action already registered: {normalized_action}"
            )

        self._action_handlers[
            normalized_action
        ] = handler

    def has_action(
        self,
        action: str,
    ) -> bool:

        return action in self._action_handlers

    def _get_state(
        self,
    ) -> Dict[str, Any]:

        if self._state_provider is None:
            return {}

        try:
            state = self._state_provider()

        except Exception as exc:
            raise RuntimeError(
                "State provider raised "
                f"{type(exc).__name__}."
            ) from exc

        if not isinstance(state, dict):
            raise RuntimeError(
                "State provider must return a dictionary."
            )

        return state

    def _evaluate_conditions(
        self,
        conditions,
        phase: str,
    ) -> Optional[str]:

        if not conditions:
            return None

        try:
            state = self._get_state()

        except RuntimeError as exc:
            return (
                f"{phase} state observation failed: {exc}"
            )

        evaluation = (
            self._condition_evaluator.evaluate_all(
                conditions=conditions,
                state=state,
            )
        )

        if evaluation.passed:
            return None

        if evaluation.results:

            failed = evaluation.results[-1]

            return (
                f"{phase} failed: "
                f"type={failed.condition_type}, "
                f"key={failed.key}, "
                f"expected={failed.expected!r}, "
                f"observed={failed.observed!r}, "
                f"reason={failed.reason}"
            )

        return (
            f"{phase} failed: "
            f"{evaluation.error or 'Unknown condition failure.'}"
        )

    def _normalize_raw_result(
        self,
        raw_result: Any,
        source_name: str,
    ) -> StepExecutionResult:

        if not isinstance(raw_result, dict):

            return StepExecutionResult(
                success=False,
                error=(
                    f"{source_name} returned an invalid result. "
                    "Expected a dictionary."
                ),
            )

        success = raw_result.get("success")

        if not isinstance(success, bool):

            return StepExecutionResult(
                success=False,
                error=(
                    f"{source_name} result must contain "
                    "a boolean 'success' field."
                ),
            )

        result = raw_result.get("result")

        if result is not None and not isinstance(
            result,
            dict,
        ):

            return StepExecutionResult(
                success=False,
                error=(
                    f"{source_name} result payload must be "
                    "a dictionary or None."
                ),
            )

        if success and raw_result.get("error") not in (None, ""):
            return StepExecutionResult(
                success=False,
                error=f"{source_name} returned contradictory success and error fields.",
            )

        if success:

            return StepExecutionResult(
                success=True,
                result=result,
            )

        error = raw_result.get("error")

        if not isinstance(error, str) or not error.strip():

            error = (
                f"{source_name} reported failure "
                "without an error message."
            )

        return StepExecutionResult(
            success=False,
            result=result,
            error=error.strip(),
        )

    def _execute_local_step(
        self,
        step: TaskStep,
    ) -> StepExecutionResult:

        handler = self._action_handlers.get(
            step.action
        )

        if handler is None:

            return StepExecutionResult(
                success=False,
                error=(
                    "No registered local action handler for: "
                    f"{step.action}"
                ),
            )

        try:
            raw_result = handler(
                dict(step.arguments)
            )

        except Exception as exc:

            return StepExecutionResult(
                success=False,
                error=(
                    "Local action handler raised "
                    f"{type(exc).__name__}."
                ),
            )

        return self._normalize_raw_result(
            raw_result=raw_result,
            source_name="Local action handler",
        )

    def _execute_routed_step(
        self,
        step: TaskStep,
    ) -> StepExecutionResult:

        if self._execution_router is None:

            return StepExecutionResult(
                success=False,
                error=(
                    "Step requires routed execution but "
                    "no ExecutionRouter is configured."
                ),
            )

        route_result = self._execution_router.route(
            agent=step.agent,
            action=step.action,
            arguments=dict(step.arguments),
        )

        return StepExecutionResult(
            success=route_result.success,
            result=route_result.result,
            error=route_result.error,
        )

    def _execute_step(
        self,
        step: TaskStep,
    ) -> StepExecutionResult:

        if step.agent is not None:

            return self._execute_routed_step(
                step
            )

        return self._execute_local_step(
            step
        )

    def execute(
        self,
        task: Task,
        approved_step_id: Optional[str] = None,
    ) -> Task:

        if not isinstance(task, Task):

            raise TypeError(
                "TaskExecutor.execute requires "
                "a Task instance."
            )

        if task.status == TaskStatus.PENDING:

            task.mark_running()

            self._record_event(
                "task_started",
                task,
                details={
                    "goal": task.goal,
                    "step_count": len(task.steps),
                },
            )

        elif task.status == TaskStatus.WAITING_FOR_USER:

            task.resume()

            self._record_event(
                "task_resumed",
                task,
                details={
                    "approved_step_id": approved_step_id,
                },
            )

        else:

            raise RuntimeError(
                "Task must be pending or waiting for user."
            )

        if not task.steps:

            task.mark_failed(
                "Task contains no executable steps."
            )

            self._record_event(
                "task_failed",
                task,
                details={
                    "error": task.error,
                },
            )

            return task

        while task.has_remaining_steps():

            step = task.get_current_step()

            if step is None:

                task.mark_failed(
                    "Task reported remaining steps but "
                    "no current step was available."
                )

                self._record_event(
                    "task_failed",
                    task,
                    details={
                        "error": task.error,
                    },
                )

                return task

            if step.status not in {
                StepStatus.PENDING,
                StepStatus.WAITING_FOR_USER,
            }:

                task.mark_failed(
                    (
                        "Current step was not executable: "
                        f"{step.step_id}"
                    )
                )

                self._record_event(
                    "task_failed",
                    task,
                    step=step,
                    details={
                        "error": task.error,
                    },
                )

                return task

            # =====================================
            # CONFIRMATION PAUSE
            # =====================================

            if step.requires_confirmation:

                if approved_step_id != step.step_id:

                    if step.status == StepStatus.PENDING:

                        step.mark_waiting_for_user(
                            "Explicit user confirmation required."
                        )

                        self._record_event(
                            "confirmation_required",
                            task,
                            step=step,
                            details={
                                "arguments": step.arguments,
                                "reason": step.error,
                            },
                        )

                    task.mark_waiting_for_user(
                        (
                            "Waiting for confirmation for "
                            f"step {step.step_id}."
                        )
                    )

                    self._record_event(
                        "task_paused",
                        task,
                        step=step,
                        details={
                            "reason": task.error,
                        },
                    )

                    return task

            # =====================================
            # PRECONDITIONS
            # =====================================

            if step.preconditions:

                self._record_event(
                    "preconditions_check_started",
                    task,
                    step=step,
                    details={
                        "conditions": step.preconditions,
                    },
                )

            precondition_error = (
                self._evaluate_conditions(
                    conditions=step.preconditions,
                    phase="Precondition",
                )
            )

            if precondition_error is not None:

                step.mark_failed(
                    error=precondition_error
                )

                self._record_event(
                    "preconditions_failed",
                    task,
                    step=step,
                    details={
                        "error": precondition_error,
                    },
                )

                task.mark_failed(
                    (
                        f"Step {step.step_id} blocked: "
                        f"{precondition_error}"
                    )
                )

                self._record_event(
                    "step_failed",
                    task,
                    step=step,
                    details={
                        "stage": "precondition",
                        "error": step.error,
                    },
                )

                self._record_event(
                    "task_failed",
                    task,
                    step=step,
                    details={
                        "error": task.error,
                    },
                )

                return task

            if step.preconditions:

                self._record_event(
                    "preconditions_passed",
                    task,
                    step=step,
                )

            # =====================================
            # EXECUTION
            # =====================================

            step.mark_running()

            self._record_event(
                "step_started",
                task,
                step=step,
                details={
                    "arguments": step.arguments,
                },
            )

            execution_result = (
                self._execute_step(step)
            )

            if not execution_result.success:

                error = (
                    execution_result.error
                    or "Step execution failed."
                )

                step.mark_failed(
                    error=error,
                    result=execution_result.result,
                )

                self._record_event(
                    "action_failed",
                    task,
                    step=step,
                    details={
                        "error": error,
                        "result": execution_result.result,
                    },
                )

                task.mark_failed(
                    (
                        f"Step {step.step_id} failed: "
                        f"{error}"
                    )
                )

                self._record_event(
                    "step_failed",
                    task,
                    step=step,
                    details={
                        "stage": "execution",
                        "error": step.error,
                    },
                )

                self._record_event(
                    "task_failed",
                    task,
                    step=step,
                    details={
                        "error": task.error,
                    },
                )

                return task

            self._record_event(
                "action_succeeded",
                task,
                step=step,
                details={
                    "result": execution_result.result,
                },
            )

            # =====================================
            # POSTCONDITIONS
            # =====================================

            if step.postconditions:

                self._record_event(
                    "postconditions_check_started",
                    task,
                    step=step,
                    details={
                        "conditions": step.postconditions,
                    },
                )

            postcondition_error = (
                self._evaluate_conditions(
                    conditions=step.postconditions,
                    phase="Postcondition",
                )
            )

            if postcondition_error is not None:

                step.mark_failed(
                    error=postcondition_error,
                    result=execution_result.result,
                )

                self._record_event(
                    "postconditions_failed",
                    task,
                    step=step,
                    details={
                        "error": postcondition_error,
                    },
                )

                task.mark_failed(
                    (
                        f"Step {step.step_id} failed "
                        f"verification: "
                        f"{postcondition_error}"
                    )
                )

                self._record_event(
                    "step_failed",
                    task,
                    step=step,
                    details={
                        "stage": "postcondition",
                        "error": step.error,
                    },
                )

                self._record_event(
                    "task_failed",
                    task,
                    step=step,
                    details={
                        "error": task.error,
                    },
                )

                return task

            if step.postconditions:

                self._record_event(
                    "postconditions_passed",
                    task,
                    step=step,
                )

            # =====================================
            # VERIFIED SUCCESS
            # =====================================

            step.mark_completed(
                result=execution_result.result
            )

            self._record_event(
                "step_completed",
                task,
                step=step,
                details={
                    "result": step.result,
                },
            )

            task.advance_step()

            # Approval is single-step only.
            approved_step_id = None

        task.mark_completed(
            result={
                "completed_steps": len(task.steps),
            }
        )

        self._record_event(
            "task_completed",
            task,
            details={
                "result": task.result,
            },
        )

        return task
