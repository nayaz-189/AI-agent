from knowledge.context_builder import (
    save_ai_context,
)

from knowledge.knowledge_query import (
    get_current_day,
    get_current_version,
)

from knowledge.state_sync import (
    synchronize_project_state,
)


def refresh_project_knowledge():
    print(
        "\nRefreshing project knowledge..."
    )

    # Synchronize actual source-code
    # architecture with stored state.
    sync_success = (
        synchronize_project_state()
    )

    if not sync_success:
        print(
            "Project-state synchronization failed."
        )

        return False

    # Generate fresh AI-oriented context.
    context = save_ai_context()

    print(
        "\nProject knowledge ready."
    )

    print(
        "Version:",
        get_current_version(),
    )

    print(
        "Day:",
        get_current_day(),
    )

    print(
        "Recent events:",
        len(
            context.get(
                "recent_events",
                [],
            )
        ),
    )

    return True