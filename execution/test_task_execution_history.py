from execution import Task, TaskStep
from execution.execution_history import (
    ExecutionHistory,
    REDACTED,
)
from execution.task_executor import TaskExecutor


STATE = {
    "document": "Hello",
}

CALLS = []


def state_provider():
    return dict(STATE)


def action_handler(arguments):
    CALLS.append(arguments.get("name"))

    return {
        "success": True,
        "result": {
            "executed": arguments.get("name"),
        },
    }


def failing_handler(arguments):
    CALLS.append("failed_action")

    return {
        "success": False,
        "error": "Simulated backend failure.",
    }


def reset():
    STATE.clear()

    STATE.update({
        "document": "Hello",
    })

    CALLS.clear()


def event_types(history):
    return [
        event["event_type"]
        for event in history.all_events()
    ]


def test_successful_history():

    reset()

    history = ExecutionHistory()

    executor = TaskExecutor(
        state_provider=state_provider,
        execution_history=history,
    )

    executor.register_action(
        "action",
        action_handler,
    )

    task = Task(
        goal="Successful evidence test",
        steps=[
            TaskStep(
                action="action",
                arguments={
                    "name": "first",
                },
                preconditions=[
                    {
                        "type": "state_equals",
                        "key": "document",
                        "expected": "Hello",
                    }
                ],
            )
        ],
    )

    executor.execute(task)

    types = event_types(history)

    assert types == [
        "task_started",
        "preconditions_check_started",
        "preconditions_passed",
        "step_started",
        "action_succeeded",
        "step_completed",
        "task_completed",
    ]

    print("TEST 1: PASSED")


def test_failure_history_stops_task():

    reset()

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history,
    )

    executor.register_action(
        "fail",
        failing_handler,
    )

    task = Task(
        goal="Failure evidence test",
        steps=[
            TaskStep(
                action="fail",
            ),
            TaskStep(
                action="fail",
            ),
        ],
    )

    executor.execute(task)

    types = event_types(history)

    assert task.status.value == "failed"

    assert types == [
        "task_started",
        "step_started",
        "action_failed",
        "step_failed",
        "task_failed",
    ]

    assert CALLS == [
        "failed_action",
    ]

    print("TEST 2: PASSED")


def test_confirmation_history():

    reset()

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history,
    )

    executor.register_action(
        "action",
        action_handler,
    )

    step = TaskStep(
        action="action",
        arguments={
            "name": "confirmed",
        },
        requires_confirmation=True,
    )

    task = Task(
        goal="Confirmation evidence test",
        steps=[step],
    )

    executor.execute(task)

    assert task.status.value == (
        "waiting_for_user"
    )

    executor.execute(
        task,
        approved_step_id=step.step_id,
    )

    assert task.status.value == "completed"

    types = event_types(history)

    assert types == [
        "task_started",
        "confirmation_required",
        "task_paused",
        "task_resumed",
        "step_started",
        "action_succeeded",
        "step_completed",
        "task_completed",
    ]

    print("TEST 3: PASSED")


def test_secret_never_appears_in_history():

    reset()

    history = ExecutionHistory()

    executor = TaskExecutor(
        execution_history=history,
    )

    executor.register_action(
        "action",
        action_handler,
    )

    step = TaskStep(
        action="action",
        arguments={
            "name": "login",
            "username": "nayaz",
            "password": "SUPER_SECRET_PASSWORD",
            "api_key": "SUPER_SECRET_API_KEY",
        },
    )

    task = Task(
        goal="Secret redaction evidence test",
        steps=[step],
    )

    executor.execute(task)

    events = history.all_events()

    serialized = repr(events)

    assert "SUPER_SECRET_PASSWORD" not in serialized
    assert "SUPER_SECRET_API_KEY" not in serialized

    step_started = next(
        event
        for event in events
        if event["event_type"] == "step_started"
    )

    arguments = (
        step_started["details"]["arguments"]
    )

    assert arguments["password"] == REDACTED
    assert arguments["api_key"] == REDACTED

    print("TEST 4: PASSED")


def test_changed_state_history():

    reset()

    history = ExecutionHistory()

    executor = TaskExecutor(
        state_provider=state_provider,
        execution_history=history,
    )

    executor.register_action(
        "action",
        action_handler,
    )

    step = TaskStep(
        action="action",
        arguments={
            "name": "sensitive",
        },
        requires_confirmation=True,
        preconditions=[
            {
                "type": "state_equals",
                "key": "document",
                "expected": "Hello",
            }
        ],
    )

    task = Task(
        goal="Stale state evidence test",
        steps=[step],
    )

    executor.execute(task)

    STATE["document"] = "Changed"

    executor.execute(
        task,
        approved_step_id=step.step_id,
    )

    assert task.status.value == "failed"

    types = event_types(history)

    assert "task_resumed" in types
    assert "preconditions_failed" in types
    assert "step_failed" in types
    assert "task_failed" in types

    assert "step_started" not in types
    assert "action_succeeded" not in types

    assert CALLS == []

    print("TEST 5: PASSED")


def main():

    print("================================")
    print(" TASK EXECUTION HISTORY TESTS")
    print("================================")

    print()
    print("TEST 1: Successful execution history")
    test_successful_history()

    print()
    print("TEST 2: Failure history")
    test_failure_history_stops_task()

    print()
    print("TEST 3: Confirmation pause/resume history")
    test_confirmation_history()

    print()
    print("TEST 4: Secret redaction through executor")
    test_secret_never_appears_in_history()

    print()
    print("TEST 5: Changed-state evidence")
    test_changed_state_history()

    print("TEST 6: Condition evidence stays private")
    test_condition_values_do_not_leak_into_history()

    print("TEST 7: Action results stay private")
    test_action_result_values_are_not_in_event_history()

    print()
    print("================================")
    print(" ALL TASK HISTORY TESTS PASSED")
    print("================================")


def test_condition_values_do_not_leak_into_history():
    reset()
    private_value = "PRIVATE_CONDITION_SENTINEL_481"
    STATE["document"] = private_value
    history = ExecutionHistory()
    executor = TaskExecutor(state_provider=state_provider, execution_history=history)
    task = Task(goal="Safe failed condition", steps=[TaskStep(
        action="never_executed",
        preconditions=[{"type": "state_equals", "key": "document", "expected": "EXPECTED_SECRET_482"}],
    )])
    executor.execute(task)
    assert task.status.value == "failed"
    evidence = repr(history.all_events()) + repr(task.error)
    assert private_value not in evidence
    assert "EXPECTED_SECRET_482" not in evidence


def test_action_result_values_are_not_in_event_history():
    reset()
    history = ExecutionHistory()
    executor = TaskExecutor(execution_history=history)
    executor.register_action("sample", lambda arguments: {
        "success": True, "result": {"unclassified_output": "PRIVATE_RESULT_SENTINEL_483"}
    })
    task = Task(goal="Safe result evidence", steps=[TaskStep(action="sample")])
    executor.execute(task)
    assert task.status.value == "completed"
    assert "PRIVATE_RESULT_SENTINEL_483" not in repr(history.all_events())


if __name__ == "__main__":
    main()
