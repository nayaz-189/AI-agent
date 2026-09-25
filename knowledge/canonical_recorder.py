import json
from datetime import datetime

from knowledge.canonical_store import (
    get_connection,
    initialize_database,
)
from knowledge.state_manager import (
    load_state,
)
from knowledge.project_memory import (
    record_event as record_legacy_event,
)


# ============================================================
# CURRENT PROJECT CONTEXT
# ============================================================

def get_project_context():
    """
    Read the current development day and version from
    project_state.json.

    This prevents callers from having to manually specify
    day/version for every record.
    """

    state = load_state()

    project = state.get(
        "project",
        {},
    )

    return {
        "day": project.get(
            "current_day"
        ),
        "version": project.get(
            "version"
        ),
    }


def current_timestamp():
    return (
        datetime.now()
        .astimezone()
        .isoformat()
    )


def encode_json(value):
    """
    Safely convert structured Python data to JSON text.
    """

    if value is None:
        value = {}

    return json.dumps(
        value,
        ensure_ascii=False,
    )


# ============================================================
# GENERIC DEVELOPMENT EVENT
# ============================================================

def record_event(
    event_type,
    component,
    description,
    status="recorded",
    metadata=None,
):
    """
    Record a normal development event.

    During the transition period this writes to:

    1. legacy append-only events.jsonl
    2. canonical SQLite database

    SQLite is the structured query layer.
    JSONL remains the audit/backup history.
    """

    initialize_database()

    context = get_project_context()

    day = context["day"]
    version = context["version"]

    metadata = (
        metadata
        if metadata is not None
        else {}
    )

    # --------------------------------------------------------
    # LEGACY / AUDIT LOG
    # --------------------------------------------------------

    legacy_metadata = dict(
        metadata
    )

    legacy_metadata["day"] = day

    record_legacy_event(
        event_type=event_type,
        component=component,
        description=description,
        version=version,
        status=status,
        metadata=legacy_metadata,
    )

    # --------------------------------------------------------
    # CANONICAL DATABASE
    # --------------------------------------------------------

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO events (
            source_id,
            timestamp,
            day,
            version,
            event_type,
            component,
            description,
            status,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            current_timestamp(),
            day,
            version,
            event_type,
            component,
            description,
            status,
            encode_json(metadata),
        ),
    )

    event_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return event_id


# ============================================================
# ARCHITECTURE DECISION
# ============================================================

def record_decision(
    title,
    decision,
    reason=None,
    alternatives=None,
    status="accepted",
):
    """
    Record an explicit architecture or development decision.
    """

    initialize_database()

    context = get_project_context()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO decisions (
            timestamp,
            day,
            version,
            title,
            decision,
            reason,
            alternatives,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_timestamp(),
            context["day"],
            context["version"],
            title,
            decision,
            reason,
            encode_json(
                alternatives
                if alternatives is not None
                else []
            ),
            status,
        ),
    )

    decision_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return decision_id


# ============================================================
# BUG RECORDING
# ============================================================

def record_bug(
    component,
    description,
    cause=None,
    fix=None,
    status="open",
):
    """
    Record a bug and, when known, its cause and fix.
    """

    initialize_database()

    context = get_project_context()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO bugs (
            timestamp,
            day,
            version,
            component,
            description,
            cause,
            fix,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_timestamp(),
            context["day"],
            context["version"],
            component,
            description,
            cause,
            fix,
            status,
        ),
    )

    bug_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return bug_id


# ============================================================
# TEST RECORDING
# ============================================================

def record_test(
    component,
    test_name,
    command=None,
    expected_result=None,
    actual_result=None,
    status="unknown",
):
    """
    Store a reproducible development test.
    """

    initialize_database()

    context = get_project_context()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tests (
            timestamp,
            day,
            version,
            component,
            test_name,
            command,
            expected_result,
            actual_result,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_timestamp(),
            context["day"],
            context["version"],
            component,
            test_name,
            command,
            expected_result,
            actual_result,
            status,
        ),
    )

    test_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return test_id


