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

## Day 15: secure document workflow (2026-10-16)

Recovery found Day 15 already active (`development`, finalized version `0.014`).
The existing `document_session.py` and `test_file_store.py` were preserved and
completed. No lifecycle records, credentials, canonical history, or external
project context were rewritten. The earlier Day 14 lifecycle warning above is
historical; it does not describe the current lifecycle.

### Request and execution flow

The interactive runtime accepts:

> Open Notepad, write a short introduction about artificial intelligence, export it into my approved AI Agent test folder, and verify the saved content.

The earlier wording, "save it to an approved test file", also remains supported.
The existing planner fast route recognizes these specific requests locally,
without a model call. Its registered `write_test_introduction` intent takes no
arguments: a model cannot supply executables, paths, text, tokens, or handlers.
The existing validator rejects additional fields and arguments. Direct registry
execution and routing through another specialist agent cannot run this intent.

After validation, runtime composes four ordinary TaskSteps:

1. `open_test_document`: create a unique empty seed file and launch the fixed
   Windows Notepad executable with that file as its sole argument.
2. `set_value`: require the owned editor to remain empty, confirm the exact text
   change, and reuse the existing semantic ValuePattern operation.
3. `export_test_document`: reread the owned editor, require exact content equality,
   obtain export approval, then write those observed bytes to a new confined file.
4. `verify_test_file`: independently reopen and verify the resulting UTF-8 file.

TaskExecutor, ExecutionRouter, Task, and TaskStep are reused without adding
application logic to the execution engine. Boolean preconditions/postconditions
are independently observed between steps. Failure stops the task; there is no
automatic recovery, retry, approval, or fallback to keyboard/mouse input.

### Authorization and targeting

`confirmation_ui.py` supplies an actual local Windows application permission
dialog for each launch, edit, and export. It displays the complete exact request,
defaults to No, and times out after 60 seconds. Only a Yes response reaches the
existing UserConfirmationBoundary. That boundary issues a 30-second token through
ConfirmationAuthority. DesktopExecutionGate checks policy, consumes the exact
single-use token, and invokes DesktopActionGate for fresh technical validation.
Tokens are issued after the user responds. Noninteractive runtime calls with no
confirmation UI fail before launching anything. Planner flags and
`approved_step_id` cannot substitute for a token.

The Notepad adapter uses a random session filename, a visible non-minimized
window, a trusted system/package process path, and one visible enabled editor.
Its binding includes the HWND, process ID, UIA runtime ID, control handle,
automation ID, class, and control type. Wrong windows, multiple windows/editors,
changed identities, password controls, read-only editors, and missing ValuePattern
fail closed. Reacquisition restricts the existing semantic controller to this
single bound editor. UIA's accessible name and ValuePattern text can differ;
scoped descriptors now supply the actual value. Other discovery paths do not
gain broad value-reading behavior. Exact session-level comparisons also reject
extra newlines even where legacy semantic comparisons normalize text.

### Confined export and privacy

