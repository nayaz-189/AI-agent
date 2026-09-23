from knowledge.project_memory import (
    load_events,
)

from knowledge.state_manager import (
    load_state,
)


def get_current_version():
    state = load_state()

    if not state:
        return None

    return (
        state
        .get("project", {})
        .get("version")
    )


def get_current_day():
    state = load_state()

    if not state:
        return None

    return (
        state
        .get("project", {})
        .get("current_day")
    )


def get_current_architecture():
    state = load_state()

    if not state:
        return {}

    return state.get(
        "architecture",
        {},
    )


def get_capabilities():
    state = load_state()

    if not state:
        return []

    return state.get(
        "capabilities",
        [],
    )


def get_known_issues():
    state = load_state()

    if not state:
        return []

    return state.get(
        "known_issues",
        [],
    )


def get_next_tasks():
    state = load_state()

    if not state:
        return []

    return state.get(
        "next_tasks",
        [],
    )


def get_recent_events(limit=10):
    events = load_events()

    if limit <= 0:
        return []

    return events[-limit:]


def get_events_by_type(
    event_type,
):
    events = load_events()

    return [
        event
        for event in events
        if event.get(
            "event_type"
        ) == event_type
    ]


def get_events_by_component(
    component,
):
    events = load_events()

    return [
        event
        for event in events
        if event.get(
            "component"
        ) == component
    ]


def get_day_events(day):
    events = load_events()

    matches = []

    for event in events:

        metadata = event.get(
            "metadata",
            {},
        )

        if metadata.get(
            "day"
        ) == day:

            matches.append(
                event
            )

    return matches


def get_project_summary():
    state = load_state()

    if not state:
        return {}

    project = state.get(
        "project",
        {},
    )

    architecture = state.get(
        "architecture",
        {},
    )

    return {
        "project":
            project.get("name"),

        "version":
            project.get("version"),

        "day":
            project.get(
                "current_day"
            ),

        "status":
            project.get("status"),

        "agents":
            architecture.get(
                "agents",
                [],
            ),

        "tools":
            architecture.get(
                "tools",
                [],
            ),

        "known_issues":
            state.get(
                "known_issues",
                [],
            ),

        "next_tasks":
            state.get(
                "next_tasks",
                [],
            ),

        "last_updated":
            state.get(
                "last_updated"
            ),
    }