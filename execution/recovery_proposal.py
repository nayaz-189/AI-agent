from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4
from execution.audit_schema import safe_id

from execution.failure_analyzer import (
    FailureAnalysis,
    RecoveryDisposition,
)


def generate_proposal_id() -> str:
    return f"recovery_{uuid4().hex[:16]}"


class RecoveryProposalType(str, Enum):
    REPLAN = "replan"
    REOBSERVE_AND_REPLAN = "reobserve_and_replan"
    INVESTIGATE = "investigate"
    STOP = "stop"


@dataclass(frozen=True)
class RecoveryProposal:
    proposal_type: RecoveryProposalType

    original_task_id: str
    failed_step_id: Optional[str]

    reason: str
    recommended_goal: Optional[str]

    requires_new_plan: bool

    proposal_id: str = ""

    def __post_init__(self) -> None:

        if not self.proposal_id:
            object.__setattr__(
                self,
                "proposal_id",
                generate_proposal_id(),
            )

        if (
            not isinstance(self.original_task_id, str)
            or not self.original_task_id.strip()
        ):
            raise ValueError(
                "Recovery proposal requires an original task ID."
            )

        if (
            not isinstance(self.reason, str)
            or not self.reason.strip()
        ):
            raise ValueError(
                "Recovery proposal requires a reason."
            )

        if not isinstance(
            self.requires_new_plan,
            bool,
        ):
            raise TypeError(
                "requires_new_plan must be boolean."
            )

        if self.recommended_goal is not None:
            if (
                not isinstance(self.recommended_goal, str)
                or not self.recommended_goal.strip()
            ):
                raise ValueError(
                    "recommended_goal must be None or a non-empty string."
                )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "proposal_id": safe_id(self.proposal_id),
            "proposal_type": self.proposal_type.value,
            "original_task_id": safe_id(self.original_task_id),
            "failed_step_id": safe_id(self.failed_step_id),
            "reason": "Recovery proposal: " + self.proposal_type.value,
            "recommended_goal": "Create a newly validated plan." if self.requires_new_plan else None,
            "requires_new_plan": self.requires_new_plan,
        }


class RecoveryProposalBuilder:
    """
    Converts FailureAnalysis into a recovery proposal.

    A proposal is NOT executable.

    It contains:
    - no TaskStep objects,
    - no tool calls,
    - no confirmation tokens,
    - no permission grants,
    - no router access.

    If recovery requires action, the proposal must go back through
    the normal planning and validation pipeline.
    """

    def build(
        self,
        analysis: FailureAnalysis,
    ) -> RecoveryProposal:

        if not isinstance(
            analysis,
            FailureAnalysis,
        ):
            raise TypeError(
                "RecoveryProposalBuilder requires FailureAnalysis."
            )

        if (
            analysis.disposition
            == RecoveryDisposition.REPLAN
        ):

            return RecoveryProposal(
                proposal_type=RecoveryProposalType.REPLAN,
                original_task_id=analysis.task_id,
                failed_step_id=analysis.failed_step_id,
                reason=analysis.diagnosis,
                recommended_goal=(
                    "Create a new candidate plan that achieves "
                    "the original intent using only currently "
                    "available validated capabilities."
                ),
                requires_new_plan=True,
            )

        if (
            analysis.disposition
            == RecoveryDisposition.RETRY_AFTER_STATE_CHANGE
        ):

            return RecoveryProposal(
                proposal_type=(
                    RecoveryProposalType.REOBSERVE_AND_REPLAN
                ),
                original_task_id=analysis.task_id,
                failed_step_id=analysis.failed_step_id,
                reason=analysis.diagnosis,
                recommended_goal=(
                    "Re-observe the relevant environment. "
                    "If the required state can be safely restored, "
                    "create a new candidate plan rather than "
                    "resuming the failed task."
                ),
                requires_new_plan=True,
            )

        if (
            analysis.disposition
            == RecoveryDisposition.INVESTIGATE
        ):

            return RecoveryProposal(
                proposal_type=RecoveryProposalType.INVESTIGATE,
                original_task_id=analysis.task_id,
                failed_step_id=analysis.failed_step_id,
                reason=analysis.diagnosis,
                recommended_goal=(
                    "Investigate the bounded failure evidence and "
                    "current environment before proposing any "
                    "new action."
                ),
                requires_new_plan=False,
            )

        return RecoveryProposal(
            proposal_type=RecoveryProposalType.STOP,
            original_task_id=analysis.task_id,
            failed_step_id=analysis.failed_step_id,
            reason=analysis.diagnosis,
            recommended_goal=None,
            requires_new_plan=False,
        )
