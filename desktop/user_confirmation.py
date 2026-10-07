from __future__ import annotations

from typing import Any, Dict

from desktop.confirmation_authority import (
    ConfirmationAuthority,
    ConfirmationToken,
)


class UserConfirmationBoundary:
    """
    Trusted boundary between an action proposed by the
    agent and explicit approval from the user.

    IMPORTANT:

    This class must not be exposed as a planner tool,
    LLM tool, skill capability, or autonomous-agent API.

    Development version:
        confirmation is supplied directly by trusted
        application code after collecting real user input.

    Future versions may obtain approval through:
        - trusted desktop UI
        - authenticated mobile app
        - verified voice interaction
        - stronger authentication for high-risk actions
    """

    def __init__(
        self,
        authority: ConfirmationAuthority,
    ):
        if not isinstance(
            authority,
            ConfirmationAuthority,
        ):
            raise TypeError(
                "authority must be a "
                "ConfirmationAuthority."
            )

        self._authority = authority

    def process_user_decision(
        self,
        request: Any,
        approved: Any,
    ) -> Dict[str, Any]:
        """
        Process a decision already obtained from the
        trusted user-interaction layer.

        This method does NOT ask an LLM whether the
        action should be approved.
        """

        result = {
            "approved": False,
            "confirmation": None,
            "error": None,
        }

        if not isinstance(request, dict):
            result["error"] = (
                "Confirmation request must be a "
                "dictionary."
            )
            return result

        if not isinstance(approved, bool):
            result["error"] = (
                "approved must be boolean."
            )
            return result

        if not approved:
            result["error"] = (
                "User rejected the requested action."
            )
            return result

        confirmation: ConfirmationToken = (
            self._authority.issue(request)
        )

        result["approved"] = True
        result["confirmation"] = confirmation

        return result


if __name__ == "__main__":
    authority = ConfirmationAuthority(
        ttl_seconds=30,
    )

    boundary = UserConfirmationBoundary(
        authority
    )

    request = {
        "action": "toggle",
        "window_handle": 123,
        "arguments": {
            "target": {
                "role": "checkbox",
                "name": "Example",
            },
            "expected_state": "off",
            "requested_state": "on",
        },
    }

    rejected = boundary.process_user_decision(
        request,
        False,
    )

    print(
        "REJECTED:",
        rejected,
    )

    approved = boundary.process_user_decision(
        request,
        True,
    )

    print(
        "APPROVED:",
        approved["approved"],
    )

    token = approved["confirmation"]

    print(
        "TOKEN VALID:",
        authority.consume(
            token.token,
            request,
        ),
    )