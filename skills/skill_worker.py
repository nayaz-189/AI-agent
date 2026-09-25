import importlib.util
import json
import sys
from pathlib import Path


def execute_skill(entrypoint_path):
    """
    Load and execute one skill entrypoint.

    This file is designed to run as a separate Python process.
    """

    entrypoint = Path(entrypoint_path).resolve()

    if not entrypoint.exists():
        raise RuntimeError(
            "Skill entrypoint does not exist."
        )

    specification = (
        importlib.util.spec_from_file_location(
            "runtime_skill",
            entrypoint,
        )
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise RuntimeError(
            "Could not load skill module."
        )

    module = (
        importlib.util.module_from_spec(
            specification
        )
    )

    specification.loader.exec_module(
        module
    )

    run_function = getattr(
        module,
        "run",
        None,
    )

    if not callable(run_function):
        raise RuntimeError(
            "Skill must provide run()."
        )

    result = run_function()

    return result


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
                    "error": str(error),
                }
            )
        )

        sys.exit(1)


if __name__ == "__main__":
    main()