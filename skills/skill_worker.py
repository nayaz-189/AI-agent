import json
import sys


def execute_skill(entrypoint_path):
    """Direct invocation cannot bypass the disabled parent launcher."""
    raise RuntimeError("Skill execution requires an OS-isolated worker.")


def main():

    if len(sys.argv) != 2:

        print(
            json.dumps(
                {
                    "success": False,
                    "error": (
                        "Expected exactly one "
                        "entrypoint argument."
                    ),
                }
            )
        )

        sys.exit(1)

    entrypoint = sys.argv[1]

    try:

        result = execute_skill(
            entrypoint
        )

        print(
            json.dumps(
                {
                    "success": True,
                    "result": result,
                }
            )
        )

    except Exception as error:

        print(
            json.dumps(
                {
                    "success": False,
                    "error": "Skill execution requires an OS-isolated worker.",
                    "error_code": "backend_unavailable",
                }
            )
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
