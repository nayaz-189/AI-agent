import json

from datetime import datetime
from pathlib import Path


STORE_DIRECTORY = (
    Path(__file__).resolve().parent
    / "store"
)

EVENTS_FILE = (
    STORE_DIRECTORY
    / "events.jsonl"
)


def ensure_store():
    STORE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not EVENTS_FILE.exists():
        EVENTS_FILE.touch()


def record_event(
    event_type,
    component,
    description,
    version=None,
    status=None,
    metadata=None,
):
    ensure_store()

    event = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "event_type": event_type,
        "component": component,
        "description": description,
        "version": version,
        "status": status,
        "metadata": metadata or {},
    }

    with open(
        EVENTS_FILE,
        "a",
        encoding="utf-8",
    ) as file:

        file.write(
            json.dumps(
                event,
                ensure_ascii=False,
            )
            + "\n"
        )

    return event


def load_events():
    ensure_store()

    events = []

    with open(
        EVENTS_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            try:
                events.append(
                    json.loads(line)
                )

            except json.JSONDecodeError:
                print(
                    "Warning: skipped invalid "
                    "project-memory event."
                )

    return events