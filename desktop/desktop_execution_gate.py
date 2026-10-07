from __future__ import annotations

from typing import Any, Dict, Optional

from desktop.action_gate import DesktopActionGate
from desktop.confirmation_authority import ConfirmationAuthority
from desktop.policy_gate import DesktopPolicyGate


class DesktopExecutionGate:
    """
    Mandatory composed desktop execution boundary.

    Execution order:

        request
          ↓
        DesktopPolicyGate
          ↓
        DesktopActionGate
          ↓
        SemanticController
          ↓
        Windows/UIA

    Policy authorization and technical authorization
    remain separate.

    This class is intended to become the normal public
    entry point for desktop mutations.
    """

    def __init__(
        self,
        confirmation_authority: Optional[
            ConfirmationAuthority
        ] = None,
    ):
        if confirmation_authority is None:
            confirmation_authority = (
                ConfirmationAuthority()
            )

        self._confirmation_authority = (
            confirmation_authority
        )

        self._policy_gate = DesktopPolicyGate(
            confirmation_authority=(
                self._confirmation_authority
            )
        )

        self._action_gate = DesktopActionGate()

    @property
    def confirmation_authority(
        self,
    ) -> ConfirmationAuthority:
        """
        Development-only access.

        Do not expose this property to planners,
        LLM tools, skills, or autonomous agents.
        """
        return self._confirmation_authority

    def execute(
        self,
        request: Any,
        confirmation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute only after consequence policy passes.

        A policy failure prevents DesktopActionGate
        from being called.
        """

        policy_result = self._policy_gate.authorize(
            request=request,
            confirmation_token=confirmation_token,
        )

        result: Dict[str, Any] = {
            "success": False,
            "policy_authorized": False,
            "technical_authorized": False,
            "executed": False,
            "verified": False,
            "policy": policy_result,
            "execution": None,
            "error": None,
        }

        if not policy_result.get(
            "authorized",
            False,
        ):
            result["error"] = (
                policy_result.get("reason")
                or "Desktop policy rejected request."
            )
            return result

        result["policy_authorized"] = True

        execution_result = (
            self._action_gate.execute(request)
        )

        result["execution"] = execution_result

        technical_authorized = bool(
            execution_result.get(
                "authorized",
                False,
            )
        )

        result["technical_authorized"] = (
            technical_authorized
        )

        result["executed"] = bool(
            execution_result.get(
                "executed",
                False,
            )
        )

        result["verified"] = bool(
            execution_result.get(
                "verified",
                False,
            )
        )

        result["success"] = bool(
            policy_result.get(
                "authorized",
                False,
            )
            and technical_authorized
            and execution_result.get(
                "success",
                False,
            )
        )

        if not result["success"]:
            result["error"] = (
                execution_result.get("error")
                or execution_result.get("reason")
                or "Desktop execution failed."
            )

        return result