from pprint import pprint

from knowledge.git_inspector import (
    inspect_git,
)


print(
    "\n=== GIT STATUS ==="
)

pprint(
    inspect_git()
)