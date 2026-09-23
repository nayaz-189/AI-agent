from knowledge.state_sync import (
    synchronize_project_state,
)


success = (
    synchronize_project_state()
)


print(
    "Synchronization success:",
    success,
)