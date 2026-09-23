from datetime import datetime

from knowledge.state_manager import (
    load_state,
    save_state,
)


state = load_state()


state["project"] = {
    "name": "AI Agent",
    "version": "0.009",
    "current_day": 9,
    "status": "development",
}


state["architecture"] = {

    "agents": [
        "browser_agent",
        "system_agent",
    ],

    "tools": [
        "open_website",
        "resolve_website",
        "open_calculator",
        "launch_application",
    ],

    "models": [
        "rafw007/gemma4-e4b-claude-coder:latest",
        "qwen3:0.6b",
    ],

    "providers": [
        "tavily",
    ],

    "resolvers": [
        "website_resolver",
        "application_resolver",
    ],
}


state["capabilities"] = [
    "Open installed Windows applications",
    "Resolve ambiguous application names",
    "Accept clarification by number or name",
    "Resolve websites",
    "Cache resolved websites",
    "Use deterministic fast routing",
    "Use local LLM planning as fallback",
    "Validate plans before execution",
    "Route plans to specialist agents",
]


state["known_issues"] = [
    (
        "Bare targets such as 'ide' are not "
        "consistently handled by the fast router."
    ),
    (
        "Low-information input may be incorrectly "
        "interpreted by the LLM."
    ),
    (
        "Application index requires process restart "
        "to detect newly installed applications."
    ),
    (
        "Validator does not yet enforce complete "
        "argument schemas and risk policies."
    ),
    (
        "Execution verification is still minimal."
    ),
]


state["next_tasks"] = [
    "Build automatic project knowledge recording",
    "Add application index refresh",
    "Strengthen command routing",
    "Strengthen validator schemas",
    "Add execution verification",
]


state["last_updated"] = (
    datetime.now()
    .astimezone()
    .isoformat()
)


save_state(state)


print(
    "Project state initialized."
)

print(
    "Version:",
    state["project"]["version"],
)

print(
    "Agents:",
    len(
        state["architecture"]["agents"]
    ),
)

print(
    "Tools:",
    len(
        state["architecture"]["tools"]
    ),
)