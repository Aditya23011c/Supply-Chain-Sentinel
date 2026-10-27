"""Run:  python -m unittest tests.test_phase3 -v      (no internet / API key needed: everything is mocked)"""
import json, os, unittest
from unittest import mock

from agents import config  # noqa: F401  (loads .env FIRST so the lines below can undo it)
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_PROVIDER", "N8N_BASE_URL"):
    os.environ.pop(k, None)

from agents import llm
from agents.monitor import feeds, monitor_agent
from agents.negotiation import negotiation_agent
from agents.orchestrator.graph import run_pipeline

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Nhava Sheva port operations suspended after cyclone warning - Hindustan Times</title><link>https://example.com/a</link><source url="x">Hindustan Times</source><pubDate>Sun, 04 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Mumbai Indians sign new coach - Sports Daily</title><link>https://example.com/b</link><source>Sports Daily</source><pubDate>Sun, 04 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""
CALM_WEATHER = json.dumps({"current": {"weather_code": 1, "wind_gusts_10m": 12}, "daily": {"precipitation_sum": [0, 1], "wind_gusts_10m_max": [20, 25]}})
STORM_WEATHER = json.dumps({"current": {"weather_code": 95, "wind_gusts_10m": 80}, "daily": {"precipitation_sum": [70, 20], "wind_gusts_10m_max": [85, 40]}})
EMPTY_RSS = '<?xml version="1.0"?><rss><channel></channel></rss>'


def fake_http(url, timeout=8):
    if "news.google.com" in url:
        return (RSS if "Mumbai" in url else EMPTY_RSS).encode()
    return CALM_WEATHER.encode()


class Core(unittest.TestCase):
    def test_extract_json(self):
        self.assertEqual(llm.extract_json('<think>hmm</think>```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(llm.extract_json('Sure! {"a": 2} hope that helps'), {"a": 2})
        with self.assertRaises(llm.LLMError):
            llm.extract_json("no json here")

    def test_no_key_means_not_configured(self):
        self.assertFalse(llm.settings()["configured"])
        self.assertIn("no LLM key", llm.label())

    def test_provider_selection(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            self.assertEqual(llm.settings()["provider"], "gemini")
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k", "GEMINI_API_KEY": "k"}):
            s = llm.settings()
            self.assertEqual((s["provider"], s["model"]), ("groq", "openai/gpt-oss-120b"))
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "groq"}):   # asked for groq but no key
            self.assertFalse(llm.settings()["configured"])


class Feeds(unittest.TestCase):
    def test_news_parsing(self):
        with mock.patch.object(feeds, "_http_get", fake_http):
            items = feeds.fetch_news(feeds.NODES[0])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["source"], "Hindustan Times")

    def test_news_failure_is_soft(self):
        with mock.patch.object(feeds, "_http_get", side_effect=OSError("offline")):
            self.assertEqual(feeds.fetch_news(feeds.NODES[0]), [])
            self.assertIsNone(feeds.fetch_weather(feeds.NODES[0]))

    def test_weather_thresholds(self):
        with mock.patch.object(feeds, "_http_get", lambda u, timeout=8: CALM_WEATHER.encode()):
            self.assertIsNone(feeds.fetch_weather(feeds.NODES[0]))
        with mock.patch.object(feeds, "_http_get", lambda u, timeout=8: STORM_WEATHER.encode()):
            w = feeds.fetch_weather(feeds.NODES[0])
        self.assertEqual(w["kind"], "weather")
        self.assertIn("85 km/h", w["title"])

    def test_rules_ignore_noise_and_catch_real(self):
        node = feeds.NODES[0]
        noise = [{"title": "Mumbai Indians sign new coach", "link": "", "source": "x", "published": ""}]
        self.assertIsNone(feeds.rules_classify(node, noise))
        real = [{"title": "Fire breaks out at factory in Mumbai industrial estate", "link": "", "source": "x", "published": ""}]
        self.assertEqual(feeds.rules_classify(node, real)["disruption_type"], "supplier_factory_fire")

    def test_airport_is_not_a_port(self):
        node = feeds.NODES[0]
        sig = [{"title": "Mumbai Airport T1 Closure: Navi Mumbai Shift Explained", "link": "", "source": "x", "published": ""},
               {"title": "Lawyers to strike on Monday over assault on advocate", "link": "", "source": "x", "published": ""}]
        self.assertIsNone(feeds.rules_classify(node, sig))
        ok = [{"title": "Port of Mumbai closed after workers strike", "link": "", "source": "x", "published": ""}]
        self.assertEqual(feeds.rules_classify(node, ok)["disruption_type"], "port_closure")

    def test_llm_output_is_validated(self):
        node, sig = feeds.NODES[0], [{"title": "t1", "link": "l", "source": "s", "published": "p"}, {"title": "t2", "link": "l", "source": "s", "published": "p"}]
        raw = {"disruption": True, "disruption_type": "alien_invasion", "headline": "X" * 500, "severity": 7, "evidence_index": 99, "reasoning": "r"}
        with mock.patch.object(llm, "chat_json", return_value=raw), mock.patch.object(llm, "settings", return_value={"configured": True, "provider": "groq", "model": "m"}):
            ev = feeds.llm_classify(node, sig)
        self.assertEqual(ev["disruption_type"], "other")
        self.assertEqual(ev["severity_estimate"], 1.0)
        self.assertLessEqual(len(ev["headline"]), 160)
        self.assertEqual(ev["evidence"][0]["title"], "t1")
        with mock.patch.object(llm, "chat_json", return_value={"disruption": False}), mock.patch.object(llm, "settings", return_value={"configured": True, "provider": "groq", "model": "m"}):
            self.assertIsNone(feeds.llm_classify(node, sig))

    def test_llm_failure_falls_back_to_rules(self):
        sig = [{"title": "Port of Mumbai closed after strike", "link": "", "source": "s", "published": ""}]
        with mock.patch.object(llm, "settings", return_value={"configured": True, "provider": "groq", "model": "m"}), \
             mock.patch.object(llm, "chat_json", side_effect=llm.LLMError("HTTP 404: model not found")):
            ev = feeds.classify(feeds.NODES[0], sig)
        self.assertIn("LLM unavailable", ev["classifier"])

    def test_full_scan_finds_mumbai(self):
        with mock.patch.object(feeds, "_http_get", fake_http):
            ev = feeds.scan_live()
        self.assertEqual(ev["location"], "Mumbai")
        self.assertEqual(ev["disruption_type"], "port_closure")
        self.assertTrue(ev["evidence"][0]["link"].startswith("https://"))

    def test_scan_with_nothing_returns_none(self):
        with mock.patch.object(feeds, "_http_get", lambda u, timeout=8: EMPTY_RSS.encode() if "news" in u else CALM_WEATHER.encode()):
            self.assertIsNone(feeds.scan_live())


