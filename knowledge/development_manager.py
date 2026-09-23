from datetime import datetime

from knowledge.context_builder import (
    save_ai_context,
)

from knowledge.git_inspector import (
    inspect_git,
)

from knowledge.git_sync import (
    inspect_sync_status,
)

from knowledge.knowledge_query import (
    get_current_day,
    get_current_version,
)

from knowledge.state_sync import (
    synchronize_project_state,
)


def print_sync_warnings(sync_status):

    changed_files = sync_status.get(
        "changed_files",
        [],
    )

    ahead = sync_status.get(
        "ahead"
    )

    behind = sync_status.get(
        "behind"
    )

    if changed_files:

        print(
            "\nWARNING:"
        )

        print(
            "There are uncommitted "
            "project changes."
        )

        print(
            "Changed files:",
            len(changed_files),
        )

    if (
        ahead is not None
        and ahead > 0
    ):

        print(
            "\nWARNING:"
        )

        print(
            "Local repository is",
            ahead,
            "commit(s) ahead of remote."
        )

    if (
        behind is not None
        and behind > 0
    ):

        print(
            "\nWARNING:"
        )

        print(
            "Local repository is",
            behind,
            "commit(s) behind remote."
        )

    if (
        not changed_files
        and ahead == 0
        and behind == 0
    ):

        print(
            "\nRepository is fully "
            "synchronized."
        )


def start_development():

    print(
        "\n=============================="
    )

    print(
        " AI AGENT DEVELOPMENT STARTUP"
    )

    print(
        "==============================\n"
    )

    print(
        "1. Synchronizing project state..."
    )

    sync_result = (
        synchronize_project_state()
    )

    if sync_result is False:

        print(
            "Project-state "
            "synchronization failed."
        )

        return False

    print(
        "\n2. Inspecting repository..."
    )

    repository = inspect_git()

    if not repository:

        print(
            "Git repository "
            "inspection failed."
        )

        return False

    print(
        "Branch:",
        repository.get(
            "branch"
        ),
    )

    print(
        "Commit:",
        repository.get(
            "short_commit"
        ),
    )

    print(
        "\n3. Checking remote "
        "synchronization..."
    )

    sync_status = (
        inspect_sync_status(
            fetch=True,
        )
    )

    print(
        "Fetch successful:",
        sync_status.get(
            "fetch_success"
        ),
    )

    print(
        "Working tree clean:",
        sync_status.get(
            "working_tree_clean"
        ),
    )

    print(
        "Ahead:",
        sync_status.get(
            "ahead"
        ),
    )

    print(
        "Behind:",
        sync_status.get(
            "behind"
        ),
    )

    print_sync_warnings(
        sync_status
    )

    print(
        "\n4. Building AI context..."
    )

    context = save_ai_context()

    print(
        "\n5. Development "
        "environment ready."
    )

    print(
        "\nProject:"
    )

    print(
        "Day:",
        get_current_day(),
    )

    print(
        "Version:",
        get_current_version(),
    )

    print(
        "Context generated:",
        context.get(
            "generated_at"
        ),
    )

    print(
        "\nStartup completed at:",
        datetime.now()
        .astimezone()
        .isoformat(),
    )

    return True