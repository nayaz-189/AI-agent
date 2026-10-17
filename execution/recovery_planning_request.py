from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
from execution.audit_schema import safe_id

from execution.failure_analyzer import FailureAnalysis
from execution.recovery_proposal import (
    RecoveryProposal,
    RecoveryProposalType,
)


def generate_request_id() -> str:
    return f"recovery_request_{uuid4().hex[:16]}"


def utc_timestamp() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass(frozen=True)
class RecoveryPlanningRequest:
    """
    Non-executable request for a NEW candidate plan.

    This object contains lineage and planning context only.

    It is not:
    - a Task,
    - a TaskStep,
    - a tool call,
    - an execution request,
    - a permission grant.
    """

    original_task_id: str
    recovery_proposal_id: str

    failed_step_id: Optional[str]

    goal: str
    reason: str

    request_id: str = field(
        default_factory=generate_request_id
    )

    created_at: str = field(
        default_factory=utc_timestamp
    )

    def __post_init__(self) -> None:

        required_strings = {
            "original_task_id": self.original_task_id,
            "recovery_proposal_id": self.recovery_proposal_id,
            "goal": self.goal,
            "reason": self.reason,
            "request_id": self.request_id,
            "created_at": self.created_at,
        }

        for name, value in required_strings.items():

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise ValueError(
                    f"{name} must be a non-empty string."
                )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "request_id": safe_id(self.request_id),
            "original_task_id": safe_id(self.original_task_id),
            "recovery_proposal_id": safe_id(self.recovery_proposal_id),
            "failed_step_id": safe_id(self.failed_step_id),
            "goal": "Create a newly validated candidate plan with applicable permissions.",
            "reason": "Recovery planning grants no execution authority.",
        }


class RecoveryPlanningRequestBuilder:
    """
    Converts an approved recovery proposal into a planning request.

    It cannot create Tasks or execute anything.
    """

    def build(
        self,
        proposal: RecoveryProposal,
        analysis: FailureAnalysis,
    ) -> RecoveryPlanningRequest:

        if not isinstance(
            proposal,
            RecoveryProposal,
        ):
            raise TypeError(
                "proposal must be a RecoveryProposal."
            )

        if not isinstance(
            analysis,
            FailureAnalysis,
        ):
            raise TypeError(
                "analysis must be a FailureAnalysis."
            )

        # -----------------------------
        # LINEAGE CONSISTENCY
        # -----------------------------

        if (
            proposal.original_task_id
            != analysis.task_id
        ):
            raise ValueError(
                "Recovery lineage mismatch: "
                "proposal and analysis refer to "
                "different original tasks."
            )

        if (
            proposal.failed_step_id
            != analysis.failed_step_id
        ):
            raise ValueError(
                "Recovery lineage mismatch: "
                "proposal and analysis refer to "
                "different failed steps."
            )

        # -----------------------------
        # ONLY ACTIONABLE PROPOSALS
        # -----------------------------

        allowed_types = {
            RecoveryProposalType.REPLAN,
            RecoveryProposalType.REOBSERVE_AND_REPLAN,
        }

        if proposal.proposal_type not in allowed_types:
            raise ValueError(
                "This recovery proposal does not authorize "
                "creation of a planning request."
            )

        if not proposal.requires_new_plan:
            raise ValueError(
                "Recovery proposal does not require a new plan."
            )

        if (
            not isinstance(
                proposal.recommended_goal,
                str,
            )
            or not proposal.recommended_goal.strip()
        ):
            raise ValueError(
                "Actionable recovery proposal requires "
                "a recommended goal."
            )

        return RecoveryPlanningRequest(
            original_task_id=proposal.original_task_id,
            recovery_proposal_id=proposal.proposal_id,
            failed_step_id=proposal.failed_step_id,
            goal=proposal.recommended_goal.strip(),
            reason=analysis.diagnosis,
        )
