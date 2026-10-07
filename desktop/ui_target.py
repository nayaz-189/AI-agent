from dataclasses import asdict
from dataclasses import dataclass
from typing import Optional


ALLOWED_TARGET_TYPES = {
    "button",
    "text_field",
    "search_field",
    "menu",
    "menu_item",
    "tab",
    "list",
    "list_item",
    "checkbox",
    "radio_button",
    "link",
    "text",
    "icon",
    "image",
    "unknown",
}


@dataclass
class UITarget:
    """
    Standard representation of a UI element found
    through semantic UI Automation or visual analysis.

    Coordinates are relative to the captured target
    window, not absolute desktop coordinates.
    """

    label: str
    target_type: str

    confidence: float

    x: int
    y: int

    width: int
    height: int

    source: str

    text: Optional[str] = None

    description: Optional[str] = None


def validate_target(target):
    """
    Validate a semantic UI target.

    This performs structural validation only.
    It does not click or otherwise interact with
    the target.
    """

    result = {
        "valid": False,
        "errors": [],
    }

    if not isinstance(target, UITarget):
        result["errors"].append(
            "Target must be a UITarget."
        )
        return result

    if (
        not isinstance(target.label, str)
        or not target.label.strip()
    ):
        result["errors"].append(
            "Target label is required."
        )

    if target.target_type not in ALLOWED_TARGET_TYPES:
        result["errors"].append(
            "Unsupported target type."
        )

    if not isinstance(
        target.confidence,
        (int, float),
    ):
        result["errors"].append(
            "Confidence must be numeric."
        )

    elif not (
        0.0
        <= target.confidence
        <= 1.0
    ):
        result["errors"].append(
            "Confidence must be between "
            "0.0 and 1.0."
        )

    for field_name in (
        "x",
        "y",
        "width",
        "height",
    ):
        value = getattr(
            target,
            field_name,
        )

        if (
            not isinstance(value, int)
            or value < 0
        ):
            result["errors"].append(
                f"{field_name} must be "
                f"a non-negative integer."
            )

    if (
        isinstance(target.width, int)
        and target.width == 0
    ):
        result["errors"].append(
            "Target width cannot be zero."
        )

    if (
        isinstance(target.height, int)
        and target.height == 0
    ):
        result["errors"].append(
            "Target height cannot be zero."
        )

    if (
        not isinstance(target.source, str)
        or not target.source.strip()
    ):
        result["errors"].append(
            "Target source is required."
        )

    result["valid"] = (
        len(result["errors"]) == 0
    )

    return result


def target_center(target):
    """
    Calculate the target's center point relative
    to the captured application window.
    """

    validation = validate_target(
        target
    )

    if not validation["valid"]:
        return None

    return {
        "x": (
            target.x
            + target.width // 2
        ),
        "y": (
            target.y
            + target.height // 2
        ),
    }


def target_to_dict(target):
    """
    Convert a validated UITarget into a plain
    dictionary suitable for IPC/JSON later.
    """

    validation = validate_target(
        target
    )

    if not validation["valid"]:
        return None

    return asdict(target)


if __name__ == "__main__":

    example = UITarget(
        label="Search",
        target_type="search_field",
        confidence=0.97,
        x=40,
        y=80,
        width=300,
        height=42,
        source="test",
        text="Search",
        description=(
            "Example semantic UI target."
        ),
    )

    print(
        "Target:",
        target_to_dict(example),
    )

    print(
        "Validation:",
        validate_target(example),
    )

    print(
        "Center:",
        target_center(example),
    )