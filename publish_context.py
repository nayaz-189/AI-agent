import subprocess
import sys
from pathlib import Path

from knowledge.context_repo_publisher import (
    ALLOWED_ARTIFACTS,
    CONTEXT_REPOSITORY,
    calculate_sha256,
    destination_is_safe,
    publish_to_context_repository,
    validate_context_repository,
)


# ============================================================
# CONTROLLED EXTERNAL CONTEXT GIT PUBLISHER
# ============================================================
#
# Purpose:
#
# Verified external publication package
#        ↓
# controlled boundary copier
#        ↓
# dedicated AI-agent-context repository
#        ↓
# verify Git repository state
#        ↓
# stage ONLY allowlisted artifacts
#        ↓
# commit
#        ↓
# push origin/main
#
# SECURITY RULES:
#
# - Never use "git add ."
# - Never stage arbitrary paths.
# - Never accept arbitrary repository paths.
# - Never accept arbitrary filenames.
# - Never publish from the protected core repository.
# - Never regenerate the publication package here.
# - Never modify core AI runtime authority.
# - Fail closed on unexpected repository content.
# - Fail closed on unexpected Git changes.
#
# ============================================================


EXPECTED_REPOSITORY_NAME = "AI-agent-context"
EXPECTED_BRANCH = "main"
EXPECTED_REMOTE = "origin"

COMMIT_MESSAGE = (
    "publish: update sanitized AI project context"
)


def run_git(*arguments, check=True):
    """
    Run Git without invoking a shell.

    Arguments are passed as a fixed subprocess argument array,
    preventing shell-command interpretation.
    """

    command = [
        "git",
        "-C",
        str(CONTEXT_REPOSITORY),
        *arguments,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=False,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            "Git command failed.\n"
            f"Command: {' '.join(command)}\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT: {result.stdout.strip()}\n"
            f"STDERR: {result.stderr.strip()}"
        )

    return result


def get_current_branch():
    result = run_git(
        "branch",
        "--show-current",
    )

    return result.stdout.strip()


def get_remote_url():
    result = run_git(
        "remote",
        "get-url",
        EXPECTED_REMOTE,
    )

    return result.stdout.strip()


def validate_git_repository():
    """
    Validate the Git identity and branch of the dedicated
    external context repository.
    """

    repository_check = (
        validate_context_repository()
    )

    if not repository_check.get(
        "valid",
        False,
    ):
        return {
            "valid": False,
            "reason": repository_check.get(
                "reason",
                "Context repository validation failed.",
            ),
        }

    if (
        CONTEXT_REPOSITORY.name
        != EXPECTED_REPOSITORY_NAME
    ):
        return {
            "valid": False,
            "reason":
                "Unexpected context repository name.",
        }

    branch = get_current_branch()

    if branch != EXPECTED_BRANCH:
        return {
            "valid": False,
            "reason":
                "Context repository is on an unexpected branch.",
            "expected_branch":
                EXPECTED_BRANCH,
            "actual_branch":
                branch,
        }

    remote_url = get_remote_url()

    if not remote_url:
        return {
            "valid": False,
            "reason":
                "Context repository origin URL is missing.",
        }

    return {
        "valid": True,
        "branch": branch,
        "remote": EXPECTED_REMOTE,
        "remote_url": remote_url,
    }


def parse_porcelain_paths(output):
    """
    Extract changed paths from Git porcelain output.

    This parser intentionally supports only the simple file
    changes expected in this repository.

    Rename/copy records are rejected because this publication
    repository should contain only two fixed artifact names.
    """

    changed_paths = set()

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue

        if len(raw_line) < 4:
            raise RuntimeError(
                "Unexpected Git status record."
            )

        status = raw_line[:2]
        path_text = raw_line[3:]

        if "R" in status or "C" in status:
            raise RuntimeError(
                "Rename/copy Git changes are not permitted "
                "in the context repository."
            )

        if " -> " in path_text:
            raise RuntimeError(
                "Unexpected renamed Git path detected."
            )

        changed_paths.add(
            Path(path_text).as_posix()
        )

    return changed_paths


def validate_working_tree_changes():
    """
    Fail closed unless every Git working-tree/index change is
    one of the two explicitly allowlisted publication files.
    """

    result = run_git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )

    try:
        changed_paths = parse_porcelain_paths(
            result.stdout
        )
    except RuntimeError as error:
        return {
            "valid": False,
            "reason": str(error),
        }

    unexpected = (
        changed_paths
        - ALLOWED_ARTIFACTS
    )

    if unexpected:
        return {
            "valid": False,
            "reason":
                "Unexpected Git changes exist in "
                "the context repository.",
            "unexpected":
                sorted(unexpected),
        }

    return {
        "valid": True,
        "changed":
            sorted(changed_paths),
    }


