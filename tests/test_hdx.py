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
from datetime import date
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "hdx.py"
sys.path.insert(0, str(MODULE_PATH.parent))
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

    def test_event_scoped_action_requires_event(self):
        parser = hdx.build_parser()
        with self.assertRaises(hdx.HdxError):
            hdx.cmd_action_plan(parser.parse_args(["action-plan", "signup"]))
        args = parser.parse_args(["action-plan", "account-change"])
        with contextlib.redirect_stdout(io.StringIO()):
            hdx.cmd_action_plan(args)

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

    def test_weekend_window_keeps_current_saturday_and_sunday(self):
        args = argparse.Namespace(date_from=None, date_to=None, time="weekend")
        saturday = date(2026, 7, 18)
        sunday = date(2026, 7, 19)
        self.assertEqual(hdx.requested_date_window(args, saturday), (saturday, sunday))
        self.assertEqual(hdx.requested_date_window(args, sunday), (sunday, sunday))

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

    def test_policy_rejects_unsafe_auto_for_paid_and_real_name(self):
        for key in ("paid_events", "real_name", "identity_document", "marketing_risk", "wechat_required"):
            with self.subTest(key=key):
                with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as handle:
                    json.dump({key: "auto_submit_if_safe"}, handle)
                    handle.flush()
                    with self.assertRaises(hdx.HdxError):
                        hdx.load_policy(handle.name)

    def test_strict_filter_rejects_online_paid_and_wrong_city(self):
        args = argparse.Namespace(city="杭州", mode="offline", price="free", verified=False,
                                  date_from=None, date_to=None, time="all")
        event = {"city": "上海", "province": "上海", "address": "线上活动", "mode": "online",
                 "pricing": "paid", "organizers": [], "start": "2026-07-20T10:00:00+08:00"}
        reasons = hdx.event_filter_reasons(event, args)
        self.assertIn("city", reasons)
        self.assertIn("mode", reasons)
        self.assertIn("price", reasons)

    def test_free_filter_excludes_mixed_price_events(self):
        args = argparse.Namespace(city="全国", mode="all", price="free", verified=False,
                                  date_from=None, date_to=None, time="all")
        event = {"city": "杭州", "province": "浙江", "address": "西湖区", "mode": "offline",
                 "pricing": "mixed", "organizers": [], "start": "2026-07-20T10:00:00+08:00"}
        self.assertIn("price", hdx.event_filter_reasons(event, args))

    def test_profile_format_type_and_time_affect_recommendation(self):
        event = {"title": "AI 产品峰会", "summary": "技术案例", "tags": [], "category": "峰会",
                 "organizers": [], "city": "杭州", "address": "西湖区", "mode": "offline",
                 "capacity": 100, "start": "2026-07-18T14:00:00+08:00",
                 "registration_fields": [], "is_free": True, "has_paid_ticket": False}
        base = {"interests": [], "preferred_cities": ["杭州"], "business_goals": [],
                "preferred_formats": ["online"], "preferred_event_types": ["展览"],
                "time_preferences": ["晚上"], "excluded_topics": [], "max_travel_minutes": None}
        matched = {**base, "preferred_formats": ["offline"], "preferred_event_types": ["峰会"],
                   "time_preferences": ["周末", "下午"]}
        self.assertGreater(hdx.recommendation_score(event, matched)["score"],
                           hdx.recommendation_score(event, base)["score"])

    def test_max_travel_is_reported_as_not_evaluated(self):
        event = {"title": "技术交流", "summary": "案例", "tags": [], "organizers": [],
                 "city": "杭州", "address": "", "mode": "offline", "capacity": 50,
                 "start": "2026-07-20T10:00:00+08:00", "registration_fields": [],
                 "is_free": True, "has_paid_ticket": False}
        profile = {"interests": [], "preferred_cities": [], "business_goals": [],
                   "preferred_formats": [], "preferred_event_types": [], "time_preferences": [],
                   "excluded_topics": [], "max_travel_minutes": 45}
        result = hdx.recommendation_score(event, profile)
        self.assertTrue(result["profile_coverage"]["not_evaluated"])

    def test_signup_field_coverage_never_returns_values(self):
        event = {"registration_fields": [
            {"key": "Name", "title": "姓名", "required": True},
            {"key": "Phone", "title": "手机号", "required": True},
            {"key": "Question", "title": "参会目标", "required": True},
        ]}
        result = hdx.signup_field_coverage(event, {"name": "测试用户", "mobile": "已提供"})
        self.assertEqual(result["covered_required_fields"], ["姓名", "手机号"])
        self.assertEqual(result["missing_required_fields"], ["参会目标"])
        self.assertNotIn("测试用户", json.dumps(result, ensure_ascii=False))

    def test_csv_formula_injection_is_escaped(self):
        rendered = hdx.render({"events": [{"id": "1", "title": "=HYPERLINK(\"x\")"}]}, "csv")
        row = next(csv.DictReader(io.StringIO(rendered)))
        self.assertTrue(row["title"].startswith("'="))

    def test_event_draft_validation(self):
        draft = dict(hdx.EVENT_DRAFT_TEMPLATE)
        result = hdx.validate_event_draft(draft)
        self.assertTrue(result["valid"])
        invalid = {**draft, "title": "短", "tickets": [{"title": "票", "price": -1, "quantity": 0}]}
        self.assertFalse(hdx.validate_event_draft(invalid)["valid"])

    def test_event_draft_flags_paid_and_identity(self):
        draft = dict(hdx.EVENT_DRAFT_TEMPLATE)
        draft["tickets"] = [{"title": "收费票", "price": 99, "quantity": 10}]
        draft["registration_fields"] = [{"title": "身份证号", "type": "text", "required": True}]
        result = hdx.validate_event_draft(draft)
        self.assertTrue(result["valid"])
        self.assertTrue(result["summary"]["paid"])
        self.assertEqual(result["summary"]["identity_fields"], ["身份证号"])

    def test_form_options_accept_strings_and_objects(self):
        self.assertEqual(hdx.form_option_value("选项A"), "选项A")
        self.assertEqual(hdx.form_option_value({"Title": "选项B"}), "选项B")

    def test_worker_and_candidate_caps(self):
        parser = hdx.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["recommend", "--workers", "5"])
            with self.assertRaises(SystemExit):
                parser.parse_args(["search", "--candidate-limit", "21"])

    def test_fetch_detects_frequency_verification_page(self):
        class FakeResponse:
            headers = mock.Mock()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return "<title>操作过于频繁</title>".encode("utf-8")
            def geturl(self): return "https://verify.huodongxing.com/gt3"
        FakeResponse.headers.get_content_charset.return_value = "utf-8"
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaises(hdx.HdxError):
                hdx.fetch("https://www.huodongxing.com/event/1234567890123")

    def test_browser_bridge_reports_temporary_tab_cleanup(self):
        bridge = hdx.CDPBridge("http://127.0.0.1:3456")
        bridge._request = mock.Mock(side_effect=[
            {"targetId": "test-target"},
            {"value": '{"ok":true}'},
            {},
        ])
        result = bridge.run_json("({ok:true})")
        self.assertTrue(result["browser_bridge"]["temporary_tab_closed"])

    def test_browser_bridge_rejects_frequency_verification_page(self):
        with self.assertRaises(hdx.BrowserBridgeError):
            hdx.page_snapshot(
                mock.Mock(run_json=mock.Mock(return_value={
                    "final_url": "https://verify.huodongxing.com/gt3",
                    "title": "操作过于频繁",
                })),
                "https://www.huodongxing.com/events",
            )

    def test_auth_status_rejects_incomplete_result(self):
        with self.assertRaises(hdx.BrowserBridgeError):
            hdx.auth_status(mock.Mock(run_json=mock.Mock(return_value={})))

    def test_doctor_requires_real_auth_for_logged_in_readiness(self):
        args = argparse.Namespace(proxy="http://127.0.0.1:3456", format="json", output=None)
        fake_bridge = mock.Mock()
        fake_bridge.status.return_value = {"connected": True, "browser_targets": 1}
        with mock.patch.object(hdx, "fetch", return_value="活动行"), \
             mock.patch.object(hdx, "CDPBridge", return_value=fake_bridge), \
             mock.patch.object(hdx, "auth_status", return_value={
                 "authenticated": True,
                 "organizer_access": True,
                 "browser_bridge": {"temporary_tab_closed": True},
             }), contextlib.redirect_stdout(io.StringIO()) as stdout:
            hdx.cmd_doctor(args)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["ready_public"])
        self.assertTrue(result["ready_logged_in_reads"])
        self.assertEqual(result["status"], "healthy")

    def test_rate_limit_errors_mark_partial_result(self):
        self.assertTrue(hdx.has_rate_limit_error([{"error": "活动行触发访问频控"}]))
        self.assertTrue(hdx.has_rate_limit_error([{"error": "访问频控熔断后未继续请求"}]))
        self.assertFalse(hdx.has_rate_limit_error([{"error": "普通解析失败"}]))


if __name__ == "__main__":
    unittest.main()
