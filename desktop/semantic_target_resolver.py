from __future__ import annotations

from typing import Any, Dict, List, Optional

from pywinauto import Desktop


ROLE_TO_CONTROL_TYPES = {
    "document": {"Document"},
    "text_field": {"Edit", "Document"},
    "search_field": {"Edit"},
    "button": {"Button"},
    "tab": {"TabItem"},
    "list": {"List"},
    "list_item": {"ListItem"},
    "menu": {"Menu", "MenuBar"},
    "menu_item": {"MenuItem"},
    "checkbox": {"CheckBox"},
    "radio_button": {"RadioButton"},
    "link": {"Hyperlink"},
    "text": {"Text"},
}


TOGGLE_STATES = {
    0: "off",
    1: "on",
    2: "indeterminate",
}


def normalize_semantic_text(
    value: Optional[str],
) -> str:
    if value is None:
        return ""

    return (
        value
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


class SemanticTargetResolver:
    """
    Read-only semantic UI target resolver.

    Produces serializable observations describing:
        - semantic identity
        - capabilities
        - observable state

    Descriptors are observations, not executable objects.

    Any state-changing operation must reacquire and
    revalidate the live UIA control before execution.
    """

    def __init__(
        self,
        max_controls: int = 500,
    ):
        self.max_controls = max_controls

    def _connect_window(
        self,
        window_handle: int,
    ):
        return Desktop(
            backend="uia"
        ).window(
            handle=window_handle
        )

    def _safe_attribute(
        self,
        control,
        attribute: str,
        default=None,
    ):
        try:
            value = getattr(
                control.element_info,
                attribute,
            )

            if value is None:
                return default

            return value

        except Exception:
            return default

    def _control_name(
        self,
        control,
    ) -> str:
        try:
            return normalize_semantic_text(
                control.window_text()
            )
        except Exception:
            return ""

    def _handle(
        self,
        control,
    ):
        try:
            handle = control.handle

            if isinstance(handle, int):
                return handle

            return None

        except Exception:
            return None

    def _supports_pattern(
        self,
        control,
        attribute: str,
    ) -> bool:
        try:
            return (
                hasattr(control, attribute)
                and getattr(
                    control,
                    attribute,
                )
                is not None
            )
        except Exception:
            return False

    def _read_selection_state(
        self,
        control,
        supports_selection_item: bool,
    ) -> Optional[bool]:
        """
        Read SelectionItemPattern.CurrentIsSelected.

        Returns:
            True  -> selected
            False -> not selected
            None  -> state unavailable / unsupported

        This method is strictly read-only.
        """

        if not supports_selection_item:
            return None

        try:
            pattern = (
                control.iface_selection_item
            )

            if pattern is None:
                return None

            value = pattern.CurrentIsSelected

            if value in (True, 1):
                return True

            if value in (False, 0):
                return False

            return None

        except Exception:
            return None

    def _read_toggle_state(
        self,
        control,
        supports_toggle: bool,
    ) -> Optional[str]:
        """
        Read TogglePattern.CurrentToggleState.

        Normalized states:
            "off"
            "on"
            "indeterminate"

        Returns None when TogglePattern is unsupported
        or the live state cannot be read.

        This method is strictly read-only.
        """

        if not supports_toggle:
            return None

        try:
            pattern = control.iface_toggle

            if pattern is None:
                return None

            value = pattern.CurrentToggleState

            # UI Automation ToggleState:
            #   0 = Off
            #   1 = On
            #   2 = Indeterminate
            #
            # int(...) also handles enum-like COM
            # values when pywinauto exposes them.
            try:
                numeric_value = int(value)
            except (TypeError, ValueError):
                numeric_value = value

            return TOGGLE_STATES.get(
                numeric_value
            )

        except Exception:
            return None

    def _build_target_descriptor(
        self,
        window_handle: int,
        index: int,
        control,
    ) -> Dict[str, Any]:

        name = self._control_name(
            control
        )

        control_type = (
            self._safe_attribute(
                control,
                "control_type",
                "",
            )
            or ""
        )

        class_name = (
            self._safe_attribute(
                control,
                "class_name",
                "",
            )
            or ""
        )

        automation_id = (
            self._safe_attribute(
                control,
                "automation_id",
                "",
            )
            or ""
        )

        control_handle = self._handle(
            control
        )

        capabilities = {
            "value": self._supports_pattern(
                control,
                "iface_value",
            ),

            "selection_item": (
                self._supports_pattern(
                    control,
                    "iface_selection_item",
                )
            ),

            "invoke": self._supports_pattern(
                control,
                "iface_invoke",
            ),

            "toggle": self._supports_pattern(
                control,
                "iface_toggle",
            ),
        }

        state = {
            "selected": (
                self._read_selection_state(
                    control,
                    capabilities[
                        "selection_item"
                    ],
                )
            ),

            "toggle": (
                self._read_toggle_state(
                    control,
                    capabilities[
                        "toggle"
                    ],
                )
            ),
        }

        fingerprint = {
            "window_handle": window_handle,
            "control_type": control_type,
            "name": name,
            "automation_id": automation_id,
            "class_name": class_name,
            "control_handle": control_handle,
        }

        return {
            # Diagnostic only.
            # Never use index alone as persistent
            # target identity.
            "index": index,

            "name": name,
            "control_type": control_type,
            "class_name": class_name,
            "automation_id": automation_id,
            "handle": control_handle,

            "capabilities": capabilities,

            # Observable semantic state.
            "state": state,

            # Compatibility fields.
            "supports_value_pattern": (
                capabilities["value"]
            ),

            "supports_selection_item": (
                capabilities[
                    "selection_item"
                ]
            ),

            "fingerprint": fingerprint,
        }

    def inspect_targets(
        self,
        window_handle: int,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "window_handle": window_handle,
            "targets": [],
            "error": None,
        }

        if not isinstance(
            window_handle,
            int,
        ):
            result["error"] = (
                "window_handle must be an integer."
            )
            return result

        try:
            window = self._connect_window(
                window_handle
            )

            controls = window.descendants()

            for index, control in enumerate(
                controls[: self.max_controls]
            ):
                result["targets"].append(
                    self._build_target_descriptor(
                        window_handle,
                        index,
                        control,
                    )
                )

            result["success"] = True
            return result

        except Exception as exc:
            result["error"] = (
                "Semantic target inspection "
                f"failed: {exc}"
            )
            return result

    def find_targets(
        self,
        window_handle: int,
        role: Optional[str] = None,
        name: Optional[str] = None,
        exact_name: bool = False,
        current_value: Optional[str] = None,
        automation_id: Optional[str] = None,
        class_name: Optional[str] = None,
        required_capability: Optional[str] = None,
        selected: Optional[bool] = None,
        toggle_state: Optional[str] = None,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "window_handle": window_handle,

            "query": {
                "role": role,
                "name": name,
                "exact_name": exact_name,
                "current_value": current_value,
                "automation_id": automation_id,
                "class_name": class_name,
                "required_capability": (
                    required_capability
                ),
                "selected": selected,
                "toggle_state": toggle_state,
            },

            "targets": [],
            "error": None,
        }

        if (
            role is not None
            and role
            not in ROLE_TO_CONTROL_TYPES
        ):
            result["error"] = (
                f"Unknown semantic role: {role!r}."
            )
            return result

        allowed_capabilities = {
            "value",
            "selection_item",
            "invoke",
            "toggle",
        }

        if (
            required_capability is not None
            and required_capability
            not in allowed_capabilities
        ):
            result["error"] = (
                "Unknown required capability: "
                f"{required_capability!r}."
            )
            return result

        if (
            selected is not None
            and not isinstance(selected, bool)
        ):
            result["error"] = (
                "selected filter must be boolean "
                "or None."
            )
            return result

        if (
            toggle_state is not None
            and toggle_state
            not in {
                "off",
                "on",
                "indeterminate",
            }
        ):
            result["error"] = (
                "toggle_state must be one of: "
                "'off', 'on', 'indeterminate', "
                "or None."
            )
            return result

        inspection = self.inspect_targets(
            window_handle
        )

        if not inspection["success"]:
            result["error"] = (
                inspection["error"]
            )
            return result

        targets: List[Dict[str, Any]] = (
            inspection["targets"]
        )

        if role is not None:
            allowed_types = (
                ROLE_TO_CONTROL_TYPES[
                    role
                ]
            )

            targets = [
                target
                for target in targets
                if target["control_type"]
                in allowed_types
            ]

        if name is not None:
            normalized_name = (
                normalize_semantic_text(
                    name
                ).casefold()
            )

            if exact_name:
                targets = [
                    target
                    for target in targets
                    if (
                        target["name"]
                        .casefold()
                        == normalized_name
                    )
                ]

            else:
                targets = [
                    target
                    for target in targets
                    if normalized_name
                    in (
                        target["name"]
                        .casefold()
                    )
                ]

        if current_value is not None:
            normalized_value = (
                normalize_semantic_text(
                    current_value
                )
            )

            targets = [
                target
                for target in targets
                if normalize_semantic_text(
                    target["name"]
                )
                == normalized_value
            ]

        if automation_id is not None:
            targets = [
                target
                for target in targets
                if target["automation_id"]
                == automation_id
            ]

        if class_name is not None:
            targets = [
                target
                for target in targets
                if target["class_name"]
                == class_name
            ]

        if required_capability is not None:
            targets = [
                target
                for target in targets
                if (
                    target[
                        "capabilities"
                    ].get(
                        required_capability,
                        False,
                    )
                )
            ]

        if selected is not None:
            targets = [
                target
                for target in targets
                if (
                    target[
                        "state"
                    ].get(
                        "selected"
                    )
                    is selected
                )
            ]

        if toggle_state is not None:
            targets = [
                target
                for target in targets
                if (
                    target[
                        "state"
                    ].get(
                        "toggle"
                    )
                    == toggle_state
                )
            ]

        result["targets"] = targets
        result["success"] = True

        return result

    def resolve_unique_target(
        self,
        window_handle: int,
        role: Optional[str] = None,
        name: Optional[str] = None,
        exact_name: bool = False,
        current_value: Optional[str] = None,
        automation_id: Optional[str] = None,
        class_name: Optional[str] = None,
        required_capability: Optional[str] = None,
        selected: Optional[bool] = None,
        toggle_state: Optional[str] = None,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "window_handle": window_handle,
            "target": None,
            "error": None,
        }

        search = self.find_targets(
            window_handle=window_handle,
            role=role,
            name=name,
            exact_name=exact_name,
            current_value=current_value,
            automation_id=automation_id,
            class_name=class_name,
            required_capability=(
                required_capability
            ),
            selected=selected,
            toggle_state=toggle_state,
        )

        if not search["success"]:
            result["error"] = search["error"]
            return result

        targets = search["targets"]

        if len(targets) == 0:
            result["error"] = (
                "No semantic target matched "
                "the requested criteria."
            )
            return result

        if len(targets) > 1:
            result["error"] = (
                "Semantic target is ambiguous: "
                f"{len(targets)} matches."
            )
            return result

        result["target"] = targets[0]
        result["success"] = True

        return result


if __name__ == "__main__":
    resolver = SemanticTargetResolver()

    print(
        "SemanticTargetResolver loaded."
    )
    print(
        "Target capabilities and observable "
        "semantic state enabled."
    )
    print(
        "Selection and toggle state observation "
        "available."
    )
    print(
        "No desktop action executed."
    )