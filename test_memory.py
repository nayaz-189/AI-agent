from knowledge.project_memory import (
    load_events,
    record_event,
)


record_event(
    event_type="test",
    component="project_memory",
    description=(
        "Project knowledge system "
        "successfully recorded its "
        "first event."
    ),
    version="0.009",
    status="passed",
)


events = load_events()


print(
    "Stored events:",
    len(events),
)

print(
    "Latest event:"
)

print(
    events[-1]
)