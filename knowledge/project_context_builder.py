import json
from datetime import datetime
from pathlib import Path

from knowledge.canonical_exporter import (
    save_knowledge_export,
)

from knowledge.git_inspector import (
    inspect_git,
)

from knowledge.source_indexer import (
    save_source_index,
)

from knowledge.state_manager import (
    load_state,
)


# ============================================================
# UNIFIED PROJECT CONTEXT BUILDER
# ============================================================
#
# Creates one portable machine-readable package describing
# the current AI Agent project.
#
# IMPORTANT:
#
# This file is DERIVED knowledge.
#
# Authority order:
#
# 1. Actual source code + Git
# 2. Canonical SQLite database
# 3. Current project state
# 4. Generated project context
# 5. Conversation memory
#
# ============================================================


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

KNOWLEDGE_STORE = (
    PROJECT_ROOT
    / "knowledge"
    / "store"
)

PROJECT_CONTEXT_PATH = (
    KNOWLEDGE_STORE
    / "project_context.json"
)

CONTEXT_SCHEMA_VERSION = "1.0"


# ============================================================
# BUILD CONTEXT
# ============================================================

def build_project_context():
    """
    Rebuild all important derived knowledge and combine it
    into one portable project context package.
    """

    # --------------------------------------------------------
    # SOURCE CODE VIEW
    # --------------------------------------------------------

    source_index = (
        save_source_index()
    )

    # --------------------------------------------------------
    # CANONICAL KNOWLEDGE VIEW
    # --------------------------------------------------------

    knowledge_export = (
        save_knowledge_export()
    )

    # --------------------------------------------------------
    # CURRENT PROJECT STATE
    # --------------------------------------------------------

    project_state = (
        load_state()
    )

    # --------------------------------------------------------
    # GIT STATE
    # --------------------------------------------------------

    repository = (
        inspect_git()
    )

    # --------------------------------------------------------
    # UNIFIED PACKAGE
    # --------------------------------------------------------

    context = {
        "schema_version":
            CONTEXT_SCHEMA_VERSION,

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "authority": {
            "order": [
                "actual_source_code_and_git",
                "canonical_sqlite_database",
                "project_state",
                "generated_project_context",
                "conversation_memory",
            ],

            "warning": (
                "This project context is a generated "
                "derived view. If it conflicts with "
                "actual source code, Git history, or "
                "canonical SQLite knowledge, the "
                "authoritative source wins."
            ),
        },

        "repository":
            repository,

        "project_state":
            project_state,

        "source_index":
            source_index,

        "canonical_knowledge":
            knowledge_export,
    }

    return context


# ============================================================
# SAVE CONTEXT
# ============================================================

def save_project_context():
    """
    Build and save project_context.json.
    """

    KNOWLEDGE_STORE.mkdir(
        parents=True,
        exist_ok=True,
    )

    context = (
        build_project_context()
    )

    PROJECT_CONTEXT_PATH.write_text(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return context


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("UNIFIED PROJECT CONTEXT BUILDER")
    print("==============================")

    context = (
        save_project_context()
    )

    print()
    print(
        "Schema:",
        context["schema_version"],
    )

    repository = (
        context["repository"]
    )

    print()
    print("REPOSITORY")
    print(
        "Branch:",
        repository.get("branch"),
    )
    print(
        "Commit:",
        repository.get(
            "short_commit"
        ),
    )
    print(
        "Clean:",
        repository.get(
            "working_tree_clean"
        ),
    )

    state = context[
        "project_state"
    ]

    project = state.get(
        "project",
        {},
    )

    print()
    print("PROJECT")
    print(
        "Day:",
        project.get(
            "current_day"
        ),
    )
    print(
        "Version:",
        project.get(
            "version"
        ),
    )
    print(
        "Status:",
        project.get(
            "status"
        ),
    )

    statistics = (
        context[
            "source_index"
        ][
            "statistics"
        ]
    )

    print()
    print("SOURCE")
    print(
        "Python files:",
        statistics.get(
            "python_files"
        ),
    )
    print(
        "Functions:",
        statistics.get(
            "top_level_functions"
        ),
    )
    print(
        "Parse failures:",
        statistics.get(
            "parse_failures"
        ),
    )

    summary = (
        context[
            "canonical_knowledge"
        ][
            "summary"
        ]
    )

    print()
    print("KNOWLEDGE")

    for name, count in (
        summary.items()
    ):
        print(
            f"{name}: {count}"
        )

    print()
    print(
        "Context saved to:",
        PROJECT_CONTEXT_PATH,
    )