"""Vision request boundary: short-lived, non-persistent screenshot analysis."""
from __future__ import annotations
import os

from .screen_access import capture


def vision_error(exc: Exception) -> str:
    """Avoid printing exception text (can contain URLs or credentials)."""
    for field in ("status_code", "code"):
        value = getattr(exc, field, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return type(exc).__name__ + " HTTP " + str(value)
    return type(exc).__name__


async def inspect(client, question: str, scope="window", *, capture_fn=None, runner=None):
    capture_fn = capture_fn or capture
    if runner is None:
        from .stability import bounded_daemon_call
        runner = bounded_daemon_call
    result = await runner(capture_fn, scope, timeout=8)
    if isinstance(result, dict):
        return result
    pixels, detail = result
    if pixels is None:
        return {"status": "blocked", "message": detail}
    from google.genai import types
    try:
        prompt = (question or "Describe what is on my screen.")[:380]
        prompt += ("\nDescribe only ordinary visible interface information. "
                   "If you detect a password, banking, checkout, billing or payment page, "
                   "do not describe the content; return exactly PROTECTED_CONTEXT. "
                   "Do not transcribe personal messages verbatim unless requested.")
        response = await client.aio.models.generate_content(
            model=os.environ.get("VORAK_VISION_MODEL", "gemini-2.5-flash"),
            contents=[types.Part.from_text(text=prompt), types.Part.from_bytes(data=pixels, mime_type="image/jpeg")],
        )
        description = (getattr(response, "text", "") or "").strip()
        if not description:
            return {"status": "failed", "message": "Vision provider returned no text."}
        if "PROTECTED_CONTEXT" in description or any(x in description.casefold() for x in ("credit card number", "otp code", "password is")):
            return {"status": "blocked", "message": "Protected content detected by visual analysis; no description shared."}
        return {"status": "observed", "message": detail, "analysis": description[:1700]}
    except Exception as exc:
        label = vision_error(exc)
        print("VISION DIAGNOSTIC:", label, flush=True)
        return {"status": "failed", "message": "Vision provider failed (" + label + "). Check model access/quota/connectivity."}
