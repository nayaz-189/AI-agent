"""Offline contract tests for read-only VORAK current information.

Run: python -m unittest discover -s tests -p test_vorak_current_research.py -v
"""
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest import TestCase, mock

from vorak_integrated import current_research as research


class WeatherTests(TestCase):
    def test_weather_uses_geocode_then_current(self):
        def fake_json(url):
            if "geocoding-api.open-meteo.com" in url:
                return {"results": [{"name": "Bengaluru", "admin1": "Karnataka",
                                     "country": "India", "latitude": 12.9, "longitude": 77.6}]}
            self.assertIn("api.open-meteo.com", url)
            return {"timezone": "Asia/Kolkata", "current": {
                "time": "2026-10-31T18:00", "temperature_2m": 26.5,
                "apparent_temperature": 27.5, "relative_humidity_2m": 63,
                "precipitation": 0, "weather_code": 2, "wind_speed_10m": 5
            }}
        with mock.patch.object(research, "_json", side_effect=fake_json):
            result = research.lookup("weather", location="Bengaluru")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["temperature_c"], 26.5)
        self.assertEqual(result["conditions"], "Partly cloudy")
        self.assertIn("India", result["location"])

    def test_unknown_city_fails_without_fabricating_weather(self):
        with mock.patch.object(research, "_json", return_value={"results": []}):
            result = research.lookup("weather", location="madeupcity")
        self.assertEqual(result["status"], "not_found")
        self.assertNotIn("temperature_c", result)

    def test_network_error_returns_unavailable(self):
        with mock.patch.object(research, "_json", side_effect=TimeoutError("private detail")):
            result = research.lookup("weather")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("private detail", json.dumps(result))


class NewsTests(TestCase):
    def test_recent_headlines_only(self):
        new = format_datetime(datetime.now(timezone.utc) - timedelta(hours=2))
        old = format_datetime(datetime.now(timezone.utc) - timedelta(days=10))
        xml = ('<rss><channel>'
               '<item><title>Recent AI update</title><link>https://news.google.com/a</link>'
               '<pubDate>' + new + '</pubDate><source>Publisher A</source></item>'
               '<item><title>Old update</title><link>https://news.google.com/b</link>'
               '<pubDate>' + old + '</pubDate></item>'
               '</channel></rss>').encode("utf-8")
        with mock.patch.object(research, "_download", return_value=xml):
            result = research.lookup("news", query="AI", hours=24)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(result["articles"][0]["publisher"], "Publisher A")
        self.assertIn("articles", result)

    def test_invalid_hours_does_not_fetch(self):
        with mock.patch.object(research, "_download") as download:
            r = research.lookup("news", hours=0)
        self.assertEqual(r["status"], "invalid")
        download.assert_not_called()

    def test_unsupported_kind(self):
        self.assertEqual(research.lookup("execute")["status"], "invalid")


class SearchTests(TestCase):
    def test_no_key_uses_link_discovery_not_verified_claims(self):
        with mock.patch.dict("os.environ", {"TAVILY_API_KEY": ""}):
            with mock.patch("vorak_integrated.actions.web_candidates",
                            return_value=[("Source", "https://example.org/post")]):
                result = research.lookup("search", query="AI developments")
        self.assertEqual(result["status"], "links_only")
        self.assertIn("not full articles", result["note"])

    def test_allowlisted_external_api_hosts(self):
        with self.assertRaises(ValueError):
            research._download("http://api.open-meteo.com/")
        with self.assertRaises(ValueError):
            research._download("https://example.org/private")


class IntegrationTests(TestCase):
    def test_live_preserves_existing_session_and_apps(self):
        source = (Path(__file__).resolve().parents[1] /
                  "vorak_integrated" / "live.py").read_text(encoding="utf-8")
        self.assertIn("async with client.aio.live.connect", source)
        self.assertIn("elif fc.name=='current_information':", source)
        self.assertIn("'name':'current_information'", source)
        self.assertIn("fc.name=='open_app_or_site'", source)
        self.assertIn("fc.name=='whatsapp_self_draft'", source)
        self.assertNotIn("'google_search': {}", source)
