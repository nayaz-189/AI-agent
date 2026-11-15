# VORAK — Recommended Repository Structure

**Status: Proposed organization.** This is a target layout, not a statement that these directories already exist.

Organize the repository around responsibilities rather than vendors or individual experiments. Keep the first version simple; do not create empty packages just to match this diagram.

~~~text
VORAK/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── SECURITY.md
│   └── decisions/
│       └── 0001-modular-monolith.md
├── apps/
│   └── desktop/                 # User-facing desktop application, if separate
├── core/
│   ├── orchestrator/            # Coordinates task lifecycle
│   ├── planner/                 # Intent parsing and task planning
│   ├── policy/                  # Permissions and approval checks
│   ├── state/                   # Task and execution state
│   └── results/                 # Result synthesis and reporting
├── providers/
│   ├── base/                    # Shared model-provider contract
│   ├── local/                   # Local model integrations
│   ├── cloud/                   # Cloud model integrations
│   └── realtime/                # Realtime voice model integration
├── tools/
│   ├── base/                    # Shared tool contract and validation
│   ├── desktop/                 # Desktop/application automation
│   ├── screen/                  # Permission-scoped screen context
│   ├── web/                     # Web research
│   ├── files/                   # File/workspace operations
│   └── developer/               # Coding and repository workflows
├── memory/                      # Explicitly scoped context and persistence
├── observability/               # Structured logs, traces and redaction
├── tests/
│   ├── unit/
│   ├── integration/
│   └── security/
└── scripts/                     # Development and maintenance scripts
~~~

## Organization rules

1. **Do not move files blindly.** First identify the current entry point, imports, build configuration and runtime assumptions.
2. **One responsibility per module.** The orchestrator coordinates; providers call models; tools perform bounded operations; policy authorizes.
3. **Keep secrets out of Git.** Commit an .env.example with placeholder variable names only, never real values.
4. **Tests follow boundaries.** Unit-test planners, routing and policy; integration-test provider/tool contracts; security-test permission bypass and prompt injection cases.
5. **Document actual behavior.** Update README setup commands only after running them successfully.
6. **Avoid premature abstraction.** Add a directory when a real module exists, not just because it appears in this proposed layout.

## Safe reorganization checklist

- [ ] Inventory the current repository and identify the actual runtime entry point.
- [ ] Identify duplicated or tightly coupled code.
- [ ] Add or update tests before moving modules.
- [ ] Move one logical module at a time and update imports.
- [ ] Run formatter, lint, type checks and tests supported by the project.
- [ ] Verify startup and one end-to-end task.
- [ ] Review Git diff and rollback plan before merging.