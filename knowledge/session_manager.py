from datetime import datetime
from uuid import uuid4

from knowledge.project_memory import (
    load_events,
    record_event,
)


_current_session = None


def start_session(
    day,
    version,
    objective,
):
    global _current_session

    session_id = (
        f"day-{day}-"
        f"{uuid4().hex[:8]}"
    )

    _current_session = {
        "session_id": session_id,
        "day": day,
        "version": version,
        "objective": objective,
        "started_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
    }

    record_event(
        event_type="session_started",
        component="development_session",
        description=objective,
        version=version,
        status="active",
        metadata={
            "session_id": session_id,
            "day": day,
        },
    )

    return _current_session


def get_current_session():
    return _current_session


def record_session_event(
    event_type,
    component,
    description,
    status=None,
    metadata=None,
):
    if _current_session is None:
        raise RuntimeError(
            "No development session "
            "is currently active."
        )

    event_metadata = (
        metadata.copy()
        if metadata
        else {}
    )

    event_metadata["session_id"] = (
        _current_session[
            "session_id"
        ]
    )

    event_metadata["day"] = (
        _current_session["day"]
    )

    return record_event(
        event_type=event_type,
        component=component,
        description=description,
        version=_current_session[
            "version"
        ],
        status=status,
        metadata=event_metadata,
    )


def end_session(
    summary,
    status="completed",
):
    global _current_session

    if _current_session is None:
        raise RuntimeError(
            "No development session "
            "is currently active."
        )

    session = _current_session

    record_event(
        event_type="session_ended",
        component="development_session",
        description=summary,
        version=session["version"],
        status=status,
        metadata={
            "session_id":
                session["session_id"],

            "day":
                session["day"],

            "started_at":
                session["started_at"],

            "ended_at":
                datetime.now()
                .astimezone()
                .isoformat(),
        },
    )

    _current_session = None

    return session


def get_session_events(
    session_id,
):
    events = load_events()

    return [
        event
        for event in events
        if (
            event
            .get("metadata", {})
            .get("session_id")
            == session_id
        )
    ]