from execution.failure_analyzer import (
    FailureAnalyzer,
    FailureCategory,
    RecoveryDisposition,
)
from execution.failure_report import FailureReport


def make_report(
    *,
    stage,
    error,
    agent="desktop",
    action="set_value",
):
    return FailureReport(
        task_id="task_test",
        failed=True,
        failed_step_id="step_test",
        agent=agent,
        action=action,
        failure_stage=stage,
        error=error,
        evidence=[],
    )


def test_precondition_analysis():

    report = make_report(
        stage="precondition",
        error=(
            "Expected editable=True, "
            "observed editable=False."
        ),
    )

    analysis = FailureAnalyzer().analyze(
        report
    )

    assert (
        analysis.category
        == FailureCategory.PRECONDITION
    )

    assert (
        analysis.disposition
        == RecoveryDisposition.RETRY_AFTER_STATE_CHANGE
    )

    assert analysis.confidence == 1.0

    print("TEST 1: PASSED")


def test_postcondition_analysis():

    report = make_report(
        stage="postcondition",
        error=(
            "Expected document='Hello', "
            "observed document=''."
        ),
    )

    analysis = FailureAnalyzer().analyze(
        report
    )

    assert (
        analysis.category
        == FailureCategory.POSTCONDITION
    )

    assert (
        analysis.disposition
        == RecoveryDisposition.INVESTIGATE
    )

    print("TEST 2: PASSED")


def test_routing_analysis():

    report = make_report(
        stage="execution",
        error=(
            "No execution backend registered "
            "for agent: desktop"
        ),
    )

    analysis = FailureAnalyzer().analyze(
        report
    )

    assert (
        analysis.category
        == FailureCategory.ROUTING
    )

    assert (
        analysis.disposition
        == RecoveryDisposition.REPLAN
    )

    print("TEST 3: PASSED")


def test_generic_execution_analysis():

    report = make_report(
        stage="execution",
        error="Application rejected the action.",
    )

    analysis = FailureAnalyzer().analyze(
        report
    )

    assert (
        analysis.category
        == FailureCategory.EXECUTION
    )

    assert (
        analysis.disposition
        == RecoveryDisposition.INVESTIGATE
    )

    assert analysis.confidence == 0.9

    print("TEST 4: PASSED")


def test_unknown_fails_closed():

    report = make_report(
        stage=None,
        error="Something unusual happened.",
    )

    analysis = FailureAnalyzer().analyze(
        report
    )

    assert (
        analysis.category
        == FailureCategory.UNKNOWN
    )

    assert (
        analysis.disposition
        == RecoveryDisposition.STOP
    )

    assert analysis.confidence == 0.0

    print("TEST 5: PASSED")


def test_success_report_rejected():

    report = FailureReport(
        task_id="task_success",
        failed=False,
        failed_step_id=None,
        agent=None,
        action=None,
        failure_stage=None,
        error=None,
        evidence=[],
    )

    try:
        FailureAnalyzer().analyze(
            report
        )

    except ValueError:
        print("TEST 6: PASSED")
        return

    raise AssertionError(
        "Successful report should not be analyzed as failure."
    )


def main():

    print("================================")
    print(" FAILURE ANALYZER TESTS")
    print("================================")

    print()
    print("TEST 1: Precondition classification")
    test_precondition_analysis()

    print()
    print("TEST 2: Postcondition classification")
    test_postcondition_analysis()

    print()
    print("TEST 3: Routing classification")
    test_routing_analysis()

    print()
    print("TEST 4: Execution classification")
    test_generic_execution_analysis()

    print()
    print("TEST 5: Unknown failure stops")
    test_unknown_fails_closed()

    print()
    print("TEST 6: Successful report rejected")
    test_success_report_rejected()

    print()
    print("================================")
    print(" ALL FAILURE ANALYZER TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()