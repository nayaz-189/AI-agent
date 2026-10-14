from execution import Task, TaskStep
from execution.task_executor import TaskExecutor


def succeed(arguments):
    return {
        "success": True,
        "result": {
            "received": arguments,
        },
    }


def fail(arguments):
    return {
        "success": False,
        "error": "Simulated action failure.",
        "result": {
            "received": arguments,
        },
    }


def main():
    print("================================")
    print(" TASK EXECUTOR TEST")
    print("================================")

    print()
    print("TEST 1: Successful multi-step task")

    executor = TaskExecutor()

    executor.register_action(
        "succeed",
        succeed,
    )

    task = Task(
        goal="Complete two successful fake actions",
        steps=[
            TaskStep(
                action="succeed",
                arguments={"number": 1},
            ),
            TaskStep(
                action="succeed",
                arguments={"number": 2},
            ),
        ],
    )

    executor.execute(task)

    print("Task status:", task.status.value)
    print(
        "Step statuses:",
        [step.status.value for step in task.steps],
    )

    assert task.status.value == "completed"
    assert all(
        step.status.value == "completed"
        for step in task.steps
    )

    print("TEST 1: PASSED")

    print()
    print("TEST 2: Failure stops later steps")

    executor = TaskExecutor()

    executor.register_action(
        "succeed",
        succeed,
    )

    executor.register_action(
        "fail",
        fail,
    )

    task = Task(
        goal="Prove failed steps stop execution",
        steps=[
            TaskStep(
                action="succeed",
                arguments={"number": 1},
            ),
            TaskStep(
                action="fail",
                arguments={"number": 2},
            ),
            TaskStep(
                action="succeed",
                arguments={"number": 3},
            ),
        ],
    )

    executor.execute(task)

    statuses = [
        step.status.value
        for step in task.steps
    ]

    print("Task status:", task.status.value)
    print("Step statuses:", statuses)
    print("Task error:", task.error)

    assert task.status.value == "failed"

    assert statuses == [
        "completed",
        "failed",
        "pending",
    ]

    print("TEST 2: PASSED")

    print()
    print("TEST 3: Unknown action fails closed")

    executor = TaskExecutor()

    task = Task(
        goal="Reject an unknown action",
        steps=[
            TaskStep(
                action="totally_unknown_action",
            ),
        ],
    )

    executor.execute(task)

    print("Task status:", task.status.value)
    print("Step status:", task.steps[0].status.value)
    print("Error:", task.error)

    assert task.status.value == "failed"
    assert task.steps[0].status.value == "failed"

    print("TEST 3: PASSED")

    print()
    print("================================")
    print(" ALL TASK EXECUTOR TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()