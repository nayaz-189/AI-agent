import json

from brain.fast_router import fast_route
from brain.llm import ask_llm
from tools.tool_registry import get_planner_tool_catalog


def build_tool_catalog_text():
    """
    Build a compact planner-facing description of registered tools.

    The registry remains the single source of truth.
    """

    catalog = get_planner_tool_catalog()

    lines = []

    for tool in catalog:
        required_arguments = tool["required_arguments"]

        if required_arguments:
            argument_text = ", ".join(required_arguments)
        else:
            argument_text = "none"

        lines.append(
            f"- {tool['name']}\n"
            f"  Description: {tool['description']}\n"
            f"  Agent: {tool['agent']}\n"
            f"  Risk: {tool['risk']}\n"
            f"  Required arguments: {argument_text}"
        )

    return "\n".join(lines)


def build_planner_prompt(command):
    """
    Build the LLM planning prompt from the live tool registry.
    """

    tool_catalog = build_tool_catalog_text()

    return f"""
You are the planning component of a personal AI agent.

Your job is to translate the user's request into ONE structured action.

You may ONLY use tools listed in AVAILABLE TOOLS.

AVAILABLE TOOLS:

{tool_catalog}

RULES:

1. Never invent a tool.
2. Never invent a capability that is not listed.
3. Return exactly one JSON object.
4. Do not include markdown.
5. Do not include explanations outside the JSON.
6. "arguments" must always be a JSON object.
7. Include every required argument for the selected tool.
8. Do not include unnecessary arguments.
9. Use the user's actual requested target.
10. If none of the available tools can safely perform the request,
    return:

{{
    "type": "unsupported",
    "reason": "No available tool can safely perform this request."
}}

EXECUTABLE ACTION FORMAT:

{{
    "tool": "tool_name",
    "arguments": {{}}
}}

UNSUPPORTED FORMAT:

{{
    "type": "unsupported",
    "reason": "reason"
}}

User request:
{command}
""".strip()


def parse_llm_plan(response):
    """
    Parse an LLM response into a Python dictionary.

    Invalid JSON or a non-object JSON value is rejected.
    """

    try:
        plan = json.loads(response)

    except (json.JSONDecodeError, TypeError):
        print("LLM returned invalid JSON:")
        print(response)
        return None

    if not isinstance(plan, dict):
        print("LLM returned JSON that is not an object:")
        print(response)
        return None

    return plan


def understand_command(command):
    """
    Convert a user command into a structured plan.

    Tier 1:
        deterministic fast router

    Tier 2:
        LLM planner using the live tool registry
    """

    if not isinstance(command, str):
        print("Planner rejected non-string command.")
        return None

    command = command.strip()

    if not command:
        return None

    fast_plan = fast_route(command)

    if fast_plan:
        print("Planner: FAST")
        return fast_plan

    print("Planner: LLM")

    prompt = build_planner_prompt(command)

    response = ask_llm(prompt)

    return parse_llm_plan(response)


if __name__ == "__main__":
    print(build_tool_catalog_text())