class Negotiation(unittest.TestCase):
    plan = {"risk_event": {"headline": "h", "disruption_type": "port_closure", "location": "Mumbai"},
            "impact": {"resource_category": "electronic-components", "affected_orders": [1, 2]}}
    sup = {"name": "Acme", "location": "Colombo"}
    cfg = {"configured": True, "provider": "groq", "model": "m"}

    def test_default_without_llm(self):
        self.assertEqual(negotiation_agent.justification(self.plan, self.sup)[1], "template")

    def test_good_llm_sentence_used(self):
        with mock.patch.object(llm, "settings", return_value=self.cfg), mock.patch.object(llm, "chat", return_value='"We must keep customer lines running."'):
            s, by = negotiation_agent.justification(self.plan, self.sup)
        self.assertEqual(s, "We must keep customer lines running.")
        self.assertTrue(by.startswith("llm:"))

    def test_hallucinated_numbers_rejected(self):
        for bad in ("We will pay 90 per unit.", "See http://evil.example", "Budget is ₹5 lakh.", "x" * 300):
            with mock.patch.object(llm, "settings", return_value=self.cfg), mock.patch.object(llm, "chat", return_value=bad):
                s, by = negotiation_agent.justification(self.plan, self.sup)
            self.assertEqual(s, negotiation_agent.DEFAULT_JUSTIFICATION)
            self.assertIn("rejected", by)


class Pipeline(unittest.TestCase):
    def test_live_scan_end_to_end(self):
        with mock.patch.object(feeds, "_http_get", fake_http):
            plan = run_pipeline("live_scan")
        self.assertEqual(plan["status"], "approved")
        self.assertEqual(plan["risk_event"]["location"], "Mumbai")
        self.assertEqual([h["decision"] for h in plan["negotiation_history"]], ["reject", "approve"])
        self.assertIn("Mumbai", plan["negotiation"]["draft_outreach"])

    def test_live_scan_falls_back_to_scripted(self):
        with mock.patch.object(feeds, "_http_get", lambda u, timeout=8: EMPTY_RSS.encode() if "news" in u else CALM_WEATHER.encode()):
            plan = run_pipeline("live_scan")
        self.assertIn("scripted-fallback", plan["risk_event"]["source"])
        self.assertEqual(plan["status"], "approved")

    def test_factory_fire_email_is_not_about_ports(self):
        plan = run_pipeline("factory_fire")
        self.assertNotIn("port disruption", plan["negotiation"]["draft_outreach"])
        self.assertIn("supplier factory fire affecting Chennai", plan["negotiation"]["draft_outreach"])


if __name__ == "__main__":
    unittest.main()
