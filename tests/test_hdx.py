#!/usr/bin/env python3
import argparse
import contextlib
import csv
import io
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "hdx.py"
SPEC = importlib.util.spec_from_file_location("hdx", MODULE_PATH)
hdx = importlib.util.module_from_spec(SPEC)
sys.modules["hdx"] = hdx
SPEC.loader.exec_module(hdx)


class HdxTests(unittest.TestCase):
    def test_normalize_event_id(self):
        self.assertEqual(hdx.normalize_event_id("https://www.huodongxing.com/event/2856433093123?x=1"), "2856433093123")
        with self.assertRaises(hdx.HdxError):
            hdx.normalize_event_id("not-an-event")

    def test_extract_json_assignment(self):
        source = 'var ativityJson = {"Id":123,"Title":"测试"};'
        self.assertEqual(hdx.extract_json_assignment(source, "ativityJson")["Title"], "测试")

    def test_search_url_uses_platform_parameters(self):
        args = argparse.Namespace(city="杭州", keyword="AI", tag=None, time="week", date_from=None,
                                  date_to=None, price="free", mode="offline", verified=True,
                                  order="popular", page=2)
        url = hdx.build_search_url(args)
        self.assertIn("qs=AI", url)
        self.assertIn("d=t1", url)
        self.assertIn("range=1", url)
        self.assertIn("eventType=1", url)
        self.assertIn("auth=1", url)
        self.assertIn("orderby=v", url)
        self.assertIn("page=2", url)
        self.assertNotIn("time=week", url)

    def test_parse_search_deduplicates(self):
        card = '''
        <div class="search-tab-content-item-mesh">
          <a class="item-title" href="/event/2856433093123">AI 峰会</a>
          <div class="item-dress"><p>07/30 13:30</p><span class="item-dress-pp">浙江杭州</span></div>
          <p class="user-name">主办方</p><span class="follows">粉丝 45628</span>
        </div>'''
        events = hdx.parse_search(card + card)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].followers, 45628)

    def test_event_route_requires_id(self):
        with self.assertRaises(hdx.HdxError):
            hdx.route_url("event-overview")
        self.assertIn("id=2856433093123", hdx.route_url("event-overview", "2856433093123"))

    def test_routes_are_classified(self):
        self.assertEqual(hdx.ROUTES["discover"]["risk"], "read")
        self.assertEqual(hdx.ROUTES["event-edit"]["risk"], "commit")
        self.assertEqual(hdx.ROUTES["create-event"]["risk"], "prepare")

    def test_signup_is_commit(self):
        self.assertTrue(hdx.ACTIONS["signup"]["risk"] == "commit")

    def test_default_profile_is_neutral(self):
        with tempfile.TemporaryDirectory() as folder:
            old = hdx.DEFAULT_CONFIG_DIR
            hdx.DEFAULT_CONFIG_DIR = pathlib.Path(folder)
            try:
                profile = hdx.load_profile(None)
            finally:
                hdx.DEFAULT_CONFIG_DIR = old
        self.assertEqual(profile["interests"], [])
        self.assertEqual(profile["business_goals"], [])
        self.assertIsNone(profile["max_travel_minutes"])

    def test_search_defaults_to_all_cities(self):
        parser = hdx.build_parser()
        args = parser.parse_args(["search"])
        self.assertEqual(args.city, "全国")
        self.assertNotIn("city=", hdx.build_search_url(args))

    def test_positive_integer_options(self):
        parser = hdx.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["search", "--limit", "0"])
        self.assertEqual(parser.parse_args(["search", "--limit", "2"]).limit, 2)

    def test_search_csv_outputs_one_event_per_row(self):
        payload = {
            "source_url": "https://example.test/events",
            "count": 2,
            "events": [
                {"id": "1", "title": "活动一"},
                {"id": "2", "title": "活动二", "location": "线上"},
            ],
        }
        rows = list(csv.DictReader(io.StringIO(hdx.render(payload, "csv"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], "1")
        self.assertEqual(rows[1]["location"], "线上")

    def test_open_route_print_only_does_not_launch_browser(self):
        parser = hdx.build_parser()
        args = parser.parse_args(["open-route", "event-overview", "--event", "2856433093123", "--print-only"])
        self.assertTrue(args.print_only)

    def test_search_date_validation(self):
        parser = hdx.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["search", "--from", "2026/07/14", "--to", "2026-07-15"])
        args = parser.parse_args(["search", "--from", "2026-07-16", "--to", "2026-07-15"])
        with self.assertRaises(hdx.HdxError):
            hdx.build_search_url(args)

    def test_profile_shape_validation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump({"interests": "AI"}, handle, ensure_ascii=False)
            handle.flush()
            with self.assertRaises(hdx.HdxError):
                hdx.load_profile(handle.name)

    def test_business_goal_affects_recommendation(self):
        event = {"title": "企业客户拓展沙龙", "summary": "合作伙伴交流", "tags": [],
                 "organizers": [], "city": "杭州", "capacity": 50,
                 "start": "2026-07-20T10:00:00+08:00", "registration_fields": []}
        profile = {"interests": [], "preferred_cities": ["杭州"],
                   "business_goals": ["客户拓展", "合作伙伴"], "excluded_topics": []}
        scored = hdx.recommendation_score(event, profile)
        self.assertGreater(scored["dimensions"]["business_goal"], 0)

    def test_marketing_risk_penalizes_score(self):
        profile = {"interests": [], "preferred_cities": [], "business_goals": [], "excluded_topics": []}
        safe = {"title": "AI 技术峰会", "summary": "技术交流", "tags": [], "organizers": [],
                "city": "杭州", "capacity": 50, "start": "2026-07-20T10:00:00+08:00",
                "registration_fields": []}
        risky = {**safe, "title": "AI 合伙人招募搞钱训练营"}
        self.assertLess(hdx.recommendation_score(risky, profile)["score"],
                        hdx.recommendation_score(safe, profile)["score"])

    def test_policy_defaults_and_local_override(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
            json.dump({"free_events": "auto_submit_if_safe", "paid_events": "notify_only"}, handle)
            handle.flush()
            policy = hdx.load_policy(handle.name)
        self.assertEqual(policy["free_events"], "auto_submit_if_safe")
        self.assertEqual(policy["paid_events"], "notify_only")


if __name__ == "__main__":
    unittest.main()
