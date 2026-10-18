# Day 16: bounded orchestration and device protocol foundation

Day 16 was integrated through PR #1 and finalized as v0.016 at `abae60d`.
Day 17 adds a durable replay journal and an explicitly started, single-device TLS
Calculator receiver on `main`. Importing modules and normal VORAK startup remain
offline. Only temporary loopback listeners with mocked OS actions were exercised
during development. Day 16 and Phase 1 results below are historical; the current
MVP setup and limitations are in the Day 17 MVP section.

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

## Day 16 / Phase 1 device protocol and trust boundary (historical)

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

The receiver now requires an explicitly supplied local SQLite test journal, with
128 records by default. Identical duplicates return their existing acknowledgement;
altered reuse is denied. Claims are serialized across journal connections. Offline
tasks stay queued and expire before execution. A caller asking for approval remains
waiting; there is deliberately no message-based method to release that hold.
`requires_approval=false` never authorizes a consequential capability. Failed tasks
are not retried under the same ID. Acknowledgements expose only opaque task IDs,
queued/running/waiting/completed/failed status, verified boolean and error enum.
Completion uses the existing runtime and an additional independent observation.

Replay records survive process restarts; storage is never authority to dispatch a
queued request without authenticated redelivery. Capacity exhaustion denies new
work; records are not evicted to let old IDs execute again. No production remote
control is enabled. Pairing, authenticated transport, revocation, protected journal
provisioning and physical-device tests remain unavailable. A lost acknowledgement
should retry the same ID, never create a new operation automatically. A crash during
execution requires independent reconciliation; this phase has no retry/reset API.

## Day 17 Phase 1: offline durable replay journal (historical)

`execution/replay_journal.py` uses standard-library SQLite. The production receiver
still defaults to `UnavailableTransport` and no journal; it creates no storage.
Only the offline test harness explicitly provisions a fresh database with
`ReplayJournal.create_for_tests`. Opening existing storage uses SQLite `mode=rw`:
missing, corrupt or incompatible storage is denied, never silently reinitialized.
No listener, pairing, credential, environment enable flag or planner tool is added.

Storage is confined to `runtime/device_tests/<temporary-test-directory>/replay.sqlite3`,
under the Git-ignored runtime directory. Tests clean up their own fixtures. The
schema contains:

- `metadata`: schema version, random journal generation and fixed capacity.
- `requests`: composite primary key `(SHA-256 peer ID, canonical task UUID)`,
  canonical request SHA-256 fingerprint, expiry, state, random local claim ID and
  controlled error enum. It contains no command body, arguments, raw peer ID,
  credentials, local context, document text or backend exception message.

The peer digest is pseudonymous, not secret or authentication. Claim IDs are local
transaction ownership markers, not user consent or pairing credentials. Receipt
reconstruction exposes only task UUID, status, verified boolean and controlled
error. Detailed execution history and trusted observation evidence remain in memory;
the journal persists only the sanitized outcome of that existing observation path.

Each state change uses `BEGIN IMMEDIATE`, uniqueness constraints and a committed
transaction. SQLite uses rollback journaling (`DELETE`), `synchronous=FULL`, a
250 ms lock timeout, integrity checks and an 8 MiB file bound. Request identity,
fingerprint and expiry are immutable. A queued request is committed first, then a
single-use `running` claim is committed **before** the existing Calculator adapter
can run. Only that claim can transition to completed/failed. Completion is recorded
only after the existing runtime and independent Windows observation succeed.
Database/commit/locking failures stop the receiver with an unverified controlled
failure; there is no in-memory fallback or success acknowledgement after a failed
completion commit. A new receiver may reopen intact storage, but cannot reclaim
a previously committed execution claim.

Crash policy:

- Before a committed claim: no dispatch occurred; authenticated redelivery may
  claim an unexpired queued request. Stored requests alone are never dispatched.
- After a committed claim, including before an OS call or after its effect but
  before recording completion: retain `running` internally and return an unverified
  failed receipt (`backend_unavailable`). Never automatically dispatch it again.
  Another live owner may still finish its own claim; opening a journal does not
  rewrite or steal active claims. This receipt does not prove the OS action failed.
