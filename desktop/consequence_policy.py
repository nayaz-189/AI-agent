from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PolicyDecision(str, Enum):
    """
    Possible consequence-policy decisions.

    ALLOW:
        The action may proceed without additional
        user confirmation.

    CONFIRM:
        Explicit user confirmation is required before
        the action may proceed.

    DENY:
        The action must not proceed.

    UNKNOWN:
        The policy cannot determine the consequence
        safely. Fail closed.
    """

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PolicyResult:
    """
    Immutable result returned by the consequence
    policy layer.

    This object describes a policy decision only.
    It grants no execution capability.
    """

    decision: PolicyDecision
    reason: str
    consequence: str
    requires_confirmation: bool
    rule_id: Optional[str] = None

    @property
    def may_execute(self) -> bool:
        """
        True only when policy explicitly allows
        execution without additional confirmation.
        """

        return self.decision == PolicyDecision.ALLOW


def make_policy_result(
    decision: PolicyDecision,
    *,
    reason: str,
    consequence: str,
    rule_id: Optional[str] = None,
) -> PolicyResult:
    """
    Construct a normalized PolicyResult.

    Confirmation semantics are derived from the
    decision rather than supplied by callers.
    """

    if not isinstance(decision, PolicyDecision):
        raise TypeError(
            "decision must be a PolicyDecision."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "reason must be a non-empty string."
        )

    if (
        not isinstance(consequence, str)
        or not consequence.strip()
    ):
        raise ValueError(
            "consequence must be a non-empty string."
        )

    if (
        rule_id is not None
        and not isinstance(rule_id, str)
    ):
        raise TypeError(
            "rule_id must be a string or None."
        )

    return PolicyResult(
        decision=decision,
        reason=reason.strip(),
        consequence=consequence.strip(),
        requires_confirmation=(
            decision == PolicyDecision.CONFIRM
        ),
        rule_id=rule_id,
    )

class ConsequencePolicy:
    """
    Deterministic first-pass consequence classifier.

    This layer decides whether a requested semantic
    desktop action may proceed automatically.

    It does NOT execute actions.
    It does NOT call SemanticController.
    It does NOT trust an LLM to grant permission.
    """

    SAFE_NAVIGATION_ROLES = {
        "tab",
        "list_item",
        "menu_item",
    }

    SENSITIVE_TERMS = {
        "delete",
        "remove",
        "erase",
        "uninstall",
        "purchase",
        "buy",
        "pay",
        "send",
        "submit",
        "publish",
        "post",
        "password",
        "security",
        "permission",
        "administrator",
        "admin",
        "factory reset",
        "sign out",
        "log out",
    }

    PROTECTED_TERMS = {
        "disable antivirus",
        "disable firewall",
        "turn off antivirus",
        "turn off firewall",
        "disable security",
        "bypass security",
    }

    def evaluate(
        self,
        request,
    ) -> PolicyResult:
        """
        Evaluate a semantic desktop request.

        Unknown or malformed requests fail closed.
        """

        if not isinstance(request, dict):
            return make_policy_result(
                PolicyDecision.UNKNOWN,
                reason=(
                    "Policy request must be a dictionary."
                ),
                consequence="unknown",
                rule_id="malformed-request",
            )

        action = request.get("action")
        arguments = request.get("arguments")

        if (
            not isinstance(action, str)
            or not isinstance(arguments, dict)
        ):
            return make_policy_result(
                PolicyDecision.UNKNOWN,
                reason=(
                    "Action or arguments are missing "
                    "or malformed."
                ),
                consequence="unknown",
                rule_id="malformed-request",
            )

        target = arguments.get("target", {})

        # Launches have no semantic control target. Technical validation still
        # checks the exact schema and locally discovered application identity.
        if action == "open_calculator":
            return make_policy_result(
                PolicyDecision.ALLOW,
                reason="Launch the fixed Windows Calculator capability.",
                consequence="application launch",
                rule_id="registered-application-launch",
            )
        if action == "launch_application":
            return make_policy_result(
                PolicyDecision.CONFIRM,
                reason="Discovery is not authorization; shortcuts can contain commands.",
                consequence="general application launch",
                rule_id="application-launch-confirmation",
            )

        if not isinstance(target, dict):
            return make_policy_result(
                PolicyDecision.UNKNOWN,
                reason="Semantic target is malformed.",
                consequence="unknown",
                rule_id="malformed-target",
            )

        role = target.get("role")
        name = target.get("name")

        normalized_name = (
            name.strip().lower()
            if isinstance(name, str)
            else ""
        )

        # ---------------------------------------------
        # Explicit protected consequences
        # ---------------------------------------------

        if any(
            term in normalized_name
            for term in self.PROTECTED_TERMS
        ):
            return make_policy_result(
                PolicyDecision.DENY,
                reason=(
                    "Target appears to affect a "
                    "protected security control."
                ),
                consequence="protected security change",
                rule_id="protected-security-control",
            )

        # ---------------------------------------------
        # Sensitive named targets
        # ---------------------------------------------

        if any(
            term in normalized_name
            for term in self.SENSITIVE_TERMS
        ):
            return make_policy_result(
                PolicyDecision.CONFIRM,
                reason=(
                    "Target name indicates a "
                    "potentially consequential action."
                ),
                consequence="sensitive user action",
                rule_id="sensitive-target-name",
            )

        # ---------------------------------------------
        # Selection/navigation
        # ---------------------------------------------

        if (
            action == "select"
            and role in self.SAFE_NAVIGATION_ROLES
        ):
            return make_policy_result(
                PolicyDecision.ALLOW,
                reason=(
                    "Semantic selection is classified "
                    "as ordinary UI navigation."
                ),
                consequence="interface navigation",
                rule_id="safe-navigation",
            )

        # ---------------------------------------------
        # Text/value mutation
        # ---------------------------------------------

        if action in {
            "set_value",
            "set_document_text",
            "type_text",
        }:
            return make_policy_result(
                PolicyDecision.CONFIRM,
                reason=(
                    "Text/value mutation can alter "
                    "user-controlled data."
                ),
                consequence="data mutation",
                rule_id="data-mutation",
            )

        # ---------------------------------------------
        # Toggle
        # ---------------------------------------------

        if action == "toggle":
            return make_policy_result(
                PolicyDecision.CONFIRM,
                reason=(
                    "Toggle changes application state "
                    "and its consequence is not yet "
                    "known strongly enough for "
                    "automatic execution."
                ),
                consequence="application state change",
                rule_id="toggle-state-change",
            )

        # ---------------------------------------------
        # Everything else fails closed
        # ---------------------------------------------

        return make_policy_result(
            PolicyDecision.UNKNOWN,
            reason=(
                "No consequence policy rule matched "
                "the requested action."
            ),
            consequence="unknown",
            rule_id="no-matching-rule",
        )
if __name__ == "__main__":
    print(
        "Consequence policy contract loaded."
    )

    for decision in PolicyDecision:
        result = make_policy_result(
            decision,
            reason="Contract test.",
            consequence="test consequence",
            rule_id="contract-test",
        )

        print(
            decision.value,
            "may_execute=",
            result.may_execute,
            "requires_confirmation=",
            result.requires_confirmation,
        )
