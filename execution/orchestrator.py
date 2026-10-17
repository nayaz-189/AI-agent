"""Trusted specialist composition using the existing executor and router.

Roles are capability labels, not security identities or independent OS workers.
No downloaded/model code runs here. Only reviewed, fixed adapters are installed.
"""
from enum import Enum
from types import MappingProxyType

from brain.validator import validate_plan
from execution.execution_history import ExecutionHistory
from execution.execution_router import ExecutionRouter
from execution.task import Task
from execution.task_executor import TaskExecutor
from execution.task_step import TaskStep
from execution.task_state import TaskStatus
from execution.safe_failure import ErrorCode, MESSAGES


DEMO_COMMAND = "Research Python AST and pathlib, summarize the findings, and save an approved report."


class Role(str, Enum):
    RESEARCH = "research"
    CODING = "coding"
    WINDOWS = "windows"
    ANDROID = "android"
    COMMUNICATION = "communication"
    MEMORY = "memory"


CAPABILITIES = MappingProxyType({
    Role.RESEARCH: frozenset({"research_sources"}),
    Role.WINDOWS: frozenset({"open_calculator", "write_test_introduction", "export_verified_report"}),
    # No OS isolation, mobile transport, dedicated account or scoped memory
    # service exists yet. Names alone must not grant their intended capabilities.
    Role.CODING: frozenset(), Role.ANDROID: frozenset(),
    Role.COMMUNICATION: frozenset(), Role.MEMORY: frozenset(),
})
_REQUIREMENTS = MappingProxyType({
    "open_calculator": (Role.WINDOWS,),
    "write_test_introduction": (Role.WINDOWS,),
    "research_and_save_report": (Role.RESEARCH, Role.WINDOWS),
})


def select_specialists(plan):
    if not validate_plan(plan) or plan["tool"] not in _REQUIREMENTS:
        raise ValueError(MESSAGES[ErrorCode.INVALID_REQUEST])
    selected = _REQUIREMENTS[plan["tool"]]
    if not 0 < len(selected) <= 6 or len(set(selected)) != len(selected):
        raise ValueError(MESSAGES[ErrorCode.PERMISSION_DENIED])
    return selected


def execute_orchestration(plan, *, history=None, confirmation_ui=None):
    history = history if history is not None else ExecutionHistory()
    task = Task(goal="Verified specialist workflow")
    try:
        selected = select_specialists(plan)
    except Exception:
        task.mark_failed(MESSAGES[ErrorCode.INVALID_REQUEST])
        return task
    if selected == (Role.WINDOWS,):
        from execution.runtime import execute_plan
        return execute_plan("Registered Windows workflow", plan, history=history,
                            confirmation_ui=confirmation_ui)

    state = {"research_verified": False, "report_verified": False}
    report = None

    def conditions(key):
        return [{"type": "state_equals", "key": key, "expected": True}]

    task.add_step(TaskStep(action="research_sources", agent=Role.RESEARCH.value,
                           arguments={}, postconditions=conditions("research_verified")))
    task.add_step(TaskStep(action="export_verified_report", agent=Role.WINDOWS.value,
                           arguments={}, preconditions=conditions("research_verified"),
                           postconditions=conditions("report_verified")))

    def research(action, arguments):
        nonlocal report
        if action not in CAPABILITIES[Role.RESEARCH] or arguments != {}:
            return {"success": False}
        from agents.research_agent import research_report
        report = research_report()
        state["research_verified"] = type(report) is str and 0 < len(report) <= 4096
        return {"success": state["research_verified"], "result": {"verified": state["research_verified"]}}

    def windows(action, arguments):
        if action != "export_verified_report" or arguments != {} or not state["research_verified"]:
            return {"success": False}
        from desktop.document_session import NotepadTestSession
        from execution.document_workflow import execute_document_workflow
        child = execute_document_workflow(NotepadTestSession(report), history=history,
                                          confirmation_ui=confirmation_ui)
        # Child completion includes independent UI and file observations, never
        # just a successful tool return. Check that evidence as well as status.
        state["report_verified"] = history.has_verification(child, "document_export")
        # Bind the independently verified child outcome to this exact parent.
        # Audit event dictionaries and backend success flags cannot mint it.
        history._record_verification(task, "research_report", state["report_verified"])
        return {"success": state["report_verified"], "result": {"verified": state["report_verified"]}}

    router = ExecutionRouter()
    router.register_backend(Role.RESEARCH.value, research)
    router.register_backend(Role.WINDOWS.value, windows)
    return TaskExecutor(execution_router=router, execution_history=history,
                        state_provider=lambda: dict(state)).execute(task)


def completion_report(task, *, history=None):
    """Report verified only with trusted, bound observation provenance.

    Missing history fails closed. Serialized events, task status and declared
    postconditions are not proof. Host Python and observer adapters remain trusted.
    """
    roles = sorted({"windows" if s.agent in {"system", "desktop_document"} else s.agent
                    for s in task.steps} & {r.value for r in Role})
    verified = type(history) is ExecutionHistory and any(
        history.has_verification(task, kind)
        for kind in ("calculator", "document_export", "research_report"))
    return {"task_id": task.to_dict()["task_id"], "status": task.status.value,
            "specialists": roles, "verified": verified, "error": task.to_dict()["error"]}
