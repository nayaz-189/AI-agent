import json
from brain.fast_router import fast_route
from brain.llm import ask_llm


def understand_command(command):

    fast_plan = fast_route(command)

    if fast_plan:
        print("Planner: FAST")
        return fast_plan

    print("Planner: LLM")

    prompt = f"""
You are the planning brain of a personal AI agent.

Convert the user's request into ONE JSON action.

Available tools:

1. open_website
   Description: Opens a website.
   Arguments:
   - url: full website URL

2. open_calculator
   Description: Opens Windows Calculator.
   Arguments: none

Return ONLY valid JSON.

Required format:

{{
    "tool": "tool_name",
    "arguments": {{}}
}}

Examples:

User: open youtube
Output:
{{
    "tool": "open_website",
    "arguments": {{
        "url": "https://www.youtube.com"
    }}
}}

User: open calculator
Output:
{{
    "tool": "open_calculator",
    "arguments": {{}}
}}

User request:
{command}
"""

    response = ask_llm(prompt)

    try:
        plan = json.loads(response)
        return plan

    except json.JSONDecodeError:
        print("LLM returned invalid JSON:")
        print(response)
        return None