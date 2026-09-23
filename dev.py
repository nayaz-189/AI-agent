from knowledge.development_manager import (
    start_development,
)


if __name__ == "__main__":

    success = start_development()

    if not success:
        raise SystemExit(1)