"""Security regressions using synthetic data and mocked external effects."""

from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from execution.execution_history import ExecutionHistory, REDACTED
from execution.execution_router import ExecutionRouter
from execution.runtime import _registered_backend, execute_plan
from execution.task import Task
from execution.task_executor import TaskExecutor
from execution.task_step import TaskStep
from tools.tool_registry import execute_tool


def test_browser_tools_require_confirmation_without_network():
    plans = [
        {"tool": "open_website", "arguments": {"url": "https://bank.example.invalid/?secret=synthetic"}},
        {"tool": "resolve_website", "arguments": {"target": "synthetic private query"}},
        {"tool": "open_google", "arguments": {}},
        {"tool": "open_youtube", "arguments": {}},
    ]
    with patch("tools.system_tools.webbrowser.open") as browser, \
         patch("tools.system_tools.resolve_official_website") as search, \
         patch("tools.system_tools.get_cached_website") as cache:
        for plan in plans:
            assert execute_plan("test", plan).status.value == "waiting_for_user"
            assert execute_tool(plan["tool"], plan["arguments"]) is False
    browser.assert_not_called()
    search.assert_not_called()
    cache.assert_not_called()


def test_discovered_shortcut_is_not_automatic_authorization():
    from desktop.desktop_execution_gate import DesktopExecutionGate

    args = {"launch_type": "shortcut", "launch_target": "C:\\Synthetic\\Run Commands.lnk"}
    with patch("brain.application_resolver.get_application_index", return_value={"test": args}), \
         patch("tools.system_tools._launch_application") as launch:
        task = execute_plan("test", {"tool": "launch_application", "arguments": args})
        direct = DesktopExecutionGate().execute({"action": "launch_application", "arguments": args})
    assert task.status.value == "waiting_for_user"
    assert direct["success"] is False and direct["policy"]["decision"] == "confirm"
    launch.assert_not_called()


def test_step_id_is_not_security_authorization():
    router = ExecutionRouter()
    router.register_backend("browser", _registered_backend("browser"))
    executor = TaskExecutor(execution_router=router)
    step = TaskStep(action="open_website", agent="browser", requires_confirmation=True,
                    arguments={"url": "https://example.com"})
    task = Task(goal="test", steps=[step])
    with patch("tools.system_tools.webbrowser.open") as browser:
        executor.execute(task)
        assert task.status.value == "waiting_for_user"
        executor.execute(task, approved_step_id=step.step_id)
    assert task.status.value == "failed"
    browser.assert_not_called()


def test_forged_confirmation_token_cannot_reach_os():
    from desktop.desktop_execution_gate import DesktopExecutionGate

    request = {"action": "launch_application", "arguments": {
        "launch_type": "app_id", "launch_target": "Example!App",
    }}
    with patch("desktop.action_gate.DesktopActionGate.execute") as technical, \
         patch("desktop.confirmation_authority.ConfirmationAuthority.issue") as issue:
        result = DesktopExecutionGate().execute(request, confirmation_token="forged")
    assert result["success"] is False
    technical.assert_not_called()
    issue.assert_not_called()


def test_agents_revalidate_entire_plan_and_ownership():
    from agents import system_agent, browser_agent

    with patch("agents.system_agent.execute_tool") as system, \
         patch("agents.browser_agent.execute_tool") as browser:
        assert system_agent.handle({"tool": "open_calculator", "arguments": {}, "confirmed": True}) is False
        assert browser_agent.handle({"tool": "open_calculator", "arguments": {}}) is False
        assert system_agent.handle({"tool": "open_website", "arguments": {"url": "https://example.com"}}) is False
    system.assert_not_called()
    browser.assert_not_called()


def test_registry_discovery_error_fails_closed():
    with patch("brain.application_resolver.get_application_index", side_effect=RuntimeError("synthetic")):
        assert execute_tool("launch_application", {"launch_type": "app_id", "launch_target": "x"}) is False


def test_router_rejects_contradictory_results():
    router = ExecutionRouter()
    router.register_backend("test", lambda action, arguments: {"success": True, "error": "failed"})
    task = Task(goal="test", steps=[TaskStep(action="test", agent="test")])
    TaskExecutor(execution_router=router).execute(task)
    assert task.status.value == "failed"


def test_local_executor_rejects_contradictory_results():
    executor = TaskExecutor()
    executor.register_action("test", lambda arguments: {"success": True, "error": "failed"})
    task = Task(goal="test", steps=[TaskStep(action="test")])
    executor.execute(task)
    assert task.status.value == "failed"


def test_runtime_history_redacts_intent_and_argument_values():
    history = ExecutionHistory()
    task = execute_plan("synthetic-private-command", {
        "tool": "open_website", "arguments": {"url": "https://example.com/?token=synthetic-private-value"},
    }, history=history)
    assert task.status.value == "waiting_for_user"
    evidence = str(history.all_events())
    assert "synthetic-private" not in evidence
    assert "arguments" not in evidence and "goal" not in evidence


def test_observer_exception_does_not_leak_into_history_or_errors():
    history = ExecutionHistory()
    with patch("tools.system_tools._open_calculator", return_value=True), \
         patch("desktop.application_observer.observe_calculator", side_effect=RuntimeError("synthetic-private-path")):
        task = execute_plan("test", {"tool": "open_calculator", "arguments": {}}, history=history)
    assert task.status.value == "failed"
    assert "synthetic-private-path" not in str(history.all_events()) + str(task.error)


