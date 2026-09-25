import json

from knowledge.canonical_store import (
    get_connection,
    initialize_database,
)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def row_to_dict(row):
    if row is None:
        return None

    result = dict(row)

    if "metadata" in result:
        metadata = result.get("metadata")

        if metadata:
            try:
                result["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                pass

    return result


def rows_to_dicts(rows):
    return [
        row_to_dict(row)
        for row in rows
    ]


# ============================================================
# DATABASE SUMMARY
# ============================================================

def get_knowledge_summary():
    connection = get_connection()
    cursor = connection.cursor()

    tables = [
        "events",
        "decisions",
        "bugs",
        "tests",
        "research_sources",
        "skills",
        "capabilities",
        "upgrades",
        "relationships",
    ]

    summary = {}

    for table in tables:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        )

        summary[table] = (
            cursor.fetchone()[0]
        )

    connection.close()

    return summary


# ============================================================
# EVENT QUERIES
# ============================================================

def get_all_events():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        ORDER BY id ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_recent_events(limit=10):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_events_by_day(day):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE day = ?
        ORDER BY id ASC
        """,
        (day,),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_events_by_version(version):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE version = ?
        ORDER BY id ASC
        """,
        (version,),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_events_by_type(event_type):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE event_type = ?
        ORDER BY id ASC
        """,
        (event_type,),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_events_by_component(component):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE component = ?
        ORDER BY id ASC
        """,
        (component,),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# FULL TEXT SEARCH
# ============================================================

def search_events(search_term):
    """
    Search across important event fields.
    """

    connection = get_connection()
    cursor = connection.cursor()

    pattern = f"%{search_term}%"

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE description LIKE ?
           OR component LIKE ?
           OR event_type LIKE ?
           OR version LIKE ?
           OR metadata LIKE ?
        ORDER BY id ASC
        """,
        (
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
        ),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# SKILL QUERIES
# ============================================================

def get_skills():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM skills
        ORDER BY name ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# CAPABILITY QUERIES
# ============================================================

def get_capabilities():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM capabilities
        ORDER BY name ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# RESEARCH QUERIES
# ============================================================

def get_research_sources():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM research_sources
        ORDER BY id ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def search_research(search_term):
    connection = get_connection()
    cursor = connection.cursor()

    pattern = f"%{search_term}%"

    cursor.execute(
        """
        SELECT *
        FROM research_sources
        WHERE name LIKE ?
           OR component LIKE ?
           OR findings LIKE ?
           OR decision LIKE ?
           OR notes LIKE ?
        ORDER BY id ASC
        """,
        (
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
        ),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# BUG QUERIES
# ============================================================

def get_bugs():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM bugs
        ORDER BY id ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# DECISION QUERIES
# ============================================================

def get_decisions():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM decisions
        ORDER BY id ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# UPGRADE QUERIES
# ============================================================

def get_upgrades():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM upgrades
        ORDER BY id ASC
        """
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


# ============================================================
# RELATIONSHIP / TRACE QUERIES
# ============================================================

def get_outgoing_relationships(
    record_type,
    record_id,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM relationships
        WHERE source_type = ?
          AND source_id = ?
        ORDER BY id ASC
        """,
        (
            record_type,
            record_id,
        ),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def get_incoming_relationships(
    record_type,
    record_id,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM relationships
        WHERE target_type = ?
          AND target_id = ?
        ORDER BY id ASC
        """,
        (
            record_type,
            record_id,
        ),
    )

    results = rows_to_dicts(
        cursor.fetchall()
    )

    connection.close()

    return results


def trace_record(
    record_type,
    record_id,
):
    """
    Return both incoming and outgoing relationships.

    Later this will become recursive so we can trace:

    research
        -> decision
        -> feature
        -> test
        -> bug
        -> fix
        -> commit
    """

    return {
        "record_type": record_type,
        "record_id": record_id,
        "incoming": get_incoming_relationships(
            record_type,
            record_id,
        ),
        "outgoing": get_outgoing_relationships(
            record_type,
            record_id,
        ),
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    initialize_database()

    print(
        "\nCANONICAL KNOWLEDGE SUMMARY"
    )

    print(
        "==========================="
    )

    summary = get_knowledge_summary()

    for name, count in summary.items():
        print(
            f"{name}: {count}"
        )

    print(
        "\nRECENT EVENTS"
    )

    print(
        "============="
    )

    events = get_recent_events(5)

    if not events:
        print(
            "No events found."
        )

    for event in events:

        print(
            f"\nEvent #{event['id']}"
        )

        print(
            "Type:",
            event["event_type"],
        )

        print(
            "Day:",
            event["day"],
        )

        print(
            "Version:",
            event["version"],
        )

        print(
            "Component:",
            event["component"],
        )

        print(
            "Description:",
            event["description"],
        )