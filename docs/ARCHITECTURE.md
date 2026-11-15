# VORAK — Architecture

**Status: Proposed / evolving architecture.** This document describes the intended system boundaries and data flow. Reconcile it with the implementation as modules are built.

## 1. Architectural objective

VORAK is intended to be a modular personal AI system. It coordinates user interaction, task planning, model selection and tool execution through one orchestrator.

The recommended initial architecture is a **modular monolith**: one application with clear internal boundaries. Avoid splitting the system into microservices until independent deployment or scaling is justified.

## 2. High-level component diagram

~~~mermaid
flowchart TB
  subgraph UX[Interaction]
    TEXT[Text interface]
    VOICE[Voice interface]
    SCREEN[Optional screen context]
  end
  TEXT --> CORE
  VOICE --> CORE
  SCREEN --> POLICY
  subgraph CORE[VORAK Core]
    INTENT[Intent normalization] --> PLAN[Task planner] --> STATE[Task state manager] --> POLICY[Permission and policy gate]
    POLICY --> ROUTER[Model router] --> RESULT[Result synthesis]
  end
  subgraph MODELS[Model providers]
    LOCAL[Local provider: Ollama]
    CLOUD[Cloud model APIs]
    LIVE[Realtime voice provider]
  end
  ROUTER --> LOCAL
  ROUTER --> CLOUD
  VOICE <--> LIVE
  LOCAL --> RESULT
  CLOUD --> RESULT
  subgraph TOOLS[Tool adapters]
    DESKTOP[Desktop automation]
    WEB[Web research]
    FILES[File and workspace operations]
    DEV[Developer tools]
  end
  POLICY --> TOOLS
  TOOLS --> RESULT
  RESULT --> AUDIT[Execution log and user-facing status]
~~~

The diagram is a target design. It does not assert that all adapters or providers are currently present.

## 3. Component responsibilities

| Component | Responsibility |
|---|---|
| Interaction layer | Accept text and voice input; present plans, approvals and results. |
| Intent normalizer | Convert raw input into a structured request with constraints. |
| Task planner | Produce ordered steps, dependencies and expected outcomes. |
| Task state manager | Track pending, running, completed, failed and cancelled steps. |
| Permission / policy gate | Check user approval, scope and risk before tool execution. |
| Model router | Select a provider/model based on task needs, availability, latency and cost. |
| Provider adapters | Normalize provider-specific request/response formats. |
| Tool adapters | Expose narrow, typed operations for desktop, web, files and developer workflows. |
| Result synthesizer | Summarize outputs, partial completion and errors without hiding failures. |
| Audit / observability | Record task IDs, tool names, approvals, timings and outcomes without logging secrets. |

## 4. Recommended task lifecycle

1. **Receive:** accept a user request and assign a task identifier.
2. **Normalize:** identify intent, constraints, requested outcome and ambiguity.
3. **Plan:** produce a sequence of steps with dependencies and completion checks.
4. **Classify risk:** identify read-only, reversible, external and destructive actions.
5. **Authorize:** request approval where policy requires it. Model output is never authorization.
6. **Route:** select a model for reasoning or a tool for deterministic operations.
7. **Execute:** invoke one bounded tool operation at a time; enforce timeouts and cancellation.
8. **Verify:** inspect the actual tool result before marking a step complete.
9. **Recover:** retry only when safe; otherwise stop, explain the failure and preserve completed work.
10. **Report:** return what was done, what failed, and what still needs user action.

## 5. Trust boundaries and security

VORAK's highest-risk boundary is the transition from model-generated plans to actions on the user's machine or accounts.

- Model output is untrusted input. It must never bypass policy checks.
- Tool adapters should expose allowlisted operations, not unrestricted shell or filesystem access by default.
- Use least-privilege access and explicit scopes for files, screen capture and application control.
- Require confirmation for deletion, sending messages, purchases, publishing, credential changes and other consequential actions.
- Keep secrets out of prompts, logs, screenshots and Git.
- Treat webpages, documents, terminal output and screen content as potentially adversarial (prompt injection).
- Provide cancellation, timeouts and a clear execution history.
- Separate read-only operations from write-capable operations.

## 6. Model routing strategy

Keep provider-specific code behind a common interface. The core should request a capability, not depend on a vendor-specific SDK.

Possible routing inputs include task type, required capability, context length, modality, local/cloud preference, provider availability, latency, usage cost, privacy and data sensitivity.

Fallback must be explicit. If a provider fails, retry or switch only when the task is safe to replay. Do not duplicate side effects.

## 7. Failure handling

| Failure | Expected behavior |
|---|---|
| Model unavailable | Use a configured fallback or report that planning cannot continue. |
| Tool timeout | Stop waiting, mark the step failed/unknown and avoid blind retries for side effects. |
| Permission denied | Stop that action and explain what approval or access is missing. |
| Partial task failure | Preserve completed step results and report remaining work. |
| Invalid tool arguments | Reject before execution and return a structured validation error. |
| Cancellation | Stop future steps and cancel active work where supported. |

## 8. Key architectural decisions

### ADR-001: Start as a modular monolith

- **Context:** The project is evolving and its boundaries are still being validated.
- **Decision:** Keep the orchestrator, routing and adapters in one deployable application with explicit interfaces.
- **Alternative:** Microservices from the start.
- **Reason:** A modular monolith reduces operational overhead and makes local desktop integration easier.
- **Trade-off:** Modules need discipline to avoid tight coupling.
- **Revisit when:** Independent deployment, isolation or scaling becomes a demonstrated requirement.

### ADR-002: Put a policy gate between planning and tools

- **Context:** Models can produce incorrect or unsafe action plans.
- **Decision:** All action-capable tools must be called through a permission and policy layer.
- **Alternative:** Allow the planner to call tools directly.
- **Reason:** Model reasoning is not a security boundary and cannot grant itself permission.
- **Trade-off:** Additional approval and policy logic is required.

### ADR-003: Use provider and tool adapters

- **Context:** The project aims to support multiple models and capabilities.
- **Decision:** Normalize integrations behind small interfaces.
- **Alternative:** Call provider SDKs and desktop APIs directly from orchestration logic.
- **Reason:** Keeps the core replaceable and testable.
- **Trade-off:** Adapter contracts need versioning and maintenance.

## 9. Suggested implementation sequence

1. Define task, plan, step, tool and provider interfaces.
2. Build a text-only orchestrator with one harmless read-only tool.
3. Add structured task state, cancellation and error handling.
4. Add model-provider adapters and explicit routing.
5. Add approval policies and an audit trail before write-capable tools.
6. Add desktop, file, web and screen adapters individually.
7. Add voice interaction and realtime streaming.
8. Add integration tests for failures, permissions and duplicate side effects.

## 10. Acceptance criteria

A task should not be marked successful merely because a model returned a plausible response. It is successful only when the relevant tool confirms the operation and any required postcondition is checked. Every task should have a traceable outcome, including failure and partial completion.