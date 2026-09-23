from knowledge.project_memory import (
    record_event,
)

from knowledge.state_manager import (
    load_state,
)


def get_version():
    state = load_state()

    if not state:
        return None

    return (
        state
        .get("project", {})
        .get("version")
    )


def record_feature(
    component,
    description,
    metadata=None,
):
    return record_event(
        event_type="feature_added",
        component=component,
        description=description,
        version=get_version(),
        status="working",
        metadata=metadata,
    )


def record_bug(
    component,
    description,
    metadata=None,
):
    return record_event(
        event_type="bug_found",
        component=component,
        description=description,
        version=get_version(),
        status="open",
        metadata=metadata,
    )


def record_fix(
    component,
    description,
    metadata=None,
):
    return record_event(
        event_type="bug_fixed",
        component=component,
        description=description,
        version=get_version(),
        status="fixed",
        metadata=metadata,
    )


def record_test(
    component,
    description,
    passed,
    metadata=None,
):
    return record_event(
        event_type="test",
        component=component,
        description=description,
        version=get_version(),
        status=(
            "passed"
            if passed
            else "failed"
        ),
        metadata=metadata,
    )


def record_decision(
    component,
    description,
    metadata=None,
):
    return record_event(
        event_type="decision",
        component=component,
        description=description,
        version=get_version(),
        status="accepted",
        metadata=metadata,
    )