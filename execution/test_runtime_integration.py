"""Run with .venv\Scripts\python.exe -m execution.test_runtime_integration.

Plain assertions match the existing suite; mocks prevent real OS mutations.
"""

from unittest.mock import patch

from desktop.consequence_policy import PolicyDecision, make_policy_result
from execution.execution_history import ExecutionHistory
from execution.execution_router import ExecutionRouter
from execution.runtime import execute_command, execute_plan
from tools.tool_registry import TOOLS, execute_tool


PLAN = {"tool": "open_calculator", "arguments": {}}
OBSERVATION = {"calculator_open": True, "window_handle": 42, "process_id": 123}


def test_successful_routed_execution():
    history = ExecutionHistory()
    with patch("tools.system_tools._open_calculator", return_value=True) as launch, \
         patch("desktop.application_observer.observe_calculator", return_value=OBSERVATION), \
         patch.object(ExecutionRouter, "route", autospec=True,
                      side_effect=ExecutionRouter.route) as route:
        task = execute_command("Open Calculator", history=history)
    assert task.status.value == "completed"
    launch.assert_called_once_with()
    assert route.call_args.kwargs == {
        "agent": "system", "action": "open_calculator", "arguments": {},
    }
    events = history.events_for_task(task.task_id)
    names = [event["event_type"] for event in events]
    assert names.index("state_observed") < names.index("postconditions_passed")
    assert names.index("postconditions_passed") < names.index("task_completed")
    assert next(e["details"] for e in events if e["event_type"] == "state_observed") == OBSERVATION


def test_unknown_tool_rejected():
    with patch("agents.system_agent.handle") as handle:
        task = execute_plan("test", {"tool": "run_python", "arguments": {}})
    assert task.status.value == "failed" and not task.steps
    handle.assert_not_called()


def test_invalid_arguments_rejected():
    plans = [
        {"tool": "open_calculator", "arguments": {"command": "calc.exe"}},
        {"tool": "open_calculator", "arguments": []},
        {"tool": "open_website", "arguments": {"url": 42}},
        {"tool": "open_website", "arguments": {"url": "file:///C:/bad.exe"}},
        {"tool": "open_website", "arguments": {"url": "javascript:alert(1)"}},
        {"tool": "resolve_application", "arguments": {"target": ""}},
    ]
    with patch("agents.system_agent.handle") as system, \
         patch("agents.browser_agent.handle") as browser:
        for plan in plans:
            assert execute_plan("test", plan).status.value == "failed"
    system.assert_not_called()
    browser.assert_not_called()


def test_unregistered_launch_target_rejected():
    with patch("brain.application_resolver.get_application_index", return_value={}), \
         patch("tools.system_tools._launch_application") as launch:
        task = execute_plan("test", {"tool": "launch_application", "arguments": {
            "launch_type": "shortcut", "launch_target": "C:\\bad.exe",
        }})
    assert task.status.value == "failed"
    launch.assert_not_called()


def test_failed_tool_execution():
    for outcome in (False, None, {"success": False}, {"success": True}, "true", 1):
        with patch.dict(TOOLS["open_calculator"], {"function": lambda: outcome}), \
             patch("desktop.application_observer.observe_calculator") as observe:
            task = execute_plan("test", PLAN)
        assert task.status.value == "failed", outcome
        observe.assert_not_called()


def test_tool_exception_fails_closed():
    with patch("tools.system_tools._open_calculator", side_effect=OSError("denied")), \
         patch("desktop.application_observer.observe_calculator") as observe:
        task = execute_plan("test", PLAN)
    assert task.status.value == "failed"
    observe.assert_not_called()


def test_failed_real_world_verification():
    history = ExecutionHistory()
    with patch("tools.system_tools._open_calculator", return_value=True), \
         patch("desktop.application_observer.observe_calculator", return_value={"calculator_open": False}):
        task = execute_plan("test", PLAN, history=history)
    assert task.status.value == "failed"
    assert "verification" in task.error
    names = [e["event_type"] for e in history.all_events()]
    assert "postconditions_failed" in names and "task_completed" not in names


def test_observation_exception_fails_closed():
    with patch("tools.system_tools._open_calculator", return_value=True), \
         patch("desktop.application_observer.observe_calculator", side_effect=RuntimeError("unavailable")):
        task = execute_plan("test", PLAN)
    assert task.status.value == "failed" and "observation failed" in task.error


def test_policy_permission_and_confirmation_blocking():
    for decision in (PolicyDecision.DENY, PolicyDecision.UNKNOWN, PolicyDecision.CONFIRM):
        policy = make_policy_result(decision, reason="test policy", consequence="test")
        with patch("desktop.consequence_policy.ConsequencePolicy.evaluate", return_value=policy), \
             patch("desktop.action_gate.DesktopActionGate.execute") as technical, \
             patch("tools.system_tools._open_calculator") as launch:
            task = execute_plan("test", PLAN)
        assert task.status.value == "failed"
        technical.assert_not_called()
        launch.assert_not_called()


def test_technical_gate_blocks_execution():
    with patch("desktop.action_gate.DesktopActionGate.validate_request", return_value={
        "valid": False, "errors": ["blocked"],
    }), patch("tools.system_tools._open_calculator") as launch:
        task = execute_plan("test", PLAN)
    assert task.status.value == "failed"
    launch.assert_not_called()


def test_planner_cannot_supply_authorization():
    for field in ("requires_confirmation", "confirmed", "approved_step_id", "confirmation_token"):
        with patch("tools.system_tools._open_calculator") as launch:
            task = execute_plan("test", dict(PLAN, **{field: True}))
        assert task.status.value == "failed" and not task.steps
        launch.assert_not_called()


