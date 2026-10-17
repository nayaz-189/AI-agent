"""Plain-assertion tests, included by the established execution test harness."""
import json
from unittest.mock import patch

from execution.audit_schema import EVENTS, event_details
from execution.execution_history import ExecutionEvent, ExecutionHistory
from execution.execution_router import ExecutionRouter, RouteResult
from execution.failure_analyzer import FailureAnalyzer, FailureCategory
from execution.failure_report import FailureReportBuilder
from execution.recovery_pipeline import RecoveryPipeline
from execution.safe_failure import ErrorCode, MESSAGES, SafeFailure
from execution.task import Task
from execution.task_executor import TaskExecutor, StepExecutionResult
from execution.task_step import TaskStep

PRIVATE = "SYNTHETIC_PRIVATE_SENTINEL_7391"


def assert_private_absent(value):
    assert PRIVATE not in json.dumps(value, default=str)


def test_default_deny_all_event_payloads():
    for kind in EVENTS | {PRIVATE}:
        event = ExecutionEvent(kind, PRIVATE, step_id=PRIVATE, agent=PRIVATE, action=PRIVATE,
                               details={PRIVATE: PRIVATE, "result": {"nested": PRIVATE},
                                        "error": PRIVATE, "stage": [PRIVATE], "step_count": PRIVATE},
                               timestamp=PRIVATE, event_id=PRIVATE)
        assert_private_absent(event.to_dict())
        assert event.agent is None and event.action is None
    assert event_details("task_started", {"step_count": True}) == {}
    assert event_details("task_started", {"step_count": 3}) == {"step_count": 3}


def test_event_evidence_identity_and_mutation_resanitization():
    event = ExecutionEvent("task_failed", "task_0123456789ab", details={"error": PRIVATE})
    event.details[PRIVATE] = PRIVATE
    history = ExecutionHistory()
    history.record(event)
    report = FailureReportBuilder().build(history, event.task_id)
    evidence = report.evidence[0]
    assert evidence["event_id"] == event.event_id
    assert evidence["timestamp"] == event.timestamp
    evidence["details"][PRIVATE] = PRIVATE
    assert_private_absent([event.to_dict(), history.all_events(), report.to_dict()])


def test_success_and_failure_drop_unclassified_backend_payloads():
    for success in (True, False):
        router = ExecutionRouter()
        router.register_backend("system", lambda action, args: {
            "success": success, "error": None if success else PRIVATE,
            "result": {"verified": success, "text": PRIVATE, "nested": [{"unknown": PRIVATE}]}})
        history = ExecutionHistory()
        task = Task(goal=PRIVATE, steps=[TaskStep(action="open_calculator", agent="system",
                                                  arguments={PRIVATE: PRIVATE})])
        TaskExecutor(execution_router=router, execution_history=history).execute(task)
        assert task.status.value == ("completed" if success else "failed")
        assert task.steps[0].result == {"verified": success}
        assert_private_absent([task.to_dict(), history.all_events(), task.error])
        if not success:
            recovery = RecoveryPipeline().prepare(history=history, task_id=task.task_id)
            assert recovery.analysis.category == FailureCategory.EXECUTION
            assert_private_absent([recovery.report.to_dict(), recovery.analysis.to_dict(),
                                   recovery.proposal.to_dict(),
                                   recovery.planning_request.to_dict() if recovery.planning_request else None])


def test_private_condition_values_and_observation_exceptions():
    for stage in ("preconditions", "postconditions"):
        for raises in (False, True):
            def state():
                if raises:
                    raise RuntimeError(PRIVATE)
                return {PRIVATE: PRIVATE + "observed"}
            condition = {"type": "state_equals", "key": PRIVATE, "expected": PRIVATE}
            step = TaskStep(action="test", **{stage: [condition]})
            task = Task(goal=PRIVATE, steps=[step])
            executor = TaskExecutor(state_provider=state)
            executor.register_action("test", lambda args: {"success": True})
            executor.execute(task)
            assert task.status.value == "failed"
            report = FailureReportBuilder().build(executor.execution_history, task.task_id)
            code = ErrorCode.PRECONDITION_FAILED if stage == "preconditions" else ErrorCode.VERIFICATION_FAILED
            assert report.failure.code == code
            assert task.error == MESSAGES[code]
            assert_private_absent([task.to_dict(), report.to_dict(), executor.execution_history.all_events()])


