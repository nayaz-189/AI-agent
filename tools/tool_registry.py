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
    "description": "Launch an already resolved Windows application shortcut.",
    "risk": "low",
    "agent": "system",
    "required_arguments": ["path"]
},
    "resolve_application": {
        "function": resolve_application,
        "description": "Find and open an installed Windows application.",
        "risk": "low",
        "agent": "system",
        "required_arguments": ["target"]
    },
    "resolve_website": {
        "function": resolve_website,
        "description": "Resolve a website name or description using web search.",
        "risk": "low",
        "agent": "browser",
        "required_arguments": ["target"]
    },
    "open_youtube": {
        "function": open_youtube,
        "description": "Open YouTube in the default browser.",
        "risk": "low",
        "agent": "system",
        "required_arguments": []
    },

    "open_google": {
        "function": open_google,
        "description": "Open Google in the default browser.",
        "risk": "low",
        "agent": "system",
        "required_arguments": []
    },

    "open_calculator": {
        "function": open_calculator,
        "description": "Open the Windows Calculator application.",
        "risk": "low",
        "agent": "system",
        "required_arguments": []
    },

    "open_website": {
        "function": open_website,
        "description": "Open a website using a URL.",
        "risk": "low",
        "agent": "browser",
        "required_arguments": ["url"]
    }
}


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