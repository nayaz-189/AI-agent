"""Reviewed, bounded security suite for development finalization.

Only project tests are run. This never discovers or executes candidate skills.
New execution test modules must be explicitly reviewed into TEST_MODULES.
"""
from contextlib import redirect_stdout, redirect_stderr
import os
from pathlib import Path
import runpy
import sys


TEST_MODULES = (
    "test_broker_contract", "test_confirmation_pause", "test_document_workflow",
    "test_execution_history", "test_execution_router", "test_failure_analyzer",
    "test_failure_report", "test_privacy_hardening", "test_recovery_pipeline",
    "test_recovery_proposal", "test_routed_task_executor", "test_runtime_integration",
    "test_security_review", "test_source_security", "test_task_conditions",
    "test_task_execution_history", "test_task_executor", "test_skill_isolation",
    "test_finalization_gate", "test_orchestrator", "test_device_protocol",
    "test_voice_audio", "test_voice_dialogue", "test_voice_identity",
    "test_voice_runtime", "test_voice_storage",
)


def run_suite():
    if sys.flags.optimize:
        return False  # Assertion tests must never silently run under python -O.
    directory = Path(__file__).resolve().parent
    discovered = {p.stem for p in directory.glob("test_*.py")}
    if discovered != set(TEST_MODULES) or len(TEST_MODULES) != len(set(TEST_MODULES)):
        return False
    try:
        # Backend/test errors may contain synthetic or private data; report only
        # process success to the finalizer, without retaining unbounded output.
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            for name in TEST_MODULES:
                runpy.run_module("execution." + name, run_name="__main__")
            runpy.run_module("brain.validator", run_name="__main__")
    except (Exception, SystemExit):
        return False
    return True


if __name__ == "__main__":
    passed = run_suite()
    print("Security regression suite: " + ("PASSED" if passed else "FAILED"))
    raise SystemExit(0 if passed else 1)
