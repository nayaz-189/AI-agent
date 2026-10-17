"""Closed diagnostic vocabulary. Backend prose is never a public error."""
from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    PERMISSION_DENIED = "permission_denied"
    CONFIRMATION_REQUIRED = "confirmation_required"
    PRECONDITION_FAILED = "precondition_failed"
    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"
    BACKEND_UNAVAILABLE = "backend_unavailable"


MESSAGES = {
    ErrorCode.INVALID_REQUEST: "Invalid request; no action executed.",
    ErrorCode.PERMISSION_DENIED: "Permission denied.",
    ErrorCode.CONFIRMATION_REQUIRED: "Explicit user confirmation required.",
    ErrorCode.PRECONDITION_FAILED: "Precondition failed: required state was not satisfied.",
    ErrorCode.EXECUTION_FAILED: "Execution failed.",
    ErrorCode.VERIFICATION_FAILED: "Postcondition failed: outcome was not verified.",
    ErrorCode.BACKEND_UNAVAILABLE: "No execution backend registered for this operation.",
}
STAGES = {"validation", "authorization", "precondition", "execution", "postcondition", "routing"}


@dataclass(frozen=True)
class SafeFailure:
    code: ErrorCode
    stage: str
    retryable: bool = False

    def __post_init__(self):
        if not isinstance(self.code, ErrorCode) or not isinstance(self.stage, str) or self.stage not in STAGES or type(self.retryable) is not bool:
            raise ValueError("Invalid safe failure.")

    @property
    def message(self):
        return MESSAGES[self.code]

    def to_dict(self):
        return {"error_code": self.code.value, "stage": self.stage, "retryable": self.retryable}


def failure_from_message(message):
    # Exact controlled strings only. Never classify arbitrary backend prose.
    code = next((code for code, text in MESSAGES.items() if message == text), ErrorCode.EXECUTION_FAILED)
    stage = {ErrorCode.INVALID_REQUEST: "validation", ErrorCode.PERMISSION_DENIED: "authorization",
             ErrorCode.CONFIRMATION_REQUIRED: "authorization", ErrorCode.PRECONDITION_FAILED: "precondition",
             ErrorCode.VERIFICATION_FAILED: "postcondition", ErrorCode.BACKEND_UNAVAILABLE: "routing"}.get(code, "execution")
    return SafeFailure(code, stage)


def safe_message(message):
    return failure_from_message(message).message


def safe_result(result):
    """Only documented boolean outcome fields cross the diagnostic boundary."""
    if not isinstance(result, dict):
        return None
    return {key: result[key] for key in ("verified", "executed", "tool_reported_success")
            if type(result.get(key)) is bool}
