from tools.tool_registry import TOOLS, execute_tool


def can_handle(plan):

    tool_name = plan.get("tool")
    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        return False

    return tool_data.get("agent") == "browser"


def handle(plan):
    from brain.validator import validate_plan

    if not validate_plan(plan) or not can_handle(plan):
        return False

    tool_name = plan["tool"]
    arguments = plan["arguments"]

    print("Browser Agent handling:", tool_name)

    return execute_tool(tool_name, arguments)
