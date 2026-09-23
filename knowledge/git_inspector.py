import subprocess
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)


def run_git_command(arguments):
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    except (
        subprocess.SubprocessError,
        OSError,
    ):
        return None


def get_branch():
    return run_git_command(
        [
            "branch",
            "--show-current",
        ]
    )


def get_commit():
    return run_git_command(
        [
            "rev-parse",
            "HEAD",
        ]
    )


def get_short_commit():
    return run_git_command(
        [
            "rev-parse",
            "--short",
            "HEAD",
        ]
    )


def get_remote():
    return run_git_command(
        [
            "remote",
            "get-url",
            "origin",
        ]
    )


def get_changed_files():
    output = run_git_command(
        [
            "status",
            "--porcelain",
        ]
    )

    if not output:
        return []

    return [
        line
        for line in output.splitlines()
        if line.strip()
    ]


def is_clean():
    return len(
        get_changed_files()
    ) == 0


def get_tracking_status():
    output = run_git_command(
        [
            "rev-list",
            "--left-right",
            "--count",
            "HEAD...@{upstream}",
        ]
    )

    if not output:
        return {
            "ahead": None,
            "behind": None,
        }

    parts = output.split()

    if len(parts) != 2:
        return {
            "ahead": None,
            "behind": None,
        }

    return {
        "ahead": int(parts[0]),
        "behind": int(parts[1]),
    }


def inspect_git():
    tracking = get_tracking_status()

    return {
        "branch": get_branch(),
        "commit": get_commit(),
        "short_commit": get_short_commit(),
        "remote": get_remote(),
        "clean": is_clean(),
        "changed_files":
            get_changed_files(),
        "ahead": tracking["ahead"],
        "behind": tracking["behind"],
    }