"""Finalizer orchestration tests use mocks; no real finalizer runs here."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import subprocess

from knowledge import development_finalizer as finalizer
from execution import regression_suite


def test_regression_subprocess_is_fixed_bounded_and_fail_closed():
    for code in (0, 1):
        with patch.object(finalizer.subprocess, "run", return_value=SimpleNamespace(returncode=code)) as run:
            assert finalizer._run_security_regressions()["passed"] is (code == 0)
        args, kwargs = run.call_args
        assert args[0] == [finalizer.sys.executable, "-E", "-m", "execution.regression_suite"]
        assert kwargs["timeout"] == 180 and kwargs["shell"] is False
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    for error in (OSError("SYNTHETIC_PRIVATE"), subprocess.TimeoutExpired("test", 180)):
        with patch.object(finalizer.subprocess, "run", side_effect=error):
            assert finalizer._run_security_regressions() == {"passed": False}


def test_compilation_success_cannot_bypass_failed_security_suite():
    for dry_run in (True, False):
        with ExitStack() as stack:
            for name, value in {
                "get_current_day": 16, "get_current_version": "0.015",
                "get_project_info": {"current_day": 16, "version": "0.015", "status": "development"},
                "classify_repository_changes": {"source": ["main.py"], "blocked": [], "unknown": []},
                "_verify_core_repository": None, "_verify_context_repository": None,
                "_compile_project": {"passed": True}, "_check_dependencies": {"passed": True},
                "_run_security_regressions": {"passed": False},
            }.items():
                stack.enter_context(patch.object(finalizer, name, return_value=value))
            mutations = [stack.enter_context(patch.object(finalizer, name)) for name in (
                "update_project", "complete_development_day", "_refresh_knowledge_pipeline",
                "stage_paths", "commit", "push_current_branch", "publish_to_context_repository")]
            with redirect_stdout(StringIO()):
                assert finalizer.finalize_development(dry_run=dry_run) is False
            for mutation in mutations:
                mutation.assert_not_called()


def test_inactive_or_inconsistent_lifecycle_blocks_finalization_without_writes():
    states = (
        None,
        {"current_day": 15, "version": "0.015", "status": "completed"},
        {"current_day": 16, "version": "0.015", "status": "completed"},
        {"current_day": 15, "version": "0.015", "status": "development"},
        {"current_day": 16, "version": "0.014", "status": "development"},
    )
    for dry_run in (True, False):
        for state in states:
            with ExitStack() as stack:
                for name, value in {
                    "get_current_day": 16,
                    "get_current_version": "0.015",
                    "get_project_info": state,
                }.items():
                    stack.enter_context(patch.object(finalizer, name, return_value=value))
                operations = [stack.enter_context(patch.object(finalizer, name)) for name in (
                    "classify_repository_changes", "update_project", "complete_development_day",
                    "_refresh_knowledge_pipeline", "stage_paths", "commit",
                    "push_current_branch", "publish_to_context_repository")]
                with redirect_stdout(StringIO()):
                    assert finalizer.finalize_development(dry_run=dry_run) is False
                for operation in operations:
                    operation.assert_not_called()


def test_suite_rejects_missing_tests_and_disabled_assertions():
    with patch.object(regression_suite.Path, "glob", return_value=[]), \
         patch.object(regression_suite.runpy, "run_module") as run:
        assert regression_suite.run_suite() is False
    run.assert_not_called()
    with patch.object(regression_suite.sys, "flags", SimpleNamespace(optimize=1)):
        assert regression_suite.run_suite() is False


def test_suite_runs_every_reviewed_module_and_validator_and_rejects_errors():
    with patch.object(regression_suite.runpy, "run_module") as run:
        assert regression_suite.run_suite() is True
    assert [call.args[0] for call in run.call_args_list] == [
        "execution." + name for name in regression_suite.TEST_MODULES] + ["brain.validator"]
    for error in (AssertionError("SYNTHETIC_PRIVATE"), SystemExit(0)):
        with patch.object(regression_suite.runpy, "run_module", side_effect=error):
            assert regression_suite.run_suite() is False


def main():
    tests = [f for name, f in globals().items() if name.startswith("test_") and callable(f)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Finalization gate: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
