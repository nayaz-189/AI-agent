# Day 16: bounded orchestration and device protocol foundation

This implementation sits on the existing review branch and completed Day 15 / 0.015
lifecycle. No lifecycle transition, commit, push, merge, finalizer, installation or
Windows security change was performed. It is a review candidate, not a new stable release.

## Operational workflow

Start the existing `main.py` with the project's virtual environment and enter:

> Research Python AST and pathlib, summarize the findings, and save an approved report.

The existing planner's exact local fast route produces `research_and_save_report`
with no arguments. Validator and tool registry reject extra agent identities,
permissions, URLs, paths, approval tokens and shell commands. Other commands keep
their existing planner/model abstraction; no new model SDK is introduced.

`execute_orchestration` derives specialists from trusted workflow requirements.
Calculator and the introduction need Windows alone; the research report needs
Research and Windows. The six role names have immutable capability sets, but only
Research and Windows have implemented adapters. No role or capability comes from
model output. These are logical specialists in one trusted process, not sandboxed
workers or six independently running LLMs. The deterministic security policy remains
outside models. There is no generic specialist-code execution or arbitrary delegation.

The report task has two routed steps:

1. Research fetches the Python 3.10 AST and pathlib documentation concurrently.
   HTTPS, exact fixed URLs, no redirects/cookies/proxies, a 15-second socket timeout
   and a 2 MB response bound restrict this adapter. It sends no local context.
   Reviewed summary sentences are emitted only after source anchors are found.
   Downloaded prose is data, never instructions. This is a bounded technical demo,
   not general web research or a semantic truth-checker. Source drift fails closed.
2. Windows passes that report to the existing owned-document session. TaskExecutor
   and ExecutionRouter run open, semantic edit, confined export and file verification.
   All three mutations still require real local Yes/No prompts. Existing 30-second,
   single-use, exact-action confirmation tokens and fresh UI checks apply. The
   output path remains `runtime/desktop_tests`; the Notepad tab may remain unsaved.

The live test exposed a Notepad RichEdit representation difference: its ValuePattern
returned CR line breaks for the LF report proposal. The adapter now prepares CR
breaks before requesting consent and binding the digest. Observations are never
trimmed or normalized; an added newline or wrong representation still fails exact
verification. Other Notepad implementations that represent text differently will
stop safely rather than silently relax that requirement.

The parent checks child completion and independent document/file observation
evidence. A successful tool return or forged completed child with no evidence is
insufficient. Failure stops later steps; recovery must construct a newly validated
task. `completion_report` returns only task ID, status, selected roles, verified
boolean and controlled error. Report text, URL responses, UI identity, tokens and
local paths are excluded from history.

## Capability status

| Role | Implemented capabilities | Unavailable |
|---|---|---|
| Research | Two fixed public Python documentation sources | Arbitrary URL/search, local context upload |
| Windows | Existing Calculator, confirmed owned Notepad introduction/report export | General keyboard, mouse, shell, browser/profile or filesystem control |
| Coding | None | Execution/testing until genuine OS isolation is proved |
| Android | Protocol interfaces only | Physical mobile operations and live transport |
| Communication | None | Gmail/WhatsApp account integration or message sending |
| Memory | None | Ultimate Memory retrieval until ownership/scope is defined |

Banking, payments, credentials, OTPs, personal email, private browsing and unrelated
files have no capabilities in these workflows. The existing broader browser tools
remain blocked by their existing confirmation policy; this work adds no browser approval.

## Device protocol and trust boundary

`execution/device_protocol.py` defines strict version-1 JSON parsing, canonical UUID
task/peer IDs, exact argument shape, a five-minute maximum lifetime and registered
operations. In this slice the only remotely dispatchable operation is Calculator
on Windows. Android is recognized as a destination but denied as unavailable.
Extra fields and duplicate JSON keys fail closed. No network endpoint is created.

`AuthenticatedTransport.receive_verified()` is a trusted adapter interface, not
an authentication mechanism. Production defaults to `UnavailableTransport`, which
delivers nothing. The test-only `MockAuthenticatedTransport` represents a channel
that already authenticated a peer. Claimed `source_device` must match that channel
identity and a locally registered peer. A model cannot register a device through
the tool registry. Constructing a Python delivery object is not cryptographic proof.

The receiver records at most 128 tasks in memory. Identical duplicates return their
existing acknowledgement; altered reuse is denied. Dispatch is serialized. Offline
tasks stay queued and expire before execution. A caller asking for approval remains
waiting; there is deliberately no message-based method to release that hold.
`requires_approval=false` never authorizes a consequential capability. Failed tasks
are not retried under the same ID. Acknowledgements expose only opaque task IDs,
queued/running/waiting/completed/failed status, verified boolean and error enum.
Completion uses the existing runtime and an additional independent observation.

