from execution import Task, TaskStep
from execution.execution_history import (
    ExecutionHistory,
)
from execution.recovery_pipeline import (
    RecoveryPipeline,
)
from execution.task_executor import (
    TaskExecutor,
)


def failing_action(arguments):

    return {
        "success": False,
        "error": (
            "No execution backend registered "
            "for agent: desktop"
        ),
    }


def test_failed_task_remains_failed():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "route_test",
        failing_action,
    )

    task = Task(
        goal="Original user goal",
        steps=[
            TaskStep(
                action="route_test",
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"

    original_status = task.status
    original_error = task.error
    original_step_status = (
        task.steps[0].status
    )

    result = RecoveryPipeline().prepare(
        history=history,
        task_id=task.task_id,
    )

    # Recovery preparation must NOT mutate
    # the original failed task.

    assert task.status == original_status
    assert task.error == original_error

    assert (
        task.steps[0].status
        == original_step_status
    )

    assert task.status.value == "failed"

    assert (
        result.report.task_id
        == task.task_id
    )

    print("TEST 1: PASSED")


def test_recovery_creates_planning_request():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "route_test",
        failing_action,
    )

    task = Task(
        goal="Original user goal",
        steps=[
            TaskStep(
                action="route_test",
            )
        ],
    )

    executor.execute(task)

    result = RecoveryPipeline().prepare(
        history=history,
        task_id=task.task_id,
    )

    request = result.planning_request

    assert request is not None

    assert (
        request.original_task_id
        == task.task_id
    )

    assert (
        request.recovery_proposal_id
        == result.proposal.proposal_id
    )

    assert (
        request.failed_step_id
        == task.steps[0].step_id
    )

    print("TEST 2: PASSED")


def test_planning_request_is_not_executable():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "route_test",
        failing_action,
    )

    task = Task(
        goal="Original user goal",
        steps=[
            TaskStep(
                action="route_test",
            )
        ],
    )

    executor.execute(task)

    result = RecoveryPipeline().prepare(
        history=history,
        task_id=task.task_id,
    )

    request = result.planning_request

    assert request is not None

    data = request.to_dict()

    forbidden_fields = {
        "agent",
        "action",
        "arguments",
        "steps",
        "tool",
        "tool_name",
        "backend",
        "confirmation_token",
        "approved_step_id",
        "execute",
    }

    assert not (
        forbidden_fields
        & set(data.keys())
    )

    print("TEST 3: PASSED")


def test_new_request_has_lineage():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "route_test",
        failing_action,
    )

    task = Task(
        goal="Original user goal",
        steps=[
            TaskStep(
                action="route_test",
            )
        ],
    )

    executor.execute(task)

    result = RecoveryPipeline().prepare(
        history=history,
        task_id=task.task_id,
    )

    request = result.planning_request

    assert request is not None

    assert request.request_id.startswith(
        "recovery_request_"
    )

    assert (
        request.original_task_id
        == task.task_id
    )

    assert (
        request.recovery_proposal_id
        == result.proposal.proposal_id
    )

    assert (
        request.request_id
        != task.task_id
    )

    print("TEST 4: PASSED")


def test_successful_task_rejected():

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history
    )

    executor.register_action(
        "success",
        lambda arguments: {
            "success": True,
            "result": {
                "ok": True,
            },
        },
    )

    task = Task(
        goal="Successful task",
        steps=[
            TaskStep(
                action="success",
            )
        ],
    )

    executor.execute(task)

    try:

        RecoveryPipeline().prepare(
            history=history,
            task_id=task.task_id,
        )

    except ValueError:

        print("TEST 5: PASSED")
        return

    raise AssertionError(
        "Recovery pipeline must reject "
        "successful tasks."
    )


def main():

    print(
        "================================"
    )

    print(
        " RECOVERY PIPELINE TESTS"
    )

    print(
        "================================"
    )

    print()
    print(
        "TEST 1: Failed task remains failed"
    )
    test_failed_task_remains_failed()

    print()
    print(
        "TEST 2: Recovery creates planning request"
    )
    test_recovery_creates_planning_request()

    print()
    print(
        "TEST 3: Planning request is non-executable"
    )
    test_planning_request_is_not_executable()

    print()
    print(
        "TEST 4: Recovery lineage"
    )
    test_new_request_has_lineage()

    print()
    print(
        "TEST 5: Successful task rejected"
    )
    test_successful_task_rejected()

    print()

    print(
        "================================"
    )

    print(
        " ALL RECOVERY PIPELINE TESTS PASSED"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    main()