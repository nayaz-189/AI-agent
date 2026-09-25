from knowledge.canonical_recorder import (
    link_records,
    record_capability,
    record_decision,
    record_test,
)


decision_id = record_decision(
    title="Canonical knowledge authority",
    decision=(
        "Use SQLite as the structured canonical "
        "knowledge layer while retaining JSONL "
        "as an append-only audit history."
    ),
    reason=(
        "The project needs complete point-to-point "
        "traceability without depending on AI "
        "conversation memory."
    ),
    alternatives=[
        "JSON files only",
        "Conversation memory",
    ],
)


capability_id = record_capability(
    name="canonical_project_knowledge",
    description=(
        "Persist and query structured project "
        "knowledge across development sessions."
    ),
    component="knowledge",
    source="Day 11 architecture",
)


test_id = record_test(
    component="canonical_recorder",
    test_name="Canonical recorder integration test",
    command="python test_canonical_recorder.py",
    expected_result=(
        "Decision, capability, test and relationships "
        "are stored successfully."
    ),
    actual_result="passed",
    status="passed",
)


link_records(
    "decision",
    decision_id,
    "enabled",
    "capability",
    capability_id,
)


link_records(
    "test",
    test_id,
    "verified",
    "capability",
    capability_id,
)


print("Canonical recorder test passed.")
print("Decision:", decision_id)
print("Capability:", capability_id)
print("Test:", test_id)