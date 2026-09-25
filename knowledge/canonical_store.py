import json
import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parent

DATABASE_DIRECTORY = (
    KNOWLEDGE_DIRECTORY
    / "database"
)

DATABASE_FILE = (
    DATABASE_DIRECTORY
    / "project_knowledge.db"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a SQLite database connection.

    The database directory is created automatically
    if it does not already exist.
    """

    DATABASE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():
    """
    Create the canonical project knowledge database
    and all required tables.

    Existing tables are preserved.
    """

    connection = get_connection()

    cursor = connection.cursor()

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------
    #
    # Stores chronological development history.
    #
    # source_id provides a stable identity for imported
    # events so migrations can be run multiple times without
    # creating duplicate records.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT UNIQUE,
            timestamp TEXT NOT NULL,
            day INTEGER,
            version TEXT,
            event_type TEXT NOT NULL,
            component TEXT,
            description TEXT NOT NULL,
            status TEXT,
            metadata TEXT
        )
        """
    )

    # --------------------------------------------------------
    # ARCHITECTURE DECISIONS
    # --------------------------------------------------------
    #
    # Stores important design decisions and why they were made.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            day INTEGER,
            version TEXT,
            title TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT,
            alternatives TEXT,
            status TEXT
        )
        """
    )

    # --------------------------------------------------------
    # BUGS
    # --------------------------------------------------------
    #
    # Stores bugs, root causes and fixes.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            day INTEGER,
            version TEXT,
            component TEXT,
            description TEXT NOT NULL,
            cause TEXT,
            fix TEXT,
            status TEXT
        )
        """
    )

    # --------------------------------------------------------
    # TESTS
    # --------------------------------------------------------
    #
    # Stores tests used to verify features and fixes.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            day INTEGER,
            version TEXT,
            component TEXT,
            test_name TEXT NOT NULL,
            command TEXT,
            expected_result TEXT,
            actual_result TEXT,
            status TEXT
        )
        """
    )

    # --------------------------------------------------------
    # RESEARCH SOURCES
    # --------------------------------------------------------
    #
    # Stores GitHub repositories, documentation, papers and
    # other technical sources studied during development.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS research_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT NOT NULL,
            source_type TEXT,
            url TEXT,
            component TEXT,
            findings TEXT,
            license TEXT,
            decision TEXT,
            notes TEXT
        )
        """
    )

    # --------------------------------------------------------
    # SKILLS
    # --------------------------------------------------------
    #
    # Stores skills learned by the agent.
    #
    # Later a skill may contain:
    #
    # - instructions
    # - tools
    # - dependencies
    # - examples
    # - permissions
    # - tests
    # - source information
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            version TEXT,
            source TEXT,
            status TEXT,
            risk_level TEXT,
            metadata TEXT
        )
        """
    )

    # --------------------------------------------------------
    # CAPABILITIES
    # --------------------------------------------------------
    #
    # Stores capabilities currently available to the agent.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS capabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            component TEXT,
            source TEXT,
            status TEXT
        )
        """
    )

    # --------------------------------------------------------
    # SELF-UPGRADE PROPOSALS
    # --------------------------------------------------------
    #
    # Stores proposed improvements to the agent itself.
    #
    # A future self-upgrade pipeline can use this table before
    # modifying production code.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS upgrades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            title TEXT NOT NULL,
            reason TEXT,
            proposed_changes TEXT,
            affected_components TEXT,
            risk_level TEXT,
            test_plan TEXT,
            status TEXT,
            git_commit TEXT
        )
        """
    )

    # --------------------------------------------------------
    # RELATIONSHIPS
    # --------------------------------------------------------
    #
    # This is what gives us point-to-point traceability.
    #
    # Example:
    #
    # research source
    #       ↓
    # decision
    #       ↓
    # capability
    #       ↓
    # implementation
    #       ↓
    # test
    #       ↓
    # bug
    #       ↓
    # fix
    #
    # source_type and target_type tell us which tables the IDs
    # belong to.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------
    #
    # These make future searches faster as the project history
    # becomes much larger.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_day
        ON events(day)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_type
        ON events(event_type)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_component
        ON events(component)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_version
        ON events(version)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relationship_source
        ON relationships(
            source_type,
            source_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_relationship_target
        ON relationships(
            target_type,
            target_id
        )
        """
    )

    connection.commit()
    connection.close()

    return True


# ============================================================
# EVENT FUNCTIONS
# ============================================================

def add_event(
    event_type,
    description,
    day=None,
    version=None,
    component=None,
    status=None,
    metadata=None,
    source_id=None,
):
    """
    Add a development event to the canonical database.
    """

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
            source_id,

            datetime.now()
            .astimezone()
            .isoformat(),

            day,
            version,
            event_type,
            component,
            description,
            status,

            json.dumps(
                metadata
                if metadata is not None
                else {},
                ensure_ascii=False,
            ),
        ),
    )

    event_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return event_id


def get_events(
    limit=None,
):
    """
    Return events in chronological database order.
    """

    connection = get_connection()

    cursor = connection.cursor()

    query = """
        SELECT *
        FROM events
        ORDER BY id ASC
    """

    parameters = ()

    if limit is not None:

        query += """
        LIMIT ?
        """

        parameters = (
            limit,
        )

    cursor.execute(
        query,
        parameters,
    )

    rows = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return rows


def get_event(
    event_id,
):
    """
    Retrieve one event by database ID.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (
            event_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# ============================================================
# RELATIONSHIP FUNCTIONS
# ============================================================

def add_relationship(
    source_type,
    source_id,
    relation,
    target_type,
    target_id,
):
    """
    Connect two canonical knowledge records.

    Example:

    bug #4
        --fixed_by-->
    event #20
    """

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

    relationship_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return relationship_id


def get_relationships(
    source_type,
    source_id,
):
    """
    Retrieve relationships originating from
    a specific canonical record.
    """

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
            source_type,
            source_id,
        ),
    )

    rows = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return rows


# ============================================================
# DATABASE INFORMATION
# ============================================================

def get_database_info():
    """
    Return basic information about the canonical database.
    """

    connection = get_connection()

    cursor = connection.cursor()

    table_names = [
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

    counts = {}

    for table_name in table_names:

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )

        counts[table_name] = (
            cursor.fetchone()[0]
        )

    connection.close()

    return {
        "database": str(DATABASE_FILE),
        "tables": counts,
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    initialize_database()

    info = get_database_info()

    print(
        "Canonical knowledge database initialized."
    )

    print(
        info["database"]
    )

    print(
        "\nTables:"
    )

    for table_name, count in (
        info["tables"].items()
    ):

        print(
            f"  {table_name}: {count}"
        )