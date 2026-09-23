import os
import re

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


def discover_applications():
    applications = []

    for location in START_MENU_LOCATIONS:

        if not location.exists():
            continue

        for shortcut in location.rglob("*.lnk"):

            applications.append(
                {
                    "name": shortcut.stem,
                    "path": str(shortcut),
                    "normalized_name": normalize_name(
                        shortcut.stem
                    ),
                }
            )

    return applications


def build_application_index():
    applications = discover_applications()

    application_index = {}

    for app in applications:

        normalized_name = app[
            "normalized_name"
        ]

        if normalized_name not in application_index:
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

    # Example:
    #
    # Visual Studio Code
    #
    # visualstudiocode
    # vsc
    # vscode

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
        #
        # "ide" matches:
        # Arduino IDE
        # Antigravity IDE
        #
        # But does not match:
        # Video Editor
        #

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

        # Don't retain extremely
        # weak candidates.

        if score >= 55:

            candidates.append(
                {
                    "name": app["name"],
                    "path": app["path"],
                    "score": score,
                }
            )

    # Nothing even remotely matched.

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