def test_registry_risk_requires_confirmation():
    with patch.dict(TOOLS["open_calculator"], {"risk": "high"}), \
         patch("tools.system_tools._open_calculator") as launch:
        task = execute_plan("test", PLAN)
        assert execute_tool("open_calculator", {}) is False
    assert task.status.value == "waiting_for_user"
    launch.assert_not_called()


def test_browser_compatibility_and_false_result():
    # Exercise the legacy boolean contract under simulated trusted policy.
    # Production browser tools require confirmation (tested separately).
    for success in (True, False):
        with patch.dict(TOOLS["open_website"], {"risk": "low"}), \
             patch("tools.system_tools.webbrowser.open", return_value=success) as browser:
            task = execute_plan("Open website", {
                "tool": "open_website", "arguments": {"url": "https://example.com"},
            })
        assert task.status.value == ("completed" if success else "failed")
        browser.assert_called_once_with("https://example.com")


def test_generic_calculator_launch_requires_observation():
    arguments = {"launch_type": "app_id", "launch_target": "Microsoft.WindowsCalculator_test!App"}
    with patch("brain.application_resolver.get_application_index", return_value={"calculator": arguments}), \
         patch.dict(TOOLS["launch_application"], {"risk": "low"}), \
         patch("desktop.consequence_policy.ConsequencePolicy.evaluate", return_value=make_policy_result(
             PolicyDecision.ALLOW, reason="Simulated trusted policy", consequence="test")), \
         patch("tools.system_tools._launch_application", return_value=True) as launch, \
         patch("desktop.application_observer.observe_calculator", return_value={"calculator_open": False}):
        task = execute_plan("Calculator", {"tool": "launch_application", "arguments": arguments})
    assert task.status.value == "failed" and "verification" in task.error
    launch.assert_called_once_with(**arguments)


def test_window_title_alone_is_not_verification():
    from desktop.application_observer import observe_calculator

    with patch("desktop.application_observer.get_win32_windows", return_value=[{
        "handle": 42, "process_id": 123, "visible": True, "title": "Calculator",
    }]), patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.EnumChildWindows"), \
         patch("desktop.application_observer._process_image", return_value="C:\\fake\\CalculatorApp.exe"):
        assert observe_calculator(timeout=0) == {"calculator_open": False}


def test_visible_calculator_observation_and_minimized_rejection():
    import ntpath
    import os
    from desktop.application_observer import observe_calculator

    image = ntpath.join(os.environ["ProgramFiles"], "WindowsApps",
                        "Microsoft.WindowsCalculator_11.2505.2.0_x64__8wekyb3d8bbwe", "CalculatorApp.exe")
    for minimized in (False, True):
        with patch("desktop.application_observer.get_win32_windows", return_value=[{
            "handle": 42, "process_id": 123, "visible": True,
        }]), patch("win32gui.IsIconic", return_value=minimized), \
             patch("win32gui.EnumChildWindows"), \
             patch("desktop.application_observer._process_image", return_value=image):
            state = observe_calculator(timeout=0)
        assert state["calculator_open"] is (not minimized)


def test_legacy_semantic_policy_is_preserved():
    from desktop.desktop_execution_gate import DesktopExecutionGate

    request = {"action": "toggle", "window_handle": 1, "arguments": {
        "target": {"role": "checkbox", "name": "Enable Test Feature"},
        "expected_state": "off", "requested_state": "on",
    }}
    with patch("desktop.action_gate.DesktopActionGate.execute") as technical:
        outcome = DesktopExecutionGate().execute(request)
    assert outcome["success"] is False
    assert outcome["policy"]["decision"] == "confirm"
    technical.assert_not_called()


def test_main_reports_verification_failure():
    from contextlib import redirect_stdout
    from io import StringIO
    from main import run_agent

    output = StringIO()
    with patch("builtins.input", side_effect=["Open Calculator", "exit"]), \
         patch("tools.system_tools._open_calculator", return_value=True), \
         patch("desktop.application_observer.observe_calculator", return_value={"calculator_open": False}), \
         redirect_stdout(output):
        run_agent()
    assert "Action failed:" in output.getvalue()
    assert "independently verified" not in output.getvalue()


def test_main_clarification_and_unsupported_compatibility():
    from contextlib import redirect_stdout
    from io import StringIO
    from main import run_agent

    application = {"name": "Example", "launch_type": "app_id", "launch_target": "Example!App"}
    plans = [
        {"type": "unsupported", "reason": "Unavailable"},
        {"type": "clarification", "candidates": [application]},
    ]
    output = StringIO()
    with patch("builtins.input", side_effect=["unsupported", "Open Example", "1", "exit"]), \
         patch("main.understand_command", side_effect=plans), \
         patch("brain.application_resolver.get_application_index", return_value={"example": application}), \
         patch("tools.system_tools._launch_application", return_value=True) as launch, \
         patch("desktop.application_observer.observe_calculator") as observe, \
         redirect_stdout(output):
        run_agent()
    launch.assert_not_called()
    observe.assert_not_called()
    assert "currently available tools" in output.getvalue()
    assert "Selected: Example" in output.getvalue()
    assert "trusted user confirmation is required" in output.getvalue()


def test_direct_launch_cannot_bypass_technical_gate():
    from desktop.desktop_execution_gate import DesktopExecutionGate

    with patch("tools.system_tools._open_calculator") as launch:
        result = DesktopExecutionGate().execute({
            "action": "open_calculator", "arguments": {}, "confirmed": True,
        })
    assert result["success"] is False
    launch.assert_not_called()


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Runtime integration: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