- Completed/failed requests stay terminal. Approval holds survive restart and
  cannot be released by changing the message flag. Expired queued/held requests
  become failed and retain their identities.

Capacity is fixed at provisioning (128 default, 1–1024 allowed). There is no
automatic pruning, TTL deletion, reset or eviction. Exhaustion denies new requests,
including when all retained requests expired. SQL triggers reject deletion, altered
bindings and terminal-state resets. Capacity recovery needs a future reviewed
peer/key-generation protocol; deleting the journal is not a supported recovery.

Limitations before pairing: SQLite does not provide exactly-once external side
effects, authenticated storage, backup rollback detection or OS isolation. A crash
can lose an action or its acknowledgement; conservative non-retry prevents a second
automatic dispatch, not ambiguity. Guarantees assume intact local storage and
trusted Python composition. Pre-existing links, reparse points and hardlinks are
rejected, and live objects pin file identity/generation, but malicious same-user
path races, restored older databases and host tampering are outside this boundary.
Windows file permissions are inherited; no dedicated private production ACL, key
store, encryption or anti-rollback provisioner was installed. Production storage
and its threat model must be reviewed before any transport is enabled. Physical
Android, real authentication and real Calculator dispatch are not tested in this
phase; all device-protocol actions are mocked.

Phase 1 validation (2026-10-18): `execution.test_device_protocol` passed all 24
tests, including separate-interpreter replay and a child process forcibly exiting
after its committed claim, concurrent receivers, expiry/approval holds, lock and
commit faults, corrupt/missing storage, capacity retention and payload privacy.
`execution.regression_suite` passed all 21 registered modules (211 execution cases,
including those 24 device cases and 15 source/export cases) plus its six validator
cases. Standalone `brain.validator` passed 6/6; `knowledge.test_source_security`
passed 15/15. These repeat checks are not additional unique tests. Compilation of
`main.py brain execution desktop knowledge tools agents skills providers` and
`git diff --check` passed. No test failures or skips were observed. No real device
or Calculator action, lifecycle transition, finalizer, commit or publication was
performed during Phase 1. The existing test module inventory and finalizer
allowlist were unchanged. Phase 2 requires separate human review.

## Day 17 MVP: explicit single-device TLS receiver

The requested continuation adds `execution/device_server.py`, a standalone-compatible
`execution/device_client.py`, and `execution/device_storage.py`. The existing runtime,
Calculator observer, journal schema/claims, security gates, source allowlists and
lifecycle are preserved. `UnavailableTransport` remains the default. Only the local
`python -m execution.device_server serve` command opens a listener; ordinary VORAK
startup, environment flags and imports do not. No service or startup task is installed.

Local pairing creates a random UUID and 256-bit secret after the operator types
`PAIR CALCULATOR`. It requires a pre-provisioned TLS certificate. Pairing information
is transferred through a trusted out-of-band channel; there is no remote pairing
route and no short-PIN authentication. Only public peer ID and certificate SHA-256
are printed. The secret stays in the private pairing file, never command-line
arguments, logs, SQLite receipts, audit exports or Git. There is one device per
installation and no silent overwrite or automatic rotation.