def verify_destination_files():
    """
    Ensure the destination contains only expected public
    artifacts and that both required files exist.
    """

    destination_check = (
        destination_is_safe()
    )

    if not destination_check.get(
        "safe",
        False,
    ):
        return {
            "valid": False,
            "reason":
                destination_check.get(
                    "reason",
                    "Destination safety check failed.",
                ),
            "details":
                destination_check,
        }

    missing = []

    for filename in sorted(
        ALLOWED_ARTIFACTS
    ):
        path = (
            CONTEXT_REPOSITORY
            / filename
        )

        if not path.is_file():
            missing.append(
                filename
            )

    if missing:
        return {
            "valid": False,
            "reason":
                "Required destination artifacts are missing.",
            "missing":
                missing,
        }

    return {
        "valid": True,
    }


def stage_allowlisted_artifacts():
    """
    Stage exactly the approved publication artifacts.

    Never use:
        git add .
        git add -A
    """

    filenames = sorted(
        ALLOWED_ARTIFACTS
    )

    run_git(
        "add",
        "--",
        *filenames,
    )

    return filenames


def get_staged_paths():
    result = run_git(
        "diff",
        "--cached",
        "--name-only",
    )

    return {
        Path(line.strip()).as_posix()
        for line in result.stdout.splitlines()
        if line.strip()
    }


def verify_staged_paths():
    """
    Ensure the Git index contains nothing except allowlisted
    publication artifacts.
    """

    staged = get_staged_paths()

    unexpected = (
        staged
        - ALLOWED_ARTIFACTS
    )

    if unexpected:
        return {
            "valid": False,
            "reason":
                "Unexpected files are staged.",
            "unexpected":
                sorted(unexpected),
        }

    return {
        "valid": True,
        "staged":
            sorted(staged),
    }


def verify_artifact_hashes():
    """
    Return hashes of the exact files that are about to be
    committed.
    """

    hashes = {}

    for filename in sorted(
        ALLOWED_ARTIFACTS
    ):
        path = (
            CONTEXT_REPOSITORY
            / filename
        )

        hashes[filename] = (
            calculate_sha256(
                path
            )
        )

    return hashes


def commit_if_needed():
    """
    Commit the staged publication artifacts.

    If no staged differences exist, no commit is created.
    """

    result = run_git(
        "diff",
        "--cached",
        "--quiet",
        check=False,
    )

    if result.returncode == 0:
        return {
            "committed": False,
            "reason":
                "No publication changes to commit.",
        }

    if result.returncode != 1:
        raise RuntimeError(
            "Unable to determine whether staged "
            "publication changes exist."
        )

    commit_result = run_git(
        "commit",
        "-m",
        COMMIT_MESSAGE,
    )

    commit_hash = run_git(
        "rev-parse",
        "--short",
        "HEAD",
    ).stdout.strip()

    return {
        "committed": True,
        "commit":
            commit_hash,
        "output":
            commit_result.stdout.strip(),
    }


def push_publication():
    """
    Push only the expected branch to the expected remote.
    """

    result = run_git(
        "push",
        EXPECTED_REMOTE,
        EXPECTED_BRANCH,
    )

    return {
        "pushed": True,
        "output":
            (
                result.stdout.strip()
                or result.stderr.strip()
            ),
    }


