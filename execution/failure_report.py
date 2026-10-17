from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from execution.safe_failure import ErrorCode, STAGES, SafeFailure, safe_message
from execution.audit_schema import safe_id, safe_action, safe_agent

from execution.execution_history import (
    ExecutionEvent,
    ExecutionHistory,
    sanitize_for_history,
)


def _safe_evidence(events):
    result = []
    for event in events[-12:]:
        if not isinstance(event, dict):
            continue
        result.append(ExecutionEvent(
            event_type=event.get("event_type") if isinstance(event.get("event_type"), str) and event["event_type"] else "unknown_event",
            task_id=event.get("task_id") if isinstance(event.get("task_id"), str) and event["task_id"] else "unknown",
            step_id=event.get("step_id"), agent=event.get("agent"), action=event.get("action"),
            details=event.get("details") if isinstance(event.get("details"), dict) else {},
            event_id=event.get("event_id"), timestamp=event.get("timestamp"),
        ).to_dict())
    return result


@dataclass(frozen=True)
class FailureReport:
    task_id: str
    failed: bool

    failed_step_id: Optional[str]
    agent: Optional[str]
    action: Optional[str]

    failure_stage: Optional[str]
    error: Optional[str]

    evidence: List[Dict[str, Any]]
    failure: Optional[SafeFailure] = None

    def __post_init__(self):
        object.__setattr__(self, "task_id", safe_id(self.task_id))
        object.__setattr__(self, "failed_step_id", safe_id(self.failed_step_id))
        object.__setattr__(self, "agent", safe_agent(self.agent))
        object.__setattr__(self, "action", safe_action(self.action))
        if self.error:
            object.__setattr__(self, "error", safe_message(self.error))
        if not isinstance(self.failure_stage, str) or self.failure_stage not in STAGES:
            object.__setattr__(self, "failure_stage", None)
        if self.failure is not None and not isinstance(self.failure, SafeFailure):
            raise ValueError("Invalid typed failure.")
        object.__setattr__(self, "evidence", _safe_evidence(self.evidence))

    def to_dict(self) -> Dict[str, Any]:
        return sanitize_for_history(
            {
                "task_id": safe_id(self.task_id),
                "failed": self.failed,
                "failed_step_id": safe_id(self.failed_step_id),
                "agent": safe_agent(self.agent),
                "action": safe_action(self.action),
                "failure_stage": self.failure_stage,
                "error": safe_message(self.error) if self.error else None,
                "failure": self.failure.to_dict() if self.failure else None,
                "evidence": _safe_evidence(self.evidence),
            }
        )


class FailureReportBuilder:
    """
    Builds bounded, sanitized failure reports from ExecutionHistory.

    This component:
    - does not execute actions,
    - does not modify tasks,
    - does not approve recovery,
    - does not expose unrestricted runtime state.

    It only transforms existing execution evidence into a
    diagnostic report.
    """

    DEFAULT_MAX_EVIDENCE_EVENTS = 12

    def __init__(
        self,
        max_evidence_events: int = DEFAULT_MAX_EVIDENCE_EVENTS,
    ) -> None:

        if (
            not isinstance(max_evidence_events, int)
            or isinstance(max_evidence_events, bool)
            or max_evidence_events <= 0
        ):
            raise ValueError(
                "max_evidence_events must be a positive integer."
            )

        self._max_evidence_events = max_evidence_events

    def _find_task_failure(
        self,
        events: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:

        for event in reversed(events):
            if event.get("event_type") == "task_failed":
                return event

        return None

    def _find_step_failure(
        self,
        events: List[Dict[str, Any]],
        failed_step_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:

        for event in reversed(events):

            if event.get("event_type") != "step_failed":
                continue

            if (
                failed_step_id is None
                or event.get("step_id") == failed_step_id
            ):
                return event

        return None

    def _find_specific_failure(
        self,
        events: List[Dict[str, Any]],
        failed_step_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:

        preferred_types = {
            "preconditions_failed",
            "action_failed",
            "postconditions_failed",
        }

        for event in reversed(events):

            if event.get("event_type") not in preferred_types:
                continue

            if (
                failed_step_id is None
                or event.get("step_id") == failed_step_id
            ):
                return event

        return None

    def _bounded_evidence(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        relevant_types = {
            "task_started",
            "task_resumed",
            "preconditions_check_started",
            "preconditions_passed",
            "preconditions_failed",
            "confirmation_required",
            "task_paused",
            "step_started",
            "action_succeeded",
            "action_failed",
            "postconditions_check_started",
            "postconditions_passed",
            "postconditions_failed",
            "step_completed",
            "step_failed",
            "task_failed",
        }

        relevant = [
            sanitize_for_history(event)
            for event in events
            if event.get("event_type") in relevant_types
        ]

        return relevant[
            -self._max_evidence_events:
        ]

    def build(
        self,
        history: ExecutionHistory,
        task_id: str,
    ) -> FailureReport:

        if not isinstance(history, ExecutionHistory):
            raise TypeError(
                "history must be an ExecutionHistory instance."
            )

        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(
                "task_id must be a non-empty string."
            )

        normalized_task_id = safe_id(task_id.strip())

        events = history.events_for_task(
            normalized_task_id
        )

        task_failure = self._find_task_failure(
            events
        )

        if task_failure is None:

            return FailureReport(
                task_id=normalized_task_id,
                failed=False,
                failed_step_id=None,
                agent=None,
                action=None,
                failure_stage=None,
                error=None,
                evidence=self._bounded_evidence(
                    events
                ),
            )

        failed_step_id = task_failure.get(
            "step_id"
        )

        step_failure = self._find_step_failure(
            events,
            failed_step_id,
        )

        specific_failure = self._find_specific_failure(
            events,
            failed_step_id,
        )

        source_event = (
            specific_failure
            or step_failure
            or task_failure
        )

        details = source_event.get(
            "details",
            {},
        )

        if not isinstance(details, dict):
            details = {}

        failure_stage = None

        if specific_failure is not None:

            event_type = specific_failure.get(
                "event_type"
            )

            stage_map = {
                "preconditions_failed": "precondition",
                "action_failed": "execution",
                "postconditions_failed": "postcondition",
            }

            failure_stage = stage_map.get(
                event_type
            )

        if (
            failure_stage is None
            and step_failure is not None
        ):
            step_details = step_failure.get(
                "details",
                {},
            )

            if isinstance(step_details, dict):
                stage = step_details.get("stage")

                if isinstance(stage, str):
                    failure_stage = stage

        try:
            code = ErrorCode(details.get("error_code"))
        except (ValueError, TypeError):
            code = ErrorCode.EXECUTION_FAILED
        if code == ErrorCode.BACKEND_UNAVAILABLE:
            failure_stage = "routing"
        failure = SafeFailure(code, failure_stage or "execution")
        error = failure.message

        return FailureReport(
            task_id=normalized_task_id,
            failed=True,
            failed_step_id=failed_step_id,
            agent=source_event.get("agent"),
            action=source_event.get("action"),
            failure_stage=failure_stage,
            error=error,
            failure=failure,
            evidence=self._bounded_evidence(
                events
            ),
        )
