import subprocess
import sys
from pathlib import Path

from knowledge.bridge_manager import (
    refresh_knowledge_bridge,
    verify_knowledge_bridge,
)
from knowledge.context_builder import save_ai_context
from knowledge.context_repo_publisher import (
    CONTEXT_REPOSITORY,
    publish_to_context_repository,
)
from knowledge.git_inspector import (
    PROJECT_ROOT,
    inspect_git,
)
from knowledge.git_sync import inspect_sync_status
from knowledge.git_writer import (
    GitWriteError,
    commit,
    get_changed_files,
    get_staged_files,
    get_tracking_status,
    push_current_branch,
    stage_paths,
)
from knowledge.knowledge_query import (
    get_current_day,
    get_current_version,
)
from knowledge.lifecycle_manager import (
    complete_development_day,
    get_project_info,
    update_project,
)
from knowledge.publication_manager import (
    create_publication_package,
    verify_publication_package,
)
from knowledge.state_sync import synchronize_project_state


# ============================================================
# DEVELOPMENT FINALIZER
# ============================================================
#
# Controlled, fail-closed development-day finalization.
#
# This module is DEVELOPMENT INFRASTRUCTURE.
# It is NOT part of the runtime agent's authority.
#
# Security / lifecycle rules:
#
# - unknown repository paths are rejected
# - known secret/private files are rejected
# - Git itself enumerates untracked files
# - .gitignore remains authoritative
# - generated runtime artifacts are not committed
# - Python compilation must succeed
# - pip dependency health must succeed
# - remote divergence blocks finalization
# - staging uses explicit approved file paths
# - staged files are verified before commit
# - `git add .` is never used
# - dry-run performs no lifecycle/Git mutation
#
# ============================================================


ALLOWED_TOP_LEVEL_FILES = {
    ".gitignore",
    "dev.py",
    "main.py",
    "requirements.txt",
}


ALLOWED_SOURCE_DIRECTORIES = {
    "execution",
    "agents",
    "brain",
    "desktop",
    "knowledge",
    "providers",
    "skills",
    "tools",
}

# One reviewed implementation note, not a blanket docs-directory exception.
# Individually reviewed documents for the next normal lifecycle transition.
# This is an exact filename allowlist, never authorization for docs/**.
ALLOWED_DOCUMENTATION_FILES = {
    "docs/runtime-integration.md",
    "docs/day16-integration.md",
    "docs/security-architecture.md",
}


BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "credentials.json",
    "secrets.json",
    "token.json",
    "tokens.json",
    "passwords.json",
}


BLOCKED_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}


BLOCKED_DIRECTORY_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    "runtime",
    "node_modules",
}


CONTEXT_ALLOWED_FILES = {
    "external_manifest.json",
    "external_project_context.json",
}


# ============================================================
# OUTPUT
# ============================================================


def _print_header(dry_run):
    print()
    print("================================")

    if dry_run:
        print(" AI AGENT FINALIZATION DRY RUN")
    else:
        print(" AI AGENT DEVELOPMENT FINALIZER")

    print("================================")
    print()


# ============================================================
# GENERIC COMMAND EXECUTION
# ============================================================


