from execution.execution_history import (
    ExecutionEvent,
    ExecutionHistory,
    REDACTED,
    sanitize_for_history,
)


def test_basic_event_recording():

    history = ExecutionHistory()

    event = ExecutionEvent(
        event_type="step_started",
        task_id="task_test",
        step_id="step_test",
        agent="desktop",
        action="set_value",
        details={
            "value": "Hello",
        },
    )

    history.record(event)

    events = history.all_events()

    assert len(events) == 1

    assert events[0]["event_type"] == (
        "step_started"
    )

    assert events[0]["task_id"] == (
        "task_test"
    )

    assert events[0]["details"]["value"] == (
        "Hello"
    )

    print("TEST 1: PASSED")


def test_secret_redaction():

    safe = sanitize_for_history(
        {
            "username": "nayaz",
            "password": "DO_NOT_STORE",
            "api_key": "SECRET_API_KEY",
            "remember_me": True,
        }
    )

    assert safe["username"] == "nayaz"

    assert safe["password"] == REDACTED

    assert safe["api_key"] == REDACTED

    assert safe["remember_me"] is True

    serialized = repr(safe)

    assert "DO_NOT_STORE" not in serialized
    assert "SECRET_API_KEY" not in serialized

    print("TEST 2: PASSED")


def test_nested_secret_redaction():

    original = {
        "account": {
            "email": "test@example.com",
            "credentials": {
                "password": "NESTED_PASSWORD",
                "access_token": "NESTED_TOKEN",
            },
        },
        "requests": [
            {
                "name": "first",
                "secret": "LIST_SECRET",
            }
        ],
    }

    safe = sanitize_for_history(
        original
    )

    assert (
        safe["account"]
        ["credentials"]
        ["password"]
        == REDACTED
    )

    assert (
        safe["account"]
        ["credentials"]
        ["access_token"]
        == REDACTED
    )

    assert (
        safe["requests"][0]["secret"]
        == REDACTED
    )

    serialized = repr(safe)

    assert "NESTED_PASSWORD" not in serialized
    assert "NESTED_TOKEN" not in serialized
    assert "LIST_SECRET" not in serialized

    print("TEST 3: PASSED")


def test_original_data_not_modified():

    original = {
        "username": "nayaz",
        "password": "ORIGINAL_SECRET",
    }

    safe = sanitize_for_history(
        original
    )

    assert (
        original["password"]
        == "ORIGINAL_SECRET"
    )

    assert (
        safe["password"]
        == REDACTED
    )

    assert safe is not original

    print("TEST 4: PASSED")


def test_history_contains_only_redacted_event():

    history = ExecutionHistory()

    event = ExecutionEvent(
        event_type="action_requested",
        task_id="task_sensitive",
        step_id="step_sensitive",
        agent="system",
        action="login",
        details={
            "arguments": {
                "username": "nayaz",
                "password": "HISTORY_SECRET",
                "auth_token": "HISTORY_TOKEN",
            }
        },
    )

    history.record(event)

    events = history.all_events()

    serialized = repr(events)

    assert "HISTORY_SECRET" not in serialized
    assert "HISTORY_TOKEN" not in serialized

    arguments = (
        events[0]
        ["details"]
        ["arguments"]
    )

    assert (
        arguments["password"]
        == REDACTED
    )

    assert (
        arguments["auth_token"]
        == REDACTED
    )

    print("TEST 5: PASSED")


def test_task_and_step_queries():

    history = ExecutionHistory()

    history.record(
        ExecutionEvent(
            event_type="step_started",
            task_id="task_one",
            step_id="step_one",
        )
    )

    history.record(
        ExecutionEvent(
            event_type="step_completed",
            task_id="task_one",
            step_id="step_one",
        )
    )

    history.record(
        ExecutionEvent(
            event_type="task_started",
            task_id="task_two",
        )
    )

    task_one_events = (
        history.events_for_task(
            "task_one"
        )
    )

    step_one_events = (
        history.events_for_step(
            "step_one"
        )
    )

    assert len(task_one_events) == 2
    assert len(step_one_events) == 2
    assert history.count() == 3

    print("TEST 6: PASSED")


def main():

    print(
        "================================"
    )

    print(
        " EXECUTION HISTORY TESTS"
    )

    print(
        "================================"
    )

    print()
    print(
        "TEST 1: Basic event recording"
    )
    test_basic_event_recording()

    print()
    print(
        "TEST 2: Secret redaction"
    )
    test_secret_redaction()

    print()
    print(
        "TEST 3: Nested secret redaction"
    )
    test_nested_secret_redaction()

    print()
    print(
        "TEST 4: Original data remains unchanged"
    )
    test_original_data_not_modified()

    print()
    print(
        "TEST 5: History contains only redacted data"
    )
    test_history_contains_only_redacted_event()

    print()
    print(
        "TEST 6: Task and step queries"
    )
    test_task_and_step_queries()

    print()

    print(
        "================================"
    )

    print(
        " ALL EXECUTION HISTORY TESTS PASSED"
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    main()