from pprint import pprint

from knowledge.knowledge_query import (
    get_current_version,
    get_current_day,
    get_known_issues,
    get_recent_events,
    get_project_summary,
)


print(
    "\n=== PROJECT ==="
)

print(
    "Version:",
    get_current_version(),
)

print(
    "Day:",
    get_current_day(),
)


print(
    "\n=== KNOWN ISSUES ==="
)

for issue in get_known_issues():
    print(
        "-",
        issue,
    )


print(
    "\n=== RECENT EVENTS ==="
)

for event in get_recent_events(5):

    print(
        event["event_type"],
        "->",
        event["description"],
    )


print(
    "\n=== PROJECT SUMMARY ==="
)

pprint(
    get_project_summary()
)