Only `C:\AI-agent\runtime\desktop_tests\` is used. It must already exist as a
normal directory. The store opens and holds every ancestor directory without
delete sharing, rejects reparse points, creates random owned files with
CREATE_NEW, and holds file handles that prevent other writers or replacement
during verification. Existing files, traversal, alternate streams, arbitrary
names, and destination substitutions are rejected. Readback uses a separately
opened handle, checks file identity/size, and compares exact UTF-8 bytes.

The output is `ai_introduction_<session-id>.txt`; its corresponding
`input_<session-id>.txt` is the empty seed. Export is **not Notepad's native Save**.
The edited Notepad tab remains unsaved. Test files and the tab are retained; the
workflow does not delete files or close applications automatically.

Runtime history remains in memory. Task arguments contain only an opaque session
ID, observations contain booleans, and backend results contain verified status.
Raw text, UI descriptors, tokens, filesystem exceptions, and request contents are
not copied into history. The demonstration does not send local document content
to a model, take screenshots, inspect browsers, or access unrelated files.

### Changes and security review

New files: `desktop/document_session.py` (Notepad adapter),
`desktop/test_file_store.py` (confined file IO), `desktop/confirmation_ui.py`
(local consent), `execution/document_workflow.py` (task composition),
`execution/notepad_smoke.py` (interactive smoke entry point), and
`execution/test_document_workflow.py` (plain assertion tests).

Modified files: `brain/fast_router.py`, `tools/tool_registry.py`,
`execution/runtime.py`, `main.py`, `desktop/desktop_execution_gate.py`,
`desktop/action_gate.py`, `desktop/consequence_policy.py`,
`desktop/semantic_controller.py`, `desktop/semantic_target_resolver.py`, and this
document. No finalizer allowlist expansion was necessary.

Review also found that the existing semantic-result helper could accept a
truthy nonboolean success flag or a contradictory error alongside success.
It now requires explicit boolean success/verification/execution and no error.
Focused regressions cover that case. Existing general launches and browser tools
retain their Day 14 confirmation blocking; this workflow cannot borrow them.

### Executed validation

All commands use the existing `.venv`; no dependencies were installed.

```powershell
.\.venv\Scripts\python.exe -m execution.test_document_workflow
.\.venv\Scripts\python.exe -c "from pathlib import Path; import runpy; [runpy.run_module('execution.'+p.stem, run_name='__main__') for p in sorted(Path('execution').glob('test_*.py'))]"
.\.venv\Scripts\python.exe -m brain.validator
.\.venv\Scripts\python.exe -m execution.notepad_smoke
.\.venv\Scripts\python.exe -c "import json; from execution.runtime import execute_command; t=execute_command('Open Calculator'); print(json.dumps({'verified': t.status.value == 'completed', 'status': t.status.value})); raise SystemExit(0 if t.status.value == 'completed' else 1)"
```

The first focused run passed 26/26. After additional review cases and the
semantic-result fix, the full suite passed **126/126 cases across 14 modules**:
53 original cases, 20 runtime cases, 20 Day 14 security cases, and 33 document
workflow cases. Validator checks passed **6/6**. Tests include actual confined
file creation/readback in addition to synthetic UI/consent fixtures. Tests never
automatically answer the production confirmation dialog.

The real Windows Notepad smoke returned exit code 0 and:

```json
{"verified": true, "status": "completed", "steps": [{"action": "open_test_document", "status": "completed"}, {"action": "set_value", "status": "completed"}, {"action": "export_test_document", "status": "completed"}, {"action": "verify_test_file", "status": "completed"}]}
```

This run used the real UI, real confirmation dialogs, semantic mutation, and
independent file readback. A subsequent real Calculator run also returned
`{"verified": true, "status": "completed"}`. The prior
`runtime/calculator_smoke.json` was inspected as historical Day 14 evidence and
was not rewritten or used as a substitute for the new run.

Final quality commands also executed successfully:

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py brain execution desktop tools
git diff --check
git status --short
.\.venv\Scripts\python.exe dev.py finalize --dry-run
```

The dry-run reported Day 15, current version `0.014`, target `0.015`, and
**16 approved source paths** with no blocked or unknown files. Core/context
repository synchronization, compilation, and dependency checks all passed.
No allowlist change, lifecycle transition, staging, commit, push, actual
finalization, or knowledge publication was performed. Day 15 is ready for
user-authorized finalization within the bounded scope and limitations below.

### Remaining limits and next development task

- These are application-level boundaries. Python adapters, registry, and UI
  callback are trusted code, not isolated agent processes. Malicious local code
  running as the user could bypass them or synthesize native UI messages.
- The permission dialog is an application prompt, not a secure Windows desktop
  or an authenticated identity check. Nothing claims complete personal-data
  isolation while running in the user's normal Windows session.
- Application identity trusts protected Windows/package locations, not fresh
  executable signature verification. UIA identity and state checks reduce stale
  targeting but cannot make observation and mutation atomic against concurrent
  user/application changes. The document must remain undisturbed during a run.
- Support is deliberately limited to the owned Notepad test document and fixed
  introduction. Localized title formats, unsupported UIA providers, missing
  approved directories, minimized windows, and inaccessible controls fail closed.
- Native application save, arbitrary document opening, and arbitrary content or
  path generation are not capabilities of this milestone. Notepad manages its
  own application state; the agent does not inspect restored unrelated tabs.
- File identity/content verification establishes the state at completion, not
  future durability against changes after handles are released.

Next: design a separate least-privilege desktop broker with an authenticated
approval channel before adding more specialist agents or desktop capabilities.
Extend the existing adapter contract and tests rather than adding another engine.

For beginners: an adapter translates a common operation into application-specific
calls; a precondition describes what must be true before acting; a postcondition
checks what actually became true afterward. A confirmation token is a temporary,
single-use permission bound to one exact request. Holding an OS file handle is
stronger than checking a path string alone because it can prevent replacement
while the operation runs. Mocked tests exercise failures safely; live tests prove
that the real Windows/UIA/file integration works on this machine.
