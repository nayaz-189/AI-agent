from knowledge.session_manager import (
    end_session,
    get_session_events,
    record_session_event,
    start_session,
)


session = start_session(
    day=9,
    version="0.009",
    objective=(
        "Build persistent project "
        "knowledge infrastructure."
    ),
)


print(
    "Started session:",
    session["session_id"],
)


record_session_event(
    event_type="feature_added",
    component="project_memory",
    description=(
        "Added append-only JSONL "
        "project event storage."
    ),
    status="working",
)


record_session_event(
    event_type="test",
    component="state_sync",
    description=(
        "Automatic project-state "
        "synchronization test passed."
    ),
    status="passed",
)


session_id = session[
    "session_id"
]


end_session(
    summary=(
        "Project knowledge "
        "infrastructure test "
        "completed successfully."
    )
)


events = get_session_events(
    session_id
)


print(
    "\nSession events:",
    len(events),
)


for event in events:

    print(
        event["event_type"],
        "->",
        event["description"],
    )