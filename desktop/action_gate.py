from __future__ import annotations

from typing import Any, Dict

from desktop.input_controller import InputController
from desktop.semantic_controller import SemanticController


ALLOWED_ACTIONS = {
    "open_calculator",
    "launch_application",
    "type_text",
    "set_document_text",
    "set_value",
    "select",
    "toggle",
}


ACTION_RISK = {
    "open_calculator": "low",
    "launch_application": "low",
    "type_text": "medium",
    "set_document_text": "medium",
    "set_value": "medium",
    "select": "medium",
    "toggle": "medium",
}


SEMANTIC_TARGET_FIELDS = {
    "role",
    "name",
    "exact_name",
    "automation_id",
    "class_name",
}


class DesktopActionGate:
    """
    Authorization and validation boundary for
    desktop actions.

    Important:

        Capability != permission.

    SemanticController knows HOW to perform an
    operation.

    DesktopActionGate decides whether a requested
    operation is technically allowed to reach the
    controller.

    Consequence-aware authorization will be added
    separately. For now, authorized=True means the
    request passed this technical action/schema gate.
    """

    def __init__(self, *, document_session=None):
        self.document_session = document_session
        self.input_controller = InputController()
        self.semantic_controller = (
            SemanticController()
        )
        if document_session is not None:
            self.semantic_controller = document_session.semantic_controller()

    # -------------------------------------------------
    # Semantic target validation
    # -------------------------------------------------

    def _validate_semantic_target(
        self,
        target: Any,
    ):
        errors = []

        if not isinstance(target, dict):
            return [
                "target must be a dictionary."
            ]

        unexpected_fields = (
            set(target.keys())
            - SEMANTIC_TARGET_FIELDS
        )

        if unexpected_fields:
            errors.append(
                "Unexpected target fields: "
                + ", ".join(
                    sorted(
                        unexpected_fields
                    )
                )
            )

        role = target.get("role")

        if (
            not isinstance(role, str)
            or not role.strip()
        ):
            errors.append(
                "target.role must be a "
                "non-empty string."
            )

        name = target.get("name")

        if (
            name is not None
            and not isinstance(name, str)
        ):
            errors.append(
                "target.name must be a string "
                "when supplied."
            )

        exact_name = target.get(
            "exact_name",
            False,
        )

        if not isinstance(
            exact_name,
            bool,
        ):
            errors.append(
                "target.exact_name must "
                "be boolean."
            )

        automation_id = target.get(
            "automation_id"
        )

        if (
            automation_id is not None
            and not isinstance(
                automation_id,
                str,
            )
        ):
            errors.append(
                "target.automation_id must be "
                "a string when supplied."
            )

        class_name = target.get(
            "class_name"
        )

        if (
            class_name is not None
            and not isinstance(
                class_name,
                str,
            )
        ):
            errors.append(
                "target.class_name must be a "
                "string when supplied."
            )

        return errors

    # Compatibility name retained for existing code.
    def _validate_set_value_target(
        self,
        target: Any,
    ):
        return self._validate_semantic_target(
            target
        )

    # -------------------------------------------------
    # Request validation
    # -------------------------------------------------

    def validate_request(
        self,
        request: Any,
    ) -> Dict[str, Any]:

        result = {
            "valid": False,
            "action": None,
            "risk": None,
            "errors": [],
        }

        if not isinstance(request, dict):
            result["errors"].append(
                "Request must be a dictionary."
            )
            return result

        if self.document_session is not None:
            # A session gate exposes only its exact owned document requests.
            try:
                valid = self.document_session.validate(request) is True
            except Exception:
                valid = False
            if not valid:
                result["errors"].append("Document target or precondition rejected.")
                return result
            if request["action"] in {"open_test_document", "export_test_document"}:
                result.update(valid=True, action=request["action"], risk="medium")
                return result
            request = {key: value for key, value in request.items() if key != "binding"}

        if request.get("action") in ("open_calculator", "launch_application"):
            from tools.tool_registry import validate_tool_arguments

            result["action"] = request["action"]
            result["risk"] = "low"
            try:
                valid = (
                    set(request) == {"action", "arguments"}
                    and validate_tool_arguments(request["action"], request.get("arguments"))
                )
            except Exception:
                valid = False
            result["valid"] = valid
            if not valid:
                result["errors"].append("Invalid or undiscovered application launch.")
            return result

        allowed_top_level_fields = {
            "action",
            "window_handle",
            "arguments",
        }

        unexpected_top_level = (
            set(request.keys())
            - allowed_top_level_fields
        )

        if unexpected_top_level:
            result["errors"].append(
                "Unexpected request fields: "
                + ", ".join(
                    sorted(
                        unexpected_top_level
                    )
                )
            )

        action = request.get("action")

        result["action"] = action

        if (
            not isinstance(action, str)
            or not action
        ):
            result["errors"].append(
                "action must be a "
                "non-empty string."
            )
            return result

        if action not in ALLOWED_ACTIONS:
            result["errors"].append(
                f"Action {action!r} is not allowed."
            )
            return result

        result["risk"] = ACTION_RISK[
            action
        ]

        window_handle = request.get(
            "window_handle"
        )

        if not isinstance(
            window_handle,
            int,
        ):
            result["errors"].append(
                "window_handle must be "
                "an integer."
            )

        arguments = request.get(
            "arguments"
        )

        if not isinstance(arguments, dict):
            result["errors"].append(
                "arguments must be a dictionary."
            )
            return result

        # ---------------------------------------------
        # type_text
        # ---------------------------------------------

        if action == "type_text":

            allowed_arguments = {
                "text",
            }

            unexpected_arguments = (
                set(arguments.keys())
                - allowed_arguments
            )

            if unexpected_arguments:
                result["errors"].append(
                    "Unexpected type_text "
                    "arguments: "
                    + ", ".join(
                        sorted(
                            unexpected_arguments
                        )
                    )
                )

            text = arguments.get("text")

            if not isinstance(text, str):
                result["errors"].append(
                    "type_text.text must be "
                    "a string."
                )

        # ---------------------------------------------
        # set_document_text
        # ---------------------------------------------

        elif action == "set_document_text":

            allowed_arguments = {
                "expected_before",
                "new_text",
            }

            unexpected_arguments = (
                set(arguments.keys())
                - allowed_arguments
            )

            if unexpected_arguments:
                result["errors"].append(
                    "Unexpected "
                    "set_document_text arguments: "
                    + ", ".join(
                        sorted(
                            unexpected_arguments
                        )
                    )
                )

            expected_before = arguments.get(
                "expected_before"
            )

            new_text = arguments.get(
                "new_text"
            )

            if not isinstance(
                expected_before,
                str,
            ):
                result["errors"].append(
                    "set_document_text."
                    "expected_before must be "
                    "a string."
                )

            if not isinstance(
                new_text,
                str,
            ):
                result["errors"].append(
                    "set_document_text.new_text "
                    "must be a string."
                )

        # ---------------------------------------------
        # set_value
        # ---------------------------------------------

        elif action == "set_value":

            allowed_arguments = {
                "target",
                "expected_before",
                "new_value",
            }

            unexpected_arguments = (
                set(arguments.keys())
                - allowed_arguments
            )

            if unexpected_arguments:
                result["errors"].append(
                    "Unexpected set_value "
                    "arguments: "
                    + ", ".join(
                        sorted(
                            unexpected_arguments
                        )
                    )
                )

            target = arguments.get(
                "target"
            )

            result["errors"].extend(
                self._validate_semantic_target(
                    target
                )
            )

            expected_before = arguments.get(
                "expected_before"
            )

            new_value = arguments.get(
                "new_value"
            )

            if not isinstance(
                expected_before,
                str,
            ):
                result["errors"].append(
                    "set_value.expected_before "
                    "must be a string."
                )

            if not isinstance(
                new_value,
                str,
            ):
                result["errors"].append(
                    "set_value.new_value must "
                    "be a string."
                )

        # ---------------------------------------------
        # select
        # ---------------------------------------------

        elif action == "select":

            allowed_arguments = {
                "target",
                "expected_selected",
            }

            unexpected_arguments = (
                set(arguments.keys())
                - allowed_arguments
            )

            if unexpected_arguments:
                result["errors"].append(
                    "Unexpected select arguments: "
                    + ", ".join(
                        sorted(
                            unexpected_arguments
                        )
                    )
                )

            target = arguments.get(
                "target"
            )

            result["errors"].extend(
                self._validate_semantic_target(
                    target
                )
            )

            expected_selected = arguments.get(
                "expected_selected"
            )

            if not isinstance(
                expected_selected,
                bool,
            ):
                result["errors"].append(
                    "select.expected_selected "
                    "must be boolean."
                )
        # ---------------------------------------------
        # toggle
        # ---------------------------------------------

        elif action == "toggle":

            allowed_arguments = {
                "target",
                "expected_state",
                "requested_state",
            }

            unexpected_arguments = (
                set(arguments.keys())
                - allowed_arguments
            )

            if unexpected_arguments:
                result["errors"].append(
                    "Unexpected toggle arguments: "
                    + ", ".join(
                        sorted(
                            unexpected_arguments
                        )
                    )
                )

            target = arguments.get(
                "target"
            )

            result["errors"].extend(
                self._validate_semantic_target(
                    target
                )
            )

            expected_state = arguments.get(
                "expected_state"
            )

            requested_state = arguments.get(
                "requested_state"
            )

            valid_toggle_states = {
                "on",
                "off",
            }

            if (
                not isinstance(
                    expected_state,
                    str,
                )
                or expected_state
                not in valid_toggle_states
            ):
                result["errors"].append(
                    "toggle.expected_state must "
                    "be 'on' or 'off'."
                )

            if (
                not isinstance(
                    requested_state,
                    str,
                )
                or requested_state
                not in valid_toggle_states
            ):
                result["errors"].append(
                    "toggle.requested_state must "
                    "be 'on' or 'off'."
                )

        result["valid"] = (
            len(result["errors"]) == 0
        )

        return result

    # -------------------------------------------------
    # Semantic execution result contract
    # -------------------------------------------------

    def _apply_semantic_execution(
        self,
        result: Dict[str, Any],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        A semantic mutation is considered successful
        only when the controller reports:

            success=True
            executed=True
            verified=True

        Verified no-op operations such as selecting an
        already-selected target are handled explicitly.
        """

        result["execution"] = execution

        # An error or a malformed success flag cannot become semantic success.
        if (not isinstance(execution, dict) or execution.get("error")
                or execution.get("success") is not True
                or execution.get("verified") is not True
                or not isinstance(execution.get("executed"), bool)):
            result["error"] = "Semantic execution failed or returned an invalid result."
            return result

        result["executed"] = bool(
            execution.get(
                "executed",
                False,
            )
        )

        result["verified"] = bool(
            execution.get(
                "verified",
                False,
            )
        )

        already_satisfied = bool(
            execution.get(
                "already_satisfied",
                False,
            )
        )

        if already_satisfied:
            result["already_satisfied"] = True

            if (
                execution.get(
                    "success",
                    False,
                )
                and result["verified"]
                and not result["executed"]
            ):
                result["success"] = True
                result["error"] = None
                return result

            result["success"] = False
            result["error"] = (
                execution.get("error")
                or (
                    "Semantic no-op verification "
                    "contract failed."
                )
            )
            return result

        if (
            execution.get(
                "success",
                False,
            )
            and result["executed"]
            and result["verified"]
        ):
            result["success"] = True
            result["error"] = None
            return result

        result["success"] = False

        result["error"] = (
            execution.get("error")
            or (
                "Semantic execution did not "
                "satisfy the execution and "
                "verification contract."
            )
        )

        return result

    # -------------------------------------------------
    # Execution
    # -------------------------------------------------

    def execute(
        self,
        request: Any,
    ) -> Dict[str, Any]:

        validation = self.validate_request(
            request
        )

        result = {
            "success": False,
            "authorized": False,
            "executed": False,
            "verified": False,
            "action": validation.get(
                "action"
            ),
            "risk": validation.get(
                "risk"
            ),
            "validation": validation,
            "execution": None,
            "error": None,
        }

        if not validation["valid"]:
            result["error"] = (
                "; ".join(
                    validation["errors"]
                )
            )
            return result

        # IMPORTANT:
        #
        # This currently means only that the request
        # passed the technical action/schema gate.
        #
        # It does NOT yet mean consequence-aware
        # user authorization.
        result["authorized"] = True

        action = request["action"]
        if action in {"open_test_document", "export_test_document"}:
            try:
                if action == "open_test_document":
                    self.document_session.open(request)
                    verified = self.document_session.state()["document_empty"]
                else:
                    self.document_session.export(request)
                    verified = self.document_session.state()["file_matches"]
                result.update(executed=True, verified=verified is True, success=verified is True)
                if not result["success"]:
                    result["error"] = "Document operation verification failed."
            except Exception:
                result["error"] = "Document operation failed safely."
            return result
        if action in {"open_calculator", "launch_application"}:
            from tools.system_tools import _open_calculator, _launch_application

            try:
                if action == "open_calculator":
                    dispatched = _open_calculator()
                else:
                    dispatched = _launch_application(**request["arguments"])
                result["executed"] = dispatched is True
                # This reports dispatch only. Runtime postconditions independently
                # observe Calculator before completing its task.
                result["success"] = dispatched is True
                if not result["success"]:
                    result["error"] = "Application launch failed."
            except Exception as exc:
                result["error"] = f"Application launch failed: {type(exc).__name__}"
            return result

        window_handle = request[
            "window_handle"
        ]
        arguments = request[
            "arguments"
        ]

        # ---------------------------------------------
        # Legacy raw text path
        # ---------------------------------------------

        if action == "type_text":
            try:
                execution = (
                    self.input_controller
                    .type_text(
                        window_handle,
                        arguments["text"],
                    )
                )

                result["execution"] = execution

                # Legacy type_text remains
                # deliberately unverified.
                result["executed"] = bool(
                    execution.get(
                        "executed",
                        execution.get(
                            "success",
                            False,
                        ),
                    )
                )

                result["verified"] = False
                result["success"] = False

                result["error"] = (
                    "type_text execution is not "
                    "semantically verified and "
                    "cannot report overall success."
                )

                return result

            except Exception as exc:
                result["error"] = (
                    "type_text execution failed: "
                    f"{exc}"
                )
                return result

        # ---------------------------------------------
        # Legacy semantic document mutation
        # ---------------------------------------------

        if action == "set_document_text":
            execution = (
                self.semantic_controller
                .set_document_text(
                    window_handle=window_handle,
                    expected_before=arguments[
                        "expected_before"
                    ],
                    new_text=arguments[
                        "new_text"
                    ],
                )
            )

            return (
                self._apply_semantic_execution(
                    result,
                    execution,
                )
            )

        # ---------------------------------------------
        # Generic ValuePattern mutation
        # ---------------------------------------------

        if action == "set_value":
            execution = (
                self.semantic_controller
                .set_value(
                    window_handle=window_handle,
                    target=arguments[
                        "target"
                    ],
                    expected_before=arguments[
                        "expected_before"
                    ],
                    new_value=arguments[
                        "new_value"
                    ],
                )
            )

            return (
                self._apply_semantic_execution(
                    result,
                    execution,
                )
            )

        # ---------------------------------------------
        # Generic SelectionItemPattern mutation
        # ---------------------------------------------

        if action == "select":
            execution = (
                self.semantic_controller
                .select(
                    window_handle=window_handle,
                    target=arguments[
                        "target"
                    ],
                    expected_selected=arguments[
                        "expected_selected"
                    ],
                )
            )

            return (
                self._apply_semantic_execution(
                    result,
                    execution,
                )
            )
        # ---------------------------------------------
        # Generic TogglePattern mutation
        # ---------------------------------------------

        if action == "toggle":
            execution = (
                self.semantic_controller
                .toggle(
                    window_handle=window_handle,
                    target=arguments[
                        "target"
                    ],
                    expected_state=arguments[
                        "expected_state"
                    ],
                    requested_state=arguments[
                        "requested_state"
                    ],
                )
            )

            return (
                self._apply_semantic_execution(
                    result,
                    execution,
                )
            )
        # Should be unreachable because validation
        # rejects unknown actions.
        result["error"] = (
            "Validated action has no execution "
            "handler."
        )

        return result


if __name__ == "__main__":
    gate = DesktopActionGate()

    print(
        "DesktopActionGate loaded."
    )

    valid_select = {
        "action": "select",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "tab",
                "name": "Example",
                "exact_name": True,
                "class_name": "ListViewItem",
            },
            "expected_selected": False,
        },
    }

    print(
        "Valid select:",
        gate.validate_request(
            valid_select
        ),
    )

    blocked_action = {
        "action": "press_enter",
        "window_handle": 1,
        "arguments": {},
    }

    print(
        "Blocked action:",
        gate.validate_request(
            blocked_action
        ),
    )

    blocked_argument = {
        "action": "select",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "tab",
            },
            "expected_selected": False,
            "override_security": True,
        },
    }

    print(
        "Blocked argument override:",
        gate.validate_request(
            blocked_argument
        ),
    )

    blocked_target = {
        "action": "select",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "tab",
                "bypass_identity": True,
            },
            "expected_selected": False,
        },
    }

    print(
        "Blocked target override:",
        gate.validate_request(
            blocked_target
        ),
    )
