import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scout_independent_news as news
from scout_independent_news import (
    IndependentNewsError,
    build_google_news_url,
    choose_news_batch,
    classify_headline,
    parse_google_news_rss,
    run_news_cycle,
)


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item><title>AAA posts quarterly results</title><link>https://example.com/a</link><pubDate>Mon, 12 Oct 2026 12:00:00 GMT</pubDate><source>Example News</source></item>
  <item><title>AAA opens new facility</title><link>https://example.com/b</link><pubDate>Mon, 12 Oct 2026 11:00:00 GMT</pubDate><source>Another Source</source></item>
</channel></rss>"""


class IndependentNewsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = root / "state.json"
        self.alerts = root / "alerts.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_batch_rotates_and_excludes_csu(self):
        batch, cursor = choose_news_batch(
            ["CSU:TSX", "AAA:TSX", "BBB:TSX", "CCC:TSX", "DDD:TSX"],
            cursor=0,
        )
        self.assertEqual(batch, ["AAA:TSX", "BBB:TSX", "CCC:TSX"])
        self.assertEqual(cursor, 3)

    def test_google_news_url_is_fixed_host(self):
        url = build_google_news_url("AAA:TSX")
        self.assertTrue(url.startswith("https://news.google.com/rss/search?"))
        self.assertIn("AAA", url)
        with self.assertRaises(IndependentNewsError):
            build_google_news_url("BAD SYMBOL:TSX")

    def test_headline_classification(self):
        self.assertEqual(classify_headline("AAA reports quarterly results"), "EARNINGS")
        self.assertEqual(classify_headline("AAA updates guidance"), "GUIDANCE")
        self.assertEqual(classify_headline("AAA subject to class action"), "LITIGATION")
        self.assertEqual(classify_headline("AAA opens new office"), "INDEPENDENT_NEWS")

    def test_rss_parser_is_sanitized_and_non_tradeable(self):
        rows = parse_google_news_rss(RSS, "AAA:TSX")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["category"], "EARNINGS")
        self.assertEqual(rows[0]["publisher"], "Example News")
        self.assertEqual(rows[0]["sourceType"], "INDEPENDENT_NEWS_RSS")
        self.assertTrue(rows[0]["reviewRequired"])
        self.assertFalse(rows[0]["tradeEligible"])

    def test_first_cycle_establishes_baseline_without_alert(self):
        with patch.object(news, "watch_symbols", return_value=["AAA:TSX"]),              patch.object(news, "fetch_symbol_news", return_value=parse_google_news_rss(RSS, "AAA:TSX")):
            result = run_news_cycle(state_path=self.state, alert_path=self.alerts)
        self.assertTrue(result["ran"])
        self.assertEqual(result["alerts"], 0)
        self.assertFalse(result["automaticRecheck"])
        self.assertFalse(self.alerts.exists())

    def test_second_cycle_emits_only_unseen_news(self):
        first_rows = parse_google_news_rss(RSS, "AAA:TSX")
        with patch.object(news, "watch_symbols", return_value=["AAA:TSX"]),              patch.object(news, "fetch_symbol_news", return_value=first_rows):
            run_news_cycle(state_path=self.state, alert_path=self.alerts)

        extra = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item><title>AAA updates guidance</title><link>https://example.com/new</link><pubDate>Mon, 12 Oct 2026 13:00:00 GMT</pubDate><source>Independent Wire</source></item>
  <item><title>AAA posts quarterly results</title><link>https://example.com/a</link><pubDate>Mon, 12 Oct 2026 12:00:00 GMT</pubDate><source>Example News</source></item>
</channel></rss>"""
        with patch.object(news, "watch_symbols", return_value=["AAA:TSX"]),              patch.object(news, "fetch_symbol_news", return_value=parse_google_news_rss(extra, "AAA:TSX")):
            result = run_news_cycle(state_path=self.state, alert_path=self.alerts)

        self.assertEqual(result["alerts"], 1)
        saved = __import__("json").loads(self.alerts.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["alerts"]), 1)
        alert = saved["alerts"][0]
        self.assertEqual(alert["status"], "NEWS_REVIEW_REQUIRED")
        self.assertFalse(alert["userConfirmedMaterial"])
        self.assertFalse(alert["tradeEligible"])
        self.assertFalse(alert["brokerSubmissionEnabled"])

    def test_independent_news_never_auto_rechecks(self):
        with patch.object(news, "watch_symbols", return_value=["AAA:TSX"]),              patch.object(news, "fetch_symbol_news", return_value=[]):
            result = run_news_cycle(state_path=self.state, alert_path=self.alerts)
        self.assertFalse(result["automaticRecheck"])
        self.assertFalse(result["tradeEligible"])
        self.assertFalse(result["brokerSubmissionEnabled"])


if __name__ == "__main__":
    unittest.main()
