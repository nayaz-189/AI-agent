from tools.tool_registry import TOOLS, execute_tool


def can_handle(plan):

    tool_name = plan.get("tool")
    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        return False

    return tool_data.get("agent") == "system"


def handle(plan):

    tool_name = plan["tool"]
    arguments = plan["arguments"]

    print("System Agent handling:", tool_name)

    return execute_tool(tool_name, arguments)