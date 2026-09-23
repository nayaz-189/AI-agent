import json

from datetime import datetime
from pathlib import Path

from knowledge.git_inspector import (
    inspect_git,
)

from knowledge.git_sync import (
    inspect_sync_status,
)

from knowledge.knowledge_query import (
    get_capabilities,
    get_current_architecture,
    get_current_day,
    get_current_version,
    get_known_issues,
    get_next_tasks,
    get_recent_events,
)


STORE_DIRECTORY = (
    Path(__file__).resolve().parent
    / "store"
)

CONTEXT_FILE = (
    STORE_DIRECTORY
    / "ai_context.json"
)


def simplify_event(event):
    return {
        "timestamp": event.get(
            "timestamp"
        ),
        "type": event.get(
            "event_type"
        ),
        "component": event.get(
            "component"
        ),
        "description": event.get(
            "description"
        ),
        "status": event.get(
            "status"
        ),
    }


def build_ai_context(
    recent_event_limit=20,
):

    recent_events = (
        get_recent_events(
            recent_event_limit
        )
    )

    repository = inspect_git()

    # Do not fetch here.
    # dev.py already performs the network
    # synchronization check.
    sync_status = inspect_sync_status(
        fetch=False,
    )

    context = {
        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "project": {
            "name": "AI Agent",
            "version":
                get_current_version(),
            "day":
                get_current_day(),
        },

        "repository": {
            "branch":
                repository.get("branch"),

            "commit":
                repository.get("commit"),

            "short_commit":
                repository.get(
                    "short_commit"
                ),

            "remote":
                repository.get("remote"),

            "working_tree_clean":
                sync_status.get(
                    "working_tree_clean"
                ),

            "changed_files":
                sync_status.get(
                    "changed_files",
                    [],
                ),

            "ahead":
                sync_status.get("ahead"),

            "behind":
                sync_status.get("behind"),

            "remote_synchronized":
                sync_status.get(
                    "remote_synchronized"
                ),

            "safe_to_pull":
                sync_status.get(
                    "safe_to_pull"
                ),
        },

        "architecture":
            get_current_architecture(),

        "capabilities":
            get_capabilities(),

        "known_issues":
            get_known_issues(),

        "next_tasks":
            get_next_tasks(),

        "recent_events": [
            simplify_event(event)
            for event in recent_events
        ],
    }

    return context


def save_ai_context(
    recent_event_limit=20,
):

    STORE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    context = build_ai_context(
        recent_event_limit
    )

    with open(
        CONTEXT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            context,
            file,
            indent=4,
            ensure_ascii=False,
        )

    return context