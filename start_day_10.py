from knowledge.lifecycle_manager import (
    start_development_day,
)

from knowledge.context_builder import (
    save_ai_context,
)


success = start_development_day(
    day=10,
    version="0.010",
)


if success:

    context = save_ai_context()

    print(
        "\nDevelopment Day 10 started."
    )

    print(
        "Version:",
        context["project"]["version"],
    )

    print(
        "Day:",
        context["project"]["day"],
    )

else:

    print(
        "Could not update "
        "project lifecycle."
    )