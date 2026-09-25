from datetime import datetime

from knowledge.project_memory import (
    record_event,
)

from knowledge.state_manager import (
    load_state,
    save_state,
)


def get_project_info():
    """
    Return the current project lifecycle
    information.
    """

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
    """
    Update project lifecycle information.

    The state file is written only when
    something actually changes.
    """

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

    changes = {}

    # -------------------------
    # DAY
    # -------------------------

    if (
        day is not None
        and day != old_day
    ):

        project[
            "current_day"
        ] = day

        changes["day"] = {
            "old": old_day,
            "new": day,
        }

    # -------------------------
    # VERSION
    # -------------------------

    if (
        version is not None
        and version != old_version
    ):

        project[
            "version"
        ] = version

        changes["version"] = {
            "old": old_version,
            "new": version,
        }

    # -------------------------
    # STATUS
    # -------------------------

    if (
        status is not None
        and status != old_status
    ):

        project[
            "status"
        ] = status

        changes["status"] = {
            "old": old_status,
            "new": status,
        }

    # -------------------------
    # NOTHING CHANGED
    # -------------------------

    if not changes:
        return True

    # -------------------------
    # SAVE REAL CHANGE
    # -------------------------

    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)

    # -------------------------
    # RECORD HISTORY
    # -------------------------

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
    """
    Start a specific development day.

    Version changes are optional and
    deliberately separate from day
    progression.
    """

    return update_project(
        day=day,
        version=version,
        status="development",
    )


def complete_development_day():
    """
    Mark the current development day
    as completed.

    Calling this more than once does
    not create duplicate completion
    events.
    """

    state = load_state()

    if not state:
        return False

    project = state.setdefault(
        "project",
        {},
    )

    day = project.get(
        "current_day"
    )

    version = project.get(
        "version"
    )

    current_status = project.get(
        "status"
    )

    # Already completed.
    # Do not write anything again.

    if current_status == "completed":
        return True

    project["status"] = (
        "completed"
    )

    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)

    record_event(
        event_type=(
            "day_completed"
        ),

        component=(
            "development"
        ),

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


def get_next_development_day():
    """
    Decide which development day
    should be active.

    completed -> next day
    development -> resume same day
    """

    project = get_project_info()

    if not project:
        return None

    current_day = project.get(
        "current_day"
    )

    status = project.get(
        "status"
    )

    if current_day is None:
        return 1

    if status == "completed":
        return current_day + 1

    return current_day


def begin_or_resume_development():
    """
    Automatically begin or resume
    development.

    IMPORTANT:
    This function advances the day only
    when the previous day has explicitly
    been marked completed.

    It does NOT increment the project
    version automatically.
    """

    project = get_project_info()

    if not project:
        return None

    current_day = project.get(
        "current_day"
    )

    current_status = project.get(
        "status"
    )

    next_day = (
        get_next_development_day()
    )

    if next_day is None:
        return None

    # -------------------------
    # ADVANCE TO NEXT DAY
    # -------------------------

    if (
        current_status
        == "completed"
    ):

        success = (
            start_development_day(
                day=next_day,
            )
        )

        if not success:
            return None

        return {
            "action": "started",
            "day": next_day,
            "version": project.get(
                "version"
            ),
        }

    # -------------------------
    # RESUME CURRENT DAY
    # -------------------------

    return {
        "action": "resumed",
        "day": current_day,
        "version": project.get(
            "version"
        ),
    }