This replay store is process-local and has no restart durability. Capacity exhaustion
denies new work; records are not evicted to let old IDs execute again. No production
remote-control claim is made. A real adapter must remain disabled until authenticated
pairing, durable replay/idempotency, revocation, crash recovery and physical-device
tests exist. A lost acknowledgement should retry the same ID, never create a new
operation automatically. A crash during execution requires independent reconciliation.

## Kotlin companion architecture (design only)

The Vivo Y300 has not been connected, inventoried or tested. Select SDK versions
after checking the actual device and current Android requirements. Do not infer
hardware-backed key support from its model name.

Suggested Kotlin modules:

- `protocol`: sealed operation types and strict serializer matching the envelope;
  no shell, generic URI, filesystem path, arbitrary intent or executable payload.
- `pairing`: explicit pairing on both devices, short-lived challenge, visible key
  fingerprint comparison, per-device capability grants, revocation and key rotation.
- `transport`: authenticated TLS channel, fixed endpoint, bounded frames, peer identity
  from the channel, signed task digest/nonce/expiry, never trust JSON identity alone.
- `queue`: private local journal with task IDs and atomic state transitions; retry
  delivery idempotently, expire before execution and reconcile uncertain outcomes.
- `approval`: exact action, peer, resource, digest and expiry shown after unlock;
  user denial or timeout stops the operation. No lock-screen bypass or background consent.
- `capabilities`: initially status/acknowledgement and companion-owned UI only; Android
  execution remains disabled until each handler and permission is reviewed.

