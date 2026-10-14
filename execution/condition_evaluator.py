from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ConditionResult:
    passed: bool
    condition_type: str
    reason: str
    key: Optional[str] = None
    expected: Any = None
    observed: Any = None


@dataclass(frozen=True)
class ConditionSetResult:
    passed: bool
    results: List[ConditionResult]
    error: Optional[str] = None


class ConditionEvaluator:
    """
    Evaluates structured deterministic conditions.

    This component:
    - does not execute actions,
    - does not call an LLM,
    - does not grant permissions,
    - fails closed on malformed or unknown conditions.
    """

    SUPPORTED_TYPES = {
        "state_equals",
        "state_not_equals",
        "value_exists",
    }

    def evaluate_condition(
        self,
        condition: Dict[str, Any],
        state: Dict[str, Any],
    ) -> ConditionResult:

        if not isinstance(condition, dict):
            return ConditionResult(
                passed=False,
                condition_type="invalid",
                reason="Condition must be a dictionary.",
            )

        if not isinstance(state, dict):
            return ConditionResult(
                passed=False,
                condition_type="invalid",
                reason="Observed state must be a dictionary.",
            )

        condition_type = condition.get("type")

        if not isinstance(condition_type, str):
            return ConditionResult(
                passed=False,
                condition_type="invalid",
                reason="Condition requires a string 'type'.",
            )

        if condition_type not in self.SUPPORTED_TYPES:
            return ConditionResult(
                passed=False,
                condition_type=condition_type,
                reason=(
                    "Unknown condition type. "
                    "Condition evaluation failed closed."
                ),
            )

        key = condition.get("key")

        if not isinstance(key, str) or not key.strip():
            return ConditionResult(
                passed=False,
                condition_type=condition_type,
                reason="Condition requires a non-empty string 'key'.",
            )

        key = key.strip()

        if condition_type == "state_equals":
            if "expected" not in condition:
                return ConditionResult(
                    passed=False,
                    condition_type=condition_type,
                    key=key,
                    reason="state_equals requires 'expected'.",
                )

            expected = condition["expected"]
            observed = state.get(key)

            passed = (
                key in state
                and observed == expected
            )

            return ConditionResult(
                passed=passed,
                condition_type=condition_type,
                key=key,
                expected=expected,
                observed=observed,
                reason=(
                    "Observed state equals expected state."
                    if passed
                    else "Observed state does not equal expected state."
                ),
            )

        if condition_type == "state_not_equals":
            if "expected" not in condition:
                return ConditionResult(
                    passed=False,
                    condition_type=condition_type,
                    key=key,
                    reason="state_not_equals requires 'expected'.",
                )

            expected = condition["expected"]
            observed = state.get(key)

            passed = (
                key in state
                and observed != expected
            )

            return ConditionResult(
                passed=passed,
                condition_type=condition_type,
                key=key,
                expected=expected,
                observed=observed,
                reason=(
                    "Observed state differs from the forbidden state."
                    if passed
                    else "Observed state matches the forbidden state."
                ),
            )

        if condition_type == "value_exists":
            observed = state.get(key)

            passed = (
                key in state
                and observed is not None
            )

            return ConditionResult(
                passed=passed,
                condition_type=condition_type,
                key=key,
                observed=observed,
                reason=(
                    "Required value exists."
                    if passed
                    else "Required value does not exist."
                ),
            )

        return ConditionResult(
            passed=False,
            condition_type=condition_type,
            key=key,
            reason="Condition evaluation failed closed.",
        )

    def evaluate_all(
        self,
        conditions: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> ConditionSetResult:

        if not isinstance(conditions, list):
            return ConditionSetResult(
                passed=False,
                results=[],
                error="Conditions must be provided as a list.",
            )

        if not isinstance(state, dict):
            return ConditionSetResult(
                passed=False,
                results=[],
                error="Observed state must be a dictionary.",
            )

        results: List[ConditionResult] = []

        for condition in conditions:
            result = self.evaluate_condition(
                condition=condition,
                state=state,
            )

            results.append(result)

            # Fail closed immediately.
            if not result.passed:
                return ConditionSetResult(
                    passed=False,
                    results=results,
                    error=result.reason,
                )

        return ConditionSetResult(
            passed=True,
            results=results,
        )