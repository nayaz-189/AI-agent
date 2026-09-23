import json

from datetime import datetime
from pathlib import Path

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

    # First make sure our stored
    # architecture matches the
    # actual codebase.

    # synchronize_project_state()

    recent_events = (
        get_recent_events(
            recent_event_limit
        )
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