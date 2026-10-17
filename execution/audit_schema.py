"""Default-deny audit schema, separate from payloads needed for execution."""
import hashlib
import re

from execution.safe_failure import ErrorCode, STAGES, failure_from_message

EVENTS = {
    "task_started", "task_resumed", "task_paused", "task_completed", "task_failed",
    "step_started", "step_completed", "step_failed", "confirmation_required",
    "preconditions_check_started", "preconditions_passed", "preconditions_failed",
    "postconditions_check_started", "postconditions_passed", "postconditions_failed",
    "action_succeeded", "action_failed", "plan_rejected", "state_observed", "document_observed",
}
ACTIONS = {"open_calculator", "launch_application", "resolve_application", "open_google",
           "open_youtube", "open_website", "resolve_website", "write_test_introduction",
           "open_test_document", "set_value", "export_test_document", "verify_test_file",
           "research_and_save_report", "research_sources", "export_verified_report"}
AGENTS = {"system", "browser", "desktop_document", "orchestrator", "research", "windows"}


def safe_id(value):
    if value is None:
        return None
    if isinstance(value, str) and re.fullmatch(r"(?:task|step|event|recovery|recovery_request|audit)_[0-9a-f]{12,64}", value):
        return value
    # Stable pseudonym preserves correlation without preserving caller text.
    text = value if isinstance(value, str) else type(value).__name__
    return "audit_" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_action(value):
    return value if isinstance(value, str) and value in ACTIONS else None


def safe_agent(value):
    return value if isinstance(value, str) and value in AGENTS else None


def event_details(event_type, details):
    if event_type not in EVENTS or not isinstance(details, dict):
        return {}
    allowed = {
        "task_started": {"step_count"},
        "preconditions_check_started": {"condition_count"},
        "postconditions_check_started": {"condition_count"},
        "action_succeeded": {"result_present"}, "action_failed": {"result_present"},
        "step_completed": {"result_present"}, "task_completed": {"completed_steps"},
        "state_observed": {"calculator_open"},
        "document_observed": {"document_ready", "document_empty", "content_matches", "file_matches"},
    }.get(event_type, set())
    result = {}
    for key in allowed:
        value = details.get(key)
        if key in {"step_count", "condition_count", "completed_steps"}:
            if type(value) is int and 0 <= value <= 100000:
                result[key] = value
        elif type(value) is bool:
            result[key] = value
    if event_type in {"task_failed", "step_failed", "preconditions_failed", "postconditions_failed",
                       "action_failed", "plan_rejected", "confirmation_required", "task_paused"}:
        failure = failure_from_message(details.get("error", details.get("reason")))
        try:
            code = ErrorCode(details.get("error_code", failure.code.value))
        except (ValueError, TypeError):
            code = ErrorCode.EXECUTION_FAILED
        stage = details.get("stage", failure.stage)
        result.update(error_code=code.value, stage=stage if isinstance(stage, str) and stage in STAGES else "execution")
    return result
