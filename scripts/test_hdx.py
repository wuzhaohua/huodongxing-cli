#!/usr/bin/env python3
import argparse
import importlib.util
import json
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("hdx.py")
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


if __name__ == "__main__":
    unittest.main()