# ============================================================
# RESEARCH SOURCE
# ============================================================

def record_research(
    name,
    source_type,
    url=None,
    component=None,
    findings=None,
    license=None,
    decision=None,
    notes=None,
):
    """
    Store research used during architecture/design work.

    Examples:
    - GitHub repository
    - documentation
    - academic paper
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO research_sources (
            timestamp,
            name,
            source_type,
            url,
            component,
            findings,
            license,
            decision,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_timestamp(),
            name,
            source_type,
            url,
            component,
            findings,
            license,
            decision,
            notes,
        ),
    )

    research_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return research_id


# ============================================================
# CAPABILITY
# ============================================================

def record_capability(
    name,
    description,
    component=None,
    source=None,
    status="available",
):
    """
    Register a capability currently available to the agent.
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO capabilities (
            timestamp,
            name,
            description,
            component,
            source,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name)
        DO UPDATE SET
            timestamp = excluded.timestamp,
            description = excluded.description,
            component = excluded.component,
            source = excluded.source,
            status = excluded.status
        """,
        (
            current_timestamp(),
            name,
            description,
            component,
            source,
            status,
        ),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT id
        FROM capabilities
        WHERE name = ?
        """,
        (name,),
    )

    capability_id = (
        cursor.fetchone()["id"]
    )

    connection.close()

    return capability_id


# ============================================================
# SKILL
# ============================================================

def record_skill(
    name,
    description,
    skill_version="1.0",
    source=None,
    status="available",
    risk_level="low",
    metadata=None,
):
    """
    Register or update a learned agent skill.
    """

    initialize_database()

    timestamp = current_timestamp()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO skills (
            created_at,
            updated_at,
            name,
            description,
            version,
            source,
            status,
            risk_level,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(name)
        DO UPDATE SET
            updated_at = excluded.updated_at,
            description = excluded.description,
            version = excluded.version,
            source = excluded.source,
            status = excluded.status,
            risk_level = excluded.risk_level,
            metadata = excluded.metadata
        """,
        (
            timestamp,
            timestamp,
            name,
            description,
            skill_version,
            source,
            status,
            risk_level,
            encode_json(metadata),
        ),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT id
        FROM skills
        WHERE name = ?
        """,
        (name,),
    )

    skill_id = (
        cursor.fetchone()["id"]
    )

    connection.close()

    return skill_id


# ============================================================
# SELF-UPGRADE PROPOSAL
# ============================================================

def record_upgrade(
    title,
    reason,
    proposed_changes,
    affected_components=None,
    risk_level="medium",
    test_plan=None,
    status="proposed",
    git_commit=None,
):
    """
    Record a proposed self-upgrade.

    Recording an upgrade DOES NOT authorize execution.

    Future security and approval layers will decide whether
    the upgrade may actually modify the agent.
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO upgrades (
            timestamp,
            title,
            reason,
            proposed_changes,
            affected_components,
            risk_level,
            test_plan,
            status,
            git_commit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_timestamp(),
            title,
            reason,
            proposed_changes,
            encode_json(
                affected_components
                if affected_components is not None
                else []
            ),
            risk_level,
            test_plan,
            status,
            git_commit,
        ),
    )

    upgrade_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return upgrade_id


# ============================================================
# RELATIONSHIPS
# ============================================================

def link_records(
    source_type,
    source_id,
    relation,
    target_type,
    target_id,
):
    """
    Create point-to-point traceability between records.

    Example:

    research #1
        --influenced-->
    decision #3
    """

    initialize_database()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO relationships (
            source_type,
            source_id,
            relation,
            target_type,
            target_id
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            source_type,
            source_id,
            relation,
            target_type,
            target_id,
        ),
    )

    relationship_id = (
        cursor.lastrowid
    )

    connection.commit()
    connection.close()

    return relationship_id