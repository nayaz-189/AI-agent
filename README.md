# VORAK
### Virtual Operations, Reasoning & Action Kernel

> **Not just an AI that answers. An AI that reasons, operates and takes action.**

**VORAK is an in-progress personal AI assistant project** focused on bringing AI models, tools, desktop workflows and voice interaction together behind one coordinated system.

The long-term goal is to let a user describe an outcome, have VORAK plan the work, choose suitable models and tools, and execute approved actions with clear permission boundaries.

> **Project status: WORK IN PROGRESS.** The architecture and capabilities described here represent the project's direction. Not every component is complete or production-ready.

## Why VORAK?

Most AI assistants are primarily conversational. VORAK explores a more action-oriented approach: understand intent, break a task into steps, select the right capability, execute safely, and report what happened.

The aim is to create a central operating layer between the user, their computer, AI models and external tools—not another chatbot with a different interface.

## Project goals

- **Reasoning and planning:** interpret requests, identify subtasks, plan execution and handle failures.
- **Model flexibility:** route work to suitable cloud or local models instead of depending on one provider.
- **Tool orchestration:** connect capabilities through modular tool adapters.
- **Desktop operations:** support controlled interaction with Windows applications and workflows.
- **Voice-first interaction:** work toward natural voice conversations and flexible wake phrases.
- **Visual context:** use screen understanding when the user explicitly grants access.
- **Development assistance:** help navigate projects, understand code and support coding workflows.
- **Web intelligence:** gather requested information from online sources and return useful results.

These are project goals; consult the implementation and release notes before assuming a feature is available.

## Conceptual architecture

~~~mermaid
flowchart TD
    U[User: text / voice] --> I[Interaction Layer]
    I --> O[VORAK Orchestrator]
    O --> P[Intent + Task Planner]
    P --> G[Permission and Policy Gate]
    G --> R[Model Router]
    R --> L[Local Model Provider]
    R --> C[Cloud Model Provider]
    G --> T[Tool Adapter Layer]
    T --> D[Desktop Automation]
    T --> W[Web Research]
    T --> S[Screen / Visual Context]
    T --> DEV[Developer Tools]
    L --> O
    C --> O
    D --> O
    W --> O
    S --> O
    DEV --> O
    O --> X[Result, status and audit trail]
    X --> I
~~~

This is the **target conceptual design**, not a claim that every box is already implemented.

For component responsibilities, trust boundaries and execution flow, see [Architecture](docs/ARCHITECTURE.md).

## Design principles

1. **One orchestrator, modular capabilities.** Keep model providers and tools replaceable.
2. **Permission before action.** Sensitive or consequential operations should require explicit approval.
3. **Least privilege.** Give each tool only the access it needs.
4. **Visible execution.** Make plans, tool calls, failures and outcomes understandable.
5. **Graceful failure.** Handle unavailable models, timeouts, tool errors and partial completion.
6. **Provider independence.** Avoid coupling core orchestration to one model vendor.
7. **Incremental development.** Build and verify one reliable capability at a time.

## Current development status

VORAK is actively being developed. It is not being presented as a finished autonomous operating system or production-ready assistant.

Areas being explored include orchestration and task planning, local and cloud model integration, voice interaction, desktop and application automation, screen-aware assistance, web and development workflows, and permission controls.

Implementation status may change as development progresses. Check the source code and project documentation for what currently works.

## Repository guide

- [Architecture](docs/ARCHITECTURE.md) — system boundaries, components and data flow.
- [Project structure](docs/PROJECT_STRUCTURE.md) — recommended organization as the codebase grows.

The repository structure is evolving. Documentation should be updated as modules are implemented or renamed.

## Security

VORAK may eventually interact with local files, applications, screens and external services. Treat those capabilities as security-sensitive.

- Never commit API keys, access tokens, passwords, cookies or private environment files.
- Keep credentials in environment variables or a secure secret store.
- Review permissions before enabling desktop, screen or file access.
- Require confirmation for destructive, external or high-impact actions.
- Treat web pages, files and tool output as untrusted input.
- Review the full Git history for exposed secrets before making this repository public. Removing a secret from the latest commit does not remove it from history; rotate any exposed credential.

## Development

This repository is under active development. Setup instructions, supported platforms, dependencies and runnable commands will be documented once verified against the actual implementation.

Do not assume a command or feature is available until it is documented and tested.

## Contributing

Ideas, issues and technical feedback are welcome. Since the architecture is still evolving, discuss substantial changes before building tightly coupled integrations.

## Project

**VORAK — Virtual Operations, Reasoning & Action Kernel**

Built as an ongoing exploration of a personal AI system that can understand intent, coordinate intelligence and perform useful work—with the user remaining in control.