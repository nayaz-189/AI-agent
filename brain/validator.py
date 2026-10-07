from tools.tool_registry import TOOLS


ALLOWED_RISK_LEVELS = {
    "low",
    "medium",
    "high",
    "critical",
}


def validate_plan(plan):
    """
    Validate one executable tool plan.

    This function validates structure and registry contract only.
    It does not execute the tool.
    """

    if not isinstance(plan, dict):
        print("Rejected: plan is not a dictionary.")
        return False

    # Executable plans must contain exactly these top-level fields.
    allowed_plan_fields = {
        "tool",
        "arguments",
    }

    plan_fields = set(plan.keys())

    unexpected_plan_fields = (
        plan_fields - allowed_plan_fields
    )

    if unexpected_plan_fields:
        print(
            "Rejected: unexpected plan field(s): "
            + ", ".join(sorted(unexpected_plan_fields))
        )
        return False

    if "tool" not in plan or "arguments" not in plan:
        print("Rejected: invalid plan structure.")
        return False

    tool_name = plan["tool"]
    arguments = plan["arguments"]

    if not isinstance(tool_name, str):
        print("Rejected: tool name must be a string.")
        return False

    tool_name = tool_name.strip()

    if not tool_name:
        print("Rejected: tool name cannot be empty.")
        return False

    tool_data = TOOLS.get(tool_name)

    if not tool_data:
        print(
            f"Rejected: '{tool_name}' is not an allowed tool."
        )
        return False

    if not isinstance(arguments, dict):
        print("Rejected: arguments must be a dictionary.")
        return False

    required_arguments = set(
        tool_data.get("required_arguments", [])
    )

    provided_arguments = set(arguments.keys())

    missing_arguments = (
        required_arguments - provided_arguments
    )

    if missing_arguments:
        print(
            f"Rejected: '{tool_name}' is missing required "
            "argument(s): "
            + ", ".join(sorted(missing_arguments))
        )
        return False

    # At the current stage, every registered argument is required.
    # Therefore anything outside required_arguments is unexpected.
    unexpected_arguments = (
        provided_arguments - required_arguments
    )

    if unexpected_arguments:
        print(
            f"Rejected: '{tool_name}' received unexpected "
            "argument(s): "
            + ", ".join(sorted(unexpected_arguments))
        )
        return False

    risk = tool_data.get("risk")

    if risk not in ALLOWED_RISK_LEVELS:
        print(
            f"Rejected: '{tool_name}' has invalid or missing "
            f"risk metadata: {risk!r}"
        )
        return False

    agent = tool_data.get("agent")

    if not isinstance(agent, str) or not agent.strip():
        print(
            f"Rejected: '{tool_name}' has invalid or missing "
            "agent metadata."
        )
        return False

    return True


def classify_plan(plan):
    """
    Classify planner output without executing it.

    Possible classifications:

    executable
    clarification
    unsupported
    invalid
    """

    if not isinstance(plan, dict):
        return "invalid"

    plan_type = plan.get("type")

    if plan_type == "clarification":
        return "clarification"

    if plan_type == "unsupported":
        return "unsupported"

    if "tool" in plan:
        return "executable"

    return "invalid"


if __name__ == "__main__":

    tests = [
        (
            "valid calculator",
            {
                "tool": "open_calculator",
                "arguments": {},
            },
            True,
        ),
        (
            "valid website",
            {
                "tool": "open_website",
                "arguments": {
                    "url": "https://example.com",
                },
            },
            True,
        ),
        (
            "unknown tool",
            {
                "tool": "delete_entire_computer",
                "arguments": {},
            },
            False,
        ),
        (
            "missing argument",
            {
                "tool": "open_website",
                "arguments": {},
            },
            False,
        ),
        (
            "unexpected argument",
            {
                "tool": "open_website",
                "arguments": {
                    "url": "https://example.com",
                    "dangerous_extra": True,
                },
            },
            False,
        ),
        (
            "unexpected top-level field",
            {
                "tool": "open_calculator",
                "arguments": {},
                "override": True,
            },
            False,
        ),
    ]

    passed = 0

    for name, plan, expected in tests:

        result = validate_plan(plan)

        status = (
            "PASS"
            if result == expected
            else "FAIL"
        )

        if status == "PASS":
            passed += 1

        print(
            f"{status}: {name} "
            f"(result={result}, expected={expected})"
        )

    print()
    print(
        f"Validator tests passed: "
        f"{passed}/{len(tests)}"
    )

    print()
    print("Planner output classification:")
    print(
        "unsupported ->",
        classify_plan(
            {
                "type": "unsupported",
                "reason": "No available tool.",
            }
        ),
    )
    print(
        "clarification ->",
        classify_plan(
            {
                "type": "clarification",
                "target": "ide",
                "candidates": [],
            }
        ),
    )