from pprint import pprint

from knowledge.project_inspector import (
    inspect_project,
)


project = inspect_project()


print("\n=== AGENTS ===")

pprint(
    project["agents"]
)


print("\n=== BRAIN MODULES ===")

pprint(
    project["brain_modules"]
)


print("\n=== PROVIDERS ===")

pprint(
    project["providers"]
)


print("\n=== TOOLS ===")

pprint(
    project["tools"]
)