def _run_command(
    arguments,
    cwd,
    timeout=120,
):
    """
    Execute a subprocess and capture its result.
    """

    try:
        result = subprocess.run(
            arguments,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (
        subprocess.SubprocessError,
        OSError,
    ) as error:
        raise RuntimeError(
            f"Command execution failed: {error}"
        ) from error

    return result


# ============================================================
# GIT STATUS PARSING
# ============================================================


def _parse_status_path(status_line):
    """
    Extract the path from a Git porcelain-v1 status line.

    Format:

        XY PATH

    Examples:

        " M .gitignore"
        "?? requirements.txt"
        " M brain/planner.py"

    For rename/copy entries, the destination path is used.
    """

    if not isinstance(status_line, str):
        return None

    if len(status_line) < 3:
        return None

    # First two characters are Git's XY status.
    path = status_line[2:].strip()

    if not path:
        return None

    if " -> " in path:
        path = path.split(
            " -> ",
            1,
        )[1].strip()

    if (
        len(path) >= 2
        and path.startswith('"')
        and path.endswith('"')
    ):
        path = path[1:-1]

    return path.replace("\\", "/")


# ============================================================
# PATH SECURITY
# ============================================================


def _normalize_repository_path(path):
    """
    Normalize a repository-relative path without resolving it
    outside the repository.
    """

    if not isinstance(path, str):
        return None

    normalized = (
        path
        .replace("\\", "/")
        .strip()
        .rstrip("/")
    )

    if not normalized:
        return None

    return normalized


def _contains_blocked_content(path):
    """
    Detect known secrets, private material, generated caches,
    virtual environments, runtime artifacts, and key files.
    """

    normalized = _normalize_repository_path(
        path
    )

    if not normalized:
        return True

    parts = [
        part.lower()
        for part in normalized.split("/")
        if part
    ]

    blocked_names = {
        value.lower()
        for value in BLOCKED_NAMES
    }

    blocked_directories = {
        value.lower()
        for value in BLOCKED_DIRECTORY_NAMES
    }

    for part in parts:
        if part in blocked_names:
            return True

        if part in blocked_directories:
            return True

    suffix = Path(
        normalized
    ).suffix.lower()

    if suffix in BLOCKED_SUFFIXES:
        return True

    if suffix in {
        ".pyc",
        ".pyo",
    }:
        return True

    return False


def _classify_path(path):
    """
    Classify a repository-relative file.

    Returns:

        source
        blocked
        unknown
    """

    normalized = _normalize_repository_path(
        path
    )

    if not normalized:
        return "unknown"

    if _contains_blocked_content(
        normalized
    ):
        return "blocked"

    # Top-level file.
    if normalized in ALLOWED_DOCUMENTATION_FILES:
        return "source"

    if "/" not in normalized:
        if normalized in ALLOWED_TOP_LEVEL_FILES:
            return "source"

        return "unknown"

    top = normalized.split(
        "/",
        1,
    )[0]

    if top in ALLOWED_SOURCE_DIRECTORIES:
        return "source"

    return "unknown"


# ============================================================
# REPOSITORY CHANGE ENUMERATION
# ============================================================


def _get_tracked_changes():
    """
    Return tracked modifications only.

    Untracked files are deliberately excluded here and
    enumerated separately using Git's ignore-aware command.
    """

    result = _run_command(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
        ],
        cwd=PROJECT_ROOT,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Unable to inspect tracked repository changes: "
            + (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown Git error."
            )
        )

    return [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _get_untracked_files():
    """
    Ask Git to enumerate untracked files while respecting:

    - .gitignore
    - .git/info/exclude
    - global Git ignore configuration

    This is intentionally preferred over Python directory
    recursion.
    """

    result = _run_command(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
        ],
        cwd=PROJECT_ROOT,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Unable to inspect untracked repository files: "
            + (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown Git error."
            )
        )

    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def classify_repository_changes():
    """
    Build the complete finalization candidate set.

    Tracked changes:
        git status --porcelain=v1 --untracked-files=no

    Untracked changes:
        git ls-files --others --exclude-standard

    This makes Git's ignore rules authoritative.
    """

    tracked_lines = _get_tracked_changes()
    untracked_paths = _get_untracked_files()

    candidate_paths = []

    for status_line in tracked_lines:
        path = _parse_status_path(
            status_line
        )

        if not path:
            candidate_paths.append(
                None
            )
            continue

        candidate_paths.append(
            path
        )

    candidate_paths.extend(
        untracked_paths
    )

    source_paths = []
    blocked_paths = []
    unknown_paths = []

    for path in candidate_paths:
        classification = _classify_path(
            path
        )

        if classification == "source":
            source_paths.append(
                path
            )

        elif classification == "blocked":
            blocked_paths.append(
                path
            )

        else:
            unknown_paths.append(
                path
            )

    return {
        "raw": (
            tracked_lines
            + [
                f"?? {path}"
                for path in untracked_paths
            ]
        ),
        "source": sorted(
            set(source_paths)
        ),
        "blocked": sorted(
            set(blocked_paths)
        ),
        "unknown": sorted(
            set(unknown_paths)
        ),
    }


