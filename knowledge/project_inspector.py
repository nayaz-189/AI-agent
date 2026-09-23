from pathlib import Path

from tools.tool_registry import TOOLS


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)


def discover_python_modules(directory_name):
    directory = (
        PROJECT_ROOT
        / directory_name
    )

    if not directory.exists():
        return []

    modules = []

    for file in directory.glob("*.py"):

        if file.name == "__init__.py":
            continue

        modules.append(
            file.stem
        )

    return sorted(modules)


def discover_agents():
    return discover_python_modules(
        "agents"
    )


def discover_brain_modules():
    return discover_python_modules(
        "brain"
    )


def discover_providers():
    return discover_python_modules(
        "providers"
    )


def discover_tools():
    tools = []

    for tool_name, tool_data in TOOLS.items():

        tools.append(
            {
                "name": tool_name,
                "description": tool_data.get(
                    "description"
                ),
                "risk": tool_data.get(
                    "risk"
                ),
                "agent": tool_data.get(
                    "agent"
                ),
                "required_arguments":
                    tool_data.get(
                        "required_arguments",
                        [],
                    ),
            }
        )

    return tools


def inspect_project():

    return {
        "agents": discover_agents(),

        "brain_modules":
            discover_brain_modules(),

        "providers":
            discover_providers(),

        "tools":
            discover_tools(),
    }