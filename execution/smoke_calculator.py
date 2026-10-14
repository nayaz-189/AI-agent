"""Explicit live smoke test: python -m execution.smoke_calculator.

Launches Calculator and reports the outcome; history remains in memory.
Does not close applications, update knowledge, finalize, commit, or publish.
"""

import json

from desktop.application_observer import observe_calculator
from execution.execution_history import ExecutionHistory
from execution.runtime import execute_command


def main():
    before = observe_calculator(timeout=0)
    history = ExecutionHistory()
    task = execute_command("Open Calculator", history=history)
    events = history.events_for_task(task.task_id)
    verified = (
        task.status.value == "completed"
        and any(event["event_type"] == "postconditions_passed" for event in events)
        and any(event["event_type"] == "state_observed"
                and event["details"].get("calculator_open") is True for event in events)
    )
    evidence = {
        "before": before,
        "verified": verified,
        "task": task.to_dict(),
        "events": events,
    }
    print(json.dumps({"verified": verified, "status": task.status.value}))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
