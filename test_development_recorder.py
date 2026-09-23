from knowledge.development_recorder import (
    record_bug,
    record_decision,
    record_fix,
    record_test,
)

from knowledge.knowledge_query import (
    get_recent_events,
)

from knowledge.project_updates import (
    add_known_issue,
    resolve_known_issue,
)


TEST_ISSUE = (
    "Day 9 temporary knowledge "
    "system test issue."
)


record_bug(
    component="knowledge_system",
    description=TEST_ISSUE,
)

add_known_issue(
    TEST_ISSUE
)


record_fix(
    component="knowledge_system",
    description=(
        "Resolved Day 9 temporary "
        "knowledge system test issue."
    ),
)

resolve_known_issue(
    TEST_ISSUE
)


record_test(
    component="knowledge_system",
    description=(
        "Development recorder "
        "test completed."
    ),
    passed=True,
)


record_decision(
    component="knowledge_system",
    description=(
        "Keep historical events "
        "separate from current "
        "project state."
    ),
)


print(
    "\nRecent development events:"
)

for event in get_recent_events(4):

    print(
        event["event_type"],
        "|",
        event["status"],
        "|",
        event["description"],
    )