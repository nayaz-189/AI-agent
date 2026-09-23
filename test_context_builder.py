print(
    "\n=== REPOSITORY ==="
)

repository = context[
    "repository"
]

print(
    "Branch:",
    repository["branch"],
)

print(
    "Commit:",
    repository["short_commit"],
)

print(
    "Clean:",
    repository["clean"],
)

print(
    "Ahead:",
    repository["ahead"],
)

print(
    "Behind:",
    repository["behind"],
)

print(
    "Changed files:",
    len(
        repository[
            "changed_files"
        ]
    ),
)
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