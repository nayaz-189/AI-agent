from datetime import datetime

from knowledge.project_memory import (
    record_event,
)

from knowledge.state_manager import (
    load_state,
    save_state,
)


def get_project_info():
    state = load_state()

    if not state:
        return None

    return state.get(
        "project",
        {},
    )


def update_project(
    day=None,
    version=None,
    status=None,
):
    state = load_state()

    if not state:
        return False

    project = state.setdefault(
        "project",
        {},
    )

    old_day = project.get(
        "current_day"
    )

    old_version = project.get(
        "version"
    )

    old_status = project.get(
        "status"
    )

    if day is not None:
        project["current_day"] = day

    if version is not None:
        project["version"] = version

    if status is not None:
        project["status"] = status

    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)

    changes = {}

    if (
        day is not None
        and day != old_day
    ):
        changes["day"] = {
            "old": old_day,
            "new": day,
        }

    if (
        version is not None
        and version != old_version
    ):
        changes["version"] = {
            "old": old_version,
            "new": version,
        }

    if (
        status is not None
        and status != old_status
    ):
        changes["status"] = {
            "old": old_status,
            "new": status,
        }

    if changes:
        record_event(
            event_type=(
                "project_lifecycle_change"
            ),
            component=(
                "lifecycle_manager"
            ),
            description=(
                "Project lifecycle "
                "state updated."
            ),
            version=project.get(
                "version"
            ),
            status=project.get(
                "status"
            ),
            metadata={
                "changes": changes
            },
        )

    return True


def start_development_day(
    day,
    version=None,
):
    return update_project(
        day=day,
        version=version,
        status="development",
    )


def complete_development_day():
    state = load_state()

    if not state:
        return False

    project = state.get(
        "project",
        {}
    )

    day = project.get(
        "current_day"
    )

    version = project.get(
        "version"
    )

    record_event(
        event_type="day_completed",
        component="development",
        description=(
            f"Development Day "
            f"{day} completed."
        ),
        version=version,
        status="completed",
        metadata={
            "day": day,
        },
    )

    return True