# ============================================================
# SOURCE VALIDATION
# ============================================================


def _compile_project():
    """
    Compile the Python source tree without running the agent.
    """

    command = [
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "agents",
        "brain",
        "desktop",
        "execution",
        "knowledge",
        "providers",
        "skills",
        "tools",
        "main.py",
        "dev.py",
    ]

    result = _run_command(
        command,
        cwd=PROJECT_ROOT,
        timeout=120,
    )

    return {
        "passed":
            result.returncode == 0,
        "stdout":
            result.stdout.strip(),
        "stderr":
            result.stderr.strip(),
    }


def _check_dependencies():
    """
    Verify the active Python environment has no broken
    dependency relationships.
    """

    result = _run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "check",
        ],
        cwd=PROJECT_ROOT,
        timeout=120,
    )

    return {
        "passed":
            result.returncode == 0,
        "stdout":
            result.stdout.strip(),
        "stderr":
            result.stderr.strip(),
    }


def _run_security_regressions():
    """Compilation is not test evidence. Run the fixed suite before mutation."""
    try:
        result = subprocess.run(
            [sys.executable, "-E", "-m", "execution.regression_suite"],
            cwd=PROJECT_ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=180, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"passed": False}
    return {"passed": result.returncode == 0}


# ============================================================
# VERSIONING
# ============================================================


def _increment_patch_version(version):
    """
    Increment the project's current numeric version.

    Example:

        0.011 -> 0.012
    """

    if not isinstance(version, str):
        raise RuntimeError(
            "Current project version is invalid."
        )

    parts = version.strip().split(".")

    if len(parts) != 2:
        raise RuntimeError(
            "Expected project version format x.yyy."
        )

    major = parts[0]
    patch = parts[1]

    if (
        not major.isdigit()
        or not patch.isdigit()
    ):
        raise RuntimeError(
            "Project version contains "
            "non-numeric fields."
        )

    next_patch = int(patch) + 1

    return (
        f"{int(major)}."
        f"{next_patch:0{len(patch)}d}"
    )


# ============================================================
# REPOSITORY SYNCHRONIZATION
# ============================================================


def _verify_core_repository():
    """
    Validate the core repository before mutation.
    """

    repository = inspect_git()

    if not repository:
        raise RuntimeError(
            "Core Git repository inspection failed."
        )

    branch = repository.get(
        "branch"
    )

    if branch != "main":
        raise RuntimeError(
            f"Core repository must be on main, not {branch!r}."
        )

    sync = inspect_sync_status(
        fetch=True
    )

    if not sync.get(
        "fetch_success",
        False,
    ):
        raise RuntimeError(
            "Core Git fetch failed."
        )

    ahead = sync.get(
        "ahead"
    )

    behind = sync.get(
        "behind"
    )

    if (
        ahead is None
        or behind is None
    ):
        raise RuntimeError(
            "Core Git tracking state is unknown."
        )

    if ahead != 0:
        raise RuntimeError(
            "Core repository already contains "
            "unpushed commits."
        )

    if behind != 0:
        raise RuntimeError(
            "Core repository is behind its upstream."
        )

    return sync


