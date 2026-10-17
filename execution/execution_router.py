from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from execution.safe_failure import SafeFailure, ErrorCode, safe_result


ExecutionBackend = Callable[
    [str, Dict[str, Any]],
    Dict[str, Any],
]


@dataclass(frozen=True)
class RouteResult:
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    failure: Optional[SafeFailure] = None

    def __post_init__(self):
        outcome = safe_result(self.result)
        if (self.success is not True or self.error not in (None, "") or self.failure is not None
                or (outcome and any(value is False for value in outcome.values()))):
            failure = self.failure if isinstance(self.failure, SafeFailure) else SafeFailure(ErrorCode.EXECUTION_FAILED, "execution")
            object.__setattr__(self, "success", False)
            object.__setattr__(self, "failure", failure)
            object.__setattr__(self, "error", failure.message)
        object.__setattr__(self, "result", outcome)


class ExecutionRouter:
    """
    Routes actions to explicitly registered execution backends.

    The router:
    - chooses the responsible subsystem,
    - does not grant permission,
    - does not bypass security gates,
    - does not execute arbitrary code,
    - fails closed when a backend is unavailable.
    """

    def __init__(self) -> None:
        self._backends: Dict[
            str,
            ExecutionBackend,
        ] = {}

    def register_backend(
        self,
        agent: str,
        backend: ExecutionBackend,
    ) -> None:

        if not isinstance(agent, str) or not agent.strip():
            raise ValueError(
                "Agent name must be a non-empty string."
            )

        if not callable(backend):
            raise TypeError(
                "Execution backend must be callable."
            )

        normalized_agent = agent.strip()

        if normalized_agent in self._backends:
            raise ValueError(
                f"Backend already registered: {normalized_agent}"
            )

        self._backends[normalized_agent] = backend

    def has_backend(
        self,
        agent: str,
    ) -> bool:

        return agent in self._backends

    def route(
        self,
        agent: str,
        action: str,
        arguments: Dict[str, Any],
    ) -> RouteResult:

        if not isinstance(agent, str) or not agent.strip():
            return RouteResult(
                success=False,
                error="Route requires a non-empty agent name.",
            )

        if not isinstance(action, str) or not action.strip():
            return RouteResult(
                success=False,
                error="Route requires a non-empty action name.",
            )

        if not isinstance(arguments, dict):
            return RouteResult(
                success=False,
                error="Route arguments must be a dictionary.",
            )

        normalized_agent = agent.strip()
        normalized_action = action.strip()

        backend = self._backends.get(
            normalized_agent
        )

        if backend is None:
            return RouteResult(
                success=False,
                failure=SafeFailure(ErrorCode.BACKEND_UNAVAILABLE, "routing"),
                error=(
                    "No execution backend registered for agent: "
                    f"{normalized_agent}"
                ),
            )

        try:
            raw_result = backend(
                normalized_action,
                dict(arguments),
            )
        except Exception as exc:
            return RouteResult(
                success=False,
                error=(
                    "Execution backend raised "
                    f"{type(exc).__name__}."
                ),
            )

        if not isinstance(raw_result, dict):
            return RouteResult(
                success=False,
                error=(
                    "Execution backend returned an invalid result. "
                    "Expected a dictionary."
                ),
            )

        if set(raw_result) - {"success", "result", "error"}:
            return RouteResult(success=False, error="Invalid backend result fields.")

        success = raw_result.get("success")

        if not isinstance(success, bool):
            return RouteResult(
                success=False,
                error=(
                    "Execution backend result must contain "
                    "a boolean 'success' field."
                ),
            )

        result = raw_result.get("result")

        if result is not None and not isinstance(
            result,
            dict,
        ):
            return RouteResult(
                success=False,
                error=(
                    "Execution backend result must be "
                    "a dictionary or None."
                ),
            )

        if success and raw_result.get("error") not in (None, ""):
            return RouteResult(
                success=False,
                error="Execution backend returned contradictory success and error fields.",
            )

        if success:
            return RouteResult(
                success=True,
                result=result,
            )

        error = raw_result.get("error")

        if not isinstance(error, str) or not error.strip():
            error = (
                "Execution backend reported failure "
                "without an error message."
            )

        return RouteResult(
            success=False,
            result=result,
            error=error.strip(),
        )
