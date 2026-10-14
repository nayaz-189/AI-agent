from execution import Task, TaskStep
from execution.execution_router import ExecutionRouter
from execution.task_executor import TaskExecutor


CALLS = []


def system_backend(action, arguments):
    CALLS.append(
        {
            "backend": "system",
            "action": action,
        }
    )

    return {
        "success": True,
        "result": {
            "handled_by": "system",
        },
    }


def desktop_backend(action, arguments):
    CALLS.append(
        {
            "backend": "desktop",
            "action": action,
        }
    )

    return {
        "success": True,
        "result": {
            "handled_by": "desktop",
        },
    }


def dangerous_local_fallback(arguments):
    CALLS.append(
        {
            "backend": "LOCAL_FALLBACK",
            "action": "set_value",
        }
    )

    return {
        "success": True,
        "result": {
            "unsafe": True,
        },
    }


def reset_calls():
    CALLS.clear()


def test_multi_backend_task():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "system",
        system_backend,
    )

    router.register_backend(
        "desktop",
        desktop_backend,
    )

    executor = TaskExecutor(
        execution_router=router
    )

    task = Task(
        goal="Route steps to correct subsystems",
        steps=[
            TaskStep(
                agent="system",
                action="launch_application",
                arguments={
                    "application": "notepad",
                },
            ),
            TaskStep(
                agent="desktop",
                action="set_value",
                arguments={
                    "value": "Hello",
                },
            ),
        ],
    )

    executor.execute(task)

    assert task.status.value == "completed"

    assert CALLS == [
        {
            "backend": "system",
            "action": "launch_application",
        },
        {
            "backend": "desktop",
            "action": "set_value",
        },
    ]

    print("TEST 1: PASSED")


def test_missing_router_blocks_routed_step():
    reset_calls()

    executor = TaskExecutor()

    task = Task(
        goal="Reject routed action without router",
        steps=[
            TaskStep(
                agent="desktop",
                action="set_value",
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"
    assert task.steps[0].status.value == "failed"
    assert CALLS == []

    print("TEST 2: PASSED")


def test_missing_backend_does_not_use_local_fallback():
    reset_calls()

    router = ExecutionRouter()

    executor = TaskExecutor(
        execution_router=router
    )

    # Register a local handler with the SAME action name.
    executor.register_action(
        "set_value",
        dangerous_local_fallback,
    )

    task = Task(
        goal="Prove routed actions cannot fall back locally",
        steps=[
            TaskStep(
                agent="desktop",
                action="set_value",
                arguments={
                    "value": "Hello",
                },
            )
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"

    # This is the critical security assertion.
    assert CALLS == []

    print("TEST 3: PASSED")


def test_unknown_agent_stops_later_steps():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "system",
        system_backend,
    )

    executor = TaskExecutor(
        execution_router=router
    )

    task = Task(
        goal="Stop after unknown agent",
        steps=[
            TaskStep(
                agent="system",
                action="first_action",
            ),
            TaskStep(
                agent="unknown_agent",
                action="second_action",
            ),
            TaskStep(
                agent="system",
                action="third_action",
            ),
        ],
    )

    executor.execute(task)

    assert task.status.value == "failed"

    assert [
        step.status.value
        for step in task.steps
    ] == [
        "completed",
        "failed",
        "pending",
    ]

    assert CALLS == [
        {
            "backend": "system",
            "action": "first_action",
        }
    ]

    print("TEST 4: PASSED")


def main():
    print("================================")
    print(" ROUTED TASK EXECUTOR TESTS")
    print("================================")

    print()
    print("TEST 1: Multi-backend task")
    test_multi_backend_task()

    print()
    print("TEST 2: Missing router blocks execution")
    test_missing_router_blocks_routed_step()

    print()
    print("TEST 3: No local fallback bypass")
    test_missing_backend_does_not_use_local_fallback()

    print()
    print("TEST 4: Unknown agent stops later steps")
    test_unknown_agent_stops_later_steps()

    print()
    print("================================")
    print(" ALL ROUTED TASK TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()