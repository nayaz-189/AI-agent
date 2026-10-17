"""Mock authenticated transport only; no physical Android/device authentication."""
from datetime import datetime, timezone
import json
from unittest.mock import patch
from uuid import uuid4

from execution.device_protocol import (AuthenticatedTransport, DeviceReceiver, VerifiedDelivery,
                                       VerifiedOutcome, _execute_calculator)


class MockAuthenticatedTransport(AuthenticatedTransport):
    def __init__(self, peer):
        self.peer = peer
        self.body = b""

    def receive_verified(self):
        return VerifiedDelivery(self.peer, self.body)


def fixture():
    now = [1_800_000_000]
    peer = str(uuid4())
    transport = MockAuthenticatedTransport(peer)
    receiver = DeviceReceiver(transport, registered_peers=(peer,), clock=lambda: now[0])
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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"Device protocol: {len(tests)} passed")