def publish_context_to_git():
    """
    Full controlled publication transaction.

    Important:
    This does NOT regenerate project context.

    It verifies and copies the existing publication package,
    then performs tightly constrained Git publication.
    """

    # --------------------------------------------------------
    # 1. VERIFY GIT REPOSITORY IDENTITY
    # --------------------------------------------------------

    repository = (
        validate_git_repository()
    )

    if not repository.get(
        "valid",
        False,
    ):
        return {
            "success": False,
            "stage":
                "repository_validation",
            "reason":
                repository.get(
                    "reason"
                ),
            "details":
                repository,
        }

    # --------------------------------------------------------
    # 2. VERIFY PRE-EXISTING GIT CHANGES
    # --------------------------------------------------------

    working_tree = (
        validate_working_tree_changes()
    )

    if not working_tree.get(
        "valid",
        False,
    ):
        return {
            "success": False,
            "stage":
                "working_tree_validation",
            "reason":
                working_tree.get(
                    "reason"
                ),
            "details":
                working_tree,
        }

    # --------------------------------------------------------
    # 3. COPY EXISTING VERIFIED PUBLICATION PACKAGE
    # --------------------------------------------------------

    copy_result = (
        publish_to_context_repository()
    )

    if not copy_result.get(
        "published",
        False,
    ):
        return {
            "success": False,
            "stage":
                "boundary_copy",
            "reason":
                copy_result.get(
                    "reason"
                ),
            "details":
                copy_result,
        }

    # --------------------------------------------------------
    # 4. RE-VERIFY DESTINATION
    # --------------------------------------------------------

    destination = (
        verify_destination_files()
    )

    if not destination.get(
        "valid",
        False,
    ):
        return {
            "success": False,
            "stage":
                "destination_verification",
            "reason":
                destination.get(
                    "reason"
                ),
            "details":
                destination,
        }

    # --------------------------------------------------------
    # 5. RE-VERIFY GIT CHANGES AFTER COPY
    # --------------------------------------------------------

    working_tree = (
        validate_working_tree_changes()
    )

    if not working_tree.get(
        "valid",
        False,
    ):
        return {
            "success": False,
            "stage":
                "post_copy_git_validation",
            "reason":
                working_tree.get(
                    "reason"
                ),
            "details":
                working_tree,
        }

    # --------------------------------------------------------
    # 6. RECORD EXACT DESTINATION HASHES
    # --------------------------------------------------------

    artifact_hashes = (
        verify_artifact_hashes()
    )

    # --------------------------------------------------------
    # 7. STAGE ONLY ALLOWLISTED ARTIFACTS
    # --------------------------------------------------------

    staged_files = (
        stage_allowlisted_artifacts()
    )

    # --------------------------------------------------------
    # 8. VERIFY THE GIT INDEX
    # --------------------------------------------------------

    staged_check = (
        verify_staged_paths()
    )

    if not staged_check.get(
        "valid",
        False,
    ):
        return {
            "success": False,
            "stage":
                "staged_file_validation",
            "reason":
                staged_check.get(
                    "reason"
                ),
            "details":
                staged_check,
        }

    # --------------------------------------------------------
    # 9. COMMIT IF THERE ARE ACTUAL CHANGES
    # --------------------------------------------------------

    commit_result = (
        commit_if_needed()
    )

    if not commit_result.get(
        "committed",
        False,
    ):
        return {
            "success": True,
            "published": False,
            "reason":
                commit_result.get(
                    "reason"
                ),
            "repository":
                str(CONTEXT_REPOSITORY),
            "hashes":
                artifact_hashes,
        }

    # --------------------------------------------------------
    # 10. PUSH EXPECTED REMOTE/BRANCH
    # --------------------------------------------------------

    push_result = (
        push_publication()
    )

    # --------------------------------------------------------
    # 11. FINAL CLEANLINESS CHECK
    # --------------------------------------------------------

    final_status = run_git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )

    clean = (
        final_status.stdout.strip()
        == ""
    )

    return {
        "success": True,
        "published": True,
        "repository":
            str(CONTEXT_REPOSITORY),
        "staged_files":
            staged_files,
        "commit":
            commit_result.get(
                "commit"
            ),
        "pushed":
            push_result.get(
                "pushed",
                False,
            ),
        "clean":
            clean,
        "hashes":
            artifact_hashes,
    }


def main():
    print()
    print("CONTROLLED CONTEXT GIT PUBLISHER")
    print("================================")

    try:
        result = (
            publish_context_to_git()
        )

    except Exception as error:
        print()
        print("PUBLICATION FAILED")
        print("Reason:", str(error))
        raise SystemExit(1)

    print()

    if not result.get(
        "success",
        False,
    ):
        print("PUBLICATION BLOCKED")
        print(
            "Stage:",
            result.get(
                "stage"
            ),
        )
        print(
            "Reason:",
            result.get(
                "reason"
            ),
        )

        details = result.get(
            "details"
        )

        if details:
            print(
                "Details:",
                details,
            )

        raise SystemExit(1)

    if not result.get(
        "published",
        False,
    ):
        print("No Git publication required.")
        print(
            "Reason:",
            result.get(
                "reason"
            ),
        )
        return

    print("Publication: SUCCESS")
    print(
        "Repository:",
        result.get(
            "repository"
        ),
    )
    print(
        "Commit:",
        result.get(
            "commit"
        ),
    )
    print(
        "Pushed:",
        result.get(
            "pushed"
        ),
    )
    print(
        "Working tree clean:",
        result.get(
            "clean"
        ),
    )

    print()
    print("Published files:")

    for filename in result.get(
        "staged_files",
        []
    ):
        print(
            " -",
            filename,
        )

    print()
    print("Artifact hashes:")

    for filename, digest in (
        result.get(
            "hashes",
            {}
        ).items()
    ):
        print(
            f" - {filename}: {digest}"
        )


if __name__ == "__main__":
    main()