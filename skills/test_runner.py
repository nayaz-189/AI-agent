from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 5


def run_skill_test(skill_directory, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Deny candidate execution before reading paths or manifests.

    Static inspection and Python isolated mode cannot contain untrusted code.
    This API stays disabled until an OS-isolated test worker is verified.
    """
    return {"passed": False, "stage": "isolation", "exit_code": None,
            "stdout": "", "stderr": "", "timed_out": False,
            "error_code": "backend_unavailable",
            "reason": "Skill testing requires an OS-isolated worker."}


def print_test_result(result):
    # Never display candidate stdout, result values or backend exception prose.
    # Testing is unavailable until an isolated worker exists, even if a caller
    # hands this presentation helper a forged successful result.
    print()
    print("SKILL TEST RUNNER")
    print("==============================")
    print("Passed: False")
    print("Stage: isolation")
    print("Reason: Skill testing requires an OS-isolated worker.")
# ============================================================
# TEST + CANONICAL RECORDING
# ============================================================

def test_and_record_skill(skill_directory, timeout=DEFAULT_TIMEOUT_SECONDS):
    """A blocked test neither runs candidate code nor writes canonical records."""
    return {**run_skill_test(skill_directory, timeout), "test_id": None, "skill_id": None}

if __name__ == "__main__":

    hello_skill = (
        Path(__file__).resolve().parent
        / "workspace"
        / "hello_skill"
    )

    result = test_and_record_skill(
        hello_skill
    )

    print_test_result(result)

    print()
    print("CANONICAL RECORD")
    print("==============================")

    print(
        "Test ID:",
        result.get("test_id"),
    )

    print(
        "Skill ID:",
        result.get("skill_id"),
    )

    if result["passed"]:
        print("Skill status: tested")
    else:
        print("Skill status: remains untrusted")
