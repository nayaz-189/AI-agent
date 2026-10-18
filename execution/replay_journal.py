"""Explicitly provisioned SQLite replay journal; not authentication or an OS sandbox.

Explicit local bootstrap is separate from opening an existing journal. No default
database is created and no retention/reset API exists. Never store wire payloads.
"""
from contextlib import contextmanager
from hashlib import sha256
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import UUID, uuid4

from execution.safe_failure import ErrorCode


TEST_STORAGE_ROOT = Path(__file__).resolve().parent.parent / "runtime" / "device_tests"
DEVICE_STORAGE_ROOT = Path(__file__).resolve().parent.parent / "runtime" / "device_receiver"
MAX_CAPACITY = 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
SCHEMA_VERSION = 1


class JournalError(RuntimeError):
    def __init__(self):
        super().__init__("Replay journal unavailable; no new dispatch permitted.")


def _identifier(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise JournalError()
    return value


def _peer_key(peer):
    return sha256(_identifier(peer).encode("ascii")).hexdigest()


def _clock(now):
    if type(now) not in (int, float) or not math.isfinite(now) or now <= 0:
        raise JournalError()
    return now


def _checked_path(path):
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.name != "replay.sqlite3"
            or not (path.is_relative_to(TEST_STORAGE_ROOT) or path.parent == DEVICE_STORAGE_ROOT)):
        raise JournalError()
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise JournalError()
    # Reject pre-existing redirection and hardlinks, including SQLite sidecars.
    # This does not defend against a malicious same-user process racing paths.
    for item in (path, *(Path(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm"))):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or getattr(info, "st_file_attributes", 0) & 0x400
                    or info.st_size > MAX_FILE_BYTES):
                raise JournalError()
    return path


_SCHEMA = (
    """CREATE TABLE metadata (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        version INTEGER NOT NULL CHECK(version=1),
        generation TEXT NOT NULL CHECK(length(generation)=32),
        capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 1024))""",
    """CREATE TABLE requests (
        peer_key TEXT NOT NULL CHECK(length(peer_key)=64 AND peer_key NOT GLOB '*[^0-9a-f]*'),
        task_id TEXT NOT NULL CHECK(length(task_id)=36),
        fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64 AND fingerprint NOT GLOB '*[^0-9a-f]*'),
        expires_at INTEGER NOT NULL CHECK(expires_at>0),
        status TEXT NOT NULL CHECK(status IN ('queued','waiting','running','completed','failed')),
        claim_id TEXT CHECK(claim_id IS NULL OR (length(claim_id)=32 AND claim_id NOT GLOB '*[^0-9a-f]*')),
        error_code TEXT CHECK(error_code IS NULL OR error_code IN
            ('precondition_failed','verification_failed','backend_unavailable')),
        PRIMARY KEY(peer_key,task_id),
        CHECK((status IN ('queued','waiting') AND claim_id IS NULL AND error_code IS NULL)
           OR (status IN ('running','completed') AND claim_id IS NOT NULL AND error_code IS NULL)
           OR (status='failed' AND error_code IS NOT NULL))) WITHOUT ROWID""",
    """CREATE TRIGGER immutable_request BEFORE UPDATE OF peer_key,task_id,fingerprint,expires_at
        ON requests BEGIN SELECT RAISE(ABORT,'Immutable request'); END""",
    """CREATE TRIGGER no_request_deletion BEFORE DELETE ON requests
        BEGIN SELECT RAISE(ABORT,'Replay retention required'); END""",
    """CREATE TRIGGER terminal_request BEFORE UPDATE ON requests WHEN OLD.status IN ('completed','failed')
        BEGIN SELECT RAISE(ABORT,'Terminal request'); END""",
    """CREATE TRIGGER forward_state_only BEFORE UPDATE ON requests WHEN NOT
        ((OLD.status='queued' AND NEW.status IN ('running','failed'))
         OR (OLD.status='waiting' AND NEW.status='failed')
         OR (OLD.status='running' AND NEW.status IN ('completed','failed')))
        BEGIN SELECT RAISE(ABORT,'Invalid transition'); END""",
    """CREATE TRIGGER fixed_metadata BEFORE UPDATE ON metadata
        BEGIN SELECT RAISE(ABORT,'Immutable metadata'); END""",
    """CREATE TRIGGER keep_metadata BEFORE DELETE ON metadata
        BEGIN SELECT RAISE(ABORT,'Required metadata'); END""",
)


class ReplayJournal:
    """Trusted local API; paths and limits never come from remote envelopes."""
    def __init__(self, path):
        self._generation = None
        try:
            self.path = _checked_path(path)
            info = self.path.stat()  # Missing journals are NEVER recreated.
            self._file_identity = (info.st_dev, info.st_ino)
            with self._transaction() as connection:
                self._generation = connection.execute("SELECT generation FROM metadata WHERE singleton=1").fetchone()[0]
        except (OSError, ValueError, TypeError, sqlite3.Error, JournalError):
            raise JournalError() from None

    @classmethod
    def create_for_tests(cls, path, *, capacity=128):
        return cls.provision(path, capacity=capacity)

    @classmethod
    def provision(cls, path, *, capacity=128):
        """Explicit first-use provisioning only; refuse any existing database."""
        try:
            if type(capacity) is not int or not 1 <= capacity <= MAX_CAPACITY:
                raise JournalError()
            path = _checked_path(path)
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=0.25)
            try:
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("BEGIN IMMEDIATE")
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("INSERT INTO metadata VALUES (1,?,?,?)", (SCHEMA_VERSION, uuid4().hex, capacity))
                connection.commit()
            finally:
                connection.close()
            return cls(path)
        except (OSError, ValueError, TypeError, sqlite3.Error, JournalError):
            # Leave failed bootstrap artifacts for explicit review, never reset.
            raise JournalError() from None

    @contextmanager
    def _transaction(self):
        connection = None
        try:
            _checked_path(self.path)
            info = self.path.stat()
            if (info.st_dev, info.st_ino) != self._file_identity:
                raise JournalError()
            connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                         isolation_level=None, timeout=0.25)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA synchronous=FULL")
            if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise JournalError()
            connection.execute("PRAGMA max_page_count=2048")
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("PRAGMA quick_check").fetchall()[0][0] != "ok":
                raise JournalError()
            metadata = connection.execute("SELECT * FROM metadata").fetchall()
            if (len(metadata) != 1 or metadata[0]["version"] != SCHEMA_VERSION
                    or not 1 <= metadata[0]["capacity"] <= MAX_CAPACITY
                    or (self._generation is not None and metadata[0]["generation"] != self._generation)):
                raise JournalError()
            yield connection
            connection.commit()  # No claim escapes until this commit succeeds.
        except (OSError, ValueError, TypeError, sqlite3.Error, JournalError):
            raise JournalError() from None
        finally:
            if connection is not None:
                connection.close()  # An unfinished transaction rolls back.

    @staticmethod
    def _receipt(row):
        status = row["status"]
        error = row["error_code"]
        if status == "running":
            # A claim may have produced a side effect before its process died.
            # Never retry or describe this uncertain outcome as verified.
            status, error = "failed", ErrorCode.BACKEND_UNAVAILABLE.value
        if (status not in {"queued", "waiting", "completed", "failed"}
                or error not in {None, "precondition_failed", "verification_failed", "backend_unavailable"}):
            raise JournalError()
        return {"task_id": _identifier(row["task_id"]), "status": status,
                "verified": status == "completed", "error_code": error}

    def accept(self, task, hold, now):
        from execution.device_protocol import DeviceTask
        if (type(task) is not DeviceTask or type(hold) is not bool
                or task.operation != "open_calculator" or task.target_device != "windows"
                or re.fullmatch(r"[0-9a-f]{64}", task.fingerprint) is None
                or not _clock(now) < task.expires_at <= now + 300):
            raise JournalError()
        key = (_peer_key(task.source_device), _identifier(task.task_id))
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM requests WHERE peer_key=? AND task_id=?", key).fetchone()
            if row is not None:
                if row["fingerprint"] != task.fingerprint:
                    return None
                receipt = self._receipt(row)
            else:
                capacity = connection.execute("SELECT capacity FROM metadata").fetchone()[0]
                if connection.execute("SELECT count(*) FROM requests").fetchone()[0] >= capacity:
                    raise JournalError()
                connection.execute("INSERT INTO requests VALUES (?,?,?,?,?,NULL,NULL)",
                                   (*key, task.fingerprint, int(task.expires_at), "waiting" if hold else "queued"))
                receipt = {"task_id": task.task_id, "status": "waiting" if hold else "queued",
                           "verified": False, "error_code": None}
        return receipt

    def claim(self, peer, task_id, fingerprint, now):
        key = (_peer_key(peer), _identifier(task_id))
        claim_id = None
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM requests WHERE peer_key=? AND task_id=?", key).fetchone()
            if row is None or row["fingerprint"] != fingerprint:
                raise JournalError()
            if row["status"] in {"queued", "waiting"} and row["expires_at"] <= _clock(now):
                connection.execute("UPDATE requests SET status='failed',error_code='precondition_failed' WHERE peer_key=? AND task_id=?", key)
            elif row["status"] == "queued":
                claim_id = uuid4().hex
                connection.execute("UPDATE requests SET status='running',claim_id=? WHERE peer_key=? AND task_id=? AND status='queued'", (claim_id, *key))
        return claim_id

    def finish(self, peer, task_id, claim_id, verified):
        if type(verified) is not bool:
            raise JournalError()
        with self._transaction() as connection:
            changed = connection.execute("""UPDATE requests SET status=?,error_code=?
                WHERE peer_key=? AND task_id=? AND status='running' AND claim_id=?""",
                ("completed" if verified else "failed", None if verified else "verification_failed",
                 _peer_key(peer), _identifier(task_id), claim_id)).rowcount
            if changed != 1:
                raise JournalError()

    def receipts(self, peers, now):
        result = []
        with self._transaction() as connection:
            for peer in sorted(peers):
                key = _peer_key(peer)
                connection.execute("""UPDATE requests SET status='failed',error_code='precondition_failed'
                    WHERE peer_key=? AND status IN ('queued','waiting') AND expires_at<=?""", (key, _clock(now)))
                result.extend(self._receipt(row) for row in connection.execute(
                    "SELECT * FROM requests WHERE peer_key=? ORDER BY task_id", (key,)))
        return result
