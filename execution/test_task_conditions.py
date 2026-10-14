from execution import Task, TaskStep
from execution.task_executor import TaskExecutor


STATE = {
    "application": "notepad",
    "editable": True,
    "document_text": "",
}


ACTION_CALL_COUNT = {
    "write": 0,
}


def state_provider():
    return dict(STATE)


def write_text(arguments):
    ACTION_CALL_COUNT["write"] += 1

    value = arguments.get("value")

    STATE["document_text"] = value

    return {
        "success": True,
        "result": {
            "written": value,
        },
    }


def lying_write_action(arguments):
    ACTION_CALL_COUNT["write"] += 1

    value = arguments.get("value")

    # Pretend success without changing STATE.
    return {
        "success": True,
        "result": {
            "claimed_written": value,
        },
    }


def reset_state():
    STATE.clear()

    STATE.update(
        {
            "application": "notepad",
            "editable": True,
            "document_text": "",
        }
    )

    ACTION_CALL_COUNT["write"] = 0


def test_all_preconditions_pass():
    reset_state()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "write_text",
        write_text,
    )

    task = Task(
        goal="Write Hello when conditions are safe",
        steps=[
            TaskStep(
                action="write_text",
                arguments={
                    "value": "Hello",
                },
                preconditions=[
                    {
                        "type": "state_equals",
                        "key": "application",
                        "expected": "notepad",
                    },
                    {
                        "type": "state_equals",
                        "key": "editable",
                        "expected": True,
                    },
                ],
                postconditions=[
                    {
                        "type": "state_equals",
                        "key": "document_text",
                        "expected": "Hello",
                    },
                ],
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "completed"
    assert task.steps[0].status.value == "completed"
    assert ACTION_CALL_COUNT["write"] == 1
    assert STATE["document_text"] == "Hello"

    print("TEST 1: PASSED")


def test_failed_precondition_blocks_action():
    reset_state()

    STATE["editable"] = False

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "write_text",
        write_text,
    )

    task = Task(
        goal="Do not write into a non-editable document",
        steps=[
            TaskStep(
                action="write_text",
                arguments={
                    "value": "Hello",
                },
                preconditions=[
                    {
                        "type": "state_equals",
                        "key": "application",
                        "expected": "notepad",
                    },
                    {
                        "type": "state_equals",
                        "key": "editable",
                        "expected": True,
                    },
                ],
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"
    assert task.steps[0].status.value == "failed"

    # Critical proof:
    # The action was never called.
    assert ACTION_CALL_COUNT["write"] == 0

    assert STATE["document_text"] == ""

    print("TEST 2: PASSED")


def test_failed_postcondition_rejects_false_success():
    reset_state()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "lying_write",
        lying_write_action,
    )

    task = Task(
        goal="Detect an action that claims success falsely",
        steps=[
            TaskStep(
                action="lying_write",
                arguments={
                    "value": "Hello",
                },
                postconditions=[
                    {
                        "type": "state_equals",
                        "key": "document_text",
                        "expected": "Hello",
                    },
                ],
            )
        ],
    )

    executor.execute(task)

    assert ACTION_CALL_COUNT["write"] == 1

    assert task.status.value == "failed"
    assert task.steps[0].status.value == "failed"

    assert STATE["document_text"] == ""

    print("TEST 3: PASSED")


def test_unknown_condition_fails_closed():
    reset_state()

    executor = TaskExecutor(
        state_provider=state_provider
    )

    executor.register_action(
        "write_text",
        write_text,
    )

    task = Task(
        goal="Reject unknown conditions",
        steps=[
            TaskStep(
                action="write_text",
                arguments={
                    "value": "Hello",
                },
                preconditions=[
                    {
                        "type": "ask_magic_oracle",
                        "key": "editable",
                    }
                ],
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"
    assert task.steps[0].status.value == "failed"

    # Unknown condition prevented execution.
    assert ACTION_CALL_COUNT["write"] == 0

    print("TEST 4: PASSED")


def main():
    print(
        "================================"
    )
    print(
        " TASK CONDITION TESTS"
    )
    print(
        "================================"
    )

    print()
    print(
        "TEST 1: All required conditions pass"
    )
    test_all_preconditions_pass()

    print()
    print(
        "TEST 2: Failed precondition blocks action"
    )
    test_failed_precondition_blocks_action()

    print()
    print(
        "TEST 3: Postcondition detects false success"
    )
    test_failed_postcondition_rejects_false_success()

    print()
    print(
        "TEST 4: Unknown condition fails closed"
    )
    test_unknown_condition_fails_closed()

    print()
    print(
        "================================"
    )
    print(
        " ALL CONDITION TESTS PASSED"
    )
    print(
        "================================"
    )


if __name__ == "__main__":
    main()