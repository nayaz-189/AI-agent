from datetime import datetime

from knowledge.state_manager import (
    load_state,
    save_state,
)


def save_with_timestamp(state):
    state["last_updated"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_state(state)


def add_known_issue(issue):
    state = load_state()

    if not state:
        return False

    issues = state.setdefault(
        "known_issues",
        [],
    )

    if issue not in issues:
        issues.append(issue)

    save_with_timestamp(state)

    return True


def resolve_known_issue(issue):
    state = load_state()

    if not state:
        return False

    issues = state.setdefault(
        "known_issues",
        [],
    )

    if issue in issues:
        issues.remove(issue)

    save_with_timestamp(state)

    return True


def add_capability(capability):
    state = load_state()

    if not state:
        return False

    capabilities = state.setdefault(
        "capabilities",
        [],
    )

    if capability not in capabilities:
        capabilities.append(
            capability
        )

    save_with_timestamp(state)

    return True


def add_next_task(task):
    state = load_state()

    if not state:
        return False

    tasks = state.setdefault(
        "next_tasks",
        [],
    )

    if task not in tasks:
        tasks.append(task)

    save_with_timestamp(state)

    return True


def complete_next_task(task):
    state = load_state()

    if not state:
        return False

    tasks = state.setdefault(
        "next_tasks",
        [],
    )

    if task in tasks:
        tasks.remove(task)

    save_with_timestamp(state)

    return True