def _verify_context_repository():
    """
    Validate the restricted context repository.

    The context publisher already validates that the target
    repository is the dedicated context repository. Here we
    additionally require the expected branch and synchronized
    tracking state.
    """

    context_root = Path(
        CONTEXT_REPOSITORY
    ).resolve()

    if not context_root.exists():
        raise RuntimeError(
            "Context repository does not exist."
        )

    if not (
        context_root / ".git"
    ).exists():
        raise RuntimeError(
            "Context repository is not a Git repository."
        )

    branch_result = _run_command(
        [
            "git",
            "branch",
            "--show-current",
        ],
        cwd=context_root,
        timeout=30,
    )

    if branch_result.returncode != 0:
        raise RuntimeError(
            "Unable to inspect context repository branch."
        )

    branch = branch_result.stdout.strip()

    if branch != "main":
        raise RuntimeError(
            f"Context repository must be on main, "
            f"not {branch!r}."
        )

    fetch_result = _run_command(
        [
            "git",
            "fetch",
            "origin",
        ],
        cwd=context_root,
        timeout=60,
    )

    if fetch_result.returncode != 0:
        raise RuntimeError(
            "Context repository fetch failed: "
            + (
                fetch_result.stderr.strip()
                or fetch_result.stdout.strip()
                or "Unknown Git error."
            )
        )

    tracking = get_tracking_status(
        context_root
    )

    if tracking["ahead"] != 0:
        raise RuntimeError(
            "Context repository already contains "
            "unpushed commits."
        )

    if tracking["behind"] != 0:
        raise RuntimeError(
            "Context repository is behind its upstream."
        )

    return tracking


# ============================================================
# KNOWLEDGE PIPELINE
# ============================================================


def _refresh_knowledge_pipeline():
    """
    Regenerate and verify project-owned knowledge artifacts.

    Flow:

        project state
            ↓
        lightweight AI context
            ↓
        internal bridge
            ↓
        internal integrity verification
            ↓
        sanitized external publication
            ↓
        external integrity verification
            ↓
        controlled context-repository copy
    """

    state_result = (
        synchronize_project_state()
    )

    if state_result is False:
        raise RuntimeError(
            "Project-state synchronization failed."
        )

    context = save_ai_context()

    bridge = refresh_knowledge_bridge()

    if not bridge.get(
        "refreshed",
        False,
    ):
        raise RuntimeError(
            "Internal knowledge bridge "
            "refresh failed."
        )

    bridge_verification = (
        verify_knowledge_bridge()
    )

    if not bridge_verification.get(
        "valid",
        False,
    ):
        raise RuntimeError(
            "Internal knowledge bridge "
            "verification failed: "
            + str(
                bridge_verification.get(
                    "reason"
                )
            )
        )

    publication = (
        create_publication_package()
    )

    if not publication.get(
        "published",
        False,
    ):
        raise RuntimeError(
            "External context publication "
            "was blocked: "
            + str(
                publication.get(
                    "reason"
                )
            )
        )

    publication_verification = (
        verify_publication_package()
    )

    if not publication_verification.get(
        "valid",
        False,
    ):
        raise RuntimeError(
            "External publication verification "
            "failed: "
            + str(
                publication_verification.get(
                    "reason"
                )
            )
        )

    context_copy = (
        publish_to_context_repository()
    )

    if not context_copy.get(
        "published",
        False,
    ):
        raise RuntimeError(
            "Context repository publication failed: "
            + str(
                context_copy.get(
                    "reason"
                )
            )
        )

    return {
        "context":
            context,
        "bridge":
            bridge_verification,
        "publication":
            publication_verification,
        "context_copy":
            context_copy,
    }


# ============================================================
# CORE STAGING VERIFICATION
# ============================================================


def _verify_staged_core_files(
    expected_paths,
):
    """
    Verify that Git staged exactly the approved paths and
    nothing else.
    """

    staged = get_staged_files(
        PROJECT_ROOT
    )

    staged_normalized = {
        path.replace("\\", "/")
        for path in staged
    }

    expected_normalized = {
        path.replace("\\", "/")
        for path in expected_paths
    }

    unexpected = (
        staged_normalized
        - expected_normalized
    )

    missing = (
        expected_normalized
        - staged_normalized
    )

    if unexpected:
        raise RuntimeError(
            "Unexpected files were staged: "
            + ", ".join(
                sorted(unexpected)
            )
        )

    if missing:
        raise RuntimeError(
            "Approved files were not staged: "
            + ", ".join(
                sorted(missing)
            )
        )

    if not staged_normalized:
        raise RuntimeError(
            "No files were staged for the core commit."
        )

    return sorted(
        staged_normalized
    )


