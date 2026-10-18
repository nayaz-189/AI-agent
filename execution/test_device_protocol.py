"""Mock authenticated transport only; no physical Android/device authentication."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import base64
import json
from pathlib import Path
import sqlite3
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from threading import Barrier, Lock, Thread
from unittest.mock import patch
from uuid import uuid4

from execution.device_protocol import (AuthenticatedTransport, DeviceReceiver, VerifiedDelivery,
                                       VerifiedOutcome, _execute_calculator)
from execution.replay_journal import ReplayJournal, JournalError, TEST_STORAGE_ROOT


class MockAuthenticatedTransport(AuthenticatedTransport):
    def __init__(self, peer):
        self.peer = peer
        self.body = b""

    def receive_verified(self):
        return VerifiedDelivery(self.peer, self.body)

    def authorize_dispatch(self, peer_id):
        return peer_id == self.peer


def fixture(*, capacity=128):
    now = [1_800_000_000]
    peer = str(uuid4())
    transport = MockAuthenticatedTransport(peer)
    TEST_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    directory = tempfile.TemporaryDirectory(prefix="replay_", dir=TEST_STORAGE_ROOT)
    journal = ReplayJournal.create_for_tests(Path(directory.name) / "replay.sqlite3", capacity=capacity)
    receiver = DeviceReceiver(transport, registered_peers=(peer,), clock=lambda: now[0], journal=journal)
    receiver._fixture_directory = directory  # Test-only lifetime/cleanup ownership.
    message = {"protocol_version": 1, "task_id": str(uuid4()), "source_device": peer,
               "target_device": "windows", "operation": "open_calculator", "arguments": {},
               "expires_at": datetime.fromtimestamp(now[0] + 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "requires_approval": False}
    transport.body = json.dumps(message).encode()
    return receiver, transport, message, now


def test_mock_mobile_to_existing_windows_runtime_and_independent_observation():
    receiver, _, _, _ = fixture()
    assert receiver.receive()["status"] == "queued"
    with patch("execution.runtime._registered_backend", return_value=lambda a, b: {"success": True}), \
         patch("desktop.application_observer.observe_calculator", return_value={"calculator_open": True}) as observe:
        result = receiver.dispatch_pending(online=True)[0]
    assert result["status"] == "completed" and result["verified"]
    assert observe.call_count >= 2  # Existing runtime verification plus receipt verification.


def test_default_transport_and_unregistered_or_spoofed_peer_denied():
    assert DeviceReceiver().receive()["status"] == "failed"
    receiver, transport, message, _ = fixture()
    for peer in (str(uuid4()), "windows", "SYNTHETIC_PRIVATE_ID"):
        transport.peer = peer
        assert receiver.receive()["status"] == "failed"
    transport.peer = message["source_device"]
    message["source_device"] = str(uuid4())
    transport.body = json.dumps(message).encode()
    assert receiver.receive()["status"] == "failed" and receiver.history() == []


def test_registered_peer_or_environment_flags_cannot_enable_default_transport():
    import os
    with patch.dict(os.environ, {"VORAK_REMOTE_ENABLED": "1", "AUTHENTICATED": "true",
                                "DURABLE_REPLAY_ENABLED": "true"}), \
         patch("execution.device_protocol._execute_calculator") as execute:
        receiver = DeviceReceiver(registered_peers=(str(uuid4()),))
        assert receiver.receive()["status"] == "failed"
        assert receiver.dispatch_pending(online=True) == []
        assert receiver.history() == []
        execute.assert_not_called()
    try:
        DeviceReceiver({"authenticated": True, "paired": True, "durable_replay": True})
        assert False, "JSON claims must not construct an authenticated transport"
    except TypeError:
        pass


def test_unknown_operations_escalation_private_paths_and_fake_confirmation_denied():
    for operation in ("shell", "read_password", "banking", "payments", "write_test_introduction", "research_and_save_report"):
        receiver, transport, message, _ = fixture()
        message["operation"] = operation
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed"
    for key in ("path", "url", "command", "agent", "confirmation_token", "approved_step_id"):
        receiver, transport, message, _ = fixture()
        message["arguments"] = {key: "SYNTHETIC_PRIVATE"}
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed" and receiver.history() == []


def test_extra_fields_duplicate_json_wrong_types_and_oversized_request_denied():
    for update in ({"authenticated": True}, {"agent": "windows"}, {"protocol_version": True},
                   {"requires_approval": "false"}, {"arguments": []}, {"target_device": "banking"}):
        receiver, transport, message, _ = fixture()
        message.update(update)
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed"
    receiver, transport, _, _ = fixture()
    for body in (b"x" * 8193, b'{"task_id": "a", "task_id": "b"}', b"null", b"\xff"):
        transport.body = body
        assert receiver.receive()["status"] == "failed"


def test_replay_completed_duplicate_and_changed_payload_never_execute_twice():
    receiver, transport, message, _ = fixture()
    receiver.receive()
    with patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(True)) as execute:
        first = receiver.dispatch_pending(online=True)[0]
        assert receiver.receive() == first
        receiver.dispatch_pending(online=True)
        message["requires_approval"] = True
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed"
        execute.assert_called_once()


def test_offline_queue_and_expiry_do_not_execute():
    receiver, _, _, now = fixture()
    receiver.receive()
    with patch("execution.device_protocol._execute_calculator") as execute:
        assert receiver.dispatch_pending()[0]["status"] == "queued"
        now[0] += 61
        assert receiver.dispatch_pending(online=True)[0]["status"] == "failed"
        assert receiver.receive()["status"] == "failed"
        execute.assert_not_called()


def test_approval_true_waits_and_cannot_be_released_by_message():
    receiver, transport, message, _ = fixture()
    message["requires_approval"] = True
    transport.body = json.dumps(message).encode()
    assert receiver.receive()["status"] == "waiting"
    with patch("execution.device_protocol._execute_calculator") as execute:
        assert receiver.dispatch_pending(online=True)[0]["status"] == "waiting"
        message["requires_approval"] = False
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed"
        execute.assert_not_called()


def test_failed_or_malicious_results_are_sanitized_and_not_retried():
    for result in ({"success": True}, VerifiedOutcome(False), VerifiedOutcome("yes")):
        receiver, _, _, _ = fixture()
        receiver.receive()
        with patch("execution.device_protocol._execute_calculator", return_value=result) as execute:
            assert receiver.dispatch_pending(online=True)[0]["status"] == "failed"
            receiver.dispatch_pending(online=True)
            execute.assert_called_once()
    receiver, _, _, _ = fixture()
    receiver.receive()
    with patch("execution.device_protocol._execute_calculator", side_effect=OSError("SYNTHETIC_SECRET")):
        receiver.dispatch_pending(online=True)
    assert "SYNTHETIC_SECRET" not in json.dumps(receiver.history())


def test_false_independent_observation_overrides_success():
    with patch("execution.runtime._registered_backend", return_value=lambda a, b: {"success": True}), \
         patch("desktop.application_observer.observe_calculator", return_value={"calculator_open": False}):
        assert _execute_calculator().verified is False


def test_android_and_excessive_lifetime_unavailable():
    for update in ({"target_device": "android"}, {"expires_at": "2999-01-01T00:00:00Z"}):
        receiver, transport, message, _ = fixture()
        message.update(update)
        transport.body = json.dumps(message).encode()
        assert receiver.receive()["status"] == "failed" and receiver.history() == []


def reopen(receiver, transport, now):
    return DeviceReceiver(transport, registered_peers=(transport.peer,), clock=lambda: now[0],
                          journal=ReplayJournal(receiver._journal.path))


def test_claim_is_durably_committed_before_dispatch():
    receiver, _, _, _ = fixture()
    assert receiver.receive()["status"] == "queued"

    def observe_committed_claim():
        with closing(sqlite3.connect(receiver._journal.path)) as connection:
            status, claim = connection.execute("SELECT status,claim_id FROM requests").fetchone()
        assert status == "running" and len(claim) == 32
        return VerifiedOutcome(True)

    with patch("execution.device_protocol._execute_calculator", side_effect=observe_committed_claim) as execute:
        assert receiver.dispatch_pending(online=True)[0]["verified"] is True
        execute.assert_called_once()


# A fresh interpreter reads the same on-disk journal. All dispatch in this child
# is mocked; even the simulated crash cannot launch a Windows application.
_CHILD = """
import json, os, sys
from unittest.mock import patch
from execution.device_protocol import DeviceReceiver, VerifiedOutcome
from execution.test_device_protocol import MockAuthenticatedTransport
from execution.replay_journal import ReplayJournal
path, peer, body, clock, mode = sys.argv[1:]
transport = MockAuthenticatedTransport(peer)
transport.body = body.encode()
receiver = DeviceReceiver(transport, registered_peers=(peer,),
                          clock=lambda: float(clock), journal=ReplayJournal(path))
