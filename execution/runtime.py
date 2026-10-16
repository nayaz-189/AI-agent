"""Composition of the existing planner, agents, router and task executor."""

from copy import deepcopy

from agents.router import route_plan
from brain.planner import understand_command
from brain.validator import validate_plan
from execution.execution_history import ExecutionEvent, ExecutionHistory
from execution.execution_router import ExecutionRouter
from execution.task import Task
from execution.task_executor import TaskExecutor
from execution.task_step import TaskStep
from tools.tool_registry import TOOLS


def _is_calculator_application(application):
    return (
        application.get("name", "").strip().lower() in {"calculator", "windows calculator"}
        or application.get("launch_target", "").lower().startswith("microsoft.windowscalculator_")
    )


def _requires_calculator_observation(tool_name, arguments):
    if tool_name == "open_calculator":
        return True
    if tool_name == "launch_application":
        from brain.application_resolver import get_application_index

        return any(
            app.get("launch_type") == arguments["launch_type"]
            and app.get("launch_target") == arguments["launch_target"]
            and _is_calculator_application(app)
            for app in get_application_index().values()
        )
    if tool_name == "resolve_application":
        from brain.application_resolver import find_application

        resolved = find_application(arguments["target"])
        return bool(resolved and resolved.get("status") == "resolved"
                    and _is_calculator_application(resolved["application"]))
    return False


def _registered_backend(expected_agent):
    def execute(action, arguments):
        plan = {"tool": action, "arguments": arguments}
        if not validate_plan(plan) or TOOLS[action]["agent"] != expected_agent:
            return {"success": False, "error": "Backend rejected tool or arguments."}
        agent = route_plan(plan)
        if agent is None:
            return {"success": False, "error": "No registered agent can handle this tool."}
        success = agent.handle(plan) is True
        return {
            "success": success,
            "result": {"tool_reported_success": success},
            "error": None if success else "Tool failed or authorization was blocked.",
        }
    return execute


def execute_plan(command, plan, *, history=None, confirmation_ui=None):
    """Validate before conversion; all task policy comes from trusted code.

    No approval token, arbitrary handler, or model-supplied condition is accepted.
    The existing history remains the evidence store, without altering knowledge.
    """
    history = history if history is not None else ExecutionHistory()
    task = Task(goal=command)
    if not validate_plan(plan):
        task.mark_failed("Plan validation rejected the request; no action executed.")
        history.record(ExecutionEvent(
            event_type="plan_rejected", task_id=task.task_id,
            details={"error": task.error},
        ))
        return task

    plan = deepcopy(plan)
    tool_name = plan["tool"].strip()
    metadata = TOOLS[tool_name]
    if tool_name == "write_test_introduction":
        from desktop.document_session import NotepadTestSession
        from execution.document_workflow import INTRODUCTION, execute_document_workflow

        return execute_document_workflow(NotepadTestSession(INTRODUCTION), history=history,
                                         confirmation_ui=confirmation_ui)
    # Alternative registered launch tools must not evade verification.
    try:
        calculator = _requires_calculator_observation(tool_name, plan["arguments"])
    except Exception:
        task.mark_failed("Application identity could not be established; no action executed.")
        history.record(ExecutionEvent(
            event_type="plan_rejected", task_id=task.task_id,
            details={"error": task.error},
        ))
        return task

    task.add_step(TaskStep(
        action=tool_name,
        agent=metadata["agent"],
        arguments=plan["arguments"],
        requires_confirmation=metadata["risk"] != "low",
        postconditions=[{
            "type": "state_equals", "key": "calculator_open", "expected": True,
        }] if calculator else [],
    ))

    router = ExecutionRouter()
    for agent_name in ("system", "browser"):
        router.register_backend(agent_name, _registered_backend(agent_name))

    def observe():
        from desktop.application_observer import observe_calculator

        state = observe_calculator()
        history.record(ExecutionEvent(
            event_type="state_observed", task_id=task.task_id,
            step_id=task.steps[0].step_id, agent=metadata["agent"],
            action=tool_name, details=state,
        ))
        return state

    executor = TaskExecutor(
        execution_router=router, state_provider=observe, execution_history=history,
    )
    return executor.execute(task)


def execute_command(command, *, history=None, confirmation_ui=None):
    """Non-interactive entry point; ambiguous/unsupported plans fail closed."""
    return execute_plan(command, understand_command(command), history=history,
                        confirmation_ui=confirmation_ui)
