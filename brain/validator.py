from tools.tool_registry import TOOLS


def validate_plan(plan):

    if not isinstance(plan, dict):
        print("Rejected: plan is not a dictionary.")
        return False

    if "tool" not in plan or "arguments" not in plan:
        print("Rejected: invalid plan structure.")
        return False

    tool_name = plan["tool"]
    arguments = plan["arguments"]

    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        print(f"Rejected: '{tool_name}' is not an allowed tool.")
        return False

    if not isinstance(arguments, dict):
        print("Rejected: arguments must be a dictionary.")
        return False

    required_arguments = tool_data.get("required_arguments", [])

    for required_argument in required_arguments:

        if required_argument not in arguments:
            print(
                f"Rejected: '{tool_name}' requires "
                f"'{required_argument}'."
            )
            return False

    return True