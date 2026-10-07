from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ConfirmationToken:
    token: str
    request_digest: str
    issued_at: float
    expires_at: float


class ConfirmationAuthority:
    """
    Issues short-lived, single-use confirmations for
    exact desktop requests.

    Important:
        The planner must never issue these tokens.

        Tokens are bound to the exact normalized request,
        expire quickly, and are consumed once.
    """

    def __init__(
        self,
        ttl_seconds: float = 30.0,
    ):
        if (
            not isinstance(ttl_seconds, (int, float))
            or isinstance(ttl_seconds, bool)
            or ttl_seconds <= 0
        ):
            raise ValueError(
                "ttl_seconds must be a positive number."
            )

        self.ttl_seconds = float(ttl_seconds)

        self._pending: Dict[
            str,
            ConfirmationToken,
        ] = {}

    def _request_digest(
        self,
        request: Any,
    ) -> str:
        """
        Produce a deterministic digest of the exact
        request being authorized.
        """

        serialized = json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def issue(
        self,
        request: Any,
    ) -> ConfirmationToken:
        """
        Issue a short-lived confirmation token for
        exactly one request.

        Calling this method represents the trusted
        user-confirmation boundary.
        """

        if not isinstance(request, dict):
            raise TypeError(
                "request must be a dictionary."
            )

        now = time.monotonic()

        token_value = secrets.token_urlsafe(32)

        confirmation = ConfirmationToken(
            token=token_value,
            request_digest=self._request_digest(
                request
            ),
            issued_at=now,
            expires_at=(
                now + self.ttl_seconds
            ),
        )

        self._pending[token_value] = confirmation

        return confirmation

    def consume(
        self,
        token: Any,
        request: Any,
    ) -> Dict[str, Any]:
        """
        Consume a confirmation.

        Success requires:

            - token exists
            - token has not expired
            - exact request digest matches
            - token has not already been consumed

        Tokens are removed on successful consumption.
        """

        result = {
            "confirmed": False,
            "error": None,
        }

        if not isinstance(token, str) or not token:
            result["error"] = (
                "Confirmation token must be a "
                "non-empty string."
            )
            return result

        if not isinstance(request, dict):
            result["error"] = (
                "Confirmation request must be a "
                "dictionary."
            )
            return result

        confirmation: Optional[
            ConfirmationToken
        ] = self._pending.get(token)

        if confirmation is None:
            result["error"] = (
                "Confirmation token is unknown "
                "or already consumed."
            )
            return result

        now = time.monotonic()

        if now > confirmation.expires_at:
            self._pending.pop(
                token,
                None,
            )

            result["error"] = (
                "Confirmation token has expired."
            )
            return result

        current_digest = self._request_digest(
            request
        )

        if (
            current_digest
            != confirmation.request_digest
        ):
            result["error"] = (
                "Confirmation token does not match "
                "the requested action."
            )
            return result

        self._pending.pop(
            token,
            None,
        )

        result["confirmed"] = True

        return result


if __name__ == "__main__":
    authority = ConfirmationAuthority(
        ttl_seconds=30,
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

    confirmation = authority.issue(
        request
    )

    print(
        "FIRST:",
        authority.consume(
            confirmation.token,
            request,
        ),
    )

    print(
        "REUSE:",
        authority.consume(
            confirmation.token,
            request,
        ),
    )