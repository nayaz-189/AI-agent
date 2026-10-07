from tools.system_tools import (
    open_youtube,
    open_google,
    open_calculator,
    open_website,
    resolve_website,
    resolve_application,
    launch_application,
)


TOOLS = {
    "launch_application": {
    "function": launch_application,
    "description": (
        "Launch an already resolved Windows application."
    ),
    "risk": "low",
    "agent": "system",
    "required_arguments": [
        "launch_type",
        "launch_target",
    ],
},

    "resolve_application": {
        "function": resolve_application,
        "description": (
            "Find and open an installed Windows application."
        ),
        "risk": "low",
        "agent": "system",
        "required_arguments": ["target"],
    },

    "resolve_website": {
        "function": resolve_website,
        "description": (
            "Resolve a website name or description using web search."
        ),
        "risk": "low",
        "agent": "browser",
        "required_arguments": ["target"],
    },

    "open_youtube": {
        "function": open_youtube,
        "description": (
            "Open YouTube in the default browser."
        ),
        "risk": "low",
        "agent": "system",
        "required_arguments": [],
    },

    "open_google": {
        "function": open_google,
        "description": (
            "Open Google in the default browser."
        ),
        "risk": "low",
        "agent": "system",
        "required_arguments": [],
    },

    "open_calculator": {
        "function": open_calculator,
        "description": (
            "Open the Windows Calculator application."
        ),
        "risk": "low",
        "agent": "system",
        "required_arguments": [],
    },

    "open_website": {
        "function": open_website,
        "description": (
            "Open a website using a full URL."
        ),
        "risk": "low",
        "agent": "browser",
        "required_arguments": ["url"],
    },
}


def get_tool_metadata(tool_name):
    """
    Return public metadata for one registered tool.

    The executable Python function is intentionally excluded.
    """

    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        return None

    return {
        "name": tool_name,
        "description": tool_data.get("description", ""),
        "risk": tool_data.get("risk", "unknown"),
        "agent": tool_data.get("agent"),
        "required_arguments": list(
            tool_data.get("required_arguments", [])
        ),
    }


def get_planner_tool_catalog():
    """
    Return the tool information that the planner is allowed to see.

    This keeps executable function objects out of LLM prompts and makes
    the tool registry the single source of truth for available actions.
    """

    catalog = []

    for tool_name in sorted(TOOLS):
        metadata = get_tool_metadata(tool_name)

        if metadata:
            catalog.append(metadata)

    return catalog


def execute_tool(tool_name, arguments=None):

    if arguments is None:
        arguments = {}

    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        print(f"Tool not found: {tool_name}")
        return False

    function = tool_data["function"]

    function(**arguments)

    return True


if __name__ == "__main__":
    print("Registered planner tools:")

    for tool in get_planner_tool_catalog():
        print(
            f"- {tool['name']} | "
            f"agent={tool['agent']} | "
            f"risk={tool['risk']} | "
            f"required={tool['required_arguments']}"
        )