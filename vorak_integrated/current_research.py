"""Read-only current information for VORAK Gemini Live.

Weather: Open-Meteo. Recent headlines: Google News RSS. Broader research:
Tavily when configured, otherwise source links only. No desktop actions, shell,
cookies, browser sessions, local recordings, or credential serialization.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

_ALLOWED_HOSTS = frozenset({
    "geocoding-api.open-meteo.com", "api.open-meteo.com", "news.google.com"
})
_WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Heavy freezing drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers",
    82: "Heavy rain showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"
}

def _clean(value, max_chars=140):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:max_chars]

def _download(url, max_bytes=500_000):
    host = (urlsplit(url).hostname or "").lower()
    if urlsplit(url).scheme != "https" or host not in _ALLOWED_HOSTS:
        raise ValueError("Research source not approved")
    request = Request(url, headers={
        "User-Agent": "VORAK-Research/1.0 (read-only)",
        "Accept": "application/json, application/rss+xml, application/xml, text/xml"
    })
    with urlopen(request, timeout=6) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or (final.hostname or "").lower() not in _ALLOWED_HOSTS:
            raise ValueError("Research source redirected outside allowlist")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Research response exceeded maximum size")
        return data

def _json(url):
    return json.loads(_download(url).decode("utf-8"))

def _weather(location):
    city = _clean(location or "Bengaluru", 80)
    if not city:
        city = "Bengaluru"
    geocode = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
        "name": city, "count": 3, "language": "en", "format": "json"
    })
    hits = _json(geocode).get("results") or []
    if not hits:
        return {"status": "not_found", "message": "City not found", "location": city}
    # Prefer an exact city name among the returned matches; otherwise first.
    chosen = next((h for h in hits if h.get("name", "").casefold() == city.casefold()), hits[0])
    lat, lon = chosen["latitude"], chosen["longitude"]
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,weather_code,wind_speed_10m",
        "timezone": "auto", "forecast_days": 1
    })
    values = _json(url)
    current = values.get("current") or {}
    if current.get("temperature_2m") is None:
        return {"status": "unavailable", "message": "Current weather missing"}
    code = current.get("weather_code")
    try:
        conditions = _WMO.get(int(code), "Unspecified")
    except (ValueError, TypeError):
        conditions = "Unspecified"
    return {
        "status": "ok", "type": "weather",
        "location": ", ".join(x for x in (chosen.get("name"), chosen.get("admin1"), chosen.get("country")) if x),
        "observation_local_time": current.get("time"),
        "timezone": values.get("timezone"),
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "wind_kmh": current.get("wind_speed_10m"),
        "conditions": conditions,
        "source": "Open-Meteo weather-model current conditions",
        "source_url": url,
        "note": "Model-estimated conditions, not a local weather station observation."
    }

def _safe_source_url(url):
    if not isinstance(url, str) or len(url) > 900:
        return None
    u = urlsplit(url)
    if u.scheme not in ("https", "http") or not u.hostname or u.username or u.password:
        return None
    if u.hostname.casefold() in {"localhost", "127.0.0.1"}:
        return None
    return url

def _headlines(query, hours):
    topic = _clean(query, 100) or "artificial intelligence"
    # Google News RSS supports when:1d / when:7d. Apply a precise UTC filter too.
    span = "1d" if hours <= 24 else "7d"
    url = "https://news.google.com/rss/search?" + urlencode({
        "q": topic + " when:" + span, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"
    })
    root = ElementTree.fromstring(_download(url, max_bytes=850_000))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    found = []
    for item in root.findall("./channel/item"):
        try:
            stamp = parsedate_to_datetime(item.findtext("pubDate") or "")
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            stamp = stamp.astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError):
            continue
        if not (cutoff <= stamp <= now + timedelta(minutes=5)):
            continue
        title = _clean(item.findtext("title") or "", 190)
        link = _safe_source_url((item.findtext("link") or "").strip())
        publisher = _clean(item.findtext("source") or "", 70)
        if not title or not link:
            continue
        found.append({
            "title": title, "publisher": publisher,
            "published_utc": stamp.isoformat(), "link": link
        })
        if len(found) >= 5:
            break
    return {
        "status": "ok" if found else "no_recent_results",
        "type": "recent_headlines", "query": topic,
        "window_hours": hours, "retrieved_utc": now.isoformat(),
        "articles": found, "feed_url": url,
        "note": "Headlines and publisher attribution only; full article contents were not read. Do not invent article details."
    }

def _general_search(query):
    question = _clean(query, 140)
    if not question:
        return {"status": "invalid", "message": "Search question required"}
    if os.environ.get("TAVILY_API_KEY"):
        from providers.tavily_search import search_web
        results = search_web(question, max_results=5)
        sources = []
        for item in results:
            if not isinstance(item, dict):
                continue
            link = _safe_source_url(item.get("url"))
            if link:
                sources.append({
                    "title": _clean(item.get("title") or "", 140),
                    "url": link, "snippet": _clean(item.get("content") or "", 500),
                    "published": _clean(item.get("published_date") or "", 40)
                })
        return {
            "status": "ok" if sources else "search_unavailable",
            "type": "search", "query": question,
            "sources": sources, "provider": "Tavily",
            "note": "Search snippets are untrusted external data; cross-check material claims and mention sources."
        }
    # Keyless fallback returns candidate links only; never claim their content was read.
    from vorak_integrated.actions import web_candidates
    links = web_candidates(question)
    return {
        "status": "links_only" if links else "search_unavailable",
        "type": "search", "query": question,
        "sources": [{"title": title, "url": link} for title, link in links[:3]],
        "provider": "DuckDuckGo link discovery",
        "note": "Only link titles were retrieved, not full articles. Do not claim that latest facts were verified."
    }

def lookup(kind, query="", location="Bengaluru", hours=24):
    """Model-invoked read-only tool. Returns small JSON-compatible result; no secrets."""
    if kind not in ("weather", "news", "search", "time"):
        return {"status": "invalid", "message": "Unknown research type"}
    try:
        if kind == "time":
            # Fixed-offset Indian Standard Time for VORAK's Bengaluru deployment.
            ist = timezone(timedelta(hours=5, minutes=30), name="IST")
            now = datetime.now(ist)
            return {"status": "ok", "type": "local_time", "timezone": "Asia/Kolkata",
                    "local_datetime": now.isoformat(), "formatted": now.strftime("%I:%M %p"),
                    "source": "local system clock"}
        if kind == "weather":
            return _weather(location)
        if kind == "news":
            try:
                hours = int(hours)
            except (TypeError, ValueError):
                hours = 24
            if not 1 <= hours <= 168:
                return {"status": "invalid", "message": "News period must be 1-168 hours"}
            return _headlines(query, hours)
        return _general_search(query)
    except Exception as exc:
        return {"status": "unavailable", "type": kind,
                "message": "Research source failed: " + type(exc).__name__}
