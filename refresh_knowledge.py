from knowledge.knowledge_controller import (
    refresh_project_knowledge,
)


success = refresh_project_knowledge()


if success:
    print(
        "\nKnowledge refresh completed."
    )

else:
    print(
        "\nKnowledge refresh failed."
    )