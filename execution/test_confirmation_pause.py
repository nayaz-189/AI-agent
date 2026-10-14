from execution import Task, TaskStep
from execution.task_executor import TaskExecutor


STATE = {
    "document": "Hello",
}

CALLS = []


def state_provider():
    return dict(STATE)


def safe_action(arguments):

    CALLS.append(
        arguments.get("name")
    )

    return {
        "success": True,
        "result": {
            "executed": arguments.get("name"),
        },
    }


def reset():

    STATE.clear()

    STATE.update(
        {
            "document": "Hello",
        }
    )

    CALLS.clear()


def test_pause_and_resume():

    reset()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "safe_action",
        safe_action,
    )

    sensitive_step = TaskStep(
        action="safe_action",
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
        goal="Test confirmation pause",
        steps=[
            TaskStep(
                action="safe_action",
                arguments={
                    "name": "first",
                },
            ),
            sensitive_step,
            TaskStep(
                action="safe_action",
                arguments={
                    "name": "third",
                },
            ),
        ],
    )

    executor.execute(task)

    assert task.status.value == "waiting_for_user"

    assert [
        step.status.value
        for step in task.steps
    ] == [
        "completed",
        "waiting_for_user",
        "pending",
    ]

    assert CALLS == [
        "first",
    ]

    executor.execute(
        task,
        approved_step_id=sensitive_step.step_id,
    )

    assert task.status.value == "completed"

    assert CALLS == [
        "first",
        "sensitive",
        "third",
    ]

    # Step 1 was NOT executed again.
    assert CALLS.count("first") == 1

    print("TEST 1: PASSED")


def test_changed_state_blocks_after_approval():

    reset()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "safe_action",
        safe_action,
    )

    sensitive_step = TaskStep(
        action="safe_action",
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
        goal="Reject stale approval context",
        steps=[
            sensitive_step,
        ],
    )

    executor.execute(task)

    assert task.status.value == "waiting_for_user"

    assert CALLS == []

    # Real-world state changes while waiting.
    STATE["document"] = "Something else"

    executor.execute(
        task,
        approved_step_id=sensitive_step.step_id,
    )

    assert task.status.value == "failed"

    # Most important assertion:
    # Approval did not bypass the precondition.
    assert CALLS == []

    print("TEST 2: PASSED")


def test_wrong_step_approval_does_not_execute():

    reset()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "safe_action",
        safe_action,
    )

    sensitive_step = TaskStep(
        action="safe_action",
        arguments={
            "name": "sensitive",
        },
        requires_confirmation=True,
    )

    task = Task(
        goal="Reject wrong approval",
        steps=[
            sensitive_step,
        ],
    )

    executor.execute(task)

    executor.execute(
        task,
        approved_step_id="step_wrong_id",
    )

    assert task.status.value == "waiting_for_user"

    assert CALLS == []

    print("TEST 3: PASSED")


def test_approval_does_not_leak():

    reset()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "safe_action",
        safe_action,
    )

    first_sensitive = TaskStep(
        action="safe_action",
        arguments={
            "name": "first_sensitive",
        },
        requires_confirmation=True,
    )

    second_sensitive = TaskStep(
        action="safe_action",
        arguments={
            "name": "second_sensitive",
        },
        requires_confirmation=True,
    )

    task = Task(
        goal="Prove approval is single-step",
        steps=[
            first_sensitive,
            second_sensitive,
        ],
    )

    executor.execute(task)

    assert task.status.value == "waiting_for_user"

    executor.execute(
        task,
        approved_step_id=first_sensitive.step_id,
    )

    # First executes.
    # Second must pause independently.
    assert task.status.value == "waiting_for_user"

    assert CALLS == [
        "first_sensitive",
    ]

    assert second_sensitive.status.value == "waiting_for_user"

    print("TEST 4: PASSED")


def main():

    print("================================")
    print(" CONFIRMATION PAUSE TESTS")
    print("================================")

    print()
    print("TEST 1: Pause and resume same step")
    test_pause_and_resume()

    print()
    print("TEST 2: Changed state blocks approved action")
    test_changed_state_blocks_after_approval()

    print()
    print("TEST 3: Wrong approval does not execute")
    test_wrong_step_approval_does_not_execute()

    print()
    print("TEST 4: Approval cannot leak")
    test_approval_does_not_leak()

    print()
    print("================================")
    print(" ALL CONFIRMATION TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()