"""Compose existing task routing and gates around an owned document session."""

from copy import deepcopy

from desktop.confirmation_authority import ConfirmationAuthority
from desktop.desktop_execution_gate import DesktopExecutionGate
from desktop.user_confirmation import UserConfirmationBoundary
from execution.execution_history import ExecutionEvent
from execution.execution_router import ExecutionRouter
from execution.task import Task
from execution.task_executor import TaskExecutor
from execution.task_step import TaskStep


INTRODUCTION = (
    "Artificial intelligence is the study of computer systems that perform tasks "
    "such as learning, reasoning, and understanding language. These systems find "
    "patterns in data to help people solve problems. Their results need careful "
    "checking, responsible use, and human judgment."
)
DEMO_COMMAND = (
    "Open Notepad, write a short introduction about artificial intelligence, "
    "export it into my approved AI Agent test folder, and verify the saved content."
)


def execute_document_workflow(session, *, history, confirmation_ui=None):
    """Trusted composition API, never a model-supplied callable or session.

    TaskStep contains only an opaque session ID. Exact requests and tokens stay
    inside the gated backend, and no step-ID approval can skip authorization.
    """
    task = Task(goal="Approved test document workflow")
    authority = ConfirmationAuthority(ttl_seconds=30)
    boundary = UserConfirmationBoundary(authority)
    gate = DesktopExecutionGate(authority, document_session=session)
    specifications = (
        ("open_test_document", (), ("document_ready", "document_empty")),
        ("set_value", ("document_ready", "document_empty"), ("content_matches",)),
        ("export_test_document", ("document_ready", "content_matches"), ("file_matches",)),
        ("verify_test_file", ("file_matches",), ("file_matches",)),
    )

    def conditions(keys):
        return [{"type": "state_equals", "key": key, "expected": True} for key in keys]

    for action, before, after in specifications:
        task.add_step(TaskStep(
            action=action, agent="desktop_document", arguments={"session_id": session.session_id},
            preconditions=conditions(before), postconditions=conditions(after),
        ))

    def observe():
        raw = session.state()
        state = {key: raw.get(key) is True for key in (
            "document_ready", "document_empty", "content_matches", "file_matches")}
        history._record_verification(task, "document_export", all(state[key] for key in (
            "document_ready", "content_matches", "file_matches")))
        history.record(ExecutionEvent(event_type="document_observed", task_id=task.task_id,
                                      details=state))
        return state

    def execute(action, arguments):
        failure = {"success": False, "error": "Document action blocked or verification failed."}
        if arguments != {"session_id": session.session_id}:
            return failure
        try:
            if action == "verify_test_file":
                verified = observe()["file_matches"]
            else:
                builders = {"open_test_document": session.open_request,
                            "set_value": session.edit_request,
                            "export_test_document": session.export_request}
                if action not in builders:
                    return failure
                if confirmation_ui is None:
                    return {"success": False, "error": "Trusted confirmation UI is unavailable."}
                request = deepcopy(builders[action]())
                if session.validate(request) is not True:
                    return failure
                # UI receives a copy; any accidental mutation cannot alter consent.
                approved = confirmation_ui(deepcopy(request))
                decision = boundary.process_user_decision(request, approved)
                if decision["approved"] is not True:
                    return {"success": False, "error": "User approval was declined or unavailable."}
                outcome = gate.execute(request, decision["confirmation"].token)
                verified = (outcome.get("success") is True and outcome.get("verified") is True
                            and not outcome.get("error"))
            return {"success": True, "result": {"verified": True}} if verified else failure
        except Exception as exc:
            # UIA/OS exceptions may include document content or local paths.
            return {"success": False, "error": f"Document operation stopped ({type(exc).__name__})."}

    router = ExecutionRouter()
    router.register_backend("desktop_document", execute)
    try:
        return TaskExecutor(state_provider=observe, execution_router=router,
                            execution_history=history).execute(task)
    finally:
        session.close()
