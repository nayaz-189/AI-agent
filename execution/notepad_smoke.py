"""Interactive smoke test. Each actual mutation requires a real Yes response."""

import json

from desktop.confirmation_ui import confirm_desktop_request
from execution.document_workflow import DEMO_COMMAND
from execution.execution_history import ExecutionHistory
from execution.runtime import execute_command
from execution.task_state import TaskStatus


def main():
    history = ExecutionHistory()
    task = execute_command(DEMO_COMMAND, history=history,
                           confirmation_ui=confirm_desktop_request)
    verified = task.status == TaskStatus.COMPLETED
    print(json.dumps({"verified": verified, "status": task.status.value,
                      "steps": [{"action": s.action, "status": s.status.value} for s in task.steps]}))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
