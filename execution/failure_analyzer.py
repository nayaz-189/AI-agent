from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from execution.failure_report import FailureReport


class FailureCategory(str, Enum):
    PRECONDITION = "precondition"
    EXECUTION = "execution"
    POSTCONDITION = "postcondition"
    ROUTING = "routing"
    UNKNOWN = "unknown"


class RecoveryDisposition(str, Enum):
    REPLAN = "replan"
    RETRY_AFTER_STATE_CHANGE = "retry_after_state_change"
    INVESTIGATE = "investigate"
    STOP = "stop"


@dataclass(frozen=True)
class FailureAnalysis:
    task_id: str
    failed_step_id: Optional[str]

    category: FailureCategory
    disposition: RecoveryDisposition

    diagnosis: str
    recommendation: str

    agent: Optional[str] = None
    action: Optional[str] = None

    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "failed_step_id": self.failed_step_id,
            "category": self.category.value,
            "disposition": self.disposition.value,
            "diagnosis": self.diagnosis,
            "recommendation": self.recommendation,
            "agent": self.agent,
            "action": self.action,
            "confidence": self.confidence,
        }


class FailureAnalyzer:
    """
    Deterministic failure analyzer.

    This component has NO execution authority.

    It may:
    - classify a failure,
    - explain likely cause,
    - recommend a recovery strategy.

    It may NOT:
    - execute an action,
    - modify the failed task,
    - mark a step successful,
    - bypass validation,
    - bypass policy,
    - issue confirmation.
    """

    def analyze(
        self,
        report: FailureReport,
    ) -> FailureAnalysis:

        if not isinstance(report, FailureReport):
            raise TypeError(
                "FailureAnalyzer requires a FailureReport."
            )

        if not report.failed:
            raise ValueError(
                "Cannot analyze a report that does not represent a failure."
            )

        error = (
            report.error.strip()
            if isinstance(report.error, str)
            else ""
        )

        error_lower = error.lower()

        # ---------------------------------
        # PRECONDITION FAILURE
        # ---------------------------------

        if report.failure_stage == "precondition":

            return FailureAnalysis(
                task_id=report.task_id,
                failed_step_id=report.failed_step_id,
                category=FailureCategory.PRECONDITION,
                disposition=(
                    RecoveryDisposition.RETRY_AFTER_STATE_CHANGE
                ),
                diagnosis=(
                    "The action was blocked because one or more "
                    "required preconditions did not match the "
                    "current observed state."
                ),
                recommendation=(
                    "Do not execute the failed action. Re-observe "
                    "the environment and create a new candidate "
                    "plan if the required state can be restored."
                ),
                agent=report.agent,
                action=report.action,
                confidence=1.0,
            )

        # ---------------------------------
        # POSTCONDITION FAILURE
        # ---------------------------------

        if report.failure_stage == "postcondition":

            return FailureAnalysis(
                task_id=report.task_id,
                failed_step_id=report.failed_step_id,
                category=FailureCategory.POSTCONDITION,
                disposition=RecoveryDisposition.INVESTIGATE,
                diagnosis=(
                    "The action reported success, but the expected "
                    "postcondition was not observed."
                ),
                recommendation=(
                    "Treat the action outcome as unverified. "
                    "Re-observe the environment before deciding "
                    "whether a new plan or a safe retry is appropriate."
                ),
                agent=report.agent,
                action=report.action,
                confidence=1.0,
            )

        # ---------------------------------
        # ROUTING FAILURE
        # ---------------------------------

        routing_signatures = (
            "no execution backend registered",
            "no executionrouter is configured",
            "no registered local action handler",
        )

        if any(
            signature in error_lower
            for signature in routing_signatures
        ):

            return FailureAnalysis(
                task_id=report.task_id,
                failed_step_id=report.failed_step_id,
                category=FailureCategory.ROUTING,
                disposition=RecoveryDisposition.REPLAN,
                diagnosis=(
                    "The requested action could not be executed "
                    "through an available registered execution path."
                ),
                recommendation=(
                    "Do not bypass the router. Build a new candidate "
                    "plan using only currently registered agents, "
                    "backends, and capabilities."
                ),
                agent=report.agent,
                action=report.action,
                confidence=1.0,
            )

        # ---------------------------------
        # GENERIC EXECUTION FAILURE
        # ---------------------------------

        if report.failure_stage == "execution":

            return FailureAnalysis(
                task_id=report.task_id,
                failed_step_id=report.failed_step_id,
                category=FailureCategory.EXECUTION,
                disposition=RecoveryDisposition.INVESTIGATE,
                diagnosis=(
                    "The selected execution path was reached, "
                    "but the action itself failed."
                ),
                recommendation=(
                    "Inspect the bounded execution evidence and "
                    "current environment. Any recovery attempt must "
                    "be expressed as a new candidate plan."
                ),
                agent=report.agent,
                action=report.action,
                confidence=0.9,
            )

        # ---------------------------------
        # UNKNOWN
        # ---------------------------------

        return FailureAnalysis(
            task_id=report.task_id,
            failed_step_id=report.failed_step_id,
            category=FailureCategory.UNKNOWN,
            disposition=RecoveryDisposition.STOP,
            diagnosis=(
                "The failure could not be safely classified by "
                "the deterministic analyzer."
            ),
            recommendation=(
                "Stop automatic recovery. Preserve the evidence "
                "for higher-level analysis or user review."
            ),
            agent=report.agent,
            action=report.action,
            confidence=0.0,
        )