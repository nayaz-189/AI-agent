import hashlib
import json
from pathlib import Path

from knowledge.canonical_store import (
    get_connection,
    initialize_database,
)


STORE_DIRECTORY = (
    Path(__file__).resolve().parent
    / "store"
)

EVENTS_FILE = (
    STORE_DIRECTORY
    / "events.jsonl"
)


# ============================================================
# HISTORICAL VERSION → DAY MAP
# ============================================================
#
# This exists ONLY for legacy records that were created before
# day was stored explicitly.
#
# Future canonical records should store day directly.
# ============================================================

LEGACY_VERSION_DAY_MAP = {
    "0.009": 9,
    "0.010": 10,
    "0.011": 11,
}


# ============================================================
# SOURCE ID
# ============================================================

def create_source_id(
    event,
    line_number,
):
    """
    Create a stable identity for each original JSONL record.

    This allows the migration to run repeatedly without
    duplicating historical events.
    """

    raw = json.dumps(
        event,
        sort_keys=True,
        ensure_ascii=False,
    )

    identity = (
        f"{line_number}:{raw}"
    )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return (
        f"legacy:{digest}"
    )


# ============================================================
# DAY EXTRACTION
# ============================================================

def determine_event_day(event):
    """
    Determine the development day of a legacy event.

    Priority:

    1. metadata.day
    2. metadata.changes.day.new
    3. known historical version/day mapping

    This fallback exists only to repair old records.
    """

    metadata = event.get(
        "metadata",
        {},
    )

    # --------------------------------------------------------
    # METHOD 1
    # Explicit day stored in metadata
    # --------------------------------------------------------

    day = metadata.get(
        "day"
    )

    if isinstance(day, int):
        return day

    # --------------------------------------------------------
    # METHOD 2
    # Lifecycle event
    #
    # Example:
    #
    # "changes": {
    #     "day": {
    #         "old": 9,
    #         "new": 10
    #     }
    # }
    # --------------------------------------------------------

    changes = metadata.get(
        "changes",
        {},
    )

    day_change = changes.get(
        "day",
        {},
    )

    new_day = day_change.get(
        "new"
    )

    if isinstance(new_day, int):
        return new_day

    # --------------------------------------------------------
    # METHOD 3
    # Legacy version/day mapping
    # --------------------------------------------------------

    version = event.get(
        "version"
    )

    return LEGACY_VERSION_DAY_MAP.get(
        version
    )


# ============================================================
# EVENT MIGRATION
# ============================================================

def migrate_events():

    if not EVENTS_FILE.exists():

        print(
            "No legacy events file found."
        )

        return {
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }

    connection = get_connection()

    cursor = connection.cursor()

    imported = 0
    updated = 0
    skipped = 0
    failed = 0

    with open(
        EVENTS_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):

            line = line.strip()

            if not line:
                continue

            try:

                event = json.loads(
                    line
                )

                source_id = (
                    create_source_id(
                        event,
                        line_number,
                    )
                )

                metadata = event.get(
                    "metadata",
                    {},
                )

                day = determine_event_day(
                    event
                )

                # ------------------------------------------------
                # CHECK IF EVENT ALREADY EXISTS
                # ------------------------------------------------

                cursor.execute(
                    """
                    SELECT
                        id,
                        day
                    FROM events
                    WHERE source_id = ?
                    """,
                    (
                        source_id,
                    ),
                )

                existing = (
                    cursor.fetchone()
                )

                # ------------------------------------------------
                # EXISTING EVENT
                # ------------------------------------------------

                if existing:

                    existing_day = (
                        existing["day"]
                    )

                    # Repair missing day information.

                    if (
                        existing_day is None
                        and day is not None
                    ):

                        cursor.execute(
                            """
                            UPDATE events
                            SET day = ?
                            WHERE id = ?
                            """,
                            (
                                day,
                                existing["id"],
                            ),
                        )

                        updated += 1

                    else:
                        skipped += 1

                    continue

                # ------------------------------------------------
                # NEW EVENT
                # ------------------------------------------------

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
                        source_id,

                        event.get(
                            "timestamp",
                            "unknown",
                        ),

                        day,

                        event.get(
                            "version"
                        ),

                        event.get(
                            "event_type",
                            "unknown",
                        ),

                        event.get(
                            "component"
                        ),

                        event.get(
                            "description",
                            "",
                        ),

                        event.get(
                            "status"
                        ),

                        json.dumps(
                            metadata,
                            ensure_ascii=False,
                        ),
                    ),
                )

                imported += 1

            except (
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ) as error:

                failed += 1

                print(
                    f"Could not migrate line "
                    f"{line_number}: {error}"
                )

    connection.commit()
    connection.close()

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


# ============================================================
# MIGRATION CONTROLLER
# ============================================================

def migrate_legacy_knowledge():

    initialize_database()

    result = migrate_events()

    print(
        "\nLegacy knowledge migration"
    )

    print(
        "Imported:",
        result["imported"],
    )

    print(
        "Updated:",
        result["updated"],
    )

    print(
        "Skipped:",
        result["skipped"],
    )

    print(
        "Failed:",
        result["failed"],
    )

    return result


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    migrate_legacy_knowledge()