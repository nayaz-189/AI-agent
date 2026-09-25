import json
from datetime import datetime
from pathlib import Path

from knowledge.canonical_query import (
    get_all_events,
    get_bugs,
    get_capabilities,
    get_decisions,
    get_knowledge_summary,
    get_research_sources,
    get_skills,
    get_upgrades,
)

from knowledge.canonical_store import (
    get_connection,
    initialize_database,
)


# ============================================================
# AI AGENT CANONICAL KNOWLEDGE EXPORTER
# ============================================================
#
# Creates a portable, machine-readable representation of the
# canonical project knowledge database.
#
# SQLite remains authoritative.
#
# knowledge_export.json is a DERIVED VIEW intended for:
#
# - external AI context
# - local AI context
# - debugging
# - synchronization
# - backup inspection
# - future knowledge bridge
#
# NEVER store secrets in canonical knowledge or this export.
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

EXPORT_PATH = (
    KNOWLEDGE_STORE
    / "knowledge_export.json"
)


EXPORT_SCHEMA_VERSION = "1.0"


# ============================================================
# RELATIONSHIPS
# ============================================================

def get_all_relationships():
    """
    Export all point-to-point relationships.

    canonical_query.py currently provides relationship queries
    by record, but not one function for retrieving all of them.
    Therefore the exporter performs this read directly against
    the canonical database.
    """

    initialize_database()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM relationships
        ORDER BY id ASC
        """
    )

    relationships = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return relationships


# ============================================================
# TESTS
# ============================================================

def get_all_tests():
    """
    Export all canonical test records.

    canonical_query.py currently does not expose get_tests(),
    so this exporter performs a read-only database query.
    """

    initialize_database()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM tests
        ORDER BY id ASC
        """
    )

    tests = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return tests


# ============================================================
# EXPORT BUILD
# ============================================================

def build_knowledge_export():
    """
    Build the complete portable canonical knowledge export.
    """

    initialize_database()

    return {
        "schema_version":
            EXPORT_SCHEMA_VERSION,

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "authority": {
            "canonical_source":
                "knowledge/database/project_knowledge.db",

            "export_role":
                "derived_portable_view",

            "rule":
                (
                    "If this export conflicts with the "
                    "canonical SQLite database or actual "
                    "source code, the authoritative source "
                    "wins."
                ),
        },

        "summary":
            get_knowledge_summary(),

        "events":
            get_all_events(),

        "decisions":
            get_decisions(),

        "bugs":
            get_bugs(),

        "tests":
            get_all_tests(),

        "research_sources":
            get_research_sources(),

        "skills":
            get_skills(),

        "capabilities":
            get_capabilities(),

        "upgrades":
            get_upgrades(),

        "relationships":
            get_all_relationships(),
    }


# ============================================================
# SAVE EXPORT
# ============================================================

def save_knowledge_export():
    """
    Generate knowledge_export.json.
    """

    KNOWLEDGE_STORE.mkdir(
        parents=True,
        exist_ok=True,
    )

    export = build_knowledge_export()

    EXPORT_PATH.write_text(
        json.dumps(
            export,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return export


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("CANONICAL KNOWLEDGE EXPORTER")
    print("==============================")

    export = save_knowledge_export()

    print()
    print(
        "Schema version:",
        export["schema_version"],
    )

    print(
        "Events:",
        len(export["events"]),
    )

    print(
        "Decisions:",
        len(export["decisions"]),
    )

    print(
        "Bugs:",
        len(export["bugs"]),
    )

    print(
        "Tests:",
        len(export["tests"]),
    )

    print(
        "Research sources:",
        len(
            export[
                "research_sources"
            ]
        ),
    )

    print(
        "Skills:",
        len(export["skills"]),
    )

    print(
        "Capabilities:",
        len(
            export[
                "capabilities"
            ]
        ),
    )

    print(
        "Upgrades:",
        len(export["upgrades"]),
    )

    print(
        "Relationships:",
        len(
            export[
                "relationships"
            ]
        ),
    )

    print()
    print(
        "Export saved to:",
        EXPORT_PATH,
    )