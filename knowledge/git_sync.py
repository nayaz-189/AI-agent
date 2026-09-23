from knowledge.git_inspector import (
    get_changed_files,
    get_tracking_status,
    run_git_command,
)


def fetch_remote():
    result = run_git_command(
        [
            "fetch",
            "origin",
        ]
    )

    # git fetch often produces no stdout
    # when successful, so None is the only
    # failure signal from our current helper.
    #
    # Verify that origin/main exists instead
    # of relying on fetch output.
    remote_branch = run_git_command(
        [
            "rev-parse",
            "--verify",
            "origin/main",
        ]
    )

    return remote_branch is not None


def inspect_sync_status(
    fetch=True,
):
    fetch_success = None

    if fetch:
        fetch_success = (
            fetch_remote()
        )

    tracking = (
        get_tracking_status()
    )

    changed_files = (
        get_changed_files()
    )

    ahead = tracking.get(
        "ahead"
    )

    behind = tracking.get(
        "behind"
    )

    working_tree_clean = (
        len(changed_files) == 0
    )

    synchronized = (
        ahead == 0
        and behind == 0
    )

    return {
        "fetch_success":
            fetch_success,

        "working_tree_clean":
            working_tree_clean,

        "changed_files":
            changed_files,

        "ahead":
            ahead,

        "behind":
            behind,

        "remote_synchronized":
            synchronized,

        "safe_to_pull":
            (
                working_tree_clean
                and behind is not None
                and behind > 0
                and ahead == 0
            ),
    }