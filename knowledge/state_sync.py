from datetime import datetime

from knowledge.project_inspector import (
    inspect_project,
)

from knowledge.project_memory import (
    record_event,
)

from knowledge.state_manager import (
    load_state,
    save_state,
)


def normalize_tools(tools):
    """
    Convert tool data into a stable format
    so old and new project states can be
    compared safely.
    """

    normalized = []

    for tool in tools:

        # Older project states may contain
        # only tool-name strings.
        if isinstance(tool, str):

            normalized.append(
                {
                    "name": tool,
                    "description": None,
                    "risk": None,
                    "agent": None,
                    "required_arguments": [],
                }
            )

        else:

            normalized.append(
                {
                    "name":
                        tool.get("name"),

                    "description":
                        tool.get(
                            "description"
                        ),

                    "risk":
                        tool.get("risk"),

                    "agent":
                        tool.get("agent"),

                    "required_arguments":
                        sorted(
                            tool.get(
                                "required_arguments",
                                [],
                            )
                        ),
                }
            )

    return sorted(
        normalized,
        key=lambda item: (
            item.get("name") or ""
        ),
    )


def synchronize_project_state():

    state = load_state()

    if state is None:

        print(
            "Could not load project state."
        )

        return False

    inspection = inspect_project()

    changes = []

    architecture = state.setdefault(
        "architecture",
        {},
    )

    # -------------------------
    # AGENTS
    # -------------------------

    old_agents = sorted(
        architecture.get(
            "agents",
            [],
        )
    )

    new_agents = sorted(
        inspection["agents"]
    )

    if old_agents != new_agents:

        changes.append(
            {
                "component": "agents",
                "before": old_agents,
                "after": new_agents,
            }
        )

        architecture["agents"] = (
            new_agents
        )

    # -------------------------
    # BRAIN MODULES
    # -------------------------

    old_brain_modules = sorted(
        architecture.get(
            "brain_modules",
            [],
        )
    )

    new_brain_modules = sorted(
        inspection[
            "brain_modules"
        ]
    )

    if (
        old_brain_modules
        != new_brain_modules
    ):

        changes.append(
            {
                "component":
                    "brain_modules",

                "before":
                    old_brain_modules,

                "after":
                    new_brain_modules,
            }
        )

        architecture[
            "brain_modules"
        ] = new_brain_modules

    # -------------------------
    # PROVIDERS
    # -------------------------

    old_providers = sorted(
        architecture.get(
            "providers",
            [],
        )
    )

    new_providers = sorted(
        inspection["providers"]
    )

    if (
        old_providers
        != new_providers
    ):

        changes.append(
            {
                "component":
                    "providers",

                "before":
                    old_providers,

                "after":
                    new_providers,
            }
        )

        architecture[
            "providers"
        ] = new_providers

    # -------------------------
    # TOOLS
    # -------------------------

    old_tools = normalize_tools(
        architecture.get(
            "tools",
            [],
        )
    )

    new_tools = normalize_tools(
        inspection["tools"]
    )

    if old_tools != new_tools:

        changes.append(
            {
                "component": "tools",
                "before": old_tools,
                "after": new_tools,
            }
        )

        architecture["tools"] = (
            new_tools
        )

    # -------------------------
    # NO CHANGES
    # -------------------------

    if not changes:

        print(
            "Project state synchronized."
        )

        print(
            "Changes detected: 0"
        )

        return True

    # -------------------------
    # SAVE ONLY WHEN CHANGED
    # -------------------------

    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)

    # -------------------------
    # RECORD REAL CHANGES
    # -------------------------

    version = (
        state
        .get("project", {})
        .get("version")
    )

    for change in changes:

        record_event(
            event_type=(
                "architecture_change"
            ),

            component=change[
                "component"
            ],

            description=(
                "Automatic project "
                "inspection detected "
                "an architecture change."
            ),

            version=version,

            status="recorded",

            metadata={
                "before":
                    change["before"],

                "after":
                    change["after"],
            },
        )

    print(
        "Project state synchronized."
    )

    print(
        "Changes detected:",
        len(changes),
    )

    for change in changes:

        print(
            "-",
            change["component"],
        )

    return True