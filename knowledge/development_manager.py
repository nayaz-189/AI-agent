from datetime import datetime

from knowledge.bridge_manager import (
    refresh_knowledge_bridge,
    verify_knowledge_bridge,
)

from knowledge.context_builder import (
    save_ai_context,
)

from knowledge.context_repo_publisher import (
    publish_to_context_repository,
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

from knowledge.lifecycle_manager import (
    begin_or_resume_development,
)

from knowledge.publication_manager import (
    create_publication_package,
    verify_publication_package,
)

from knowledge.state_sync import (
    synchronize_project_state,
)


# ============================================================
# DEVELOPMENT STARTUP MANAGER
# ============================================================
#
# Standard development startup:
#
#     python dev.py
#
# Responsibilities:
#
# 1. Begin/resume development lifecycle
# 2. Synchronize project state
# 3. Inspect core Git repository
# 4. Check core remote synchronization
# 5. Build lightweight AI context
# 6. Refresh complete internal knowledge bridge
# 7. Verify internal bridge integrity
# 8. Build restricted external AI publication package
# 9. Verify external publication integrity
# 10. Copy approved artifacts to separate context repository
# 11. Mark development environment ready
#
# SECURITY:
#
# This manager does NOT:
#
# - commit Git changes
# - push Git changes
# - grant permissions
# - expose the canonical database
# - expose the internal knowledge bridge
# - give an external AI execution authority
#
# External publication remains a one-way, allowlisted,
# integrity-checked knowledge path.
#
# ============================================================


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

    # ========================================================
    # 1. LIFECYCLE
    # ========================================================

    print(
        "1. Checking development "
        "lifecycle..."
    )

    lifecycle = (
        begin_or_resume_development()
    )

    if lifecycle is None:
        print(
            "Development lifecycle "
            "could not be loaded."
        )

        return False

    action = lifecycle.get(
        "action"
    )

    day = lifecycle.get(
        "day"
    )

    version = lifecycle.get(
        "version"
    )

    if action == "started":
        print(
            f"Started Development "
            f"Day {day}."
        )

    else:
        print(
            f"Resuming Development "
            f"Day {day}."
        )

    print(
        "Version:",
        version,
    )

    # ========================================================
    # 2. PROJECT STATE
    # ========================================================

    print(
        "\n2. Synchronizing "
        "project state..."
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

    # ========================================================
    # 3. CORE REPOSITORY
    # ========================================================

    print(
        "\n3. Inspecting core "
        "repository..."
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

    # ========================================================
    # 4. CORE REMOTE SYNCHRONIZATION
    # ========================================================

    print(
        "\n4. Checking core remote "
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

    # ========================================================
    # 5. LIGHTWEIGHT AI CONTEXT
    # ========================================================

    print(
        "\n5. Building lightweight "
        "AI context..."
    )

    context = save_ai_context()

    # ========================================================
    # 6. INTERNAL KNOWLEDGE BRIDGE
    # ========================================================

    print(
        "\n6. Refreshing internal "
        "knowledge bridge..."
    )

    try:
        bridge = (
            refresh_knowledge_bridge()
        )

    except Exception as error:
        print(
            "Knowledge bridge refresh "
            "failed:"
        )

        print(error)

        return False

    if not bridge.get(
        "refreshed",
        False,
    ):
        print(
            "Knowledge bridge did not "
            "report successful refresh."
        )

        return False

    print(
        "Bridge context:",
        bridge.get(
            "context_path"
        ),
    )

    # ========================================================
    # 7. INTERNAL BRIDGE INTEGRITY
    # ========================================================

    print(
        "\n7. Verifying internal "
        "knowledge bridge..."
    )

    verification = (
        verify_knowledge_bridge()
    )

    if not verification.get(
        "valid",
        False,
    ):
        print(
            "Knowledge bridge integrity "
            "verification failed."
        )

        print(
            verification.get(
                "reason"
            )
        )

        return False

    print(
        "Bridge integrity: VALID"
    )

    print(
        "SHA-256:",
        verification.get(
            "sha256"
        ),
    )

    # ========================================================
    # 8. RESTRICTED EXTERNAL CONTEXT
    # ========================================================

    print(
        "\n8. Building restricted "
        "external AI context..."
    )

    try:
        publication = (
            create_publication_package()
        )

    except Exception as error:
        print(
            "External context publication "
            "failed:"
        )

        print(error)

        return False

    if not publication.get(
        "published",
        False,
    ):
        print(
            "External context was blocked."
        )

        print(
            publication.get(
                "reason"
            )
        )

        return False

    print(
        "External context:",
        publication.get(
            "context_path"
        ),
    )

    # ========================================================
    # 9. EXTERNAL CONTEXT INTEGRITY
    # ========================================================

    print(
        "\n9. Verifying external "
        "AI context..."
    )

    publication_verification = (
        verify_publication_package()
    )

    if not publication_verification.get(
        "valid",
        False,
    ):
        print(
            "External context integrity "
            "verification failed."
        )

        print(
            publication_verification.get(
                "reason"
            )
        )

        return False

    print(
        "External context integrity: VALID"
    )

    print(
        "SHA-256:",
        publication_verification.get(
            "sha256"
        ),
    )

    # ========================================================
    # 10. CONTEXT REPOSITORY PUBLICATION
    # ========================================================

    print(
        "\n10. Synchronizing restricted "
        "context repository..."
    )

    try:
        context_repo_result = (
            publish_to_context_repository()
        )

    except Exception as error:
        print(
            "Context repository "
            "publication failed:"
        )

        print(error)

        return False

    if not context_repo_result.get(
        "published",
        False,
    ):
        print(
            "Context repository "
            "publication was blocked."
        )

        print(
            context_repo_result.get(
                "reason"
            )
        )

        details = (
            context_repo_result.get(
                "details"
            )
        )

        if details:
            print(
                "Details:",
                details,
            )

        return False

    print(
        "Context repository: SYNCHRONIZED"
    )

    print(
        "Destination:",
        context_repo_result.get(
            "destination"
        ),
    )

    print(
        "Copied:",
        context_repo_result.get(
            "copied"
        ),
    )

    print(
        "SHA-256:",
        context_repo_result.get(
            "sha256"
        ),
    )

    print(
        "Git commit/push: NOT PERFORMED"
    )

    # ========================================================
    # 11. READY
    # ========================================================

    print(
        "\n11. Development "
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
        "Lightweight context generated:",
        context.get(
            "generated_at"
        ),
    )

    print(
        "Knowledge bridge generated:",
        bridge.get(
            "manifest",
            {},
        ).get(
            "generated_at"
        ),
    )

    print(
        "External context synchronized:",
        True,
    )

    print(
        "\nStartup completed at:",
        datetime.now()
        .astimezone()
        .isoformat(),
    )

    return True