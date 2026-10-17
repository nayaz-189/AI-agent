"""Contract/policy checks only; these do NOT prove OS process isolation."""
import json
from unittest.mock import patch

from execution.runtime import execute_plan, _registered_backend
from skills.capability_broker import preflight_isolated_request
from skills.capability_protocol import BrokerRequest, validate_capability_request

PRIVATE = "SYNTHETIC_PRIVATE_8287"
ENVELOPE = {"version": "2.0", "request_id": "a" * 32, "capability": "open_calculator",
            "resource_id": "b" * 32, "action_digest": "c" * 64}


def test_valid_contract_still_denies_without_authenticated_isolated_worker():
    request = BrokerRequest.parse(ENVELOPE)
    assert request.request_id == ENVELOPE["request_id"]
    with patch("tools.tool_registry.execute_tool") as execute:
        for _ in range(2):  # A replay cannot execute either.
            response = preflight_isolated_request(ENVELOPE).to_dict()
            assert response == {"version": "2.0", "request_id": "a" * 32,
                                "success": False, "executed": False, "verified": False,
                                "error_code": "backend_unavailable"}
    execute.assert_not_called()


def test_contract_rejects_self_asserted_identity_authority_and_payloads():
    for key in ("agent", "caller", "permissions", "confirmed", "confirmation_token",
                "approved_step_id", "arguments", "path", "code", "shell", "screenshot"):
        result = preflight_isolated_request(dict(ENVELOPE, **{key: PRIVATE})).to_dict()
        assert result["error_code"] == "invalid_request"
        assert result["executed"] is False and PRIVATE not in json.dumps(result)
    for key in ENVELOPE:
        bad = dict(ENVELOPE)
        bad[key] = [PRIVATE]
        assert preflight_isolated_request(bad).error_code == "invalid_request"


def test_specialist_private_data_escalations_fail_before_routing():
    attempts = [
        ("research", "read_banking_data", {"account": PRIVATE}),
        ("coding", "read_file", {"path": "C:/synthetic/browser/Passwords"}),
        ("email", "list_files", {"path": "C:/synthetic/user-profile"}),
        ("webpage", "capture_desktop", {"instruction": PRIVATE}),
        ("coding", "run_python", {"code": PRIVATE}),
        ("coding", "run_shell", {"command": PRIVATE}),
        ("research", "export_test_document", {"path": PRIVATE}),
    ]
    with patch("agents.system_agent.handle") as system, patch("agents.browser_agent.handle") as browser:
        for agent, action, arguments in attempts:
            task = execute_plan(PRIVATE, {"tool": action, "arguments": arguments})
            assert task.status.value == "failed" and not task.steps
            assert PRIVATE not in json.dumps(task.to_dict())
            # Agent identity strings are not accepted by the future wire schema.
            assert preflight_isolated_request(dict(ENVELOPE, agent=agent)).error_code == "invalid_request"
    system.assert_not_called()
    browser.assert_not_called()


def test_registered_backend_cannot_route_another_agent_tool():
    with patch("agents.system_agent.handle") as system, patch("agents.browser_agent.handle") as browser:
        assert _registered_backend("browser")("open_calculator", {})["success"] is False
        assert _registered_backend("system")("open_website", {"url": "https://example.com"})["success"] is False
    system.assert_not_called()
    browser.assert_not_called()


def test_legacy_protocol_rejects_private_extra_key_without_echo():
    value = {"protocol_version": "1.0", "type": "capability_request", "capability": "open_website",
             "arguments": {}, PRIVATE: PRIVATE, 1: PRIVATE}
    result = validate_capability_request(value)
    assert result["valid"] is False and PRIVATE not in json.dumps(result)


def main():
    tests = [f for name, f in globals().items() if name.startswith("test_") and callable(f)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Broker contract: {len(tests)}/{len(tests)} passed; OS isolation NOT tested")


if __name__ == "__main__":
    main()