def test_exception_and_backend_routing_prose_cannot_spoof_classification():
    for throws in (True, False):
        def backend(action, arguments):
            if throws:
                raise RuntimeError(PRIVATE)
            return {"success": False, "error": MESSAGES[ErrorCode.BACKEND_UNAVAILABLE]}
        router = ExecutionRouter()
        router.register_backend("system", backend)
        task = Task(goal=PRIVATE, steps=[TaskStep(action="open_calculator", agent="system")])
        executor = TaskExecutor(execution_router=router)
        executor.execute(task)
        report = FailureReportBuilder().build(executor.execution_history, task.task_id)
        assert FailureAnalyzer().analyze(report).category == FailureCategory.EXECUTION
        assert_private_absent([task.to_dict(), report.to_dict()])


def test_typed_failures_override_success_and_reject_arbitrary_failure_objects():
    for cls in (RouteResult, StepExecutionResult):
        for failure in (SafeFailure(ErrorCode.PERMISSION_DENIED, "authorization"), {PRIVATE: PRIVATE}):
            result = cls(success=True, failure=failure, result={"payload": PRIVATE})
            assert result.success is False
            assert isinstance(result.failure, SafeFailure)
            assert_private_absent([result.error, result.result, result.failure.to_dict()])
        for field in ("verified", "executed", "tool_reported_success"):
            result = cls(success=True, result={field: False})
            assert result.success is False and result.failure.code == ErrorCode.EXECUTION_FAILED
        assert cls(success=True, error=[]).success is False


def test_failed_task_cannot_resume_or_execute_again():
    calls = []
    executor = TaskExecutor()
    executor.register_action("test", lambda args: calls.append(True) or {"success": False, "error": PRIVATE})
    task = Task(goal=PRIVATE, steps=[TaskStep(action="test")])
    executor.execute(task)
    try:
        executor.execute(task, approved_step_id=task.steps[0].step_id)
    except (ValueError, RuntimeError):
        pass
    assert task.status.value == "failed" and len(calls) == 1


def test_raw_backend_failure_field_cannot_hide_behind_success():
    for field in ("failure", "confirmed", "approved_step_id", PRIVATE):
        response = {"success": True, field: PRIVATE}
        router = ExecutionRouter()
        router.register_backend("system", lambda action, arguments: response)
        result = router.route("system", "open_calculator", {})
        assert result.success is False
        executor = TaskExecutor()
        executor.register_action("test", lambda arguments: response)
        task = executor.execute(Task(goal=PRIVATE, steps=[TaskStep(action="test")]))
        assert task.status.value == "failed"
        assert_private_absent([task.to_dict(), executor.execution_history.all_events(), result.error])


def test_skill_audit_is_memory_only_and_drops_arguments_and_prose():
    from skills.capability_audit import CAPABILITY_HISTORY, record_capability_attempt
    from skills.execution_gate import build_audited_result
    CAPABILITY_HISTORY.clear()
    with patch("knowledge.canonical_recorder.record_event") as canonical:
        result = build_audited_result(executed=False, skill_name=PRIVATE, capability=PRIVATE,
                                     reason=PRIVATE, arguments={"innocent": PRIVATE}, extra={PRIVATE: PRIVATE})
        record_capability_attempt(PRIVATE, PRIVATE, False, PRIVATE, arguments={PRIVATE: PRIVATE})
    canonical.assert_not_called()
    assert CAPABILITY_HISTORY.count() == 2
    assert_private_absent([result, CAPABILITY_HISTORY.all_events()])
    CAPABILITY_HISTORY.clear()


def test_legacy_worker_diagnostics_and_malformed_success_are_closed():
    from pathlib import Path
    from types import SimpleNamespace
    from skills.runtime_manager import invoke_skill
    # Use an existing project source solely for the entrypoint-exists check.
    # subprocess.run is mocked: no skill code is executed.
    active = {"installed_path": str(Path(__file__).resolve().parent),
              "entrypoint": Path(__file__).name, "permissions": []}
    for response, expected in (({"success": True, "result": {"text": PRIVATE}}, False),
                               ({"success": True, "error": PRIVATE}, False),
                               ({"success": "yes"}, False),
                               ({"success": False, "error": PRIVATE}, False),
                               ([PRIVATE], False)):
        process = SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr=PRIVATE)
        with patch("skills.runtime_manager.get_active_skill", return_value=active), \
             patch("skills.runtime_manager.check_activation_eligibility", return_value={"eligible": True}), \
             patch("subprocess.run", return_value=process) as launch:
            result = invoke_skill(PRIVATE)
        launch.assert_not_called()
        assert result["success"] is expected
        assert_private_absent(result)
    with patch("skills.runtime_manager._invoke_skill", side_effect=RuntimeError(PRIVATE)):
        result = invoke_skill(PRIVATE)
    assert result["success"] is False
    assert_private_absent(result)


def main():
    tests = [f for name, f in globals().items() if name.startswith("test_") and callable(f)]
    for test in tests:
        test()
        print("PASS:", test.__name__)
    print(f"Privacy hardening: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