# ============================================================
# CONTEXT REPOSITORY
# ============================================================


def _get_context_changed_paths():
    """
    Return normalized changed paths from the restricted
    context repository.
    """

    changes = get_changed_files(
        CONTEXT_REPOSITORY
    )

    paths = []

    for status_line in changes:
        path = _parse_status_path(
            status_line
        )

        if not path:
            raise RuntimeError(
                "Unable to parse context repository change."
            )

        normalized = (
            path
            .replace("\\", "/")
            .strip()
            .rstrip("/")
        )

        paths.append(
            normalized
        )

    return sorted(
        set(paths)
    )


def _commit_context_repository(
    version,
):
    """
    Commit only the approved sanitized publication artifacts.
    """

    actual = _get_context_changed_paths()

    if not actual:
        return {
            "changed": False,
            "committed": False,
            "pushed": False,
        }

    unexpected = (
        set(actual)
        - CONTEXT_ALLOWED_FILES
    )

    if unexpected:
        raise RuntimeError(
            "Unexpected context repository files: "
            + ", ".join(
                sorted(unexpected)
            )
        )

    stage_paths(
        actual,
        CONTEXT_REPOSITORY,
    )

    staged = {
        path.replace("\\", "/")
        for path in get_staged_files(
            CONTEXT_REPOSITORY
        )
    }

    expected = set(
        actual
    )

    if staged != expected:
        raise RuntimeError(
            "Context repository staged-file "
            "verification failed."
        )

    commit_result = commit(
        f"Publish project context v{version}",
        CONTEXT_REPOSITORY,
    )

    push_result = push_current_branch(
        CONTEXT_REPOSITORY
    )

    return {
        "changed": True,
        "committed": True,
        "pushed": True,
        "commit":
            commit_result,
        "push":
            push_result,
    }


# ============================================================
# FINAL VERIFICATION
# ============================================================


def _verify_final_state():
    """
    Verify both repositories and publication integrity after
    finalization.
    """

    repository = inspect_git()

    if not repository:
        raise RuntimeError(
            "Final core Git inspection failed."
        )

    if not repository.get(
        "clean",
        False,
    ):
        raise RuntimeError(
            "Core working tree is not clean "
            "after finalization."
        )

    core_tracking = (
        get_tracking_status(
            PROJECT_ROOT
        )
    )

    if (
        core_tracking["ahead"] != 0
        or core_tracking["behind"] != 0
    ):
        raise RuntimeError(
            "Core repository is not synchronized "
            "after finalization."
        )

    context_changes = (
        get_changed_files(
            CONTEXT_REPOSITORY
        )
    )

    if context_changes:
        raise RuntimeError(
            "Context repository is not clean "
            "after finalization."
        )

    context_tracking = (
        get_tracking_status(
            CONTEXT_REPOSITORY
        )
    )

    if (
        context_tracking["ahead"] != 0
        or context_tracking["behind"] != 0
    ):
        raise RuntimeError(
            "Context repository is not synchronized "
            "after finalization."
        )

    final_publication = (
        verify_publication_package()
    )

    if not final_publication.get(
        "valid",
        False,
    ):
        raise RuntimeError(
            "Final external publication "
            "integrity verification failed."
        )

    return True


# ============================================================
# MAIN FINALIZER
# ============================================================


