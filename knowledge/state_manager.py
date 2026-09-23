import json

from pathlib import Path


STORE_DIRECTORY = (
    Path(__file__).resolve().parent
    / "store"
)

STATE_FILE = (
    STORE_DIRECTORY
    / "project_state.json"
)


DEFAULT_STATE = {
    "project": {
        "name": "AI Agent",
        "version": "0.009",
        "current_day": 9,
        "status": "development",
    },

    "architecture": {
        "agents": [],
        "tools": [],
        "models": [],
        "providers": [],
        "resolvers": [],
    },

    "capabilities": [],

    "known_issues": [],

    "next_tasks": [],

    "last_updated": None,
}


def ensure_state_file():
    STORE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not STATE_FILE.exists():

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                DEFAULT_STATE,
                file,
                indent=4,
            )


def load_state():
    ensure_state_file()

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except json.JSONDecodeError:

        print(
            "Warning: project state "
            "file is invalid."
        )

        return None


def save_state(state):
    ensure_state_file()

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            state,
            file,
            indent=4,
            ensure_ascii=False,
        )


def update_section(
    section,
    value,
):
    state = load_state()

    if state is None:
        return False

    state[section] = value

    save_state(state)

    return True


def get_section(section):
    state = load_state()

    if state is None:
        return None

    return state.get(section)