def test_router_exception_does_not_leak_private_message():
    def fail(action, arguments):
        raise ValueError("synthetic-private-error")
    router = ExecutionRouter()
    router.register_backend("test", fail)
    result = router.route("test", "action", {})
    assert result.success is False and "synthetic-private-error" not in result.error


def test_main_and_parser_do_not_echo_raw_model_content():
    from brain.planner import parse_llm_plan
    from main import run_agent

    output = StringIO()
    with patch("builtins.input", side_effect=["test", "exit"]), \
         patch("main.understand_command", return_value={
             "tool": "synthetic-private-command", "arguments": {"synthetic-private-key": "x"},
         }), redirect_stdout(output):
        run_agent()
        assert parse_llm_plan("synthetic-private-response") is None
    assert "synthetic-private" not in output.getvalue()


def test_llm_ignores_remote_host_and_proxy_environment():
    from brain.llm import ask_llm

    with patch.dict("os.environ", {"OLLAMA_HOST": "https://remote.example.invalid", "HTTPS_PROXY": "https://proxy.example.invalid"}), \
         patch("brain.llm.ollama.Client") as client:
        client.return_value.__enter__.return_value.chat.return_value = {"message": {"content": "{}"}}
        assert ask_llm("synthetic input") == "{}"
    client.assert_called_once_with(
        host="http://127.0.0.1:11434", trust_env=False, follow_redirects=False,
    )
    client.return_value.__exit__.assert_called_once()


def test_nonlocal_model_rejected_before_client_creation():
    from brain.llm import ask_llm

    with patch("brain.llm.get_model", return_value={"name": "test", "local": False, "provider": "ollama"}), \
         patch("brain.llm.ollama.Client") as client:
        try:
            ask_llm("synthetic")
        except ValueError:
            pass
        else:
            raise AssertionError("Remote model accepted")
    client.assert_not_called()


def test_calculator_package_identity_rejects_lookalikes():
    from desktop.application_observer import _is_calculator_image

    with patch("desktop.application_observer._program_files_directory", return_value="C:\\Program Files"):
        root = "C:\\Program Files\\WindowsApps\\"
        assert _is_calculator_image(root + "Microsoft.WindowsCalculator_11.2505.2.0_x64__8wekyb3d8bbwe\\CalculatorApp.exe")
        for name in ("Microsoft.WindowsCalculator_fake", "Microsoft.WindowsCalculator_11.2505.2.0_x64__wrongpublisher"):
            assert not _is_calculator_image(root + name + "\\CalculatorApp.exe")
        assert not _is_calculator_image("C:\\Other\\CalculatorApp.exe")


def test_titleless_observation_does_not_read_window_text():
    from desktop.window_manager import get_win32_windows

    with patch("win32gui.EnumWindows", side_effect=lambda callback, results: callback(42, results)), \
         patch("win32process.GetWindowThreadProcessId", return_value=(1, 123)), \
         patch("win32gui.GetClassName", return_value="test"), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.GetWindowText") as title:
        windows = get_win32_windows(include_titles=False)
    assert len(windows) == 1 and windows[0]["title"] == ""
    title.assert_not_called()


def test_observer_requests_titleless_metadata():
    from desktop.application_observer import observe_calculator

    with patch("desktop.application_observer.get_win32_windows", return_value=[]) as windows:
        assert observe_calculator(timeout=0) == {"calculator_open": False}
    windows.assert_called_once_with(include_titles=False)


def test_finalizer_document_exception_is_exact():
    from knowledge.development_finalizer import _classify_path

    assert _classify_path("docs/runtime-integration.md") == "source"
    for path in ("docs/other.md", "docs/sub/runtime-integration.md", "docs/runtime-integration.md.bak"):
        assert _classify_path(path) == "unknown"
    for path in ("docs/.env", "execution/credentials.json", "runtime/calculator_smoke.json", "docs/test.key"):
        assert _classify_path(path) == "blocked"


def test_finalizer_compiles_execution_directory():
    from knowledge import development_finalizer as finalizer

    with patch.object(finalizer, "_run_command", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run:
        assert finalizer._compile_project()["passed"] is True
    assert "execution" in run.call_args.args[0]


def test_dry_run_never_calls_finalization_mutations():
    from contextlib import ExitStack
    from knowledge import development_finalizer as finalizer

    with ExitStack() as stack:
        for name, value in {
            "get_current_day": 14, "get_current_version": "0.013",
            "classify_repository_changes": {"source": ["main.py"], "blocked": [], "unknown": []},
            "_verify_core_repository": None, "_verify_context_repository": None,
            "_compile_project": {"passed": True}, "_check_dependencies": {"passed": True},
            "_run_security_regressions": {"passed": True},
        }.items():
            stack.enter_context(patch.object(finalizer, name, return_value=value))
        mutations = [stack.enter_context(patch.object(finalizer, name)) for name in (
            "update_project", "complete_development_day", "_refresh_knowledge_pipeline",
            "stage_paths", "commit", "push_current_branch", "publish_to_context_repository",
        )]
        with redirect_stdout(StringIO()):
            assert finalizer.finalize_development(dry_run=True) is True
        for mutation in mutations:
            mutation.assert_not_called()


def main():
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Security review: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
