import ast
from pathlib import Path


# ============================================================
# PERMISSION MAPPING
# ============================================================

# These modules imply that a skill may need certain permissions.
MODULE_PERMISSION_MAP = {
    "subprocess": "terminal",
    "os": "system",
    "shutil": "write_files",
    "requests": "network",
    "urllib": "network",
    "http": "network",
    "socket": "network",
    "webbrowser": "browser",
}


# Calls that deserve additional attention.
DANGEROUS_CALLS = {
    "eval": "Dynamic Python execution",
    "exec": "Dynamic Python execution",
    "compile": "Dynamic code compilation",
    "__import__": "Dynamic module importing",
}


# ============================================================
# AST HELPERS
# ============================================================

def get_call_name(node):
    """
    Convert a Python function call into a readable name.

    Example:
        subprocess.run(...) -> subprocess.run
        eval(...)           -> eval
    """

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = get_call_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None


# ============================================================
# PYTHON FILE INSPECTION
# ============================================================

def inspect_python_file(file_path):

    file_path = Path(file_path)

    result = {
        "file": str(file_path),
        "valid_python": True,
        "imports": [],
        "required_permissions": set(),
        "dangerous_calls": [],
        "errors": [],
    }

    try:
        source = file_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source,
            filename=str(file_path),
        )

    except SyntaxError as error:

        result["valid_python"] = False

        result["errors"].append(
            f"Python syntax error: {error}"
        )

        return result

    except Exception as error:

        result["valid_python"] = False

        result["errors"].append(
            f"Could not inspect file: {error}"
        )

        return result

    for node in ast.walk(tree):

        # --------------------------------------------
        # import module
        # --------------------------------------------

        if isinstance(node, ast.Import):

            for alias in node.names:

                module = alias.name.split(".")[0]

                result["imports"].append(
                    alias.name
                )

                permission = (
                    MODULE_PERMISSION_MAP.get(
                        module
                    )
                )

                if permission:
                    result[
                        "required_permissions"
                    ].add(permission)

        # --------------------------------------------
        # from module import something
        # --------------------------------------------

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                module = (
                    node.module.split(".")[0]
                )

                result["imports"].append(
                    node.module
                )

                permission = (
                    MODULE_PERMISSION_MAP.get(
                        module
                    )
                )

                if permission:
                    result[
                        "required_permissions"
                    ].add(permission)

        # --------------------------------------------
        # Function calls
        # --------------------------------------------

        elif isinstance(node, ast.Call):

            call_name = get_call_name(
                node.func
            )

            if not call_name:
                continue

            simple_name = (
                call_name.split(".")[-1]
            )

            if (
                simple_name
                in DANGEROUS_CALLS
            ):

                result[
                    "dangerous_calls"
                ].append(
                    {
                        "call": call_name,
                        "reason": (
                            DANGEROUS_CALLS[
                                simple_name
                            ]
                        ),
                        "line": getattr(
                            node,
                            "lineno",
                            None,
                        ),
                    }
                )

    result["imports"] = sorted(
        set(result["imports"])
    )

    result["required_permissions"] = sorted(
        result["required_permissions"]
    )

    return result


# ============================================================
# COMPLETE SKILL SECURITY INSPECTION
# ============================================================

def inspect_skill_security(
    skill_directory,
    manifest,
):

    skill_directory = Path(
        skill_directory
    )

    declared_permissions = set(
        manifest.get(
            "permissions",
            [],
        )
    )

    required_permissions = set()

    file_results = []

    dangerous_calls = []

    errors = []

    python_files = list(
        skill_directory.rglob("*.py")
    )

    for python_file in python_files:

        file_result = (
            inspect_python_file(
                python_file
            )
        )

        file_results.append(
            file_result
        )

        required_permissions.update(
            file_result[
                "required_permissions"
            ]
        )

        dangerous_calls.extend(
            file_result[
                "dangerous_calls"
            ]
        )

        errors.extend(
            file_result["errors"]
        )

    undeclared_permissions = (
        required_permissions
        - declared_permissions
    )

    unused_permissions = (
        declared_permissions
        - required_permissions
    )

    # ========================================================
    # SECURITY VERDICT
    # ========================================================

    verdict = "pass"

    if errors:
        verdict = "block"

    elif dangerous_calls:
        verdict = "block"

    elif undeclared_permissions:
        verdict = "block"

    elif unused_permissions:
        verdict = "warning"

    return {
        "verdict": verdict,

        "python_files_checked": len(
            python_files
        ),

        "declared_permissions": sorted(
            declared_permissions
        ),

        "required_permissions": sorted(
            required_permissions
        ),

        "undeclared_permissions": sorted(
            undeclared_permissions
        ),

        "unused_permissions": sorted(
            unused_permissions
        ),

        "dangerous_calls": dangerous_calls,

        "errors": errors,

        "files": file_results,
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    import json

    from skills.skill_manager import (
        inspect_skill,
    )

    test_directory = (
        Path(__file__).resolve().parent
        / "workspace"
        / "hello_skill"
    )

    skill_result = inspect_skill(
        test_directory
    )

    if not skill_result["valid"]:

        print(
            "Skill structure validation failed."
        )

        print(
            skill_result["errors"]
        )

    else:

        security_result = (
            inspect_skill_security(
                test_directory,
                skill_result["manifest"],
            )
        )

        print(
            json.dumps(
                security_result,
                indent=2,
            )
        )