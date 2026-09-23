from pprint import pprint

from knowledge.git_sync import (
    inspect_sync_status,
)


print(
    "\n=== GIT SYNC STATUS ==="
)

status = inspect_sync_status(
    fetch=True,
)

pprint(status)