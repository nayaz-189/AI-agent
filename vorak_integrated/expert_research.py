"""Optional source-cited expert research for VORAK.

An intentionally narrow research-only connector. Requires explicit VORAK_EXPERT_RESEARCH=1
and a Perplexity Agent API key. No shell, browser automation, screen access,
credentials in results, concurrent agent loops, or automatic retries.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ENDPOINT = "https://api.perplexity.ai/v1/agent"
MAX_RESPONSE_BYTES = 1_500_000

def _url(value):
    if not isinstance(value, str) or len(value) > 1500:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        return None
    return value

def _collect(result):
    """Return bounded answer and source URLs; never invent citations."""
    texts = []
    sources = []
    seen = set()
    for item in result.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                texts.append(str(content.get("text") or "")[:10000])
            for annotation in content.get("annotations", []) or []:
                if isinstance(annotation, dict):
                    link = _url(annotation.get("url") or annotation.get("source"))
                    if link and link not in seen:
                        sources.append({"url": link, "title": str(annotation.get("title") or "")[:150]})
                        seen.add(link)
        # Agent API may return web search results in a separate output item.
        for hit in item.get("results", []) or []:
            if not isinstance(hit, dict):
                continue
            link = _url(hit.get("url"))
            if link and link not in seen:
                sources.append({"url": link, "title": str(hit.get("title") or "")[:150]})
                seen.add(link)
        if len(sources) >= 20:
            break
    answer = "\n".join(t for t in texts if t).strip()[:7000]
    return answer, sources[:12]

def research(query, depth="standard"):
    """One bounded expert-research request; no background job or task execution."""
    question = str(query or "").strip()
    if not 10 <= len(question) <= 1500 or any(ord(c) < 32 and c not in "\n\t" for c in question):
        return {"status": "invalid_query", "message": "Provide a focused research question."}
    if os.environ.get("VORAK_EXPERT_RESEARCH") != "1":
        return {"status": "disabled", "message": "Expert API not enabled; use ordinary research."}
    key = os.environ.get("PERPLEXITY_API_KEY")
    if not key:
        return {"status": "not_configured", "message": "PERPLEXITY_API_KEY is not configured."}
    depth = str(depth).lower()
    if depth not in {"standard", "deep"}:
        return {"status": "invalid_depth", "message": "Choose standard or deep."}
    payload = {
        "preset": "high" if depth == "deep" else "low",
        "input": question,
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            if response.status != 200 or urlsplit(response.geturl()).hostname != "api.perplexity.ai":
                return {"status": "unavailable", "message": "Unexpected research API response."}
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            return {"status": "unavailable", "message": "Research result exceeded size limit."}
        result = json.loads(body.decode("utf-8"))
        answer, sources = _collect(result)
        if not answer:
            return {"status": "unavailable", "message": "No answer was returned."}
        return {
            "status": "ok" if sources else "uncited",
            "provider": "Perplexity Agent API",
            "depth": depth,
            "answer": answer,
            "sources": sources,
            "note": ("Retrieved sources require checking against their originals. "
                     "If uncited, do not present claims as independently verified."),
        }
    except HTTPError as exc:
        # Do not print response bodies (they may contain account or secret details).
        return {"status": "provider_error", "http_status": exc.code,
                "message": "Expert provider rejected the request or exceeded quota."}
    except (URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"status": "unavailable", "message": "Expert research request failed."}
