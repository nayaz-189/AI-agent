import json
import subprocess
import sys
from pathlib import Path

from skills.skill_manager import inspect_skill
from skills.security_inspector import inspect_skill_security
from knowledge.canonical_recorder import (
    record_skill,
    record_test,
)

DEFAULT_TIMEOUT_SECONDS = 5


def run_skill_test(
    skill_directory,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """
    Run a skill entrypoint in a separate Python process.

    IMPORTANT:
    This is a controlled test runner, NOT a complete
    security sandbox.
    """

    skill_directory = Path(skill_directory).resolve()

    result = {
        "passed": False,
        "stage": "validation",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
        "reason": None,
    }

    # --------------------------------------------------------
    # 1. STRUCTURE VALIDATION
    # --------------------------------------------------------

    inspection = inspect_skill(skill_directory)

    if not inspection["valid"]:
        result["reason"] = "Skill structure validation failed."
        return result

    manifest = inspection["manifest"]

    # --------------------------------------------------------
    # 2. SECURITY CHECK
    # --------------------------------------------------------

    result["stage"] = "security"

    security = inspect_skill_security(
        skill_directory,
        manifest,
    )

    if security["verdict"] == "block":
        result["reason"] = "Skill blocked by security inspection."
        return result

    # --------------------------------------------------------
    # 3. FIND ENTRYPOINT
    # --------------------------------------------------------

    entrypoint = skill_directory / manifest["entrypoint"]

    if not entrypoint.exists():
        result["reason"] = "Skill entrypoint does not exist."
        return result

    # --------------------------------------------------------
    # 4. BUILD SMALL TEST HARNESS
    # --------------------------------------------------------

    harness = f"""
import importlib.util
import json

entrypoint = {str(entrypoint)!r}

spec = importlib.util.spec_from_file_location(
    "skill_module",
    entrypoint
)

module = importlib.util.module_from_spec(spec)

spec.loader.exec_module(module)

if not hasattr(module, "run"):
    raise RuntimeError(
        "Skill entrypoint must define run()."
    )

output = module.run()

print(
    json.dumps(
        {{
            "skill_result": output
        }}
    )
)
"""

    # --------------------------------------------------------
    # 5. RUN IN SEPARATE PROCESS
    # --------------------------------------------------------

    result["stage"] = "execution_test"

    try:
        process = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                harness,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(skill_directory),
        )

    except subprocess.TimeoutExpired:
        result["timed_out"] = True
        result["reason"] = (
            f"Skill exceeded {timeout} second test timeout."
        )
        return result

    except Exception as error:
        result["reason"] = (
            f"Could not start skill test: {error}"
        )
        return result

    result["exit_code"] = process.returncode
    result["stdout"] = process.stdout.strip()
    result["stderr"] = process.stderr.strip()

    # --------------------------------------------------------
    # 6. VERIFY PROCESS RESULT
    # --------------------------------------------------------

    if process.returncode != 0:
        result["reason"] = "Skill test process failed."
        return result

    # --------------------------------------------------------
    # 7. VERIFY OUTPUT
    # --------------------------------------------------------

    try:
        output = json.loads(result["stdout"])

    except json.JSONDecodeError:
        result["reason"] = (
            "Skill did not return valid test JSON."
        )
        return result

    if "skill_result" not in output:
        result["reason"] = (
            "Skill test output is missing skill_result."
        )
        return result

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    result["passed"] = True
    result["stage"] = "completed"
    result["reason"] = "Skill test passed."
    result["skill_result"] = output["skill_result"]

    return result


def print_test_result(result):

    print()
    print("SKILL TEST RUNNER")
    print("==============================")

    print("Passed:", result["passed"])
    print("Stage:", result["stage"])
    print("Reason:", result["reason"])
    print("Exit code:", result["exit_code"])
    print("Timed out:", result["timed_out"])

    if result.get("skill_result") is not None:
        print(
            "Skill result:",
            result["skill_result"],
        )

    if result["stderr"]:
        print("Stderr:", result["stderr"])
# ============================================================
# TEST + CANONICAL RECORDING
# ============================================================

def test_and_record_skill(
    skill_directory,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """
    Test a skill and permanently record the result.

    A skill becomes 'tested' only when the test passes.
    """

    skill_directory = Path(skill_directory).resolve()

    inspection = inspect_skill(
        skill_directory
    )

    if not inspection["valid"]:
        return {
            "passed": False,
            "reason": "Skill validation failed before testing.",
        }

    manifest = inspection["manifest"]

    # Run controlled test
    result = run_skill_test(
        skill_directory,
        timeout=timeout,
    )

    # Record test permanently
    test_id = record_test(
        component="skill_system",
        test_name=(
            f"Skill test: {manifest['name']} "
            f"{manifest['version']}"
        ),
        command=(
            f"Controlled test runner for "
            f"{manifest['name']}"
        ),
        expected_result=(
            "Skill passes validation, security inspection "
            "and controlled execution test."
        ),
        actual_result=(
            "passed"
            if result["passed"]
            else result["reason"]
        ),
        status=(
            "passed"
            if result["passed"]
            else "failed"
        ),
    )

    # Only upgrade lifecycle status after success.
    if result["passed"]:

        skill_id = record_skill(
            name=manifest["name"],
            description=manifest["description"],
            skill_version=manifest["version"],
            source=str(skill_directory),
            status="tested",
            risk_level=manifest["risk_level"],
            metadata={
                "entrypoint": manifest["entrypoint"],
                "permissions": manifest["permissions"],
                "test_id": test_id,
                "test_status": "passed",
            },
        )

    else:

        skill_id = None

    return {
        **result,
        "test_id": test_id,
        "skill_id": skill_id,
    }

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