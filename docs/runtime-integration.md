# Day 14 runtime integration

The project remains at version 0.013 until the normal development workflow is
explicitly authorized. No dependencies, knowledge records, credentials, commits,
or publication settings were changed for this integration.

## Execution path

`main.run_agent` retains clarification, unsupported-command handling, and exit.
The existing `understand_command` planner recognizes `Open Calculator` through
its deterministic fast router and selects the existing `open_calculator` tool.

`execution.runtime.execute_plan` validates the plan and argument values, then
creates one existing `Task` and `TaskStep`. Agent selection and risk come from
the existing tool registry. Calculator postconditions come from runtime code.
Unknown tools, extra fields, planner confirmation flags, invalid values, and
application identities absent from the local application index are rejected.

`TaskExecutor` routes through `ExecutionRouter`, the existing agent router,
`system_agent`, and `execute_tool`. The registry revalidates arguments and
accepts only an explicit boolean `True` result. A missing result, false result,
exception, or truthy non-boolean value cannot become success.

Application tools call `DesktopExecutionGate`, which applies
`DesktopPolicyGate` and `DesktopActionGate` before the private OS primitive.
Calculator uses the absolute Windows system path with `shell=False`.
Generic application launches accept only discovered identities and now require
trusted confirmation: discovery alone does not authorize a shortcut's embedded
commands. Browser opening and website resolution also require confirmation to
protect personal browser sessions and prevent disclosure through search queries.
The runtime does not yet offer a trusted confirmation/resume interaction, so
these paths remain blocked. Existing semantic action policy and exact-request
confirmation authority remain in place. Only the fixed Calculator tool is
currently automatic.

The launch result indicates dispatch only. For Calculator, the executor then
calls the independent read-only observer. It requires a visible, non-minimized
window owned by the system Calculator process or the Windows Calculator package
under the Windows-known Program Files/WindowsApps location, with the Microsoft
Calculator publisher identity; UWP child process identities are also inspected.
Window titles are not read. Observation failure or timeout fails the
task. Existing ExecutionHistory records observation and postcondition events
before completion. Both agent entry points revalidate whole plans and tool
ownership. Router/executor results with contradictory success and error fields
are rejected.

Runtime history stays in memory. Command goals, URLs, application targets and
text values are redacted, and exception details and raw planner output are not
echoed. Planning uses an explicit loopback Ollama client with environment proxy
overrides and redirects disabled and requires locally configured model metadata. Runtime
events and observations are never passed to the planner.

## Run locally

From PowerShell in `C:\AI-agent`:

```powershell
.\.venv\Scripts\python.exe main.py
```

Enter `Open Calculator`. Expected result:
`Calculator is open (independently verified).`

For a reproducible live smoke test, optionally close Calculator yourself first:

```powershell
.\.venv\Scripts\python.exe -m execution.smoke_calculator
```

This command launches Calculator, observes before and after, exits nonzero on
failure, and prints only verification/status. It keeps history in memory and
does not close other apps. The earlier `runtime/calculator_smoke.json` artifact
is retained as historical evidence; it is not rewritten by this command and is
ignored by the existing runtime directory rule.

For regression tests (plain assertions; pytest is not installed):

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import runpy; [runpy.run_module('execution.'+p.stem, run_name='__main__') for p in sorted(Path('execution').glob('test_*.py'))]"
.\.venv\Scripts\python.exe -m brain.validator
```

## Observed results

On 2026-10-14, all 12 execution test modules passed: 53 existing tests and
20 new runtime integration tests. The new tests cover routing, argument and
tool rejection, false/malformed results, exceptions, observation failures,
policy/technical blocking, confirmation forgery, and CLI compatibility.
All 6 validator self-checks passed, and `git diff --check` reported no whitespace
errors. The existing executor module includes 3 inline scenarios, so the total
case count is greater than the number of named test functions.

The subsequent security review reran 13 execution modules: 53 original cases,
20 runtime integration cases, and 20 new security cases, all passing. All 6
validator checks also passed. The hardened live smoke test returned
`{"verified": true, "status": "completed"}` without writing runtime history.

The first finalizer dry-run blocked `docs/runtime-integration.md` as unknown.
The fix allows that exact reviewed file only; other docs files and existing
blocked files remain rejected. Compilation now includes the already-allowlisted
execution source directory. The final dry-run passed repository synchronization,
compilation and dependency checks, with no finalization, stage, commit, push, or
knowledge mutation.

**Day 14 readiness remains blocked by lifecycle state:** the actual dry-run
reports Day 13, version 0.013 (target 0.014). The finalizer constructs its commit
label from that day. Start/correct Day 14 through the existing lifecycle workflow
and rerun the dry-run before authorizing actual finalization. This review did
not change lifecycle records.

The live smoke test passed with Calculator absent before the action and present
afterward. Task `task_7af28e438fd1` observed process 2960 and window 3016446,
then recorded `postconditions_passed` followed by `task_completed`. These IDs
are historical evidence, not stable identifiers for future runs.

## Remaining limits and next task

- Independent outcome verification currently covers Calculator. Generic app and
  browser commands are recognized but blocked pending trusted confirmation.
- Interactive and smoke-test history stay in memory. No parallel knowledge store
  or automatic finalizer was added.
- Consequential registry tools pause, and policy-confirmation requests block.
  There is deliberately no runtime path that turns planner flags or step IDs
  into security credentials. A trusted confirmation UI still needs integration.
- Fixed Calculator launch and observation trust Windows system locations and
  OS/package integrity. They are not executable-signature verification or a
  sandbox against compromised local Python code. Cached application discovery
  can become stale; missing or inaccessible targets fail closed.
- Calculator observation establishes the requested visible state, not ownership
  of a newly created process. A preexisting visible Calculator can satisfy it.
  The recorded smoke run specifically observed absence before launch.
- Verification requires an interactive Windows session and process/window
  access. It does not prove future responsiveness or validate calculation UI.

Recommended next integration: connect a trusted confirmation interaction to
the existing ConfirmationAuthority for verified Notepad editing through the
existing semantic desktop gates.
