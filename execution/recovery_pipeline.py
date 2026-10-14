from dataclasses import dataclass
from typing import Optional

from execution.execution_history import ExecutionHistory
from execution.failure_analyzer import (
    FailureAnalysis,
    FailureAnalyzer,
)
from execution.failure_report import (
    FailureReport,
    FailureReportBuilder,
)
from execution.recovery_planning_request import (
    RecoveryPlanningRequest,
    RecoveryPlanningRequestBuilder,
)
from execution.recovery_proposal import (
    RecoveryProposal,
    RecoveryProposalBuilder,
)


@dataclass(frozen=True)
class RecoveryPipelineResult:
    report: FailureReport
    analysis: FailureAnalysis
    proposal: RecoveryProposal
    planning_request: Optional[
        RecoveryPlanningRequest
    ]


class RecoveryPipeline:
    """
    Diagnostic/recovery preparation pipeline.

    This pipeline has NO TaskExecutor and NO ExecutionRouter.

    It can:
    - read sanitized execution history,
    - build a failure report,
    - analyze the failure,
    - build a recovery proposal,
    - optionally produce a NEW planning request.

    It cannot:
    - modify the failed Task,
    - resume the failed Task,
    - execute tools,
    - route actions,
    - approve confirmations.
    """

    def __init__(self) -> None:

        self._report_builder = (
            FailureReportBuilder()
        )

        self._analyzer = (
            FailureAnalyzer()
        )

        self._proposal_builder = (
            RecoveryProposalBuilder()
        )

        self._planning_request_builder = (
            RecoveryPlanningRequestBuilder()
        )

    def prepare(
        self,
        history: ExecutionHistory,
        task_id: str,
    ) -> RecoveryPipelineResult:

        report = self._report_builder.build(
            history=history,
            task_id=task_id,
        )

        if not report.failed:
            raise ValueError(
                "Recovery pipeline requires "
                "a failed task."
            )

        analysis = self._analyzer.analyze(
            report
        )

        proposal = (
            self._proposal_builder.build(
                analysis
            )
        )

        planning_request = None

        if proposal.requires_new_plan:

            planning_request = (
                self._planning_request_builder.build(
                    proposal=proposal,
                    analysis=analysis,
                )
            )

        return RecoveryPipelineResult(
            report=report,
            analysis=analysis,
            proposal=proposal,
            planning_request=planning_request,
        )