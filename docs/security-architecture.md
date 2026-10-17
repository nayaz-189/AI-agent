# Security hardening and Windows isolation readiness

Review date: 2026-10-17. This is an implementation/review note, not a lifecycle transition.

## Baseline and scope

The working branch is `review/day15-privacy-hardening`, at
`8cb435ddb8c3ed84ca3136bef81be370c8871b79` (PR #1). Finalized main is
`8cd2076ffbf10c2cfcab98e5d9aa05e608e1b660`, version 0.015, completed Day 15.
The resumed session recovered 13 modified and 3 new source files. None of the
declined bulk test edits had occurred. Existing work was retained; test changes
were made with explicit patches after comparing the actual interfaces.

No commit, push, merge, finalization, dependency installation, security-setting
change, credential access, or external context publication was performed.

## Threat model and present trust boundaries

Untrusted inputs include planner JSON, requested arguments, backend prose,
document text, malformed success responses, and arbitrary diagnostic metadata.
Synthetic tests model research/banking requests, coding/password-file requests,
email/profile requests, forged specialist identities, screenshot instructions,
arbitrary Python/shell execution, and unauthorized exports. They perform no such
private access. Existing tests exercise forged, expired, reused and mismatched
confirmation tokens, stale documents, ambiguous controls and failed verification.

The planner proposes an action. Validation checks the registered tool and exact
arguments. Trusted runtime composition chooses the agent, confirmation policy and
postconditions. TaskExecutor sequences the operation, ExecutionRouter selects the
registered backend, and the registry/desktop gates enforce policy. Calculator
completion requires an independent observation of the recognized application.

Notepad uses an owned random test document, exact HWND/process/UIA identity,
fresh state checks, existing semantic ValuePattern operations, and three real
user prompts. ConfirmationAuthority issues a 30-second, single-use credential
bound to the exact request. `approved_step_id` is scheduling evidence only.
The exporter rereads the document and checks its digest before creating a new
file under `runtime/desktop_tests`; independent file readback must match exactly.
The executor remains independent of the application adapter.

These are application boundaries. Python modules, local handlers, installed skill
code, registry mutation and confirmation issuance are trusted in-process code.
An attacker already executing Python in this process can bypass these classes.
Separate Python processes and `python -I` do not enforce OS resource isolation.
Skill invocation, skill testing, the direct worker and the legacy name-based
capability entry point now unconditionally deny execution, before reading any
candidate path or launching a process. Installed/active labels cannot enable it.
Metadata inspection is not execution authorization. A real OS-isolated worker
and authenticated broker must be demonstrated before these paths can reopen.

## Implemented corrections

- Events use a closed per-event schema. Known action/agent names, opaque IDs,
  controlled error codes/stages, bounded counts, timestamps and selected booleans
  survive. Unknown fields, arguments, goals, result prose, titles, paths, URLs,
  tokens, condition values and exception messages do not enter stored history.
- Arbitrary textual IDs become stable hashes. This supports correlation, not
  anonymization against dictionary guessing. Generated IDs remain unchanged.
- RouteResult and StepExecutionResult retain optional typed SafeFailure values.
  Contradictory success/error/failure or explicit false outcome flags fail closed.
  Backend prose cannot impersonate a routing failure. Controlled messages preserve
  the existing Task/TaskStep string-error interfaces and recovery classification.
- Condition diagnostics drop expected/observed values. Task, failure and recovery
  exports use structural metadata. Failure evidence preserves original event IDs
  and timestamps; mutable detail dictionaries are filtered again on export.
- Skill capability audit no longer writes runtime payloads to canonical knowledge.
  It uses the same in-memory event boundary. Skill execution diagnostics omit raw
  arguments, extra payloads, stdout/stderr and exceptions. Successful arbitrary
  worker payloads are no longer public diagnostic results.
- Source discovery uses explicit project roots and reviewed nested skill folders,
  not recursive discovery of arbitrary directories. Windows reads validate the
  opened file's final path, reparse attributes and link count before reading;
  source defaults are replaced with `<default>`. AST inspection executes no code.
- External context v2 exposes project metadata, approved source paths and counts,
  not canonical prose or runtime logs. Both context and manifest receive closed
  schema validation in addition to SHA-256 checking. A matching hash is neither
  a privacy guarantee nor an authenticated publisher signature.

The legacy key redactor remains for compatibility but is not a security boundary.
Execution inputs necessarily exist in live task/session memory; sanitized exports
do not erase them from memory. Existing historical artifacts/canonical records
were not deleted or rewritten. Internal project context/bridge data remains
private; only the restricted external schema is suitable for publication.

## Broker contract and next isolation milestone

The existing `skills/capability_protocol.py` now also defines an immutable v2
BrokerRequest and BrokerResponse. Requests contain an opaque request ID, one of
two existing workflow capability names, an opaque resource ID and an action
digest. Paths, arbitrary code, caller identity strings, permissions and approval
tokens are not accepted. The digest and resource ID are claims, not authority.

`preflight_isolated_request` in the existing broker parses the contract and
**always denies execution** because an authenticated isolated worker does not
exist. Replaying a request remains denied. No live replay protection, resource
ownership service, authenticated IPC, specialist identity or OS sandbox is
claimed by these contract tests. Existing desktop workflows were not migrated.

Recommended first worker: a small headless AppContainer process performing one
bounded deterministic text/hash operation on an explicitly supplied synthetic
buffer. Do not start with host desktop automation. AppContainer provides resource
and process/window isolation, which makes broad host UI automation a poor first
fit. Capability and ACL configuration still require tests; AppContainer is not
a blanket guarantee of zero reads of every system file.
[Microsoft AppContainer documentation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation).

Implementation sequence and planning estimates (not commitments):

1. 1-2 days: define specialist capability policy, resource ownership, bounded IPC
   frames and request lifetime. Keep authorization decisions outside the model.
2. 3-5 days: build a native AppContainer launcher with no network capabilities,
   explicit read-only runtime dependencies, a dedicated fixture directory, a Job
   Object, bounded resources, and no inherited privileged handles. SDK/toolchain
   installation and any ACL changes require separate approval.
3. 2-4 days: authenticate IPC peers using OS-established process/token identity
   and pipe ACLs; map verified identities to policy, never accept a JSON agent
   name as identity. Bind resources to caller/session. Atomically consume request
   nonces and exact-action approvals; reject retries across broker restarts unless
   a designed durable replay store exists. Independently verify worker output.
4. 2-3 days: prove isolation using synthetic denied files, network endpoints,
   peer-agent handles, policy files, replay/crash/race and resource-exhaustion
   tests. Verify denied access at the OS boundary, not just a mocked Python gate.
5. Only after evidence: decide whether a dedicated desktop worker is viable.
   Retain the current owned-document restrictions until it is demonstrated.

A restricted token alone needs correct restricting SIDs and ACLs; Microsoft also
warns against sharing the default desktop. A dedicated user adds account/ACL and
credential provisioning work. A VM has stronger separation and more operational
cost. Windows Sandbox availability depends on the Windows edition; verify its
requirements before selecting it. Host inventory is intentionally excluded from
publishable project documentation.
[Restricted token documentation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken),
[Windows Sandbox requirements](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/).

## VBS/TEE feasibility boundary

Read-only host findings remain local and are not included in this publication
candidate. Enabled VBS/HVCI and a positive `IsEnclaveTypeSupported` result are
different checks; neither proves a signed enclave can be built, loaded, called or
attested. No enclave implementation, signing or attestation test exists here.
Validate the current OS, SDK, compiler and signing requirements separately before
an approved proof of concept. Do not change host security settings for this review.
[VBS enclave requirements](https://learn.microsoft.com/en-us/windows/win32/trusted-execution/vbs-enclaves),
[Enclave support API](https://learn.microsoft.com/en-us/windows/win32/api/enclaveapi/nf-enclaveapi-isenclavetypesupported),
[DeviceGuard/HVCI fields](https://learn.microsoft.com/en-us/windows/security/hardware-security/enable-virtualization-based-protection-of-code-integrity).

A genuine integration needs a native host and enclave DLL, enclave-specific build
and import bindings, a valid signing pipeline, bounded marshaling, enclave load/
call tests, and measured performance. Allow roughly 1-2 weeks for an initial
signed proof of concept after toolchain/signing approval, followed by separate
security review. Do not disable code integrity or ship a debuggable enclave.
[Microsoft development guide](https://learn.microsoft.com/en-us/windows/win32/trusted-execution/vbs-enclaves-dev-guide).

Candidate uses: narrow signing/key operations, wrapping a long-lived memory key,
bounded sensitive computations, and authorization signatures over an authenticated
approval, exact digest, caller, resource, nonce and expiry. An enclave cannot prove
that a human approved a forged host UI event. Attestation requires a verifier,
identity/update policy, fresh challenges and verified trust roots; none exists
here. Desktop, browser and file adapters belong in restricted workers, not inside
an enclave. No enclave, TPM key or attestation key was created in this review.

Credential strategy: use user-scoped DPAPI for local at-rest secrets only where
its same-user threat model is adequate; avoid machine scope for user secrets.
Prefer non-exportable TPM-backed CNG keys for appropriate signing operations,
subject to provisioning and recovery design. Windows Hello can supply user
verification in a designed authentication flow; it does not turn a Python worker
into a TEE. A TPM protects key operations; an enclave protects a narrow computation;
a sandbox restricts process access; a broker decides authorization; a planner only
proposes work. Cryptographic authorization authenticates a bound decision but does
not itself enforce filesystem or desktop isolation.
[DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata),
[Windows TPM use](https://learn.microsoft.com/en-us/windows/security/hardware-security/tpm/how-windows-uses-the-tpm),
[CNG providers](https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers).

## Remaining limitations and readiness

- Same-user malicious code is not OS-isolated. Skill execution/testing is disabled.
  Specialist adapters are reviewed host code, not untrusted autonomous processes.
  Python access controls are not a TEE. Real authenticated broker IPC is absent.
- The publication copier now holds Windows directory/file handles, rejects
  redirection and multiple hard links before IO, validates an in-memory snapshot,
  opens both destinations before writing, and independently rereads the output.
  Real synthetic link/race tests cover these checks. Two-file replacement is not
  atomic: a write failure may leave a partial pair, but cannot report success.
  No actual external publication was performed.
- The non-Windows index read fallback lacks the Windows final-handle checks;
  this review's filesystem evidence is Windows-specific.
- The earlier Notepad attempt stopped at its first permission prompt. That result
  was not success. The subsequent Day 16 report test exposed and fixed CR/LF text
  preparation, then completed all three real approvals and independent file
  verification. See the current Day 16 report for the full result and limitations.
- The real Calculator check started with no recognized Calculator window,
  completed through the runtime, and passed an additional independent observation.
  `runtime/calculator_smoke.json` is older Day 14 evidence, not this run's result.
- Day 15 is already completed. The normal finalizer dry-run was not invoked:
  this branch is not main and this document is not on the finalizer's exact
  documentation allowlist. No lifecycle records or allowlist were broadened.

The changes require human code review, not an unconditional security or isolation
sign-off. The approved live Notepad report check is now complete. Do not
finalize another version against an already completed lifecycle without the normal
process. The finalizer now requires a fixed, bounded security regression subprocess
in addition to compilation; regression failures prevent lifecycle/Git mutations.
See [Day 16 integration](day16-integration.md) for the current tests and inventory.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import runpy; [runpy.run_module('execution.'+p.stem, run_name='__main__') for p in sorted(Path('execution').glob('test_*.py'))]"
.\.venv\Scripts\python.exe -m brain.validator
.\.venv\Scripts\python.exe -m knowledge.test_source_security
.\.venv\Scripts\python.exe -m compileall -q main.py brain execution desktop knowledge tools agents skills providers
git diff --check
git status --short
```

Earlier review execution: **153/153 cases passed across 17 test modules**, including 25
new cases (10 privacy, 5 broker contract, 10 source/export). Validator: **6/6**.
Standalone source/export rerun: **10/10**, the same cases already counted in the
153, not additional unique tests. Compilation and `git diff --check`: exit 0.
Automated failures/skips: **0/0** in the final runs. An earlier diagnostic run
found three stale verification-message assertions; these now check the exact
controlled verification error and pass. No assertions were relaxed to accept a
failed operation as success.

The in-memory source index contained **148 Python files, 0 parse failures**;
the source test confirms every tracked Python file remains discoverable.
Read-only finalizer classification returned **34 source paths, 0 blocked paths,
1 unknown path: `docs/security-architecture.md`**. The normal finalizer dry-run
was not run, for the lifecycle/branch/documentation reasons above. Native enclave
loading/attestation, OS sandbox isolation and authenticated broker IPC tests were
not executed because those implementations do not exist.

The execution harness includes the source/export tests via
`execution/test_source_security.py`. These are the project's plain assertions;
no pytest dependency was installed. Results and the exact changed-file inventory
follow. No private payloads are persisted to produce test evidence.

## Earlier security-only inventory (superseded by the Day 16 inventory)

27 modified files (relative to the existing PR head):

| Files | Responsibility |
|---|---|
| `execution/condition_evaluator.py` | Remove condition values from diagnostics |
| `execution/execution_history.py` | Closed event schema, evidence time and identity |
| `execution/execution_router.py` | Typed failures, strict result normalization |
| `execution/failure_analyzer.py` | Controlled routing classification |
| `execution/failure_report.py` | Sanitized bounded evidence and typed failure |
| `execution/recovery_planning_request.py` | Structural recovery request export |
| `execution/recovery_proposal.py` | Structural recovery proposal export |
| `execution/runtime.py` | Controlled plan-validation error |
| `execution/task.py` | Safe task diagnostics and export |
| `execution/task_executor.py` | Typed execution failures and verified result handling |
| `execution/task_step.py` | Safe step diagnostics and export |
| `execution/test_execution_history.py` | Assert closed schema rather than raw details |
| `execution/test_execution_router.py` | Assert controlled typed error |
| `execution/test_failure_analyzer.py` | Controlled routing-message compatibility |
| `execution/test_failure_report.py` | Assert approved action identity and error |
| `execution/test_recovery_pipeline.py` | Exercise actual missing routing backend |
| `execution/test_runtime_integration.py` | Structural observation and verification errors |
| `execution/test_security_review.py` | Assert absence of goals/arguments |
| `execution/test_task_execution_history.py` | Assert omission of arguments |
| `knowledge/external_context_exporter.py` | Closed external metadata views |
| `knowledge/publication_manager.py` | Context and manifest privacy checks alongside hashes |
| `knowledge/source_indexer.py` | Explicit discovery and checked Windows reads |
| `skills/capability_audit.py` | In-memory structural capability audit |
| `skills/capability_broker.py` | Non-executing, default-deny v2 contract entry point |
| `skills/capability_protocol.py` | Typed request/response and safe rejection text |
| `skills/execution_gate.py` | Omit raw capability diagnostics |
| `skills/runtime_manager.py` | Safe worker output and malformed-result rejection |

8 new files:

| File | Responsibility |
|---|---|
| `docs/security-architecture.md` | This review, evidence and implementation roadmap |
| `execution/audit_schema.py` | Per-event diagnostic allowlists |
| `execution/safe_failure.py` | Error enum, typed failure and controlled messages |
| `execution/test_broker_contract.py` | Five contract/adversarial policy tests |
| `execution/test_privacy_hardening.py` | Ten privacy and failure regressions |
| `execution/test_source_security.py` | Include source tests in the existing harness |
| `knowledge/public_context_schema.py` | Closed context and manifest schemas |
| `knowledge/test_source_security.py` | Ten synthetic source/export regressions |

Desktop security gates, confirmation authority, Windows configuration and canonical
lifecycle files remain unchanged. Subsequent integration adds a fixed composite
tool and a finalizer regression gate; the current inventory is in the Day 16 document.
