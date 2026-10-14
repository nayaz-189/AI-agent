from execution.failure_analyzer import (
    FailureAnalysis,
    FailureCategory,
    RecoveryDisposition,
)
from execution.recovery_proposal import (
    RecoveryProposalBuilder,
    RecoveryProposalType,
)


def make_analysis(
    disposition,
    category=FailureCategory.EXECUTION,
):
    return FailureAnalysis(
        task_id="task_original",
        failed_step_id="step_failed",
        category=category,
        disposition=disposition,
        diagnosis="Test diagnosis.",
        recommendation="Test recommendation.",
        agent="desktop",
        action="set_value",
        confidence=1.0,
    )


def test_replan_proposal():

    analysis = make_analysis(
        RecoveryDisposition.REPLAN,
        FailureCategory.ROUTING,
    )

    proposal = (
        RecoveryProposalBuilder()
        .build(analysis)
    )

    assert (
        proposal.proposal_type
        == RecoveryProposalType.REPLAN
    )

    assert proposal.requires_new_plan is True

    assert (
        proposal.original_task_id
        == "task_original"
    )

    assert proposal.proposal_id.startswith(
        "recovery_"
    )

    print("TEST 1: PASSED")


def test_reobserve_proposal():

    analysis = make_analysis(
        RecoveryDisposition.RETRY_AFTER_STATE_CHANGE,
        FailureCategory.PRECONDITION,
    )

    proposal = (
        RecoveryProposalBuilder()
        .build(analysis)
    )

    assert (
        proposal.proposal_type
        == RecoveryProposalType.REOBSERVE_AND_REPLAN
    )

    assert proposal.requires_new_plan is True

    print("TEST 2: PASSED")


def test_investigate_proposal():

    analysis = make_analysis(
        RecoveryDisposition.INVESTIGATE
    )

    proposal = (
        RecoveryProposalBuilder()
        .build(analysis)
    )

    assert (
        proposal.proposal_type
        == RecoveryProposalType.INVESTIGATE
    )

    assert proposal.requires_new_plan is False

    print("TEST 3: PASSED")


def test_stop_proposal():

    analysis = make_analysis(
        RecoveryDisposition.STOP,
        FailureCategory.UNKNOWN,
    )

    proposal = (
        RecoveryProposalBuilder()
        .build(analysis)
    )

    assert (
        proposal.proposal_type
        == RecoveryProposalType.STOP
    )

    assert proposal.requires_new_plan is False

    assert proposal.recommended_goal is None

    print("TEST 4: PASSED")


def test_proposal_contains_no_execution_authority():

    analysis = make_analysis(
        RecoveryDisposition.REPLAN
    )

    proposal = (
        RecoveryProposalBuilder()
        .build(analysis)
    )

    data = proposal.to_dict()

    forbidden_fields = {
        "arguments",
        "tool",
        "tool_name",
        "confirmation_token",
        "approved_step_id",
        "execute",
        "backend",
    }

    assert not (
        forbidden_fields
        & set(data.keys())
    )

    assert "steps" not in data

    print("TEST 5: PASSED")


def test_unique_proposal_ids():

    analysis = make_analysis(
        RecoveryDisposition.REPLAN
    )

    builder = RecoveryProposalBuilder()

    first = builder.build(analysis)
    second = builder.build(analysis)

    assert (
        first.proposal_id
        != second.proposal_id
    )

    print("TEST 6: PASSED")


def main():

    print("================================")
    print(" RECOVERY PROPOSAL TESTS")
    print("================================")

    print()
    print("TEST 1: Replan proposal")
    test_replan_proposal()

    print()
    print("TEST 2: Reobserve proposal")
    test_reobserve_proposal()

    print()
    print("TEST 3: Investigation proposal")
    test_investigate_proposal()

    print()
    print("TEST 4: Stop proposal")
    test_stop_proposal()

    print()
    print("TEST 5: No execution authority")
    test_proposal_contains_no_execution_authority()

    print()
    print("TEST 6: Unique proposal IDs")
    test_unique_proposal_ids()

    print()
    print("================================")
    print(" ALL RECOVERY PROPOSAL TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()