def finalize_development(
    dry_run=False,
):
    """
    Finalize the current development day.

    DRY RUN performs only validation.

    It deliberately does NOT:

    - update the version
    - complete the development day
    - stage files
    - commit files
    - push repositories
    - regenerate project knowledge
    """

    _print_header(
        dry_run
    )

    try:
        # ----------------------------------------------------
        # 1. CURRENT LIFECYCLE
        # ----------------------------------------------------

        day = get_current_day()
        version = get_current_version()
        project = get_project_info()

        # A completed day must never be finalized again. Reconcile the
        # separately read lifecycle fields before any repository mutation.
        if (type(project) is not dict
                or project.get("status") != "development"
                or type(project.get("current_day")) is not int
                or project.get("current_day") != day
                or project.get("version") != version):
            raise RuntimeError(
                "An active and consistent development day is required."
            )

        if (
            day is None
            or version is None
        ):
            raise RuntimeError(
                "Project lifecycle could not be loaded."
            )

        next_version = (
            _increment_patch_version(
                version
            )
        )

        print(
            f"Day: {day}"
        )
        print(
            f"Current version: {version}"
        )
        print(
            f"Target version: {next_version}"
        )

        # ----------------------------------------------------
        # 2. CLASSIFY REPOSITORY
        # ----------------------------------------------------

        print(
            "\n1. Classifying repository changes..."
        )

        changes = (
            classify_repository_changes()
        )

        if changes["blocked"]:
            raise RuntimeError(
                "Blocked files detected: "
                + ", ".join(
                    changes["blocked"]
                )
            )

        if changes["unknown"]:
            raise RuntimeError(
                "Unknown files detected: "
                + ", ".join(
                    changes["unknown"]
                )
            )

        if not changes["source"]:
            raise RuntimeError(
                "No finalizable source changes detected."
            )

        print(
            "Approved source paths:",
            len(
                changes["source"]
            ),
        )

        for path in changes["source"]:
            print(
                "  -",
                path,
            )

        # ----------------------------------------------------
        # 3. REPOSITORY SYNCHRONIZATION
        # ----------------------------------------------------

        print(
            "\n2. Checking repository synchronization..."
        )

        _verify_core_repository()
        _verify_context_repository()

        print(
            "Core/context repositories: synchronized"
        )

        # ----------------------------------------------------
        # 4. PYTHON COMPILATION
        # ----------------------------------------------------

        print(
            "\n3. Compiling project..."
        )

        compilation = (
            _compile_project()
        )

        if not compilation[
            "passed"
        ]:
            error_text = (
                compilation["stderr"]
                or compilation["stdout"]
                or "Unknown compilation error."
            )

            raise RuntimeError(
                "Compilation failed:\n"
                + error_text
            )

        print(
            "Compilation: PASSED"
        )

        # ----------------------------------------------------
        # 5. DEPENDENCY HEALTH
        # ----------------------------------------------------

        print(
            "\n4. Checking Python dependencies..."
        )

        dependencies = (
            _check_dependencies()
        )

        if not dependencies[
            "passed"
        ]:
            error_text = (
                dependencies["stderr"]
                or dependencies["stdout"]
                or "Unknown pip dependency error."
            )

            raise RuntimeError(
                "Dependency check failed:\n"
                + error_text
            )

        print(
            "Dependency check: PASSED"
        )

        print("\n5. Running required security regressions...")
        if _run_security_regressions().get("passed") is not True:
            raise RuntimeError("Security regression checks failed or could not complete.")
        print("Security regressions: PASSED")

        # ----------------------------------------------------
        # DRY RUN ENDS HERE
        # ----------------------------------------------------

        if dry_run:
            print(
                "\nDRY RUN PASSED."
            )

            print(
                "No version change, completion, "
                "Git stage, commit, push, or "
                "knowledge mutation was performed."
            )

            return True

        # ----------------------------------------------------
        # 6. VERSION TRANSITION
        # ----------------------------------------------------

        print(
            "\n5. Updating project version..."
        )

        version_result = (
            update_project(
                version=next_version
            )
        )

        if version_result is False:
            raise RuntimeError(
                "Project version update failed."
            )

        if (
            get_current_version()
            != next_version
        ):
            raise RuntimeError(
                "Version postcondition failed."
            )

        print(
            "Version:",
            next_version,
        )

        # ----------------------------------------------------
        # 7. KNOWLEDGE REFRESH
        # ----------------------------------------------------

        print(
            "\n6. Refreshing project knowledge..."
        )

        _refresh_knowledge_pipeline()

        print(
            "Internal bridge: VALID"
        )
        print(
            "External publication: VALID"
        )

        # ----------------------------------------------------
        # 8. RECLASSIFY IMMEDIATELY BEFORE STAGING
        # ----------------------------------------------------

        print(
            "\n7. Revalidating repository changes..."
        )

        final_changes = (
            classify_repository_changes()
        )

        if final_changes["blocked"]:
            raise RuntimeError(
                "Blocked files appeared before staging: "
                + ", ".join(
                    final_changes["blocked"]
                )
            )

        if final_changes["unknown"]:
            raise RuntimeError(
                "Unknown files appeared before staging: "
                + ", ".join(
                    final_changes["unknown"]
                )
            )

        if not final_changes["source"]:
            raise RuntimeError(
                "No source changes remain for commit."
            )

        print(
            "Repository changes: VALID"
        )

        # ----------------------------------------------------
        # 9. EXPLICIT CORE STAGING
        # ----------------------------------------------------

        print(
            "\n8. Staging approved core files..."
        )

        stage_paths(
            final_changes["source"],
            PROJECT_ROOT,
        )

        staged = (
            _verify_staged_core_files(
                final_changes["source"]
            )
        )

        print(
            "Staged files verified:",
            len(staged),
        )

        # ----------------------------------------------------
        # 10. CORE COMMIT / PUSH
        # ----------------------------------------------------

        print(
            "\n9. Committing core repository..."
        )

        commit(
            f"Complete Day {day} - "
            f"v{next_version}",
            PROJECT_ROOT,
        )

        push_current_branch(
            PROJECT_ROOT
        )

        print(
            "Core commit: COMPLETE"
        )
        print(
            "Core push: COMPLETE"
        )

        # ----------------------------------------------------
        # 11. COMPLETE DEVELOPMENT DAY
        # ----------------------------------------------------

        print(
            "\n10. Marking development day complete..."
        )

        completion = (
            complete_development_day()
        )

        if completion is not True:
            raise RuntimeError(
                "Development-day completion failed."
            )

        print(
            f"Day {day}: COMPLETED"
        )

        # ----------------------------------------------------
        # 12. REGENERATE COMPLETED-STATE CONTEXT
        # ----------------------------------------------------

        print(
            "\n11. Publishing completed-state context..."
        )

        _refresh_knowledge_pipeline()

        print(
            "Completed-state context: VALID"
        )

        # ----------------------------------------------------
        # 13. COMMIT RESTRICTED CONTEXT REPOSITORY
        # ----------------------------------------------------

        print(
            "\n12. Committing restricted "
            "context repository..."
        )

        context_result = (
            _commit_context_repository(
                next_version
            )
        )

        if context_result[
            "changed"
        ]:
            print(
                "Context commit: COMPLETE"
            )
            print(
                "Context push: COMPLETE"
            )
        else:
            print(
                "Context repository already current."
            )

        # ----------------------------------------------------
        # 14. FINAL VERIFICATION
        # ----------------------------------------------------

        print(
            "\n13. Final verification..."
        )

        _verify_final_state()

        print(
            "Core repository: CLEAN + SYNCHRONIZED"
        )
        print(
            "Context repository: CLEAN + SYNCHRONIZED"
        )
        print(
            "External context: VALID"
        )

        print()
        print(
            "================================"
        )
        print(
            f" DAY {day} FINALIZATION COMPLETE"
        )
        print(
            f" VERSION {next_version}"
        )
        print(
            "================================"
        )

        return True

    except (
        RuntimeError,
        GitWriteError,
        subprocess.SubprocessError,
        OSError,
        ValueError,
    ) as error:
        print()
        print(
            "FINALIZATION BLOCKED:"
        )
        print(
            error
        )

        return False
