from knowledge.context_builder import (
    save_ai_context,
)


context = save_ai_context()


print(
    "\nAI context generated."
)

print(
    "Version:",
    context["project"]["version"],
)

print(
    "Day:",
    context["project"]["day"],
)

print(
    "Agents:",
    len(
        context[
            "architecture"
        ].get(
            "agents",
            [],
        )
    ),
)

print(
    "Tools:",
    len(
        context[
            "architecture"
        ].get(
            "tools",
            [],
        )
    ),
)

print(
    "Capabilities:",
    len(
        context[
            "capabilities"
        ]
    ),
)

print(
    "Known issues:",
    len(
        context[
            "known_issues"
        ]
    ),
)

print(
    "Recent events:",
    len(
        context[
            "recent_events"
        ]
    ),
)