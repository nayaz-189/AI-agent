import sys

from knowledge.development_finalizer import (
    finalize_development,
)
from knowledge.development_manager import (
    start_development,
)


def main():
    arguments = sys.argv[1:]

    if not arguments:
        return start_development()

    if arguments == [
        "finalize",
    ]:
        return finalize_development(
            dry_run=False
        )

    if arguments == [
        "finalize",
        "--dry-run",
    ]:
        return finalize_development(
            dry_run=True
        )

    print(
        "Unknown development command."
    )

    print(
        "Supported commands:"
    )

    print(
        "  python dev.py"
    )

    print(
        "  python dev.py finalize --dry-run"
    )

    print(
        "  python dev.py finalize"
    )

    return False


if __name__ == "__main__":
    success = main()

    if not success:
        raise SystemExit(1)