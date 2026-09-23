from brain.application_resolver import (
    find_application,
)


tests = [
    "ollama",
    "vs code",
    "ide",
    "github",
]


for target in tests:

    print(
        "\n===================="
    )

    print(
        "Target:",
        target
    )

    result = find_application(
        target
    )

    print(
        "Result:",
        result
    )