Use Android Keystore for device keys; hardware-backed availability must be checked
at runtime and is not guaranteed. Keystore is not a general application sandbox.
[Android Keystore](https://developer.android.com/privacy-and-security/keystore).
Disable cleartext traffic and keep production trust configuration separate from
debug certificates. Mutual peer authentication still needs its own implementation.
[Network security configuration](https://developer.android.com/privacy-and-security/security-config).

Use WorkManager for deferrable, network-constrained queue synchronization with
bounded backoff. It respects OS scheduling and power constraints; it does not promise
instant background delivery. Foreground user actions may dispatch immediately while
visible. A future push service should carry only an opaque wake-up hint; retrieve
and authenticate the task separately. No push account or service was configured.
[WorkManager](https://developer.android.com/develop/background-work/background-tasks/persistent).

Request `POST_NOTIFICATIONS` contextually where required (Android 13+). Show only
generic pending-task information until the app is unlocked. Notification denial
must leave tasks available in-app, not prompt a permission bypass. Notification
posting does not require reading other apps' notifications.
[Notification permission](https://developer.android.com/develop/ui/compose/notifications/notification-permission).

No Accessibility service, notification listener, SMS, contacts, microphone, screen
capture, broad storage, personal browser integration or banking interaction belongs
in the default manifest. No APK, Kotlin build, permission request or phone installation
was performed in this milestone.

## Security exit and remaining limitations

Skill execution, testing, direct worker imports and name-based capability invocation
now deny before candidate IO/process launch. A real subprocess test uses a malicious
synthetic fixture and proves it is never imported. This demonstrates the restriction,
not OS isolation. Host Python code, registry composition, confirmation issuance and
test injection seams remain trusted. A malicious same-user process is outside this
application boundary. Do not run untrusted Python in it.

Audit events and failure/recovery exports use closed schemas. The skill-test display
also refuses backend text. Source indexing excludes temporary worktrees and checks
opened Windows file identity/link attributes. External publication validates closed
schemas and hashes under held handles, rejects link redirection, and independently
checks copied bytes. The two output files are not an atomic transaction; a failure
may leave a partial pair but cannot be reported successful. No external publication
occurred. The non-Windows source fallback does not provide equivalent race protection.

Strict publication JSON parsing also rejects duplicate keys: otherwise a private
value could hide behind a later allowed value while the raw bytes were published.
A matching hash cannot detect that privacy error. Synthetic tests exercise both
manifest and context duplicates, including a recomputed matching digest.

The finalizer now runs `execution.regression_suite` with a 180-second timeout, in
addition to compilation. Its explicit module list must equal discovered execution
tests; optimized Python and missing/unreviewed test modules fail closed. Tests cover
compile-success/security-failure, timeout and subprocess errors before mutation.
The runner does not discover candidate skill tests. No finalizer was run here.

The completed Day 15 lifecycle and review branch are preserved. These new documents
are not added to the finalizer's exact documentation allowlist. Human review/approved
integration should precede a normal next-day lifecycle transition; do not edit
canonical lifecycle records or weaken blocked-path checks to force finalization.

## Verification and review inventory

Final automated results: **189 passing execution cases across 21 modules**, with
**0 final failures and 0 skips**. This comprises 186 named test functions plus the
three procedural cases in `test_task_executor.main`; counting only `test_*`
functions incorrectly reports 186. Validator tests: **6/6**. The 15 source/export
cases are included in 189 and also passed as a standalone run; they are not 15
additional unique tests. No pytest dependency was installed.

Commands actually executed:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import runpy; [runpy.run_module('execution.'+p.stem, run_name='__main__') for p in sorted(Path('execution').glob('test_*.py'))]"
.\.venv\Scripts\python.exe -m execution.regression_suite
.\.venv\Scripts\python.exe -m brain.validator
.\.venv\Scripts\python.exe -m knowledge.test_source_security
.\.venv\Scripts\python.exe -m execution.test_document_workflow
.\.venv\Scripts\python.exe -m execution.test_orchestrator
.\.venv\Scripts\python.exe -m execution.test_device_protocol
.\.venv\Scripts\python.exe -m execution.test_skill_isolation
.\.venv\Scripts\python.exe -m compileall -q main.py brain execution desktop knowledge tools agents skills providers
git diff --check
```

The final complete suite was also run through the same per-module `runpy` loop
with in-memory output capture and per-module counts. The fixed finalizer regression
runner passed after the final code changes. Compilation and diff whitespace checks
returned exit 0. An in-memory source index found **156 Python files, 0 parse failures**.

Real Windows results:

- Calculator: runtime completed and a subsequent independent observation was true.
- Report: both fixed public pages fetched and validated; a 490-character report
  went through the real planner, orchestrator, Notepad and three user-approved
  dialogs. The final task completed with `verified=true` and four successful
  independent file observations. This was actual UI/file IO, not mocks or a
  successful tool return alone. Runtime history stayed in memory.
- Two earlier report attempts failed before export; the user had approved opening
  and editing but never received an export prompt. A diagnostic retry established
  that semantic mutation succeeded but exact content verification failed. A scoped
  read of the owned document proved CR/LF representation was the cause. The adapter
  fix and strict regression preceded the successful final attempt.
- One new negative-test fixture initially attempted to complete unfinished steps.
  The fixture was corrected to use valid task transitions; its assertion still
  requires rejection of completed-child status without observation evidence.
- Physical Android, real authenticated transport, enclave loading/attestation and
  OS worker isolation tests were **not executed**; their implementations do not exist.

All **53 candidate files** were scanned for key/token patterns, personal home paths,
email literals and unexpected artifact types. The only pattern hit was the existing
synthetic `test@example.com` fixture. No real secret or personal host inventory was
identified in the candidate files. Pattern scanning is not a mathematical guarantee
against secrets. Runtime fixtures, credentials, private profiles, generated knowledge
and local environment inventory are excluded. No actual publication occurred.

Read-only finalizer classification: **51 source candidates, 0 blocked paths, 2
unknown documentation paths** (this document and `security-architecture.md`). Its
exact allowlist was not broadened. The real finalizer and its dry-run were not
invoked. Ready for review-branch commit/publication approval within the documented
scope; not ready to claim OS-isolated agents or physical remote control. Integration
with main and lifecycle advancement require separate approval and normal lifecycle
commands. Nothing is staged, committed, pushed or merged by this work.

Next milestone: implement and review explicit two-device pairing, authenticated
transport and a durable replay journal; then test the single Calculator capability
on both physical devices. Keep mobile mutations, coding workers, communication and
memory disabled until their own scoped boundaries are proved.

### Exact uncommitted inventory

36 modified files:

```text
brain/fast_router.py
desktop/document_session.py
execution/condition_evaluator.py
execution/execution_history.py
execution/execution_router.py
execution/failure_analyzer.py
execution/failure_report.py
execution/recovery_planning_request.py
execution/recovery_proposal.py
execution/runtime.py
execution/task.py
execution/task_executor.py
execution/task_step.py
execution/test_document_workflow.py
execution/test_execution_history.py
execution/test_execution_router.py
execution/test_failure_analyzer.py
execution/test_failure_report.py
execution/test_recovery_pipeline.py
execution/test_runtime_integration.py
execution/test_security_review.py
execution/test_task_execution_history.py
knowledge/context_repo_publisher.py
knowledge/development_finalizer.py
knowledge/external_context_exporter.py
knowledge/publication_manager.py
knowledge/source_indexer.py
main.py
skills/capability_audit.py
skills/capability_broker.py
skills/capability_protocol.py
skills/execution_gate.py
skills/runtime_manager.py
skills/skill_worker.py
skills/test_runner.py
tools/tool_registry.py
```

17 new files:

```text
agents/research_agent.py
docs/day16-integration.md
docs/security-architecture.md
execution/audit_schema.py
execution/device_protocol.py
execution/orchestrator.py
execution/regression_suite.py
execution/safe_failure.py
execution/test_broker_contract.py
execution/test_device_protocol.py
execution/test_finalization_gate.py
execution/test_orchestrator.py
execution/test_privacy_hardening.py
execution/test_skill_isolation.py
execution/test_source_security.py
knowledge/public_context_schema.py
knowledge/test_source_security.py
```
