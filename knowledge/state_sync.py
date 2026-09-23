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


def get_tool_names(tools):
    return sorted(
        tool["name"]
        for tool in tools
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

    old_tools = architecture.get(
        "tools",
        [],
    )

    # Our older state may contain
    # just tool-name strings.

    if (
        old_tools
        and isinstance(
            old_tools[0],
            str,
        )
    ):
        old_tool_names = sorted(
            old_tools
        )

    else:
        old_tool_names = (
            get_tool_names(
                old_tools
            )
        )

    new_tools = inspection["tools"]

    new_tool_names = (
        get_tool_names(
            new_tools
        )
    )

    if (
        old_tool_names
        != new_tool_names
    ):

        changes.append(
            {
                "component": "tools",
                "before": old_tool_names,
                "after": new_tool_names,
            }
        )

    # Store full tool metadata,
    # not merely their names.

    architecture["tools"] = (
        new_tools
    )

    # -------------------------
    # UPDATE TIMESTAMP
    # -------------------------

    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)

    # -------------------------
    # RECORD CHANGES
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