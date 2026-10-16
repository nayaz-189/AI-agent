from __future__ import annotations

import time
from typing import Any, Dict, Optional

from pywinauto import Desktop

from desktop.window_manager import find_windows
from desktop.semantic_target_resolver import (
    ROLE_TO_CONTROL_TYPES,
    SemanticTargetResolver,
)


def normalize_text(value: Optional[str]) -> str:
    """
    Normalize UIA text for state comparison.
    """
    if value is None:
        return ""

    return (
        value
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .rstrip("\n")
    )


class SemanticController:
    """
    Controlled semantic Windows UI controller.

    Responsibilities:
        - resolve semantic targets
        - reacquire targets before execution
        - perform permitted semantic operations
        - invalidate stale observations after mutation
        - verify resulting UI state

    This controller does NOT grant permission.
    DesktopActionGate remains the authorization boundary.
    """

    def __init__(
        self,
        reacquire_delay: float = 0.25,
    ):
        self.reacquire_delay = reacquire_delay
        self.target_resolver = SemanticTargetResolver()

    # -------------------------------------------------
    # Window resolution
    # -------------------------------------------------

    def resolve_unique_window(
        self,
        query: str,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "query": query,
            "window": None,
            "matches": [],
            "error": None,
        }

        if (
            not isinstance(query, str)
            or not query.strip()
        ):
            result["error"] = (
                "Window query must be a "
                "non-empty string."
            )
            return result

        matches = find_windows(
            query.strip(),
            include_hidden=True,
        )

        result["matches"] = matches

        if len(matches) == 0:
            result["error"] = (
                f"No window matched {query!r}."
            )
            return result

        if len(matches) > 1:
            result["error"] = (
                f"Window query {query!r} is "
                f"ambiguous: {len(matches)} "
                "matches."
            )
            return result

        result["window"] = matches[0]
        result["success"] = True

        return result

    def _connect_window(
        self,
        handle: int,
    ):
        """
        Always obtain a fresh UIA wrapper.
        """
        return Desktop(
            backend="uia"
        ).window(
            handle=handle
        )

    # -------------------------------------------------
    # Semantic inspection / resolution
    # -------------------------------------------------

    def inspect_semantic_targets(
        self,
        window_handle: int,
    ) -> Dict[str, Any]:

        return (
            self.target_resolver
            .inspect_targets(
                window_handle
            )
        )

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
    ) -> Dict[str, Any]:

        return (
            self.target_resolver
            .resolve_unique_target(
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
            )
        )

    # -------------------------------------------------
    # Target identity / reacquisition
    # -------------------------------------------------

    def _control_matches_descriptor(
        self,
        control,
        descriptor: Dict[str, Any],
        expected_value: Optional[str],
    ) -> bool:
        """
        Compare a fresh UIA control against an
        authorized semantic descriptor.

        We intentionally do not trust the old UIA
        wrapper after planning or mutation.
        """

        try:
            info = control.element_info

            control_type = (
                info.control_type or ""
            )

            class_name = (
                info.class_name or ""
            )

            automation_id = (
                info.automation_id or ""
            )

            name = normalize_text(
                control.window_text()
            )

            fingerprint = descriptor[
                "fingerprint"
            ]

            if (
                control_type
                != fingerprint[
                    "control_type"
                ]
            ):
                return False

            if (
                class_name
                != fingerprint[
                    "class_name"
                ]
            ):
                return False

            if (
                automation_id
                != fingerprint[
                    "automation_id"
                ]
            ):
                return False

            expected_handle = (
                fingerprint.get(
                    "control_handle"
                )
            )

            if expected_handle is not None:
                try:
                    if (
                        control.handle
                        != expected_handle
                    ):
                        return False
                except Exception:
                    return False

            if expected_value is not None:
                # Only scoped resolvers expose ValuePattern data. Do not read
                # values from arbitrary/password controls during discovery.
                if "value" in descriptor:
                    return str(control.iface_value.CurrentValue) == expected_value
                if (
                    name
                    != normalize_text(
                        expected_value
                    )
                ):
                    return False

            else:
                expected_name = (
                    fingerprint.get(
                        "name",
                        "",
                    )
                )

                if (
                    expected_name
                    and name
                    != normalize_text(
                        expected_name
                    )
                ):
                    return False

            return True

        except Exception:
            return False

    def _reacquire_target_for_execution(
        self,
        window_handle: int,
        descriptor: Dict[str, Any],
        expected_value: Optional[str],
    ):
        """
        Reacquire exactly one live UIA object matching
        the previously observed target descriptor.
        """

        window = self._connect_window(
            window_handle
        )

        control_type = descriptor[
            "control_type"
        ]

        candidates = window.descendants(
            control_type=control_type
        )

        matching = [
            control
            for control in candidates
            if self._control_matches_descriptor(
                control,
                descriptor,
                expected_value,
            )
        ]

        if len(matching) != 1:
            return None

        return matching[0]
    def _read_live_toggle_state(
        self,
        control,
    ) -> Optional[str]:
        """
        Read TogglePattern.CurrentToggleState from a
        freshly acquired control.

        Returns:
            "off"
            "on"
            "indeterminate"
            None -> unavailable
        """

        try:
            if not (
                hasattr(
                    control,
                    "iface_toggle",
                )
                and control.iface_toggle
                is not None
            ):
                return None

            value = (
                control
                .iface_toggle
                .CurrentToggleState
            )

            try:
                numeric_value = int(value)
            except (TypeError, ValueError):
                return None

            toggle_states = {
                0: "off",
                1: "on",
                2: "indeterminate",
            }

            return toggle_states.get(
                numeric_value
            )

        except Exception:
            return None
        
    def _read_live_selected_state(
        self,
        control,
    ) -> Optional[bool]:
        """
        Read SelectionItemPattern.CurrentIsSelected
        from a freshly acquired control.

        Returns:
            True  -> selected
            False -> not selected
            None  -> unavailable
        """

        try:
            if not (
                hasattr(
                    control,
                    "iface_selection_item",
                )
                and control.iface_selection_item
                is not None
            ):
                return None

            value = (
                control
                .iface_selection_item
                .CurrentIsSelected
            )

            if value in (True, 1):
                return True

            if value in (False, 0):
                return False

            return None

        except Exception:
            return None

    # -------------------------------------------------
    # Generic ValuePattern mutation
    # -------------------------------------------------

    def set_value(
        self,
        window_handle: int,
        target: Dict[str, Any],
        expected_before: str,
        new_value: str,
    ) -> Dict[str, Any]:
        """
        Generic semantic ValuePattern mutation.

        Safety sequence:

            semantic query
                ↓
            unique target
                ↓
            ValuePattern capability
                ↓
            expected-before precondition
                ↓
            target fingerprint
                ↓
            reacquire live target
                ↓
            revalidate identity
                ↓
            SetValue
                ↓
            invalidate old target
                ↓
            reacquire current state
                ↓
            verify postcondition
        """

        result = {
            "success": False,
            "executed": False,
            "verified": False,
            "window_handle": window_handle,
            "target": None,
            "before": None,
            "requested_after": new_value,
            "observed_after": None,
            "error": None,
        }

        if not isinstance(
            window_handle,
            int,
        ):
            result["error"] = (
                "window_handle must be "
                "an integer."
            )
            return result

        if not isinstance(target, dict):
            result["error"] = (
                "target must be a dictionary."
            )
            return result

        if not isinstance(
            expected_before,
            str,
        ):
            result["error"] = (
                "expected_before must be "
                "a string."
            )
            return result

        if not isinstance(new_value, str):
            result["error"] = (
                "new_value must be a string."
            )
            return result

        allowed_target_fields = {
            "role",
            "name",
            "exact_name",
            "automation_id",
            "class_name",
        }

        unexpected_fields = (
            set(target.keys())
            - allowed_target_fields
        )

        if unexpected_fields:
            result["error"] = (
                "Unexpected target fields: "
                + ", ".join(
                    sorted(
                        unexpected_fields
                    )
                )
            )
            return result

        role = target.get("role")

        if (
            not isinstance(role, str)
            or role
            not in ROLE_TO_CONTROL_TYPES
        ):
            result["error"] = (
                "target.role must be a "
                "known semantic role."
            )
            return result

        name = target.get("name")

        automation_id = target.get(
            "automation_id"
        )

        class_name = target.get(
            "class_name"
        )

        exact_name = target.get(
            "exact_name",
            False,
        )

        if (
            name is not None
            and not isinstance(name, str)
        ):
            result["error"] = (
                "target.name must be a string "
                "when supplied."
            )
            return result

        if (
            automation_id is not None
            and not isinstance(
                automation_id,
                str,
            )
        ):
            result["error"] = (
                "target.automation_id must be "
                "a string when supplied."
            )
            return result

        if (
            class_name is not None
            and not isinstance(
                class_name,
                str,
            )
        ):
            result["error"] = (
                "target.class_name must be a "
                "string when supplied."
            )
            return result

        if not isinstance(
            exact_name,
            bool,
        ):
            result["error"] = (
                "target.exact_name must "
                "be boolean."
            )
            return result

        # Phase 1:
        # Resolve exactly one current target.
        resolution = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=name,
                exact_name=exact_name,
                current_value=(
                    expected_before
                ),
                automation_id=automation_id,
                class_name=class_name,
                required_capability="value",
            )
        )

        if not resolution["success"]:
            result["error"] = (
                resolution["error"]
            )
            return result

        descriptor = resolution["target"]

        result["target"] = descriptor

        result["before"] = normalize_text(
            descriptor.get("value", descriptor["name"])
        )

        if not descriptor[
            "capabilities"
        ].get(
            "value",
            False,
        ):
            result["error"] = (
                "Resolved target does not "
                "support ValuePattern."
            )
            return result

        # Phase 2:
        # Reacquire and revalidate immediately
        # before mutation.
        try:
            live_control = (
                self
                ._reacquire_target_for_execution(
                    window_handle=(
                        window_handle
                    ),
                    descriptor=descriptor,
                    expected_value=(
                        expected_before
                    ),
                )
            )

            if live_control is None:
                result["error"] = (
                    "Semantic target identity "
                    "changed before execution."
                )
                return result

            if not (
                hasattr(
                    live_control,
                    "iface_value",
                )
                and live_control.iface_value
                is not None
            ):
                result["error"] = (
                    "ValuePattern disappeared "
                    "before execution."
                )
                return result

            live_control.iface_value.SetValue(
                new_value
            )

            result["executed"] = True

        except Exception as exc:
            result["error"] = (
                "Semantic set_value execution "
                f"failed: {exc}"
            )
            return result

        # Any state-changing action invalidates
        # previous UI observations.
        time.sleep(
            self.reacquire_delay
        )

        # Phase 3:
        # Resolve the target again using stable
        # semantic characteristics, but now require
        # the new state.
        verification = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=None,
                exact_name=False,
                current_value=new_value,
                automation_id=automation_id,
                class_name=class_name,
                required_capability="value",
            )
        )

        if not verification["success"]:
            result["error"] = (
                "Action executed but "
                "postcondition verification "
                "failed: "
                f"{verification['error']}"
            )
            return result

        observed = verification[
            "target"
        ]

        # If the original target had a real HWND,
        # require the same HWND after mutation.
        old_control_handle = (
            descriptor["fingerprint"].get(
                "control_handle"
            )
        )

        new_control_handle = (
            observed["fingerprint"].get(
                "control_handle"
            )
        )

        if (
            old_control_handle is not None
            and new_control_handle
            != old_control_handle
        ):
            result["error"] = (
                "Action executed but target "
                "identity changed during "
                "verification."
            )
            return result

        result["observed_after"] = (
            normalize_text(
                observed.get("value", observed["name"])
            )
        )

        if (
            result["observed_after"]
            != normalize_text(new_value)
        ):
            result["error"] = (
                "Action executed but observed "
                "value does not match requested "
                "value."
            )
            return result

        result["verified"] = True
        result["success"] = True

        return result

    # -------------------------------------------------
    # Generic SelectionItemPattern mutation
    # -------------------------------------------------

    def select(
        self,
        window_handle: int,
        target: Dict[str, Any],
        expected_selected: bool,
    ) -> Dict[str, Any]:
        """
        Select one semantic UI target using
        SelectionItemPattern.

        The operation is fail-closed.

        A mutation occurs only when:
            - exactly one target resolves
            - SelectionItemPattern is available
            - observed state matches expected_selected
            - the target can be freshly reacquired
            - live identity still matches
            - live selection state still matches
              expected_selected

        After Select(), the target is reacquired and
        selected=True must be observed before success
        is reported.

        If expected_selected=True and the target is
        already selected, the desired state is already
        satisfied. In that case no mutation occurs.
        """

        result = {
            "success": False,
            "executed": False,
            "verified": False,
            "already_satisfied": False,
            "window_handle": window_handle,
            "target": None,
            "before_selected": None,
            "requested_selected": True,
            "observed_after_selected": None,
            "error": None,
        }

        if not isinstance(
            window_handle,
            int,
        ):
            result["error"] = (
                "window_handle must be "
                "an integer."
            )
            return result

        if not isinstance(target, dict):
            result["error"] = (
                "target must be a dictionary."
            )
            return result

        if not isinstance(
            expected_selected,
            bool,
        ):
            result["error"] = (
                "expected_selected must be "
                "boolean."
            )
            return result

        allowed_target_fields = {
            "role",
            "name",
            "exact_name",
            "automation_id",
            "class_name",
        }

        unexpected_fields = (
            set(target.keys())
            - allowed_target_fields
        )

        if unexpected_fields:
            result["error"] = (
                "Unexpected target fields: "
                + ", ".join(
                    sorted(
                        unexpected_fields
                    )
                )
            )
            return result

        role = target.get("role")

        if (
            not isinstance(role, str)
            or role
            not in ROLE_TO_CONTROL_TYPES
        ):
            result["error"] = (
                "target.role must be a "
                "known semantic role."
            )
            return result

        name = target.get("name")

        automation_id = target.get(
            "automation_id"
        )

        class_name = target.get(
            "class_name"
        )

        exact_name = target.get(
            "exact_name",
            False,
        )

        if (
            name is not None
            and not isinstance(name, str)
        ):
            result["error"] = (
                "target.name must be a string "
                "when supplied."
            )
            return result

        if (
            automation_id is not None
            and not isinstance(
                automation_id,
                str,
            )
        ):
            result["error"] = (
                "target.automation_id must be "
                "a string when supplied."
            )
            return result

        if (
            class_name is not None
            and not isinstance(
                class_name,
                str,
            )
        ):
            result["error"] = (
                "target.class_name must be a "
                "string when supplied."
            )
            return result

        if not isinstance(
            exact_name,
            bool,
        ):
            result["error"] = (
                "target.exact_name must "
                "be boolean."
            )
            return result

        # Phase 1:
        # Resolve exactly one target whose current
        # selection state matches the caller's
        # expected precondition.
        resolution = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=name,
                exact_name=exact_name,
                automation_id=automation_id,
                class_name=class_name,
                required_capability=(
                    "selection_item"
                ),
                selected=expected_selected,
            )
        )

        if not resolution["success"]:
            result["error"] = (
                resolution["error"]
            )
            return result

        descriptor = resolution[
            "target"
        ]

        result["target"] = descriptor

        before_selected = (
            descriptor.get(
                "state",
                {},
            ).get(
                "selected"
            )
        )

        result["before_selected"] = (
            before_selected
        )

        if not descriptor[
            "capabilities"
        ].get(
            "selection_item",
            False,
        ):
            result["error"] = (
                "Resolved target does not "
                "support SelectionItemPattern."
            )
            return result

        if before_selected is None:
            result["error"] = (
                "Resolved target selection "
                "state is unavailable."
            )
            return result

        if (
            before_selected
            is not expected_selected
        ):
            result["error"] = (
                "Resolved target does not "
                "match expected selection "
                "precondition."
            )
            return result

        # Desired state is already satisfied.
        # This is a verified no-op, not a mutation.
        if expected_selected is True:
            result[
                "observed_after_selected"
            ] = True

            result["verified"] = True
            result["already_satisfied"] = True
            result["success"] = True

            return result

        # Phase 2:
        # Reacquire the target from a fresh UIA tree
        # immediately before mutation.
        try:
            live_control = (
                self
                ._reacquire_target_for_execution(
                    window_handle=(
                        window_handle
                    ),
                    descriptor=descriptor,
                    expected_value=None,
                )
            )

            if live_control is None:
                result["error"] = (
                    "Semantic target identity "
                    "changed before execution."
                )
                return result

            if not (
                hasattr(
                    live_control,
                    "iface_selection_item",
                )
                and (
                    live_control
                    .iface_selection_item
                    is not None
                )
            ):
                result["error"] = (
                    "SelectionItemPattern "
                    "disappeared before execution."
                )
                return result

            # TOCTOU protection:
            # re-read the actual live selection
            # state immediately before Select().
            live_selected = (
                self
                ._read_live_selected_state(
                    live_control
                )
            )

            if live_selected is None:
                result["error"] = (
                    "Could not read live "
                    "selection state before "
                    "execution."
                )
                return result

            if (
                live_selected
                is not expected_selected
            ):
                result["error"] = (
                    "Selection state changed "
                    "before execution."
                )
                return result

            live_control.iface_selection_item.Select()

            result["executed"] = True

        except Exception as exc:
            result["error"] = (
                "Semantic select execution "
                f"failed: {exc}"
            )
            return result

        # The old descriptor/UIA wrapper is now
        # considered stale.
        time.sleep(
            self.reacquire_delay
        )

        # Phase 3:
        # Resolve the same semantic target again and
        # require selected=True.
        verification = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=name,
                exact_name=exact_name,
                automation_id=automation_id,
                class_name=class_name,
                required_capability=(
                    "selection_item"
                ),
                selected=True,
            )
        )

        if not verification["success"]:
            result["error"] = (
                "Action executed but "
                "postcondition verification "
                "failed: "
                f"{verification['error']}"
            )
            return result

        observed = verification[
            "target"
        ]

        # For controls that expose a real HWND,
        # require HWND continuity.
        #
        # Controls such as modern Notepad TabItems
        # may legitimately expose no HWND, so their
        # identity remains semantic.
        old_control_handle = (
            descriptor[
                "fingerprint"
            ].get(
                "control_handle"
            )
        )

        new_control_handle = (
            observed[
                "fingerprint"
            ].get(
                "control_handle"
            )
        )

        if (
            old_control_handle is not None
            and new_control_handle
            != old_control_handle
        ):
            result["error"] = (
                "Action executed but target "
                "identity changed during "
                "verification."
            )
            return result

        observed_selected = (
            observed.get(
                "state",
                {},
            ).get(
                "selected"
            )
        )

        result[
            "observed_after_selected"
        ] = observed_selected

        if observed_selected is not True:
            result["error"] = (
                "Action executed but target "
                "was not observed as selected."
            )
            return result

        result["verified"] = True
        result["success"] = True

        return result
    # -------------------------------------------------
    # Generic TogglePattern mutation
    # -------------------------------------------------

    def toggle(
        self,
        window_handle: int,
        target: Dict[str, Any],
        expected_state: str,
        requested_state: str,
    ) -> Dict[str, Any]:
        """
        Set a semantic two-state UI target using
        TogglePattern.

        Mutation is intentionally restricted to
        deterministic "on" and "off" states.

        "indeterminate" may be observed by the resolver,
        but is not writable through this primitive.

        Safety sequence:

            resolve expected state
                ↓
            unique semantic target
                ↓
            TogglePattern capability
                ↓
            fingerprint
                ↓
            fresh target reacquisition
                ↓
            live state TOCTOU check
                ↓
            Toggle() exactly once
                ↓
            fresh semantic resolution
                ↓
            requested-state verification

        If expected_state == requested_state, the desired
        state is already satisfied and the operation
        returns a verified no-op.
        """

        result = {
            "success": False,
            "executed": False,
            "verified": False,
            "already_satisfied": False,
            "window_handle": window_handle,
            "target": None,
            "before_toggle": None,
            "requested_toggle": requested_state,
            "observed_after_toggle": None,
            "error": None,
        }

        if not isinstance(window_handle, int):
            result["error"] = (
                "window_handle must be an integer."
            )
            return result

        if not isinstance(target, dict):
            result["error"] = (
                "target must be a dictionary."
            )
            return result

        valid_mutation_states = {
            "off",
            "on",
        }

        if (
            not isinstance(expected_state, str)
            or expected_state
            not in valid_mutation_states
        ):
            result["error"] = (
                "expected_state must be "
                "'on' or 'off'."
            )
            return result

        if (
            not isinstance(requested_state, str)
            or requested_state
            not in valid_mutation_states
        ):
            result["error"] = (
                "requested_state must be "
                "'on' or 'off'."
            )
            return result

        allowed_target_fields = {
            "role",
            "name",
            "exact_name",
            "automation_id",
            "class_name",
        }

        unexpected_fields = (
            set(target.keys())
            - allowed_target_fields
        )

        if unexpected_fields:
            result["error"] = (
                "Unexpected target fields: "
                + ", ".join(
                    sorted(unexpected_fields)
                )
            )
            return result

        role = target.get("role")

        if (
            not isinstance(role, str)
            or role not in ROLE_TO_CONTROL_TYPES
        ):
            result["error"] = (
                "target.role must be a "
                "known semantic role."
            )
            return result

        name = target.get("name")
        automation_id = target.get(
            "automation_id"
        )
        class_name = target.get(
            "class_name"
        )
        exact_name = target.get(
            "exact_name",
            False,
        )

        if (
            name is not None
            and not isinstance(name, str)
        ):
            result["error"] = (
                "target.name must be a string "
                "when supplied."
            )
            return result

        if (
            automation_id is not None
            and not isinstance(
                automation_id,
                str,
            )
        ):
            result["error"] = (
                "target.automation_id must be "
                "a string when supplied."
            )
            return result

        if (
            class_name is not None
            and not isinstance(
                class_name,
                str,
            )
        ):
            result["error"] = (
                "target.class_name must be a "
                "string when supplied."
            )
            return result

        if not isinstance(exact_name, bool):
            result["error"] = (
                "target.exact_name must "
                "be boolean."
            )
            return result

        # Phase 1:
        # Resolve exactly one target whose current
        # toggle state matches the caller's expected
        # precondition.
        resolution = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=name,
                exact_name=exact_name,
                automation_id=automation_id,
                class_name=class_name,
                required_capability="toggle",
                toggle_state=expected_state,
            )
        )

        if not resolution["success"]:
            result["error"] = (
                resolution["error"]
            )
            return result

        descriptor = resolution["target"]
        result["target"] = descriptor

        before_toggle = (
            descriptor.get(
                "state",
                {},
            ).get(
                "toggle"
            )
        )

        result["before_toggle"] = (
            before_toggle
        )

        if not descriptor[
            "capabilities"
        ].get(
            "toggle",
            False,
        ):
            result["error"] = (
                "Resolved target does not "
                "support TogglePattern."
            )
            return result

        if before_toggle not in {
            "off",
            "on",
        }:
            result["error"] = (
                "Resolved target toggle state "
                "is not a deterministic "
                "two-state value."
            )
            return result

        if before_toggle != expected_state:
            result["error"] = (
                "Resolved target does not "
                "match expected toggle "
                "precondition."
            )
            return result

        # Desired state is already satisfied.
        # This is a verified no-op.
        if expected_state == requested_state:
            result[
                "observed_after_toggle"
            ] = before_toggle

            result["verified"] = True
            result["already_satisfied"] = True
            result["success"] = True

            return result

        # For a deterministic two-state target,
        # exactly one Toggle() call must move between
        # on and off.
        expected_opposite = (
            "off"
            if expected_state == "on"
            else "on"
        )

        if requested_state != expected_opposite:
            result["error"] = (
                "requested_state is not the "
                "deterministic opposite of "
                "expected_state."
            )
            return result

        # Phase 2:
        # Freshly reacquire immediately before mutation.
        try:
            live_control = (
                self
                ._reacquire_target_for_execution(
                    window_handle=window_handle,
                    descriptor=descriptor,
                    expected_value=None,
                )
            )

            if live_control is None:
                result["error"] = (
                    "Semantic target identity "
                    "changed before execution."
                )
                return result

            if not (
                hasattr(
                    live_control,
                    "iface_toggle",
                )
                and live_control.iface_toggle
                is not None
            ):
                result["error"] = (
                    "TogglePattern disappeared "
                    "before execution."
                )
                return result

            # TOCTOU protection:
            # re-read actual live state immediately
            # before mutation.
            live_toggle = (
                self._read_live_toggle_state(
                    live_control
                )
            )

            if live_toggle is None:
                result["error"] = (
                    "Could not read live toggle "
                    "state before execution."
                )
                return result

            if live_toggle != expected_state:
                result["error"] = (
                    "Toggle state changed "
                    "before execution."
                )
                return result

            live_control.iface_toggle.Toggle()

            result["executed"] = True

        except Exception as exc:
            result["error"] = (
                "Semantic toggle execution "
                f"failed: {exc}"
            )
            return result

        # Previous observations are stale after mutation.
        time.sleep(
            self.reacquire_delay
        )

        # Phase 3:
        # Freshly resolve the same semantic target and
        # require the requested postcondition.
        verification = (
            self.target_resolver
            .resolve_unique_target(
                window_handle=window_handle,
                role=role,
                name=name,
                exact_name=exact_name,
                automation_id=automation_id,
                class_name=class_name,
                required_capability="toggle",
                toggle_state=requested_state,
            )
        )

        if not verification["success"]:
            result["error"] = (
                "Action executed but "
                "postcondition verification "
                "failed: "
                f"{verification['error']}"
            )
            return result

        observed = verification["target"]

        # Controls exposing a real HWND must retain
        # that identity across the mutation.
        old_control_handle = (
            descriptor[
                "fingerprint"
            ].get(
                "control_handle"
            )
        )

        new_control_handle = (
            observed[
                "fingerprint"
            ].get(
                "control_handle"
            )
        )

        if (
            old_control_handle is not None
            and new_control_handle
            != old_control_handle
        ):
            result["error"] = (
                "Action executed but target "
                "identity changed during "
                "verification."
            )
            return result

        observed_toggle = (
            observed.get(
                "state",
                {},
            ).get(
                "toggle"
            )
        )

        result[
            "observed_after_toggle"
        ] = observed_toggle

        if observed_toggle != requested_state:
            result["error"] = (
                "Action executed but target "
                "was not observed in the "
                "requested toggle state."
            )
            return result

        result["verified"] = True
        result["success"] = True

        return result
    # -------------------------------------------------
    # Compatibility API
    # -------------------------------------------------

    def inspect_documents(
        self,
        handle: int,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "window_handle": handle,
            "documents": [],
            "error": None,
        }

        search = (
            self.target_resolver
            .find_targets(
                window_handle=handle,
                role="document",
            )
        )

        if not search["success"]:
            result["error"] = search["error"]
            return result

        for target in search["targets"]:
            raw_text = target["name"]

            result["documents"].append(
                {
                    "index": target[
                        "index"
                    ],

                    "handle": target[
                        "handle"
                    ],

                    "class_name": target[
                        "class_name"
                    ],

                    "raw_text": raw_text,

                    "normalized_text": (
                        normalize_text(
                            raw_text
                        )
                    ),

                    "value_pattern": (
                        target[
                            "capabilities"
                        ]["value"]
                    ),
                }
            )

        result["success"] = True
        return result

    def resolve_unique_document(
        self,
        handle: int,
        expected_text: Optional[str] = None,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "window_handle": handle,
            "document": None,
            "error": None,
        }

        search = (
            self.target_resolver
            .find_targets(
                window_handle=handle,
                role="document",
            )
        )

        if not search["success"]:
            result["error"] = search["error"]
            return result

        targets = search["targets"]

        if expected_text is not None:
            expected_normalized = (
                normalize_text(
                    expected_text
                )
            )

            targets = [
                target
                for target in targets
                if normalize_text(
                    target["name"]
                )
                == expected_normalized
            ]

        if len(targets) == 0:
            result["error"] = (
                "No semantic Document matched "
                "the required precondition."
            )
            return result

        if len(targets) > 1:
            result["error"] = (
                "Semantic Document target "
                "is ambiguous."
            )
            return result

        target = targets[0]

        result["document"] = {
            "index": target["index"],

            "handle": target["handle"],

            "class_name": target[
                "class_name"
            ],

            "raw_text": target["name"],

            "normalized_text": (
                normalize_text(
                    target["name"]
                )
            ),

            "value_pattern": (
                target[
                    "capabilities"
                ]["value"]
            ),
        }

        result["success"] = True
        return result

    def _reacquire_document_for_execution(
        self,
        window_handle: int,
        expected_before: str,
    ):

        window = self._connect_window(
            window_handle
        )

        candidates = window.descendants(
            control_type="Document"
        )

        expected_normalized = (
            normalize_text(
                expected_before
            )
        )

        matching = [
            document
            for document in candidates
            if normalize_text(
                document.window_text()
            )
            == expected_normalized
        ]

        if len(matching) != 1:
            return None

        return matching[0]

    def set_document_text(
        self,
        window_handle: int,
        expected_before: str,
        new_text: str,
    ) -> Dict[str, Any]:
        """
        Legacy compatibility path.

        Kept until generic set_value has passed
        equivalent regression testing.
        """

        result = {
            "success": False,
            "executed": False,
            "verified": False,
            "window_handle": window_handle,
            "before": None,
            "requested_after": new_text,
            "observed_after": None,
            "error": None,
        }

        if not isinstance(
            window_handle,
            int,
        ):
            result["error"] = (
                "window_handle must be "
                "an integer."
            )
            return result

        if not isinstance(
            expected_before,
            str,
        ):
            result["error"] = (
                "expected_before must "
                "be a string."
            )
            return result

        if not isinstance(new_text, str):
            result["error"] = (
                "new_text must be a string."
            )
            return result

        target = (
            self.resolve_unique_document(
                window_handle,
                expected_text=(
                    expected_before
                ),
            )
        )

        if not target["success"]:
            result["error"] = target["error"]
            return result

        document_info = target[
            "document"
        ]

        result["before"] = (
            document_info[
                "normalized_text"
            ]
        )

        if not document_info[
            "value_pattern"
        ]:
            result["error"] = (
                "Target does not expose "
                "UI Automation ValuePattern."
            )
            return result

        try:
            document = (
                self
                ._reacquire_document_for_execution(
                    window_handle,
                    expected_before,
                )
            )

            if document is None:
                result["error"] = (
                    "Semantic target identity "
                    "changed before execution."
                )
                return result

            if not (
                hasattr(
                    document,
                    "iface_value",
                )
                and document.iface_value
                is not None
            ):
                result["error"] = (
                    "ValuePattern disappeared "
                    "before execution."
                )
                return result

            document.iface_value.SetValue(
                new_text
            )

            result["executed"] = True

        except Exception as exc:
            result["error"] = (
                "Semantic text execution "
                f"failed: {exc}"
            )
            return result

        time.sleep(
            self.reacquire_delay
        )

        verification = (
            self.target_resolver
            .find_targets(
                window_handle=(
                    window_handle
                ),
                role="document",
            )
        )

        if not verification["success"]:
            result["error"] = (
                "Action executed but "
                "post-action inspection "
                "failed: "
                f"{verification['error']}"
            )
            return result

        expected_after = normalize_text(
            new_text
        )

        matching_after = [
            target
            for target
            in verification["targets"]
            if normalize_text(
                target["name"]
            )
            == expected_after
        ]

        if len(matching_after) != 1:
            result["error"] = (
                "Action executed but "
                "resulting UI state could "
                "not be uniquely verified."
            )
            return result

        result["observed_after"] = (
            normalize_text(
                matching_after[0][
                    "name"
                ]
            )
        )

        result["verified"] = True
        result["success"] = True

        return result


if __name__ == "__main__":
    controller = SemanticController()

    print(
        "SemanticController loaded."
    )
    print(
        "Generic semantic set_value "
        "capability available."
    )
    print(
        "Generic semantic select "
        "capability available."
    )
    print(
        "No desktop modification executed."
    )
