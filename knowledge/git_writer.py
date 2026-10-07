import subprocess
from pathlib import Path

from knowledge.git_inspector import PROJECT_ROOT


class GitWriteError(RuntimeError):
    """
    Raised when a controlled Git write operation cannot
    be completed safely.
    """


def _resolve_repository_root(repository_root=None):
    """
    Resolve and validate the repository root.

    The core project is used by default, but an explicitly
    supplied repository such as the sanitized context
    repository may also be used.
    """

    if repository_root is None:
        root = PROJECT_ROOT.resolve()
    else:
        root = Path(repository_root).resolve()

    if not root.exists():
        raise GitWriteError(
            f"Repository does not exist: {root}"
        )

    if not root.is_dir():
        raise GitWriteError(
            f"Repository path is not a directory: {root}"
        )

    if not (root / ".git").exists():
        raise GitWriteError(
            f"Path is not a Git repository: {root}"
        )

    return root


def _run_git(arguments, repository_root=None):
    """
    Execute Git inside one explicitly validated repository.

    Returns stripped stdout on success.
    Raises GitWriteError on failure.
    """

    root = _resolve_repository_root(
        repository_root
    )

    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    except (
        subprocess.SubprocessError,
        OSError,
    ) as exc:
        raise GitWriteError(
            f"Git command could not run: {' '.join(arguments)}"
        ) from exc

    if result.returncode != 0:
        error = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Unknown Git error."
        )

        raise GitWriteError(
            f"Git command failed: {error}"
        )

    return result.stdout.strip()


def _normalize_relative_path(
    path,
    repository_root=None,
):
    """
    Convert a requested path into a safe repository-relative
    path.

    Paths outside the selected repository are rejected.
    """

    root = _resolve_repository_root(
        repository_root
    )

    candidate = Path(path)

    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (
            root / candidate
        ).resolve()

    try:
        relative = resolved.relative_to(
            root
        )
    except ValueError as exc:
        raise GitWriteError(
            "Refusing Git write outside repository root."
        ) from exc

    if str(relative) in ("", "."):
        raise GitWriteError(
            "Repository root cannot be staged directly."
        )

    return relative


def get_branch(repository_root=None):
    return _run_git(
        [
            "branch",
            "--show-current",
        ],
        repository_root,
    )


def get_tracking_status(repository_root=None):
    output = _run_git(
        [
            "rev-list",
            "--left-right",
            "--count",
            "HEAD...@{upstream}",
        ],
        repository_root,
    )

    parts = output.split()

    if len(parts) != 2:
        raise GitWriteError(
            "Unable to determine Git tracking status."
        )

    return {
        "ahead": int(parts[0]),
        "behind": int(parts[1]),
    }


def get_changed_files(repository_root=None):
    output = _run_git(
        [
            "status",
            "--porcelain",
        ],
        repository_root,
    )

    if not output:
        return []

    return [
        line
        for line in output.splitlines()
        if line.strip()
    ]


def stage_paths(
    paths,
    repository_root=None,
):
    """
    Stage only explicitly supplied paths.

    There is intentionally no stage-all operation.
    """

    if not isinstance(
        paths,
        (list, tuple),
    ):
        raise GitWriteError(
            "Stage paths must be supplied as a list or tuple."
        )

    if not paths:
        raise GitWriteError(
            "No paths were supplied for staging."
        )

    normalized = []

    for path in paths:
        relative = _normalize_relative_path(
            path,
            repository_root,
        )

        normalized.append(
            relative.as_posix()
        )

    _run_git(
        [
            "add",
            "--",
            *normalized,
        ],
        repository_root,
    )

    return {
        "staged": True,
        "paths": normalized,
    }


def get_staged_files(repository_root=None):
    output = _run_git(
        [
            "diff",
            "--cached",
            "--name-only",
        ],
        repository_root,
    )

    if not output:
        return []

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


def commit(
    message,
    repository_root=None,
):
    """
    Commit the existing Git index.

    This function never stages files.
    """

    if not isinstance(message, str):
        raise GitWriteError(
            "Commit message must be a string."
        )

    message = message.strip()

    if not message:
        raise GitWriteError(
            "Commit message cannot be empty."
        )

    staged_files = get_staged_files(
        repository_root
    )

    if not staged_files:
        raise GitWriteError(
            "Refusing commit because nothing is staged."
        )

    output = _run_git(
        [
            "commit",
            "-m",
            message,
        ],
        repository_root,
    )

    return {
        "committed": True,
        "message": message,
        "files": staged_files,
        "output": output,
    }


def push_current_branch(repository_root=None):
    """
    Push the selected repository's current branch.

    Refuse to push when the local branch is behind upstream.
    """

    branch = get_branch(
        repository_root
    )

    if not branch:
        raise GitWriteError(
            "Unable to determine current Git branch."
        )

    tracking = get_tracking_status(
        repository_root
    )

    if tracking["behind"] > 0:
        raise GitWriteError(
            "Refusing push because the local branch "
            "is behind its upstream."
        )

    output = _run_git(
        ["push"],
        repository_root,
    )

    return {
        "pushed": True,
        "branch": branch,
        "output": output,
    }