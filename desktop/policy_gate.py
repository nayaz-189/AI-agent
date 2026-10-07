from __future__ import annotations

from typing import Any, Dict, Optional

from desktop.confirmation_authority import (
    ConfirmationAuthority,
)
from desktop.consequence_policy import (
    ConsequencePolicy,
    PolicyDecision,
)


class DesktopPolicyGate:
    """
    Consequence-aware authorization boundary placed
    before DesktopActionGate.

    Decisions:

        ALLOW
            May proceed automatically.

        CONFIRM
            May proceed only with a valid,
            exact-request confirmation token.

        DENY
            Must never proceed through this gate.

        UNKNOWN
            Must never proceed through this gate.

    Confirmation cannot override DENY or UNKNOWN.
    """

    def __init__(
        self,
        confirmation_authority: Optional[
            ConfirmationAuthority
        ] = None,
    ):
        self.policy = ConsequencePolicy()

        self.confirmation_authority = (
            confirmation_authority
        )

    def authorize(
        self,
        request: Any,
        confirmation_token: Optional[str] = None,
    ) -> Dict[str, Any]:

        policy_result = self.policy.evaluate(
            request
        )

        result = {
            "authorized": False,
            "decision": (
                policy_result.decision.value
            ),
            "reason": policy_result.reason,
            "consequence": (
                policy_result.consequence
            ),
            "requires_confirmation": (
                policy_result.requires_confirmation
            ),
            "rule_id": policy_result.rule_id,
            "confirmation_checked": False,
            "confirmation_valid": False,
            "confirmation_error": None,
        }

        # ---------------------------------------------
        # ALLOW
        # ---------------------------------------------

        if (
            policy_result.decision
            == PolicyDecision.ALLOW
        ):
            result["authorized"] = True
            return result

        # ---------------------------------------------
        # DENY / UNKNOWN
        #
        # Confirmation MUST NOT override either.
        # ---------------------------------------------

        if policy_result.decision in {
            PolicyDecision.DENY,
            PolicyDecision.UNKNOWN,
        }:
            return result

        # ---------------------------------------------
        # CONFIRM
        # ---------------------------------------------

        if (
            policy_result.decision
            == PolicyDecision.CONFIRM
        ):
            if confirmation_token is None:
                result["confirmation_error"] = (
                    "Explicit user confirmation "
                    "is required."
                )
                return result

            if self.confirmation_authority is None:
                result["confirmation_error"] = (
                    "No confirmation authority "
                    "is configured."
                )
                return result

            result["confirmation_checked"] = True

            confirmation_result = (
                self.confirmation_authority.consume(
                    confirmation_token,
                    request,
                )
            )

            if not confirmation_result.get(
                "confirmed",
                False,
            ):
                result["confirmation_error"] = (
                    confirmation_result.get(
                        "error"
                    )
                    or (
                        "Confirmation validation "
                        "failed."
                    )
                )
                return result

            result["confirmation_valid"] = True
            result["authorized"] = True

            return result

        # Defensive fail-closed fallback.
        return result


if __name__ == "__main__":
    authority = ConfirmationAuthority(
        ttl_seconds=30,
    )

    gate = DesktopPolicyGate(
        confirmation_authority=authority
    )

    safe_request = {
        "action": "select",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "tab",
                "name": "Settings",
            },
            "expected_selected": False,
        },
    }

    confirm_request = {
        "action": "toggle",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "checkbox",
                "name": "Enable Test Feature",
            },
            "expected_state": "off",
            "requested_state": "on",
        },
    }

    denied_request = {
        "action": "toggle",
        "window_handle": 1,
        "arguments": {
            "target": {
                "role": "checkbox",
                "name": "Disable Firewall",
            },
            "expected_state": "off",
            "requested_state": "on",
        },
    }

    print(
        "ALLOW:",
        gate.authorize(
            safe_request
        ),
    )

    print(
        "NO CONFIRMATION:",
        gate.authorize(
            confirm_request
        ),
    )

    confirmation = authority.issue(
        confirm_request
    )

    print(
        "CONFIRMED:",
        gate.authorize(
            confirm_request,
            confirmation.token,
        ),
    )

    fake_override = authority.issue(
        denied_request
    )

    print(
        "DENY CANNOT OVERRIDE:",
        gate.authorize(
            denied_request,
            fake_override.token,
        ),
    )