receipt = receiver.receive()
def backend():
    if mode == 'crash':
        os._exit(73)
    raise AssertionError('A replay must not dispatch')
with patch('execution.device_protocol._execute_calculator', side_effect=backend) as execute:
    results = receiver.dispatch_pending(online=True)
    assert execute.call_count == 0
print(json.dumps({'receipt': receipt, 'results': results}))
"""


def child(receiver, transport, now, mode="replay"):
    return subprocess.run([sys.executable, "-c", _CHILD, str(receiver._journal.path), transport.peer,
                           transport.body.decode(), str(now[0]), mode],
                          cwd=Path(__file__).resolve().parent.parent,
                          capture_output=True, text=True, timeout=20)


def test_terminal_replay_in_new_process_and_altered_request_rejected():
    for verified in (True, False):
        receiver, transport, message, now = fixture()
        receiver.receive()
        with patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(verified)):
            original = receiver.dispatch_pending(online=True)[0]
        process = child(receiver, transport, now)
        assert process.returncode == 0, process.stderr
        result = json.loads(process.stdout)
        assert result["receipt"] == original and result["results"] == [original]
        restarted = reopen(receiver, transport, now)
        message["requires_approval"] = True
        transport.body = json.dumps(message).encode()
        assert restarted.receive()["status"] == "failed"
        assert restarted.history() == [original]


def test_process_death_after_claim_never_reexecutes_or_claims_verification():
    receiver, transport, _, now = fixture()
    process = child(receiver, transport, now, "crash")
    assert process.returncode == 73, process.stderr
    restarted = reopen(receiver, transport, now)
    with patch("execution.device_protocol._execute_calculator") as execute:
        receipt = restarted.receive()
        assert receipt["status"] == "failed" and receipt["verified"] is False
        assert receipt["error_code"] == "backend_unavailable"
        assert restarted.dispatch_pending(online=True) == [receipt]
        execute.assert_not_called()
    process = child(receiver, transport, now)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["receipt"] == receipt
    with closing(sqlite3.connect(receiver._journal.path)) as connection:
        assert connection.execute("SELECT status FROM requests").fetchone()[0] == "running"


def test_simultaneous_receivers_claim_once():
    receiver, transport, _, now = fixture()
    other = reopen(receiver, transport, now)
    receiver.receive()
    other.receive()
    barrier, lock, calls = Barrier(2), Lock(), []

    def backend():
        with lock:
            calls.append(True)
        return VerifiedOutcome(True)

    def dispatch(instance):
        barrier.wait(timeout=5)
        return instance.dispatch_pending(online=True)

    with patch("execution.device_protocol._execute_calculator", side_effect=backend):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(dispatch, (receiver, other)))
    assert len(calls) == 1
    assert all(result and result[0]["status"] in {"completed", "failed"} for result in results)
    assert reopen(receiver, transport, now).history()[0]["verified"] is True


def test_persisted_queue_requires_authenticated_redelivery():
    receiver, transport, _, now = fixture()
    receiver.receive()
    offline = DeviceReceiver(registered_peers=(transport.peer,), clock=lambda: now[0],
                             journal=ReplayJournal(receiver._journal.path))
    with patch("execution.device_protocol._execute_calculator") as execute:
        assert offline.receive()["status"] == "failed"
        assert offline.dispatch_pending(online=True)[0]["status"] == "queued"
        execute.assert_not_called()
    restarted = reopen(receiver, transport, now)
    assert restarted.receive()["status"] == "queued"
    with patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(True)) as execute:
        assert restarted.dispatch_pending(online=True)[0]["verified"] is True
        execute.assert_called_once()


def test_expiry_and_approval_hold_survive_restart():
    for hold in (False, True):
        receiver, transport, message, now = fixture()
        message["requires_approval"] = hold
        transport.body = json.dumps(message).encode()
        receiver.receive()
        restarted = reopen(receiver, transport, now)
        restarted.receive()
        with patch("execution.device_protocol._execute_calculator") as execute:
            if hold:
                assert restarted.dispatch_pending(online=True)[0]["status"] == "waiting"
                message["requires_approval"] = False
                transport.body = json.dumps(message).encode()
                assert restarted.receive()["status"] == "failed"
            now[0] += 61
            result = restarted.dispatch_pending(online=True)[0]
            assert result["status"] == "failed" and not result["verified"]
            assert result["error_code"] == "precondition_failed"
            execute.assert_not_called()


def test_database_lock_and_connection_error_fail_closed():
    receiver, _, _, _ = fixture()
    receiver.receive()
    connection = sqlite3.connect(receiver._journal.path, isolation_level=None)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        with patch("execution.device_protocol._execute_calculator") as execute:
            receipt = receiver.dispatch_pending(online=True)[0]
            assert receipt["error_code"] == "backend_unavailable" and not receipt["verified"]
            execute.assert_not_called()
    finally:
        connection.close()
    receiver, _, _, _ = fixture()
    with patch("execution.replay_journal.sqlite3.connect", side_effect=sqlite3.OperationalError("SYNTHETIC_SECRET")), \
         patch("execution.device_protocol._execute_calculator") as execute:
        assert receiver.receive()["error_code"] == "backend_unavailable"
        assert receiver.dispatch_pending(online=True)[0]["verified"] is False
        assert "SYNTHETIC_SECRET" not in json.dumps(receiver.history())
        execute.assert_not_called()


def test_claim_and_completion_commit_failures_never_return_success():
    real_connect = sqlite3.connect
    for failure_number in (1, 2):
        receiver, transport, _, now = fixture()
        receiver.receive()
        commits = []

        class FailingCommit(sqlite3.Connection):
            def commit(self):
                commits.append(True)
                if len(commits) == failure_number:
                    raise sqlite3.OperationalError("SYNTHETIC_DISK_FAILURE")
                return super().commit()

        def connect(*args, **kwargs):
            return real_connect(*args, **kwargs, factory=FailingCommit)

        with patch("execution.replay_journal.sqlite3.connect", side_effect=connect), \
             patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(True)) as execute:
            result = receiver.dispatch_pending(online=True)[0]
            assert not result["verified"] and result["error_code"] == "backend_unavailable"
            assert execute.call_count == failure_number - 1
        restarted = reopen(receiver, transport, now)
        receipt = restarted.receive()
        if failure_number == 1:
            assert receipt["status"] == "queued"  # No claim committed and no OS dispatch.
        else:
            assert receipt["status"] == "failed" and not receipt["verified"]
            with patch("execution.device_protocol._execute_calculator") as execute:
                restarted.dispatch_pending(online=True)
                execute.assert_not_called()


def test_corrupt_missing_and_uninitialized_storage_never_recreated():
    for damage in ("corrupt", "missing", "empty"):
        receiver, _, _, _ = fixture()
        receiver.receive()
        path = receiver._journal.path
        # These are newly created synthetic temporary fixtures only.
        if damage == "missing":
            path.unlink()
        else:
            path.write_bytes(b"not a database" if damage == "corrupt" else b"")
        with patch("execution.device_protocol._execute_calculator") as execute:
            assert receiver.dispatch_pending(online=True)[0]["verified"] is False
            execute.assert_not_called()
        try:
            ReplayJournal(path)
            assert False, "Damaged storage must not be replaced or initialized"
        except JournalError:
            pass
        if damage == "missing":
            assert not path.exists()


def test_capacity_retains_expired_identity_and_fails_closed():
    receiver, transport, message, now = fixture(capacity=1)
    receiver.receive()
    now[0] += 61
    assert receiver.history()[0]["status"] == "failed"
    message["task_id"] = str(uuid4())
    message["expires_at"] = datetime.fromtimestamp(now[0] + 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    transport.body = json.dumps(message).encode()
    with patch("execution.device_protocol._execute_calculator") as execute:
        assert receiver.receive()["error_code"] == "backend_unavailable"
        assert receiver.dispatch_pending(online=True)[0]["verified"] is False
        execute.assert_not_called()
    with closing(sqlite3.connect(receiver._journal.path)) as connection:
        assert connection.execute("SELECT count(*) FROM requests").fetchone()[0] == 1
    restarted = reopen(receiver, transport, now)
    retained = restarted.history()[0]
    message["task_id"] = retained["task_id"]
    transport.body = json.dumps(message).encode()
    assert restarted.receive()["error_code"] == "permission_denied"  # Changed expiry is altered reuse.
    assert restarted.history() == [retained]


def test_journal_binding_terminal_states_and_retention_are_immutable():
    receiver, _, _, _ = fixture()
    receiver.receive()
    with patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(True)):
        original = receiver.dispatch_pending(online=True)
    for sql in ("DELETE FROM requests", "UPDATE requests SET status='queued',claim_id=NULL",
                "UPDATE requests SET fingerprint='" + "0" * 64 + "'",
                "UPDATE metadata SET capacity=1024", "DELETE FROM metadata"):
        with closing(sqlite3.connect(receiver._journal.path)) as connection:
            try:
                connection.execute(sql)
                assert False, "Replay retention and bindings must not be mutable"
            except sqlite3.IntegrityError:
                pass
    assert receiver.history() == original
    try:
        ReplayJournal.create_for_tests(receiver._journal.path)
        assert False, "Bootstrap must never overwrite an existing journal"
    except JournalError:
        pass


def test_persistence_and_receipts_exclude_private_payloads_and_peer_identity():
    receiver, transport, message, _ = fixture()
    for key in ("credentials", "password", "private_text", "approved"):
        invalid = dict(message, **{key: "SYNTHETIC_PRIVATE_CREDENTIAL"})
        transport.body = json.dumps(invalid).encode()
        assert receiver.receive()["status"] == "failed"
    transport.body = json.dumps(message).encode()
    receiver.receive()
    with patch("execution.device_protocol._execute_calculator", side_effect=OSError("SYNTHETIC_PRIVATE_CREDENTIAL")):
        receiver.dispatch_pending(online=True)
    raw = receiver._journal.path.read_bytes()
    receipts = json.dumps(receiver.history()).encode()
    for forbidden in (b"SYNTHETIC_PRIVATE_CREDENTIAL", transport.peer.encode(), transport.body,
                      b"requires_approval", b"open_calculator", b"arguments"):
        assert forbidden not in raw and forbidden not in receipts
    with closing(sqlite3.connect(receiver._journal.path)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(requests)")}
    assert columns == {"peer_key", "task_id", "fingerprint", "expires_at", "status", "claim_id", "error_code"}


def test_storage_path_and_absent_journal_cannot_enable_execution():
    receiver, transport, _, now = fixture()
    for path in (Path("replay.sqlite3"), TEST_STORAGE_ROOT.parent / "replay.sqlite3",
                 receiver._journal.path.parent / ".." / "replay.sqlite3",
                 receiver._journal.path.with_name("other.sqlite3")):
        try:
            ReplayJournal(path)
            assert False, "Only the confined explicit journal location is permitted"
        except JournalError:
            pass
    no_journal = DeviceReceiver(transport, registered_peers=(transport.peer,), clock=lambda: now[0])
    with patch("execution.device_protocol._execute_calculator") as execute:
        assert no_journal.receive()["error_code"] == "backend_unavailable"
        assert no_journal.dispatch_pending(online=True) == []
        execute.assert_not_called()


@contextmanager
def paired_fixture():
    from execution.device_server import initialize, PairingStore
    TEST_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tls_", dir=TEST_STORAGE_ROOT) as temporary:
        directory = Path(temporary) / "private"
        initialize(directory)
        openssl = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        assert Path(openssl).is_file(), "OpenSSL is required only to generate disposable TLS test certificates"
        result = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes",
                                 "-days", "1", "-subj", "/CN=vorak-loopback-test",
                                 "-keyout", str(directory / "server.key"),
                                 "-out", str(directory / "server.pem")],
                                capture_output=True, timeout=20)
        assert result.returncode == 0, "Temporary TLS certificate generation failed"
        import os
        if os.name != "nt":
            (directory / "server.pem").chmod(0o600)
        store = PairingStore(directory)
        public = store.pair("127.0.0.1", 8765)
        profile = store.load()
        assert set(public) == {"peer_id", "cert_sha256"} and profile["secret"] not in json.dumps(public)
        yield store, ReplayJournal(directory / "replay.sqlite3"), profile


@contextmanager
def tls_listener(store, journal):
    from execution.device_server import create_listener, server_context, handle_connection
    context = server_context(store)
    listener = create_listener(port=0)
    listener.settimeout(5)
    results = []

    def serve_one():
        try:
            raw, _ = listener.accept()
            results.append(handle_connection(raw, context, store, journal))
        except OSError:
            results.append(False)

    thread = Thread(target=serve_one, daemon=True)
    thread.start()
    try:
        yield dict(store.load(), port=listener.getsockname()[1]), results
    finally:
        thread.join(timeout=12)
        listener.close()
        assert not thread.is_alive(), "Bounded TLS test handler must terminate"


def test_tls_pairing_verified_receipt_and_restart_replay():
    from execution.device_client import calculator_request, exchange
    with paired_fixture() as (store, journal, profile):
        body = calculator_request(profile["peer_id"])
        with patch("execution.device_protocol._execute_calculator", return_value=VerifiedOutcome(True)) as execute:
            with tls_listener(store, journal) as (client, results):
                first = exchange(client, body)
                assert first["verified"] and first["status"] == "completed"
            assert results == [True]
            # New receiver and SQLite object, new TLS connection, same identity.
            with tls_listener(store, ReplayJournal(journal.path)) as (client, results):
                assert exchange(client, body) == first
            assert results == [True]
            execute.assert_called_once()


def test_tls_wrong_certificate_pin_rejected_before_dispatch():
    from execution.device_client import calculator_request, exchange, ProtocolError
    with paired_fixture() as (store, journal, profile):
        with patch("execution.device_protocol._execute_calculator") as execute:
            with tls_listener(store, journal) as (client, results):
                client["cert_sha256"] = "0" * 64
                try:
                    exchange(client, calculator_request(profile["peer_id"]))
                    assert False, "Untrusted endpoint must not receive a request"
                except ProtocolError:
                    pass
            assert results == [False] and journal.receipts((profile["peer_id"],), __import__("time").time()) == []
            execute.assert_not_called()


def test_unpaired_and_modified_authenticated_requests_rejected():
    from execution.device_client import calculator_request, request_packet, ProtocolError
    from execution.device_server import process_packet
    with paired_fixture() as (store, journal, profile):
        body = calculator_request(profile["peer_id"])
        bad_secret = request_packet(dict(profile, secret="0" * 64), body)
        unknown_peer = request_packet(dict(profile, peer_id=str(uuid4())), body)
        altered = json.loads(request_packet(profile, body))
        altered["payload"]["body"] = base64.b64encode(body.replace(b"open_calculator", b"arbitrary_shell")).decode()
        fake = json.dumps({"authenticated": True, "paired": True, "approved": True}).encode()
        with patch("execution.device_protocol._execute_calculator") as execute:
            for packet in (bad_secret, unknown_peer, json.dumps(altered).encode(), fake):
                try:
                    process_packet(store, journal, packet)
                    assert False, "Authentication must bind the complete request and registered peer"
                except ProtocolError:
                    pass
            execute.assert_not_called()


def test_signed_invalid_operations_arguments_and_approval_do_not_authorize():
    from execution.device_client import calculator_request, request_packet, verify_response
    from execution.device_server import process_packet
    with paired_fixture() as (store, journal, profile):
        for change in ({"operation": "shell"}, {"arguments": {"path": "SYNTHETIC_PRIVATE"}},
                       {"approved": True}, {"source_device": str(uuid4())}, {"requires_approval": True},
                       {"expires_at": "2000-01-01T00:00:00Z"}):
            body = json.loads(calculator_request(profile["peer_id"]))
            body.update(change)
            packet = request_packet(profile, json.dumps(body).encode())
            with patch("execution.device_protocol._execute_calculator") as execute:
                receipt = verify_response(profile, packet, process_packet(store, journal, packet), body["task_id"])
                assert not receipt["verified"] and receipt["status"] in {"waiting", "failed"}
                execute.assert_not_called()


def test_revocation_survives_restart_and_blocks_already_prepared_dispatch():
    from execution.device_client import calculator_request, request_packet, ProtocolError
    from execution.device_server import PairedTransport, PairingStore, process_packet
    with paired_fixture() as (store, journal, profile):
        packet = request_packet(profile, calculator_request(profile["peer_id"]))
        transport = PairedTransport(store, packet)
        receiver = DeviceReceiver(transport, registered_peers=(profile["peer_id"],), journal=journal)
        assert receiver.receive()["status"] == "queued"
        store.revoke()
        with patch("execution.device_protocol._execute_calculator") as execute:
            receipt = receiver.dispatch_pending(online=True)[0]
            assert receipt["status"] == "failed" and not receipt["verified"]
            try:
                process_packet(PairingStore(store.directory), ReplayJournal(journal.path), packet)
                assert False, "Revoked pairing must remain revoked after restart"
            except ProtocolError:
                pass
            execute.assert_not_called()


def test_authenticated_failed_receipts_and_database_failure():
    from execution.device_client import calculator_request, request_packet, verify_response
    from execution.device_server import process_packet
    with paired_fixture() as (store, journal, profile):
        body = calculator_request(profile["peer_id"])
        packet = request_packet(profile, body)
        task_id = json.loads(body)["task_id"]
        with patch("execution.device_protocol._execute_calculator", side_effect=OSError("SYNTHETIC_PRIVATE_ERROR")) as execute:
            receipt = verify_response(profile, packet, process_packet(store, journal, packet), task_id)
            assert receipt["status"] == "failed" and not receipt["verified"]
            assert verify_response(profile, packet, process_packet(store, journal, packet), task_id) == receipt
            execute.assert_called_once()
        assert "SYNTHETIC_PRIVATE_ERROR" not in json.dumps(receipt)
        body = calculator_request(profile["peer_id"])
        packet = request_packet(profile, body)
        with patch("execution.replay_journal.sqlite3.connect", side_effect=sqlite3.OperationalError("PRIVATE_DB")), \
             patch("execution.device_protocol._execute_calculator") as execute:
            receipt = verify_response(profile, packet, process_packet(store, journal, packet), json.loads(body)["task_id"])
            assert receipt["error_code"] == "backend_unavailable" and not receipt["verified"]
            execute.assert_not_called()


def test_response_authentication_binding_and_success_shape_are_strict():
    from execution.device_client import (calculator_request, request_packet, signed, hex_key,
                                         RESPONSE_DOMAIN, verify_response, ProtocolError)
    import hashlib
    with paired_fixture() as (_, _, profile):
        body = calculator_request(profile["peer_id"])
        task_id = json.loads(body)["task_id"]
        packet = request_packet(profile, body)
        good = {"request_hash": hashlib.sha256(packet).hexdigest(),
                "receipt": {"task_id": task_id, "status": "completed", "verified": True, "error_code": None}}
        response = signed(good, hex_key(profile["secret"]), RESPONSE_DOMAIN)
        changed = json.loads(response)
        changed["payload"]["receipt"]["verified"] = False
        bad_shape = dict(good, receipt=dict(good["receipt"], verified=False))
        bad_id = dict(good, receipt=dict(good["receipt"], task_id=str(uuid4())))
        for raw, request in ((json.dumps(changed).encode(), packet),
                             (response, request_packet(profile, body)),
                             (signed(bad_shape, hex_key(profile["secret"]), RESPONSE_DOMAIN), packet),
                             (signed(bad_id, hex_key(profile["secret"]), RESPONSE_DOMAIN), packet),
                             (b'{"success":true}', packet)):
            try:
                verify_response(profile, request, raw, task_id)
                assert False, "Neither stale receipts nor an HTTP-style success can prove verification"
            except ProtocolError:
                pass


def test_network_default_off_and_lan_requires_explicit_private_address():
    import importlib
    from execution import device_server
    with patch("socket.socket") as create:
        importlib.reload(device_server)
        assert DeviceReceiver().receive()["status"] == "failed"
        for address, allow in (("0.0.0.0", True), ("8.8.8.8", True), ("localhost", True),
                               ("192.168.1.10", False), ("127.0.0.2", True)):
            try:
                device_server.create_listener(address, allow_lan=allow)
                assert False, "Public, wildcard, DNS and implicit LAN binding must fail before socket creation"
            except ValueError:
                pass
            except RuntimeError:
                pass
        create.assert_not_called()


def test_private_storage_rejects_redirection_and_existing_pairing_overwrite():
    from execution.device_storage import private_read, private_create, StorageError
    from execution.device_server import initialize
    from execution.device_client import ProtocolError
    with paired_fixture() as (store, _, profile):
        try:
            store.pair("127.0.0.1", 8765)
            assert False, "Existing pairing must not be silently replaced"
        except FileExistsError:
            pass
        try:
            initialize(store.directory)
            assert False, "Initialization must never reset existing device state"
        except ProtocolError:
            pass
        for name in ("../pairing.json", "nested/file", str(store.directory / "pairing.json")):
            try:
                private_read(store.directory, name)
                assert False, "Private store paths must be fixed basenames"
            except StorageError:
                pass
        import os
        private_create(store.directory, "synthetic", b"test")
        os.link(store.directory / "synthetic", store.directory / "hardlink")
        try:
            private_read(store.directory, "hardlink")
            assert False, "Hardlinked credential input must be denied"
        except StorageError:
            pass
        assert store.load() == profile


def test_tls_rejects_plaintext_and_oversized_frames():
    import struct
    from execution.device_client import MAX_FRAME
    with paired_fixture() as (store, journal, _):
        with patch("execution.device_protocol._execute_calculator") as execute:
            with tls_listener(store, journal) as (client, results):
                with socket.create_connection((client["host"], client["port"]), timeout=3) as connection:
                    connection.sendall(b"GET / HTTP/1.1\r\n\r\n")
            assert results == [False]
            with tls_listener(store, journal) as (client, results):
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE  # Test attack client sends no secret/request.
                with socket.create_connection((client["host"], client["port"]), timeout=3) as raw:
                    with context.wrap_socket(raw, server_hostname="127.0.0.1") as connection:
                        connection.sendall(struct.pack("!I", MAX_FRAME + 1))
            assert results == [False]
            execute.assert_not_called()


def test_client_retains_exact_request_after_uncertain_failure_without_auto_retry():
    from execution import device_client
    from execution.device_storage import private_directory, private_create, private_read
    from contextlib import redirect_stdout
    import io
    with paired_fixture() as (store, _, profile):
        home = store.directory
        directory = private_directory(home / ".vorak-device", create=True)
        private_create(directory, "pairing.json", device_client.canonical(profile))
        output = io.StringIO()
        with patch.object(Path, "home", return_value=home), redirect_stdout(output), \
             patch.object(device_client, "exchange", side_effect=TimeoutError("SYNTHETIC_PRIVATE_TIMEOUT")) as exchange:
            assert device_client.main(["open-calculator"]) == 1
            assert exchange.call_count == 1
            original = private_read(directory, "pending.json")
            assert device_client.main(["open-calculator"]) == 1
            assert exchange.call_count == 2  # Only the second explicit command retries.
            assert all(call.args[1] == original for call in exchange.call_args_list)
            assert private_read(directory, "pending.json") == original
        assert "SYNTHETIC_PRIVATE_TIMEOUT" not in output.getvalue()
        assert profile["secret"] not in output.getvalue()
        assert json.loads(original)["operation"] == "open_calculator"


def test_revocation_after_claim_blocks_os_action():
    from execution.device_client import calculator_request, request_packet, verify_response
    from execution.device_server import process_packet
    with paired_fixture() as (store, journal, profile):
        body = calculator_request(profile["peer_id"])
        packet = request_packet(profile, body)
        claim = journal.claim

        def revoke_after_claim(*args):
            result = claim(*args)
            store.revoke()
            return result

        with patch.object(journal, "claim", side_effect=revoke_after_claim), \
             patch("execution.device_protocol._execute_calculator") as execute:
            receipt = verify_response(profile, packet, process_packet(store, journal, packet), json.loads(body)["task_id"])
            assert receipt["status"] == "failed" and receipt["verified"] is False
            execute.assert_not_called()


def test_frame_has_absolute_deadline_and_client_rejects_public_destination():
    from unittest.mock import Mock
    from execution.device_client import receive_frame, ProtocolError, exchange, calculator_request
    import struct
    connection = Mock()
    connection.recv.return_value = struct.pack("!I", 4)
    with patch("execution.device_client.time.monotonic", side_effect=(0, 1, 9)):
        try:
            receive_frame(connection)
            assert False, "Partial frame traffic cannot reset the total deadline"
        except ProtocolError:
            pass
    with paired_fixture() as (_, _, profile):
        with patch("socket.create_connection") as connect:
            try:
                exchange(dict(profile, host="8.8.8.8"), calculator_request(profile["peer_id"]))
                assert False, "Client must not connect to a public destination"
            except ProtocolError:
                pass
            connect.assert_not_called()


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"Device protocol: {len(tests)} passed")