The client verifies the exact certificate SHA-256 pin obtained out of band before
sending a request. This is explicit pinning, not trust on first use or CA/hostname
validation. TLS 1.2 or newer provides encryption; no custom encryption is used.
HMAC-SHA256, with distinct request/response domains and constant-time comparison,
authenticates the complete request envelope and response. Each request contains a
fresh random exchange nonce; the reply binds its receipt to that exact signed
packet. The durable journal binds the authenticated peer and task UUID to canonical
command contents, so changing the nonce does not bypass replay protection.
See Python's [TLS API](https://docs.python.org/3.10/library/ssl.html) and
[HMAC comparison API](https://docs.python.org/3.10/library/hmac.html).

The server validates authentication before constructing `VerifiedDelivery`. It
then uses `DeviceReceiver`, the committed journal claim, the existing runtime and
independent Calculator observation. Pairing authorization is rechecked before the
claim and again immediately before the OS action. Revocation cannot undo an action
already executing. All other operations, extra arguments, fake approval flags,
unregistered peers and malformed messages remain denied. Client receipt validation
requires the matching task/request, a valid response MAC and consistent completed /
verified fields. HTTP success or a generic success dictionary is insufficient.

Frames are bounded to 16 KiB, command bodies to 8 KiB, with a five-second handshake
timeout and an absolute eight-second receive deadline. The single connection worker
and backlog of four bound concurrency; SQLite still serializes claims across
independent receivers. The client waits at most 45 seconds for a receipt, and never
automatically retries. Any uncertain result preserves the exact pending task.

Windows state is confined to ignored `runtime/device_receiver/`. Initialization
atomically creates an owner/SYSTEM-only directory ACL and a new journal; it refuses
an existing directory rather than repairing or resetting state. Existing ACLs,
file ownership, hardlinks and reparse points are checked; insecure state fails
closed. The Termux client uses `~/.vorak-device`, owner-only directory/file modes
and link checks. Do not put it on Android shared storage. Credentials are not
hardware-backed or encrypted at rest by this application; OS access control and
device encryption protect them. Malicious same-user code, administrator/root
access, filesystem rollback and race-proof isolation remain outside the boundary.

### Manual Windows setup (not executed during development)

Run from `C:\AI-agent` in your normal interactive Windows account. No elevation is
needed. Ensure the `runtime` parent already exists. Do not run these commands over
an untrusted remote terminal or record pairing material in a transcript.

```powershell
.\.venv\Scripts\python.exe -m execution.device_server init
```

Using an already installed OpenSSL, generate a local certificate and encrypted
private key. The Git for Windows OpenSSL location below was available for tests;
if unavailable, provision a certificate/key with a trusted tool before continuing.
No installation is performed by VORAK. Keep the key password local.

```powershell
& 'C:\Program Files\Git\usr\bin\openssl.exe' req -x509 -newkey rsa:3072 -sha256 -days 30 -subj '/CN=VORAK-local' -keyout runtime/device_receiver/server.key -out runtime/device_receiver/server.pem
```

Replace `192.168.1.10` with your Windows host's actual private LAN IPv4 address.
The address is configured locally, never supplied by the phone in a command.

```powershell
.\.venv\Scripts\python.exe -m execution.device_server pair --host 192.168.1.10 --port 8765
```

Read `runtime/device_receiver/pairing.json` only in a trusted local editor. Transfer
its secret, public peer ID and certificate pin directly to your phone over a trusted
out-of-band channel (for example, manually enter them while viewing the local
file). Do not email/upload them, use cloud-synchronized clipboards, paste them into
chat, or copy them to shared storage. Compare the pin with the Windows pairing
output. The secret is 64 hex characters, not a short PIN.

Start the listener deliberately. Without LAN options it binds only `127.0.0.1`:

```powershell
.\.venv\Scripts\python.exe -m execution.device_server serve --encrypted-key
# Physical-phone test, only after local review and deliberate LAN configuration:
.\.venv\Scripts\python.exe -m execution.device_server serve --encrypted-key --bind 192.168.1.10 --port 8765 --allow-lan
```

Use one serve command at a time; Ctrl+C stops it. Public addresses, DNS names and
wildcard binds are rejected. Use a trusted private LAN, never router port forwarding
or a tunnel. Address checks cannot detect a router forwarding an Internet connection.
No firewall rule is changed automatically; any necessary rule must be deliberately
limited by the user to the private network and intended phone. The Windows session
must support the existing Calculator observation adapter.

Revoke locally, including while the server is running:

```powershell
.\.venv\Scripts\python.exe -m execution.device_server revoke
```

Revocation persists across restart. It does not remove replay history, reset
pairing, or undo actions already executing. Stop the listener too when finished.

### Manual Vivo Y300 setup (not physically tested)

Install Termux from an official channel following the
[Termux installation instructions](https://github.com/termux/termux-app#installation),
and install its Python package yourself (`pkg install python`) if needed. These
are manual prerequisites, not dependencies installed by this change. Copy only
`execution/device_client.py` and `execution/device_storage.py` into a directory
inside Termux's private home; the client does not need the repository, cloud models,
Android Accessibility, screen capture, storage permissions or an Android Studio build.

```sh
python device_client.py pair
python device_client.py open-calculator
```

Pairing prompts for the locally chosen Windows address/port, peer ID, certificate
pin and secret (hidden entry). Credentials are saved only in private app storage.
The Calculator command persists its exact request before connecting and prints
only the authenticated, sanitized receipt. Look for `status: completed` and
`verified: true`; do not infer success from connection establishment.

This intentionally small client retains **one demonstration request**. Repeating
`open-calculator` explicitly resends that same request, with a new exchange nonce;
it never silently creates another task after an uncertain result. Its two-minute
expiry is retained. After expiry, the server rejects it. There is no general task
queue, automatic retry, pending-file reset, credential rotation or safe journal
pruning interface. Do not delete state to work around an uncertain outcome or full
journal; reconciliation and generation rotation need a separate reviewed change.

### Validation and remaining limits

Automated TLS tests use newly generated disposable certificates and keys from the
already installed OpenSSL, ephemeral loopback ports and mocked Windows operations.
No production listener, credential, firewall rule, device pairing or Calculator
window was created. Physical Android connectivity and the real phone-to-Windows
workflow remain unverified until the manual procedure succeeds.

TLS pins require manual certificate lifecycle management; this pin-only client
does not implement PKI expiry/revocation checks. Revoke a compromised pairing
immediately. SQLite cannot provide exactly-once external effects or detect restored
old backups. The capacity limit remains 128 requests, with no eviction. A local
administrator, compromised trusted process, stolen pairing secret or rooted phone
can defeat the corresponding trust boundary. A malicious network peer can consume
the bounded worker's timeout and cause denial of service; this is not an Internet
server or production availability design. Untrusted skills remain disabled.

MVP checks actually executed on 2026-10-18:

- `python -m execution.test_device_protocol`: 37 passed.
- `python -m execution.regression_suite`: passed once after implementation;
  224 execution cases across the 21 registered modules, plus six validator cases.
- `python -m brain.validator`: 6/6; `python -m knowledge.test_source_security`: 15/15.
  These cases overlap the full suite, not additional unique coverage.
- `python -m compileall -q main.py brain execution desktop knowledge tools agents skills providers`:
  exit 0. All Python commands used `.\.venv\Scripts\python.exe`.
- `git diff --check`: passed. Source pattern scan found no credential/key literals
  or personal home paths in changed files; runtime credential/journal paths are ignored.

There were no automated test failures or skips. The final existing-directory reset
guard was exercised by the full suite after its addition. Actual Win32 private-ACL
creation/read checks passed on disposable fixtures. No production listener or
physical phone was used. No dependencies were installed, no lifecycle or finalizer
allowlist was changed, and no commit, push, merge or finalizer was run.

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

## Historical Day 16 security exit and remaining limitations

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

## Historical Day 16 verification and review inventory

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

## Historical Day 16 post-merge release review — 2026-10-17

The Day 16 implementation and reviewed security corrections were
integrated into main through pull request #1 (merge commit 5df3079).

Verified scope:
- Six specialist role definitions; Research and Windows have implemented adapters.
- Fixed-source research and verified Notepad test-document workflows.
- Task-bound, in-memory completion-verification evidence.
- Default-deny device transport with no production remote connectivity.
- Untrusted skill execution remains disabled.
- Exact documentation allowlist and active lifecycle finalization guard.
- Local Windows security regression suite and source/export checks passed.

Known limitations:
- No physical Android connection or authenticated cross-device transport.
- No OS-isolated execution workers or production enclave.
- No arbitrary desktop or mobile action authorization.
- No GitHub CI run for the final correction commit.
- In-memory evidence does not protect against malicious code in the trusted process.

Day 16 lifecycle activated at version 0.015.
Target release: v0.016.
Finalization pending successful finalizer dry-run and explicit approval.
