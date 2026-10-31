"""Offline tests for the opt-in specialist research connector.

Run:
python -m unittest discover -s tests -p test_vorak_expert_research.py -v
"""
from pathlib import Path
from unittest import TestCase, mock
import json

from vorak_integrated import expert_research
from vorak_integrated import current_research


class ExpertResearchTests(TestCase):
    def test_disabled_never_calls_network(self):
        with mock.patch.dict("os.environ", {"VORAK_EXPERT_RESEARCH": "0", "PERPLEXITY_API_KEY": "example"}):
            with mock.patch.object(expert_research, "urlopen") as net:
                result = expert_research.research("Investigate the history of machine learning.")
        self.assertEqual(result["status"], "disabled")
        net.assert_not_called()

    def test_missing_api_key_never_calls_network(self):
        with mock.patch.dict("os.environ", {"VORAK_EXPERT_RESEARCH": "1", "PERPLEXITY_API_KEY": ""}):
            with mock.patch.object(expert_research, "urlopen") as net:
                result = expert_research.research("Investigate the history of machine learning.")
        self.assertEqual(result["status"], "not_configured")
        net.assert_not_called()

    def test_invalid_query_never_calls_network(self):
        with mock.patch.object(expert_research, "urlopen") as net:
            result = expert_research.research("bad")
        self.assertEqual(result["status"], "invalid_query")
        net.assert_not_called()

    def test_only_source_urls_from_provider(self):
        payload = {"output": [
            {"type": "message", "content": [
                {"type": "output_text", "text": "Research finding",
                 "annotations": [{"url": "https://example.org/paper", "title": "Paper"}]}
            ]},
            {"type": "web_search_call", "results": [
                {"url": "https://other.org/article", "title": "Other"},
                {"url": "http://127.0.0.1/internal", "title": "Rejected"},
            ]}
        ]}
        answer, sources = expert_research._collect(payload)
        self.assertEqual(answer, "Research finding")
        self.assertEqual(len(sources), 2)
        self.assertTrue(all(not x["url"].startswith("http://127.") for x in sources))

    def test_no_citations_means_no_verified_claim(self):
        answer, sources = expert_research._collect({
            "output": [{"content": [{"type": "output_text", "text": "Claim"}]}]
        })
        self.assertEqual(answer, "Claim")
        self.assertEqual(sources, [])

    def test_live_endpoint_never_called_by_default(self):
        with mock.patch.dict("os.environ", {"VORAK_EXPERT_RESEARCH": "", "PERPLEXITY_API_KEY": ""}):
            self.assertEqual(expert_research.research("Investigate AI benchmarks.")["status"], "disabled")


class IntegrationTests(TestCase):
    def test_local_india_time_is_deterministic(self):
        value = current_research.lookup("time")
        self.assertEqual(value["status"], "ok")
        self.assertEqual(value["timezone"], "Asia/Kolkata")
        self.assertRegex(value["formatted"], r"^\d{2}:\d{2} [AP]M$")

    def test_live_session_preserved(self):
        s = (Path(__file__).resolve().parents[1] / "vorak_integrated" / "live.py").read_text(encoding="utf-8")
        self.assertIn("async with client.aio.live.connect", s)
        self.assertIn("elif fc.name=='expert_research':", s)
        self.assertIn("'name':'expert_research'", s)
        self.assertIn("elif fc.name=='current_information':", s)
        self.assertIn("'enum':['weather','news','search','time']", s)
        self.assertIn("'name':'whatsapp_self_work'", s)
        self.assertIn("NO_INTERRUPTION", s)
