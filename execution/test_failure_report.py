from execution import Task, TaskStep
from execution.execution_history import ExecutionHistory
from execution.failure_report import FailureReportBuilder
from execution.task_executor import TaskExecutor


STATE = {
    "editable": True,
}


def state_provider():
    return dict(STATE)


def successful_action(arguments):
    return {
        "success": True,
        "result": {
            "executed": True,
        },
    }


def failing_action(arguments):
    return {
        "success": False,
        "error": "Simulated execution failure.",
    }


def test_execution_failure_report():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "fail",
        failing_action,
    )

    task = Task(
        goal="Generate execution failure",
        steps=[
            TaskStep(
                action="fail",
            )
        ],
    )

    executor.execute(task)

    builder = FailureReportBuilder()

    report = builder.build(
        history,
        task.task_id,
    )

    assert report.failed is True

    assert report.failed_step_id == (
        task.steps[0].step_id
    )

    assert report.failure_stage == (
        "execution"
    )

    assert report.action is None  # Arbitrary local labels are not public identities.

    assert report.error == (
        "Execution failed."
    )

    print("TEST 1: PASSED")


def test_precondition_failure_report():

    STATE["editable"] = False

    history = ExecutionHistory()

    executor = TaskExecutor(
        state_provider=state_provider,
        execution_history=history,
    )

    executor.register_action(
        "write",
        successful_action,
    )

    task = Task(
        goal="Generate precondition failure",
        steps=[
            TaskStep(
                action="write",
                preconditions=[
                    {
                        "type": "state_equals",
                        "key": "editable",
                        "expected": True,
                    }
                ],
            )
        ],
    )

    executor.execute(task)

    report = FailureReportBuilder().build(
        history,
        task.task_id,
    )

    assert report.failed is True

    assert report.failure_stage == (
        "precondition"
    )

    assert report.action is None

    assert report.error is not None

    assert "Precondition failed" in report.error

    print("TEST 2: PASSED")


def test_successful_task_is_not_failure():

    STATE["editable"] = True

    history = ExecutionHistory()

    executor = TaskExecutor(
        state_provider=state_provider,
        execution_history=history,
    )

    executor.register_action(
        "write",
        successful_action,
    )

    task = Task(
        goal="Successful task",
        steps=[
            TaskStep(
                action="write",
            )
        ],
    )

    executor.execute(task)

    report = FailureReportBuilder().build(
        history,
        task.task_id,
    )

    assert report.failed is False
    assert report.failed_step_id is None
    assert report.failure_stage is None
    assert report.error is None

    print("TEST 3: PASSED")


def test_report_remains_sanitized():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "fail",
        failing_action,
    )

    task = Task(
        goal="Sensitive failure",
        steps=[
            TaskStep(
                action="fail",
                arguments={
                    "username": "nayaz",
                    "password": "NEVER_EXPOSE_PASSWORD",
                    "api_key": "NEVER_EXPOSE_API_KEY",
                },
            )
        ],
    )

    executor.execute(task)

    report = FailureReportBuilder().build(
        history,
        task.task_id,
    )

    serialized = repr(
        report.to_dict()
    )

    assert (
        "NEVER_EXPOSE_PASSWORD"
        not in serialized
    )

    assert (
        "NEVER_EXPOSE_API_KEY"
        not in serialized
    )

    print("TEST 4: PASSED")


def test_evidence_is_bounded():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "success",
        successful_action,
    )

    executor.register_action(
        "fail",
        failing_action,
    )

    steps = [
        TaskStep(
            action="success",
        )
        for _ in range(10)
    ]

    steps.append(
        TaskStep(
            action="fail",
        )
    )

    task = Task(
        goal="Generate long evidence trail",
        steps=steps,
    )

    executor.execute(task)

    builder = FailureReportBuilder(
        max_evidence_events=5
    )

    report = builder.build(
        history,
        task.task_id,
    )

    assert report.failed is True

    assert len(report.evidence) <= 5

    assert (
        report.evidence[-1]["event_type"]
        == "task_failed"
    )

    print("TEST 5: PASSED")


def main():

    print("================================")
    print(" FAILURE REPORT TESTS")
    print("================================")

    print()
    print("TEST 1: Execution failure report")
    test_execution_failure_report()

    print()
    print("TEST 2: Precondition failure report")
    test_precondition_failure_report()

    print()
    print("TEST 3: Successful task")
    test_successful_task_is_not_failure()

    print()
    print("TEST 4: Sensitive data remains redacted")
    test_report_remains_sanitized()

    print()
    print("TEST 5: Evidence is bounded")
    test_evidence_is_bounded()

    print()
    print("================================")
    print(" ALL FAILURE REPORT TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()
