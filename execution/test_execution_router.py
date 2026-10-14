from execution.execution_router import ExecutionRouter


CALLS = []


def system_backend(action, arguments):
    CALLS.append(
        {
            "backend": "system",
            "action": action,
            "arguments": arguments,
        }
    )

    return {
        "success": True,
        "result": {
            "handled_by": "system",
            "action": action,
        },
    }


def desktop_backend(action, arguments):
    CALLS.append(
        {
            "backend": "desktop",
            "action": action,
            "arguments": arguments,
        }
    )

    return {
        "success": True,
        "result": {
            "handled_by": "desktop",
            "action": action,
        },
    }


def failing_backend(action, arguments):
    CALLS.append(
        {
            "backend": "failing",
            "action": action,
            "arguments": arguments,
        }
    )

    return {
        "success": False,
        "error": "Simulated backend failure.",
    }


def reset_calls():
    CALLS.clear()


def test_system_route():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "system",
        system_backend,
    )

    result = router.route(
        agent="system",
        action="launch_application",
        arguments={
            "application": "notepad",
        },
    )

    assert result.success is True
    assert len(CALLS) == 1
    assert CALLS[0]["backend"] == "system"
    assert CALLS[0]["action"] == "launch_application"

    print("TEST 1: PASSED")


def test_desktop_route():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "desktop",
        desktop_backend,
    )

    result = router.route(
        agent="desktop",
        action="set_value",
        arguments={
            "value": "Hello",
        },
    )

    assert result.success is True
    assert len(CALLS) == 1
    assert CALLS[0]["backend"] == "desktop"
    assert CALLS[0]["action"] == "set_value"

    print("TEST 2: PASSED")


def test_missing_backend_fails_closed():
    reset_calls()

    router = ExecutionRouter()

    result = router.route(
        agent="desktop",
        action="set_value",
        arguments={
            "value": "Hello",
        },
    )

    assert result.success is False

    # Critical:
    # Nothing was executed.
    assert len(CALLS) == 0

    assert result.error is not None
    assert "No execution backend" in result.error

    print("TEST 3: PASSED")


def test_backend_failure_propagates():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "system",
        failing_backend,
    )

    result = router.route(
        agent="system",
        action="launch_application",
        arguments={
            "application": "notepad",
        },
    )

    assert result.success is False
    assert len(CALLS) == 1
    assert result.error == "Simulated backend failure."

    print("TEST 4: PASSED")


def test_duplicate_backend_rejected():
    reset_calls()

    router = ExecutionRouter()

    router.register_backend(
        "system",
        system_backend,
    )

    rejected = False

    try:
        router.register_backend(
            "system",
            desktop_backend,
        )
    except ValueError:
        rejected = True

    assert rejected is True

    print("TEST 5: PASSED")


def main():
    print("================================")
    print(" EXECUTION ROUTER TESTS")
    print("================================")

    print()
    print("TEST 1: Route to system backend")
    test_system_route()

    print()
    print("TEST 2: Route to desktop backend")
    test_desktop_route()

    print()
    print("TEST 3: Missing backend fails closed")
    test_missing_backend_fails_closed()

    print()
    print("TEST 4: Backend failure propagates")
    test_backend_failure_propagates()

    print()
    print("TEST 5: Duplicate backend rejected")
    test_duplicate_backend_rejected()

    print()
    print("================================")
    print(" ALL EXECUTION ROUTER TESTS PASSED")
    print("================================")


if __name__ == "__main__":
    main()