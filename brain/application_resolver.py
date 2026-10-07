import json
import os
import re
import subprocess

from pathlib import Path
from difflib import SequenceMatcher


START_MENU_LOCATIONS = [
    Path(
        os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    )
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs",

    Path(
        os.environ.get("APPDATA", "")
    )
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs",
]


_APPLICATION_INDEX = None


def normalize_name(name):
    return "".join(
        character
        for character in name.lower()
        if character.isalnum()
    )


def get_words(name):
    return re.findall(
        r"[a-zA-Z0-9]+",
        name.lower(),
    )


def discover_shortcut_applications():
    """
    Discover traditional Start Menu .lnk applications.
    """

    applications = []

    for location in START_MENU_LOCATIONS:

        if not location.exists():
            continue

        for shortcut in location.rglob("*.lnk"):

            applications.append(
                {
                    "name": shortcut.stem,
                    "launch_type": "shortcut",
                    "launch_target": str(shortcut),
                    "normalized_name": normalize_name(
                        shortcut.stem
                    ),
                }
            )

    return applications


def discover_packaged_applications():
    """
    Discover applications exposed by Windows Get-StartApps.

    This includes many packaged/system applications such as
    Calculator, Notepad, and Microsoft Store applications.
    """

    powershell_command = (
        "Get-StartApps | "
        "Select-Object Name, AppID | "
        "ConvertTo-Json -Compress"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                powershell_command,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ) as error:

        print(
            "Packaged application discovery failed:",
            error,
        )

        return []

    if result.returncode != 0:

        print(
            "Packaged application discovery "
            "returned an error."
        )

        return []

    output = result.stdout.strip()

    if not output:
        return []

    try:
        data = json.loads(output)

    except json.JSONDecodeError:

        print(
            "Could not parse packaged "
            "application discovery output."
        )

        return []

    # PowerShell returns one object instead of
    # a list when only one application exists.

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    applications = []

    for item in data:

        if not isinstance(item, dict):
            continue

        name = item.get("Name")
        app_id = item.get("AppID")

        if (
            not isinstance(name, str)
            or not isinstance(app_id, str)
        ):
            continue

        name = name.strip()
        app_id = app_id.strip()

        if not name or not app_id:
            continue

        applications.append(
            {
                "name": name,
                "launch_type": "app_id",
                "launch_target": app_id,
                "normalized_name": normalize_name(
                    name
                ),
            }
        )

    return applications


def discover_applications():
    """
    Discover applications from all currently supported
    Windows application sources.
    """

    applications = []

    applications.extend(
        discover_shortcut_applications()
    )

    applications.extend(
        discover_packaged_applications()
    )

    return applications


def build_application_index():
    """
    Build a deduplicated application index.

    If the same application name appears through multiple
    discovery mechanisms, prefer an AppID because it is a
    direct Windows application identity.
    """

    applications = discover_applications()

    application_index = {}

    for app in applications:

        normalized_name = app[
            "normalized_name"
        ]

        existing = application_index.get(
            normalized_name
        )

        if existing is None:

            application_index[
                normalized_name
            ] = app

            continue

        if (
            app["launch_type"] == "app_id"
            and existing["launch_type"]
            != "app_id"
        ):

            application_index[
                normalized_name
            ] = app

    return application_index


def get_application_index():
    global _APPLICATION_INDEX

    if _APPLICATION_INDEX is None:

        print(
            "Building application index..."
        )

        _APPLICATION_INDEX = (
            build_application_index()
        )

        print(
            f"Application index ready: "
            f"{len(_APPLICATION_INDEX)} apps"
        )

    return _APPLICATION_INDEX


def refresh_application_index():
    """
    Force application discovery to run again.
    """

    global _APPLICATION_INDEX

    _APPLICATION_INDEX = None

    return get_application_index()


def make_acronym(name):
    words = get_words(name)

    return "".join(
        word[0]
        for word in words
        if word
    )


def generate_aliases(name):
    words = get_words(name)

    aliases = {
        normalize_name(name),
        make_acronym(name),
    }

    if len(words) >= 2:

        compact_alias = (
            "".join(
                word[0]
                for word in words[:-1]
                if word
            )
            + words[-1]
        )

        aliases.add(
            normalize_name(
                compact_alias
            )
        )

    return aliases


def find_application(target):

    target_normalized = normalize_name(
        target
    )

    target_words = get_words(
        target
    )

    if not target_normalized:
        return None

    application_index = (
        get_application_index()
    )

    applications = (
        application_index.values()
    )

    candidates = []

    for app in applications:

        app_name = app[
            "normalized_name"
        ]

        app_words = get_words(
            app["name"]
        )

        aliases = generate_aliases(
            app["name"]
        )

        score = 0

        # -------------------------
        # EXACT MATCH
        # -------------------------

        if app_name == target_normalized:

            score = 100

        # -------------------------
        # GENERATED ALIAS
        # -------------------------

        elif target_normalized in aliases:

            score = 95

        # -------------------------
        # SINGLE REAL WORD
        # -------------------------

        elif (
            len(target_words) == 1
            and target_words[0]
            in app_words
        ):

            score = 85

        # -------------------------
        # LONGER SUBSTRING
        # -------------------------

        elif (
            len(target_normalized) >= 4
            and target_normalized
            in app_name
        ):

            score = 80

        # -------------------------
        # APPLICATION NAME
        # INSIDE USER TARGET
        # -------------------------

        elif (
            len(app_name) >= 4
            and app_name
            in target_normalized
        ):

            score = 75

        # -------------------------
        # FUZZY / TYPO MATCHING
        # -------------------------

        else:

            similarity = SequenceMatcher(
                None,
                target_normalized,
                app_name,
            ).ratio()

            score = round(
                similarity * 100
            )

        if score >= 55:

            candidates.append(
                {
                    "name": app["name"],
                    "launch_type":
                        app["launch_type"],
                    "launch_target":
                        app["launch_target"],
                    "score": score,
                }
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda app: app["score"],
        reverse=True,
    )

    print(
        "\nApplication candidates:"
    )

    for candidate in candidates[:5]:

        print(
            candidate["score"],
            candidate["name"],
            f"[{candidate['launch_type']}]",
        )

    best = candidates[0]

    # -------------------------
    # LOW CONFIDENCE
    # -------------------------

    if best["score"] < 70:

        print(
            "Application match "
            "confidence is too low."
        )

        return None

    # -------------------------
    # EXACT MATCH
    # -------------------------

    if best["score"] == 100:

        return {
            "status": "resolved",
            "application": best,
        }

    # -------------------------
    # AMBIGUITY DETECTION
    # -------------------------

    if len(candidates) > 1:

        second_best = candidates[1]

        score_gap = (
            best["score"]
            - second_best["score"]
        )

        if score_gap < 10:

            ambiguous_candidates = []

            for candidate in candidates:

                candidate_gap = (
                    best["score"]
                    - candidate["score"]
                )

                if candidate_gap < 10:

                    ambiguous_candidates.append(
                        candidate
                    )

            print(
                "\nApplication match "
                "is ambiguous."
            )

            return {
                "status": "ambiguous",
                "candidates":
                    ambiguous_candidates,
            }

    # -------------------------
    # CLEAR WINNER
    # -------------------------

    return {
        "status": "resolved",
        "application": best,
    }


if __name__ == "__main__":

    for test_target in [
        "calculator",
        "notepad",
        "whatsapp",
        "vs code",
    ]:

        print()
        print(
            f"Testing: {test_target}"
        )

        print(
            find_application(
                test_target
            )
        )