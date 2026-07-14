#!/usr/bin/env python3
"""Safe, CLI-first control plane for Huodongxing.

Public reads use the Python standard library. Logged-in pages are routed to the
user's browser. Mutating actions are deliberately two-phase: this CLI prepares
and routes; the final browser action requires explicit confirmation.
"""

from __future__ import annotations

import argparse
import copy
import concurrent.futures
import csv
import html
import io
import json
import os
import re
import shutil
import stat
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from hdx_browser import (
    BrowserBridgeError,
    CDPBridge,
    auth_status,
    my_tickets,
    organizer_events,
    page_snapshot,
)


BASE_URL = "https://www.huodongxing.com"
VERSION = "3.0.0"
DEFAULT_CONFIG_DIR = Path(os.environ.get("HDX_CONFIG_DIR", "~/.config/hdx")).expanduser()
DEFAULT_CACHE_DIR = Path(os.environ.get("HDX_CACHE_DIR", "~/.cache/hdx")).expanduser()
DEFAULT_CACHE_TTL = int(os.environ.get("HDX_CACHE_TTL", "1800"))
DEFAULT_TIMEOUT = 25
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
TIME_CODES = {"all": "", "week": "t1", "weekend": "t4", "month": "t5"}
ORDER_CODES = {"relevance": "o", "newest": "n", "popular": "v", "participants": "r"}
EVENT_TYPES = {"all": "", "offline": "1", "online": "2"}
RANGE_CODES = {"all": "", "free": "1", "paid": "2"}


class HdxError(RuntimeError):
    pass


@dataclass
class EventSummary:
    id: str
    title: str
    time_text: str
    location: str
    organizer: str
    followers: Optional[int]
    url: str
    image: Optional[str] = None


ROUTES: Dict[str, Dict[str, str]] = {
    # Public discovery.
    "discover": {"domain": "public", "risk": "read", "path": "/events", "description": "发现和筛选活动"},
    "organizers": {"domain": "public", "risk": "read", "path": "/zhubanfang", "description": "查找主办方"},
    "rank": {"domain": "public", "risk": "read", "path": "/ranklist", "description": "活动人气榜"},
    "topics": {"domain": "public", "risk": "read", "path": "/topic", "description": "精选专题"},
    "venues": {"domain": "public", "risk": "read", "url": "https://bbx.huodongxing.com/venue", "description": "场地服务"},
    "toolbox": {"domain": "public", "risk": "read", "url": "https://bbx.huodongxing.com/bbx", "description": "活动百宝箱"},
    # Attendee and account.
    "me-tickets": {"domain": "attendee", "risk": "sensitive-read", "path": "/user/regevents", "description": "我的票券和订单状态"},
    "me-favorites": {"domain": "attendee", "risk": "sensitive-read", "path": "/user/userfollows", "description": "收藏和关注"},
    "me-profile": {"domain": "attendee", "risk": "sensitive-read", "path": "/user/index", "description": "个人主页"},
    "account-settings": {"domain": "account", "risk": "commit", "path": "/account/profile", "description": "账户资料设置"},
    "account-contact": {"domain": "account", "risk": "commit", "path": "/account/rebindcontact?type=1", "description": "联系方式与安全验证"},
    # Organizer global console.
    "host-dashboard": {"domain": "organizer", "risk": "sensitive-read", "path": "/console/home", "description": "主办方仪表盘"},
    "host-events": {"domain": "organizer", "risk": "sensitive-read", "path": "/console/eventadmin", "description": "主办方活动列表"},
    "create-event": {"domain": "organizer", "risk": "prepare", "path": "/createv3", "description": "新版创建活动表单"},
    "create-online-event": {"domain": "organizer", "risk": "prepare", "path": "/createonlineevent", "description": "创建线上活动"},
    "host-page": {"domain": "organizer", "risk": "commit", "path": "/console/orgnizers", "description": "主办方主页设置"},
    "host-authentication": {"domain": "account", "risk": "commit", "path": "/console/authenticationinfo", "description": "主办方认证"},
    "host-ads": {"domain": "marketing", "risk": "paid-commit", "path": "/console/adtask", "description": "广告投放"},
    "host-sms": {"domain": "marketing", "risk": "paid-commit", "path": "/console/pushsms", "description": "营销短信"},
    "host-groups": {"domain": "marketing", "risk": "commit", "path": "/console/activitygroup", "description": "多活动关联"},
    "host-email": {"domain": "marketing", "risk": "commit", "path": "/console/pushemail", "description": "邮件和素材工具"},
    "host-users": {"domain": "users", "risk": "sensitive-read", "path": "/console/fans", "description": "全部用户"},
    "host-comments": {"domain": "users", "risk": "sensitive-read", "path": "/console/commentlist?type=2", "description": "咨询"},
    "host-reviews": {"domain": "users", "risk": "sensitive-read", "path": "/console/commentlist?type=1", "description": "评价"},
    "host-invoices": {"domain": "finance", "risk": "sensitive-read", "path": "/console/invoicemanagement", "description": "发票开具"},
    "host-invoice-requests": {"domain": "finance", "risk": "commit", "path": "/console/invoicedocuments", "description": "申请发票"},
    "host-contract": {"domain": "finance", "risk": "commit", "path": "/console/agent", "description": "票务代理合作签约"},
    "host-finance": {"domain": "finance", "risk": "paid-commit", "path": "/console/finance", "description": "票款提领"},
    "host-balance": {"domain": "finance", "risk": "paid-commit", "path": "/console/balance", "description": "充值与消费"},
    "host-subaccounts": {"domain": "account", "risk": "commit", "path": "/console/ChildAccount", "description": "子账号"},
    "host-accounts": {"domain": "account", "risk": "commit", "path": "/console/Account", "description": "账号管理"},
    "host-notices": {"domain": "organizer", "risk": "read", "path": "/console/notices", "description": "平台通知"},
    # Per-event operations.
    "event-overview": {"domain": "event", "risk": "sensitive-read", "path": "/myevent/home?id={event}", "description": "活动概览"},
    "event-edit": {"domain": "event", "risk": "commit", "path": "/myevent/edit?view=editbase&id={event}", "description": "编辑活动"},
    "event-invite": {"domain": "event", "risk": "commit", "path": "/myevent/inviteattendees?id={event}", "description": "邀请报名"},
    "event-notify": {"domain": "marketing", "risk": "paid-commit", "path": "/myevent/promote?id={event}&tab=9", "description": "一键通知"},
    "event-refresh": {"domain": "marketing", "risk": "commit", "path": "/myevent/promote?id={event}&tab=7", "description": "一键刷新"},
    "event-top": {"domain": "marketing", "risk": "paid-commit", "path": "/myevent/promote?id={event}&tab=8", "description": "活动置顶"},
    "event-poster": {"domain": "marketing", "risk": "prepare", "path": "/myevent/promote?id={event}&tab=2", "description": "邀请函和海报"},
    "event-distribution": {"domain": "marketing", "risk": "commit", "path": "/myevent/promote?id={event}&tab=11", "description": "分销管理"},
    "event-channel": {"domain": "marketing", "risk": "commit", "path": "/myevent/marketingtools?id={event}&tab=6", "description": "渠道码"},
    "event-invite-code": {"domain": "marketing", "risk": "commit", "path": "/myevent/marketingtools?id={event}&tab=34", "description": "邀请码"},
    "event-whitelist": {"domain": "marketing", "risk": "commit", "path": "/myevent/marketingtools?id={event}&tab=36", "description": "报名白名单"},
    "event-coupon": {"domain": "marketing", "risk": "paid-commit", "path": "/myevent/marketingtools?id={event}&tab=5", "description": "优惠码"},
    "event-priority-review": {"domain": "marketing", "risk": "commit", "path": "/myevent/promote?id={event}&tab=13", "description": "优先审核"},
    "event-attendees": {"domain": "event", "risk": "sensitive-read", "path": "/myevent/attendees?id={event}", "description": "名单管理"},
    "event-notification-records": {"domain": "event", "risk": "sensitive-read", "path": "/myevent/notification_record?aid={event}", "description": "发送记录"},
    "event-checkin": {"domain": "event", "risk": "commit", "path": "/myevent/signnote?id={event}&tab=1", "description": "现场验票"},
    "event-collaborators": {"domain": "event", "risk": "commit", "path": "/myevent/subaccount?id={event}", "description": "协作成员"},
    "event-settlement": {"domain": "finance", "risk": "sensitive-read", "path": "/myevent/salesdetail?id={event}", "description": "票款结算"},
    "event-embed": {"domain": "event", "risk": "read", "path": "/myevent/webpageembedd?id={event}", "description": "嵌入官网"},
    "event-copy": {"domain": "event", "risk": "prepare", "path": "/myevent/republish?id={event}", "description": "复制活动"},
}


ACTIONS: Dict[str, Dict[str, Any]] = {
    "signup": {"risk": "commit", "route": None, "impact": "提交个人资料并创建报名或待审核记录", "verify": "成功页、订单、电子票或待审核状态"},
    "cancel-registration": {"risk": "commit", "route": "me-tickets", "impact": "取消自己的票券，可能触发退款", "verify": "票券和退款状态"},
    "request-refund": {"risk": "paid-commit", "route": "me-tickets", "impact": "提交退款申请", "verify": "退票申请和资金状态"},
    "publish-event": {"risk": "commit", "route": "create-event", "impact": "创建并发布公开或私密活动", "verify": "主办方活动列表状态和公开页"},
    "edit-event": {"risk": "commit", "route": "event-edit", "impact": "修改参与者可见的活动信息", "verify": "后台字段和公开详情回读"},
    "copy-event": {"risk": "commit", "route": "event-copy", "impact": "基于既有活动创建副本", "verify": "新活动草稿或列表记录"},
    "delete-event": {"risk": "destructive-commit", "route": "host-events", "impact": "删除活动，可能不可恢复", "verify": "活动列表和公开页"},
    "change-privacy": {"risk": "commit", "route": "host-events", "impact": "改变活动公开可见性", "verify": "列表公开状态和匿名访问结果"},
    "invite": {"risk": "external-commit", "route": "event-invite", "impact": "向外部对象发送邀请", "verify": "收件范围和发送记录"},
    "send-message": {"risk": "paid-commit", "route": "event-attendees", "impact": "向参与者发送短信或邮件并可能扣费", "verify": "发送记录、人数和费用"},
    "add-attendee": {"risk": "sensitive-commit", "route": "event-attendees", "impact": "新增或导入含个人资料的名单", "verify": "名单新增记录"},
    "approve-attendee": {"risk": "commit", "route": "event-attendees", "impact": "批准报名申请", "verify": "名单审核状态"},
    "reject-attendee": {"risk": "external-commit", "route": "event-attendees", "impact": "拒绝报名并可能通知参加者", "verify": "名单状态和通知记录"},
    "cancel-attendee": {"risk": "destructive-commit", "route": "event-attendees", "impact": "取消他人报名资格且可能不可恢复", "verify": "票券状态"},
    "refund": {"risk": "paid-commit", "route": "event-attendees", "impact": "退款或取消票券，涉及资金", "verify": "退款单、票券和结算"},
    "checkin": {"risk": "commit", "route": "event-checkin", "impact": "改变参加者签到状态", "verify": "签到状态和时间"},
    "tag-attendee": {"risk": "sensitive-commit", "route": "event-attendees", "impact": "写入参加者标签或备注", "verify": "标签或备注回读"},
    "block-attendee": {"risk": "destructive-commit", "route": "event-attendees", "impact": "阻止用户报名主办方后续活动", "verify": "黑名单状态"},
    "refresh-event": {"risk": "commit", "route": "event-refresh", "impact": "消耗刷新权益并更新活动排序", "verify": "刷新时间或权益记录"},
    "top-event": {"risk": "paid-commit", "route": "event-top", "impact": "购买或消耗活动置顶权益", "verify": "置顶状态和订单"},
    "set-channel": {"risk": "commit", "route": "event-channel", "impact": "新建或修改渠道码", "verify": "渠道列表"},
    "set-invite-code": {"risk": "commit", "route": "event-invite-code", "impact": "改变报名准入条件", "verify": "邀请码设置"},
    "set-whitelist": {"risk": "commit", "route": "event-whitelist", "impact": "上传或修改报名白名单", "verify": "白名单范围"},
    "set-coupon": {"risk": "paid-commit", "route": "event-coupon", "impact": "改变付费票优惠规则", "verify": "优惠码状态和适用票种"},
    "manage-collaborator": {"risk": "security-commit", "route": "event-collaborators", "impact": "授予或撤销活动管理权限", "verify": "协作成员和权限"},
    "withdraw": {"risk": "paid-commit", "route": "host-finance", "impact": "提领票款，涉及资金和收款账户", "verify": "提领记录"},
    "pay": {"risk": "paid-commit", "route": "host-balance", "impact": "支付、充值或购买服务", "verify": "订单、余额和权益"},
    "account-change": {"risk": "security-commit", "route": "account-settings", "impact": "修改账号、联系方式、权限或安全设置", "verify": "账号设置回读"},
}

EVENT_SCOPED_ACTIONS = frozenset(ACTIONS) - {"publish-event", "withdraw", "pay", "account-change"}


class EventListParser(HTMLParser):
    def __init__(self) -> None:
        HTMLParser.__init__(self, convert_charrefs=True)
        self.events: List[EventSummary] = []
        self.depth = 0
        self.capture: Optional[str] = None
        self.buf: List[str] = []
        self.current: Optional[Dict[str, Any]] = None

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        data = dict(attrs)
        classes = set((data.get("class") or "").split())
        if tag == "div" and "search-tab-content-item-mesh" in classes:
            self.depth, self.current = 1, {"followers": None}
            return
        if not self.depth:
            return
        if tag == "div":
            self.depth += 1
        if tag == "a" and "item-title" in classes:
            href = data.get("href") or ""
            match = re.search(r"/event/(\d+)", href)
            if self.current is not None and match:
                self.current["id"] = match.group(1)
                self.current["url"] = urllib.parse.urljoin(BASE_URL, html.unescape(href))
            self._start("title")
        elif tag == "p" and "user-name" in classes:
            self._start("organizer")
        elif tag == "span" and "item-dress-pp" in classes:
            self._start("location")
        elif tag == "span" and "follows" in classes:
            self._start("followers_text")
        elif tag == "div" and "item-dress" in classes and self.current is not None:
            self.current["in_dress"] = True
        elif tag == "p" and self.current and self.current.get("in_dress"):
            self._start("time_text")
        elif tag == "img" and self.current is not None and data.get("class") == "item-logo":
            self.current["image"] = data.get("src")

    def handle_endtag(self, tag: str) -> None:
        if self.capture and tag in ("a", "p", "span"):
            if self.current is not None:
                self.current[self.capture] = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            self.capture, self.buf = None, []
        if not self.depth:
            return
        if tag == "div":
            self.depth -= 1
            if self.current and self.current.get("in_dress") and self.depth:
                self.current.pop("in_dress", None)
            if self.depth == 0:
                self._finish()

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buf.append(data)

    def _start(self, name: str) -> None:
        self.capture, self.buf = name, []

    def _finish(self) -> None:
        c = self.current or {}
        followers = re.search(r"(\d+)", c.get("followers_text", ""))
        if c.get("id") and c.get("title"):
            self.events.append(EventSummary(
                id=c["id"], title=c["title"], time_text=c.get("time_text", ""),
                location=c.get("location", ""), organizer=c.get("organizer", ""),
                followers=int(followers.group(1)) if followers else None,
                url=c["url"], image=c.get("image"),
            ))
        self.current = None


def fetch(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            source = response.read().decode(charset, errors="replace")
            effective_url = response.geturl()
            if "verify.huodongxing.com" in effective_url or "操作过于频繁" in source or "访问过于频繁" in source:
                raise HdxError("活动行触发访问频控或验证码；已停止请求，请稍后再试，不要循环重试")
            return source
    except urllib.error.HTTPError as exc:
        raise HdxError("活动行返回 HTTP %s: %s" % (exc.code, url))
    except urllib.error.URLError as exc:
        raise HdxError("无法连接活动行: %s" % exc.reason)


def extract_json_assignment(source: str, variable: str, default: Any = None) -> Any:
    match = re.search(r"\b(?:var|let|const)\s+%s\s*=\s*" % re.escape(variable), source)
    if not match:
        return default
    try:
        value, _ = json.JSONDecoder().raw_decode(source[match.end():].lstrip())
        return value
    except json.JSONDecodeError:
        return default


def normalize_event_id(value: str) -> str:
    match = re.search(r"(?:/event/)?(\d{10,})", value)
    if not match:
        raise HdxError("请提供活动 ID 或活动行 event URL")
    return match.group(1)


def ms_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"Date\((\d+)\)", value)
    if not match:
        return value
    return datetime.fromtimestamp(int(match.group(1)) / 1000).astimezone().isoformat(timespec="minutes")


def classify_pricing(prices: List[float]) -> str:
    if not prices or max(prices) <= 0:
        return "free"
    if min(prices) <= 0 < max(prices):
        return "mixed"
    return "paid"


def detect_event_mode(city: Any, address: Any) -> str:
    text = "%s %s" % (city or "", address or "")
    online_markers = ("线上活动", "在线活动", "网络活动", "online", "直播间")
    return "online" if any(marker.lower() in text.lower() for marker in online_markers) else "offline"


def form_option_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("Title") or value.get("Value")
    return value


def ticket_remaining(ticket: Dict[str, Any]) -> Optional[int]:
    if ticket.get("Quantity") is None:
        return None
    try:
        return max(0, int(ticket.get("Quantity") or 0) - int(ticket.get("SoldNumber") or 0))
    except (TypeError, ValueError):
        return None


def build_search_url(args: argparse.Namespace) -> str:
    params: Dict[str, str] = {"orderby": ORDER_CODES[args.order]}
    if args.city and args.city not in ("全部", "全国"):
        params["city"] = args.city
    if args.keyword:
        params["qs"] = args.keyword
    if args.tag:
        params["tag"] = args.tag
    if TIME_CODES[args.time]:
        params["d"] = TIME_CODES[args.time]
    if args.date_from or args.date_to:
        if not (args.date_from and args.date_to):
            raise HdxError("自定义日期必须同时提供 --from 和 --to")
        if args.date_from > args.date_to:
            raise HdxError("--from 不能晚于 --to")
        params.update({"d": "ts", "date": args.date_from, "dateTo": args.date_to})
    if RANGE_CODES[args.price]:
        params["range"] = RANGE_CODES[args.price]
    if EVENT_TYPES[args.mode]:
        params["eventType"] = EVENT_TYPES[args.mode]
    if args.verified:
        params["auth"] = "1"
    if args.page > 1:
        params["page"] = str(args.page)
    return "%s/events?%s" % (BASE_URL, urllib.parse.urlencode(params))


def parse_search(source: str) -> List[EventSummary]:
    parser = EventListParser()
    parser.feed(source)
    seen, result = set(), []
    for event in parser.events:
        if event.id not in seen:
            seen.add(event.id)
            result.append(event)
    return result


def detail_cache_path(event_id: str) -> Path:
    return DEFAULT_CACHE_DIR / "details" / (event_id + ".json")


def read_detail_cache(event_id: str) -> Optional[Dict[str, Any]]:
    path = detail_cache_path(event_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            return None
        if time.time() - float(payload.get("cached_at") or 0) > DEFAULT_CACHE_TTL:
            return None
        result = payload["data"]
        result["cache"] = {"hit": True, "age_seconds": int(time.time() - float(payload["cached_at"]))}
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def write_detail_cache(event_id: str, data: Dict[str, Any]) -> None:
    path = detail_cache_path(event_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"cached_at": time.time(), "data": {key: value for key, value in data.items() if key != "cache"}}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    except OSError:
        # Cache failure must not make a public read fail.
        return


def detail_data(event_id: str, use_cache: bool = True) -> Dict[str, Any]:
    if use_cache:
        cached = read_detail_cache(event_id)
        if cached:
            return cached
    url = "%s/event/%s" % (BASE_URL, event_id)
    source = fetch(url)
    activity = extract_json_assignment(source, "ativityJson") or extract_json_assignment(source, "act")
    if not activity:
        raise HdxError("详情页没有可解析的结构化活动数据: %s" % url)
    organizers = extract_json_assignment(source, "OrganizerList", []) or []
    forms = extract_json_assignment(source, "formItemsJson", []) or []
    tickets = extract_json_assignment(source, "eventTicketsJson", []) or []
    setting = activity.get("Setting") or {}
    prices = [float(t.get("Price") or 0) for t in tickets]
    lowest, highest = (min(prices), max(prices)) if prices else (0.0, 0.0)
    pricing = classify_pricing(prices)
    city, address = activity.get("City"), activity.get("Address")
    result = {
        "id": str(activity.get("Id", event_id)), "title": activity.get("Title"), "url": url,
        "start": ms_date(activity.get("Start")), "end": ms_date(activity.get("End")),
        "time_text": " ~ ".join(x for x in (activity.get("StartShort"), activity.get("EndShort")) if x),
        "province": setting.get("Province"), "city": city, "address": address,
        "mode": detect_event_mode(city, address),
        "address_hidden_until_signup": bool(setting.get("ShowAddressAfterRegister")),
        "category": activity.get("Category"),
        "tags": [x.strip() for x in (activity.get("Tag") or "").split(",") if x.strip()],
        "summary": setting.get("Summary"), "is_free": pricing == "free",
        "has_free_ticket": lowest == 0, "has_paid_ticket": highest > 0, "pricing": pricing,
        "price": {"lowest": lowest, "highest": highest}, "capacity": activity.get("MaxInstance"),
        "registered": activity.get("InstanceNumber"), "views": activity.get("VisitNumber"),
        "follows": activity.get("Follows"), "status": activity.get("Status"),
        "requires_participant_details": bool(setting.get("RequireParticipant")),
        "requires_real_name": bool(setting.get("RealnameRegistration")),
        "requires_review": any(bool(t.get("NeedApply")) for t in tickets) or bool(setting.get("ApplyReject")),
        "wechat_only": bool(setting.get("IsOnlyWeixin")), "refund_type": setting.get("RefundType"),
        "organizers": [{"id": str(o.get("Id", "")), "name": o.get("Name"), "followers": o.get("Follows"),
                        "events": o.get("Events"), "verified": bool(o.get("IsIdentity")), "vip_rank": o.get("VipRank")}
                       for o in organizers],
        "tickets": [{"sn": t.get("SN"), "title": t.get("Title"), "price": t.get("Price"),
                     "status": t.get("StatusStr"), "quantity": t.get("Quantity"), "sold": t.get("SoldNumber"),
                     "remaining": ticket_remaining(t),
                     "min_order": t.get("MinOrder"), "max_order": t.get("MaxOrder"),
                     "requires_review": bool(t.get("NeedApply"))} for t in tickets],
        "registration_fields": [{"key": f.get("Key"), "title": f.get("Title"), "type": f.get("Type"),
                                 "required": bool(f.get("Required")), "multiple": bool(f.get("Multiple")),
                                 "options": [form_option_value(s) for s in (f.get("Subitems") or [])]}
                                for f in forms if not f.get("IsHide")],
    }
    result["cache"] = {"hit": False, "age_seconds": 0}
    write_detail_cache(event_id, result)
    return result


def resolve_config_path(path: Optional[str], env_name: str, default_name: str) -> Path:
    selected = path or os.environ.get(env_name)
    return Path(selected).expanduser() if selected else DEFAULT_CONFIG_DIR / default_name


def load_json_config(path: Optional[str], env_name: str, default_name: str) -> Dict[str, Any]:
    candidate = resolve_config_path(path, env_name, default_name)
    if not candidate.exists():
        return {}
    with candidate.open(encoding="utf-8") as handle:
        supplied = json.load(handle)
    if not isinstance(supplied, dict):
        raise HdxError("配置必须是 JSON 对象: %s" % candidate)
    return supplied


def load_profile(path: Optional[str]) -> Dict[str, Any]:
    profile = {
        "interests": [], "preferred_cities": [], "business_goals": [],
        "preferred_formats": [], "preferred_event_types": [], "excluded_topics": [],
        "time_preferences": [], "max_travel_minutes": None,
    }
    supplied = load_json_config(path, "HDX_PROFILE", "profile.json")
    for key in profile:
        value = supplied.get(key, profile[key])
        if key == "max_travel_minutes":
            if value is not None and (not isinstance(value, int) or value < 0):
                raise HdxError("profile.max_travel_minutes 必须是非负整数或 null")
        elif not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise HdxError("profile.%s 必须是字符串数组" % key)
        profile[key] = value
    return profile


def load_policy(path: Optional[str]) -> Dict[str, Any]:
    policy = {
        "free_events": "ask", "paid_events": "ask", "requires_review": "ask",
        "real_name": "ask", "wechat_required": "ask", "identity_document": "deny",
        "marketing_risk": "skip", "verify_after_submit": True,
    }
    supplied = load_json_config(path, "HDX_POLICY", "policy.json")
    policy.update({k: v for k, v in supplied.items() if k in policy})
    allowed_by_key = {
        "free_events": {"ask", "notify_only", "auto_submit_if_safe", "skip", "deny"},
        "requires_review": {"ask", "notify_only", "auto_submit_if_safe", "skip", "deny"},
        "paid_events": {"ask", "notify_only", "skip", "deny"},
        "real_name": {"ask", "notify_only", "skip", "deny"},
        "wechat_required": {"ask", "notify_only", "skip", "deny"},
        "identity_document": {"ask", "notify_only", "skip", "deny"},
        "marketing_risk": {"ask", "notify_only", "skip", "deny"},
    }
    for key, allowed in allowed_by_key.items():
        if policy[key] not in allowed:
            raise HdxError("policy.%s 的值无效" % key)
    if not isinstance(policy["verify_after_submit"], bool):
        raise HdxError("policy.verify_after_submit 必须是布尔值")
    return policy


def load_signup_data(path: Optional[str]) -> Dict[str, Any]:
    supplied = load_json_config(path, "HDX_SIGNUP", "signup.json")
    fields = supplied.get("fields", supplied)
    if not isinstance(fields, dict):
        raise HdxError("signup.json 必须是 JSON 对象，或包含 fields 对象")
    return fields


def config_file_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    mode = stat.S_IMODE(path.stat().st_mode)
    return {
        "exists": True,
        "path": str(path),
        "mode": oct(mode),
        "private": mode & 0o077 == 0,
    }


def normalize_field_name(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "")).lower()


FIELD_ALIASES = {
    "姓名": ("姓名", "真实姓名", "name", "realname"),
    "手机": ("手机", "手机号", "电话", "phone", "mobile"),
    "邮箱": ("邮箱", "电子邮箱", "email"),
    "微信": ("微信", "微信号", "wechat", "weixin"),
    "公司": ("公司", "单位", "公司单位", "company", "organization"),
    "职位": ("职位", "职务", "title", "jobtitle"),
    "城市": ("城市", "所在城市", "city"),
}


def signup_field_coverage(event: Dict[str, Any], signup: Dict[str, Any]) -> Dict[str, Any]:
    available = {normalize_field_name(key): value for key, value in signup.items()}
    covered, missing = [], []
    for field in [item for item in event.get("registration_fields", []) if item.get("required")]:
        title, key = str(field.get("title") or ""), str(field.get("key") or "")
        candidates = {normalize_field_name(title), normalize_field_name(key)}
        for label, aliases in FIELD_ALIASES.items():
            if label in title:
                candidates.update(normalize_field_name(alias) for alias in aliases)
        present = any(name in available and available[name] not in (None, "", []) for name in candidates if name)
        (covered if present else missing).append(title or key or "未命名字段")
    return {"covered_required_fields": covered, "missing_required_fields": missing}


MARKETING_TERMS = ("合伙人招募", "招商", "加盟", "赚钱", "搞钱", "流量变现", "课程", "训练营", "token中转", "算力中转")
IDENTITY_TERMS = ("身份证", "证件号", "护照")
GOAL_ALIASES = {
    "客户拓展": ("客户", "获客", "销售", "商机", "商务", "增长"),
    "合作伙伴": ("合作伙伴", "伙伴", "生态", "渠道", "合作"),
    "技术学习": ("技术", "实战", "案例", "开发", "架构"),
    "ai学习": ("ai", "人工智能", "大模型", "智能体", "agent"),
    "品牌曝光": ("品牌", "媒体", "公关", "传播", "曝光"),
    "出海": ("出海", "跨境", "海外", "全球化", "国际市场"),
    "招聘": ("招聘", "人才", "人力资源", "雇主品牌"),
}


def event_risks(event: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
    text = " ".join(str(event.get(k) or "") for k in ("title", "summary", "tags")).lower()
    risks = []
    if any(term.lower() in text for term in MARKETING_TERMS):
        risks.append("marketing_risk")
    excluded = [x for x in profile.get("excluded_topics", []) if x.lower() in text]
    if excluded:
        risks.append("excluded_topic")
    fields = " ".join(str(x.get("title") or "") for x in event.get("registration_fields", []))
    if any(term in fields for term in IDENTITY_TERMS):
        risks.append("identity_document")
    if event.get("requires_real_name"):
        risks.append("real_name")
    if event.get("requires_review"):
        risks.append("requires_review")
    if event.get("wechat_only") or "微信" in fields:
        risks.append("wechat_required")
    if event.get("has_paid_ticket") or not event.get("is_free"):
        risks.append("paid")
    return list(dict.fromkeys(risks))


def recommendation_score(event: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(str(event.get(k) or "") for k in ("title", "summary", "tags", "category"))
    lowered = text.lower()
    hits = [x for x in profile.get("interests", []) if x.lower() in lowered]
    goal_hits = []
    for goal in profile.get("business_goals", []):
        aliases = GOAL_ALIASES.get(goal.lower(), GOAL_ALIASES.get(goal, (goal,)))
        if goal.lower() in lowered or any(term.lower() in lowered for term in aliases):
            goal_hits.append(goal)
    topic = 8 if not profile.get("interests") else min(30, 8 + len(hits) * 8)
    goal_score = min(15, len(goal_hits) * 6)
    organizer = (event.get("organizers") or [{}])[0]
    followers = int(organizer.get("followers") or 0)
    org_score = 15 if followers >= 30000 else 12 if followers >= 10000 else 9 if followers >= 1000 else 6
    city, preferred = event.get("city") or "", profile.get("preferred_cities", [])
    location = 15 if preferred and city == preferred[0] else 10 if city in preferred else 6
    capacity = int(event.get("capacity") or 0)
    scale = 5 if capacity >= 500 else 4 if capacity >= 100 else 3 if capacity >= 50 else 2
    time_score = 6
    start_dt = None
    try:
        start_dt = datetime.fromisoformat(event["start"])
        days = (start_dt.date() - datetime.now().astimezone().date()).days
        time_score = 10 if 0 <= days <= 7 else 8 if 8 <= days <= 14 else 6 if days > 14 else 2
    except (TypeError, ValueError, KeyError):
        pass
    time_hits = []
    if start_dt:
        hour, weekend = start_dt.hour, start_dt.weekday() >= 5
        labels = {
            "周末": weekend, "工作日": not weekend, "上午": hour < 12,
            "下午": 12 <= hour < 18, "晚上": hour >= 18,
        }
        time_hits = [value for value in profile.get("time_preferences", []) if labels.get(value, False)]
        if profile.get("time_preferences"):
            time_score = min(10, time_score + (2 if time_hits else -2))

    preferred_formats = [value.lower() for value in profile.get("preferred_formats", [])]
    mode_aliases = {"online": ("online", "线上"), "offline": ("offline", "线下")}
    mode = event.get("mode") or detect_event_mode(event.get("city"), event.get("address"))
    format_hit = any(alias in preferred_formats for alias in mode_aliases.get(mode, (mode,)))
    type_hits = [value for value in profile.get("preferred_event_types", []) if value.lower() in lowered]
    preference_score = 5
    if preferred_formats:
        preference_score += 3 if format_hit else -2
    if profile.get("preferred_event_types"):
        preference_score += 2 if type_hits else -1
    preference_score = max(0, min(10, preference_score))

    risks = event_risks(event, profile)
    penalty = 20 if "marketing_risk" in risks else 0
    penalty += 50 if "excluded_topic" in risks else 0
    total = max(0, min(100, topic + goal_score + org_score + location + scale + time_score + preference_score - penalty))
    level = "S" if total >= 80 else "A" if total >= 60 else "B" if total >= 40 else "C" if total >= 20 else "D"
    reasons = (["主题匹配：" + "、".join(hits[:4])] if hits else [])
    if followers:
        reasons.append("主办方约 %s 粉丝" % followers)
    if city in preferred:
        reasons.append("地点符合偏好：%s" % city)
    if event.get("is_free"):
        reasons.append("免费活动")
    if event.get("requires_review"):
        reasons.append("报名需要审核")
    if goal_hits:
        reasons.append("业务目标匹配：" + "、".join(goal_hits[:3]))
    if format_hit:
        reasons.append("活动形式符合偏好：%s" % mode)
    if type_hits:
        reasons.append("活动类型匹配：" + "、".join(type_hits[:3]))
    if time_hits:
        reasons.append("时间偏好匹配：" + "、".join(time_hits[:3]))
    if penalty:
        reasons.append("风险扣分：" + "、".join(risks))
    not_evaluated = []
    if profile.get("max_travel_minutes") is not None:
        not_evaluated.append("max_travel_minutes: 缺少出发地和实时路程数据，未计分")
    return {"score": total, "level": level, "reasons": reasons,
            "dimensions": {"topic": topic, "organizer": org_score, "time": time_score,
                           "location": location, "scale": scale, "business_goal": goal_score,
                           "format_and_type": preference_score, "risk_penalty": penalty}, "risks": risks,
            "profile_coverage": {"used": [name for name, value in {
                "interests": hits, "business_goals": goal_hits, "preferred_cities": city in preferred,
                "preferred_formats": format_hit, "preferred_event_types": type_hits,
                "time_preferences": time_hits,
            }.items() if value], "not_evaluated": not_evaluated},
            "confidence": "high" if event.get("summary") and event.get("organizers") else "medium"}


def requested_date_window(args: argparse.Namespace, today: Optional[Any] = None) -> Optional[tuple[Any, Any]]:
    today = today or datetime.now().astimezone().date()
    if args.date_from and args.date_to:
        return datetime.strptime(args.date_from, "%Y-%m-%d").date(), datetime.strptime(args.date_to, "%Y-%m-%d").date()
    if args.time == "week":
        return today, today + timedelta(days=6 - today.weekday())
    if args.time == "weekend":
        if today.weekday() == 5:
            return today, today + timedelta(days=1)
        if today.weekday() == 6:
            return today, today
        days_to_saturday = (5 - today.weekday()) % 7
        start = today + timedelta(days=days_to_saturday)
        return start, start + timedelta(days=1)
    if args.time == "month":
        return today, today + timedelta(days=30)
    return None


def event_filter_reasons(event: Dict[str, Any], args: argparse.Namespace) -> List[str]:
    reasons = []
    requested_city = (args.city or "").strip()
    location_text = " ".join(str(event.get(key) or "") for key in ("province", "city", "address"))
    if requested_city not in ("", "全部", "全国") and requested_city not in location_text:
        reasons.append("city")
    if args.mode != "all" and event.get("mode") != args.mode:
        reasons.append("mode")
    pricing = event.get("pricing") or classify_pricing([
        float(item.get("price") or 0) for item in event.get("tickets", [])
    ])
    if args.price == "free" and pricing != "free":
        reasons.append("price")
    if args.price == "paid" and pricing not in ("paid", "mixed"):
        reasons.append("price")
    if args.verified and not any(item.get("verified") for item in event.get("organizers", [])):
        reasons.append("verified")
    window = requested_date_window(args)
    if window:
        try:
            start = datetime.fromisoformat(event["start"]).date()
            end = datetime.fromisoformat(event.get("end") or event["start"]).date()
            if start > window[1] or end < window[0]:
                reasons.append("time")
        except (KeyError, TypeError, ValueError):
            reasons.append("time_unverified")
    return reasons


def summary_prefilter_reasons(summary: EventSummary, args: argparse.Namespace) -> List[str]:
    reasons = []
    requested_city = (args.city or "").strip()
    if requested_city not in ("", "全部", "全国") and requested_city not in summary.location:
        reasons.append("city_summary")
    if args.mode != "all" and detect_event_mode(summary.location, summary.location) != args.mode:
        reasons.append("mode_summary")
    return reasons


def strict_filter_requested(args: argparse.Namespace) -> bool:
    return bool(
        getattr(args, "strict", True)
        and ((args.city and args.city not in ("全部", "全国")) or args.mode != "all"
             or args.price != "all" or args.time != "all" or args.date_from or args.verified)
    )


def collect_candidates(args: argparse.Namespace, wanted: int) -> tuple[List[str], List[EventSummary]]:
    urls, summaries, seen = [], [], set()
    max_pages = max(1, min(getattr(args, "max_pages", 3), 5))
    for page in range(args.page, args.page + max_pages):
        local_args = copy.copy(args)
        local_args.page = page
        url = build_search_url(local_args)
        urls.append(url)
        batch = parse_search(fetch(url))
        if not batch:
            break
        for summary in batch:
            if summary.id not in seen:
                seen.add(summary.id)
                summaries.append(summary)
        if len(summaries) >= wanted:
            break
    return urls, summaries[:wanted]


def enrich_summaries(summaries: List[EventSummary], workers: int) -> List[tuple[EventSummary, Optional[Dict[str, Any]], Optional[str]]]:
    stopped = threading.Event()

    def enrich(summary: EventSummary) -> tuple[EventSummary, Optional[Dict[str, Any]], Optional[str]]:
        if stopped.is_set():
            return summary, None, "访问频控熔断后未继续请求"
        try:
            return summary, detail_data(summary.id), None
        except (HdxError, AttributeError, TypeError, ValueError) as exc:
            if "访问频控" in str(exc) or "验证码" in str(exc):
                stopped.set()
            return summary, None, str(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(summaries) or 1)) as pool:
        return list(pool.map(enrich, summaries))


def search_record(summary: EventSummary, event: Dict[str, Any]) -> Dict[str, Any]:
    record = asdict(summary)
    record.update({key: event.get(key) for key in (
        "start", "end", "city", "address", "mode", "pricing", "is_free",
        "has_free_ticket", "has_paid_ticket", "price",
    )})
    record["detail_verified"] = True
    return record


def has_rate_limit_error(errors: List[Dict[str, Any]]) -> bool:
    return any(
        any(marker in str(item.get("error") or "") for marker in ("访问频控", "验证码", "频控熔断"))
        for item in errors
    )


def route_url(name: str, event: Optional[str] = None) -> str:
    if name not in ROUTES:
        raise HdxError("未知 route: %s" % name)
    route = ROUTES[name]
    value = route.get("url") or (BASE_URL + route["path"])
    if "{event}" in value:
        if not event:
            raise HdxError("route %s 需要 --event" % name)
        value = value.format(event=normalize_event_id(event))
    return value


def csv_safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def render(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if fmt == "csv" and isinstance(data, dict) and isinstance(data.get("events"), list):
        rows = [{"source_url": data.get("source_url"), **row} for row in data["events"]]
    else:
        rows = data if isinstance(data, list) else [data]
    if fmt == "csv":
        flattened = []
        for row in rows:
            row = asdict(row) if hasattr(row, "__dataclass_fields__") else row
            flattened.append({
                k: csv_safe_cell(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                for k, v in row.items()
            })
        if not flattened:
            return ""
        out = io.StringIO()
        fieldnames = list(dict.fromkeys(key for row in flattened for key in row.keys()))
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened)
        return out.getvalue()
    lines = []
    for row in rows:
        row = asdict(row) if hasattr(row, "__dataclass_fields__") else row
        title = row.get("title") or row.get("name") or row.get("id") or "结果"
        lines.append("### %s" % title)
        for key, value in row.items():
            if key == "title" or value in (None, "", [], {}):
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append("- %s: %s" % (key, value))
        lines.append("")
    return "\n".join(lines).rstrip()


def output(data: Any, args: argparse.Namespace) -> None:
    text = render(data, getattr(args, "format", "json"))
    path = getattr(args, "output", None)
    if path:
        Path(path).write_text(text + ("\n" if text else ""), encoding="utf-8")
        print(path)
    else:
        print(text)


EVENT_DRAFT_TEMPLATE: Dict[str, Any] = {
    "schema_version": 1,
    "title": "不少于 5 个字的活动标题",
    "mode": "offline",
    "start": "2026-08-01T09:00:00+08:00",
    "end": "2026-08-01T17:00:00+08:00",
    "city": "杭州",
    "address": "活动详细地址",
    "online_url": None,
    "summary": "最多 150 字的活动亮点",
    "content_markdown": "活动详情、议程、嘉宾和注意事项",
    "poster_path": None,
    "visibility": "public",
    "show_address_after_signup": False,
    "capacity": 100,
    "tickets": [{"title": "免费票", "price": 0, "quantity": 100, "requires_review": False}],
    "registration_fields": [
        {"title": "姓名", "type": "text", "required": True},
        {"title": "手机", "type": "phone", "required": True},
    ],
    "language": "system",
    "custom_privacy": None,
    "support_contact": {"phone": None, "email": None},
}


def load_event_draft(path: str) -> Dict[str, Any]:
    candidate = Path(path).expanduser()
    with candidate.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise HdxError("活动草稿必须是 JSON 对象")
    return value


def validate_event_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    errors, warnings = [], []
    title = str(draft.get("title") or "").strip()
    if len(title) < 5:
        errors.append("title 至少 5 个字")
    mode = draft.get("mode")
    if mode not in ("offline", "online", "hybrid"):
        errors.append("mode 必须是 offline、online 或 hybrid")
    parsed_dates = {}
    for key in ("start", "end"):
        try:
            parsed_dates[key] = datetime.fromisoformat(str(draft.get(key) or ""))
        except ValueError:
            errors.append("%s 必须是 ISO 8601 时间" % key)
    if all(key in parsed_dates for key in ("start", "end")) and parsed_dates["start"] >= parsed_dates["end"]:
        errors.append("start 必须早于 end")
    if mode in ("offline", "hybrid"):
        if not draft.get("city"):
            errors.append("线下或混合活动必须提供 city")
        if not draft.get("address"):
            errors.append("线下或混合活动必须提供 address")
    if mode in ("online", "hybrid") and not draft.get("online_url"):
        warnings.append("线上入口尚未提供；创建前需在平台补充或确认直播方案")
    summary = str(draft.get("summary") or "")
    if len(summary) > 150:
        errors.append("summary 不能超过 150 字")
    if not draft.get("content_markdown"):
        warnings.append("content_markdown 为空，活动详情不完整")
    if draft.get("visibility", "public") not in ("public", "private"):
        errors.append("visibility 必须是 public 或 private")
    capacity = draft.get("capacity")
    if not isinstance(capacity, int) or capacity < 1:
        errors.append("capacity 必须是正整数")
    tickets = draft.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        errors.append("tickets 至少包含一个票种")
        tickets = []
    paid = False
    for index, ticket in enumerate(tickets):
        if not isinstance(ticket, dict):
            errors.append("tickets[%d] 必须是对象" % index)
            continue
        if not str(ticket.get("title") or "").strip():
            errors.append("tickets[%d].title 不能为空" % index)
        price = ticket.get("price")
        quantity = ticket.get("quantity")
        if not isinstance(price, (int, float)) or price < 0:
            errors.append("tickets[%d].price 必须是非负数" % index)
        elif price > 0:
            paid = True
        if not isinstance(quantity, int) or quantity < 1:
            errors.append("tickets[%d].quantity 必须是正整数" % index)
    field_types = {"text", "textarea", "number", "select", "radio", "checkbox", "date", "email", "phone", "file"}
    identity_fields = []
    fields = draft.get("registration_fields", [])
    if not isinstance(fields, list):
        errors.append("registration_fields 必须是数组")
        fields = []
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append("registration_fields[%d] 必须是对象" % index)
            continue
        field_title = str(field.get("title") or "")
        if not field_title:
            errors.append("registration_fields[%d].title 不能为空" % index)
        if field.get("type") not in field_types:
            errors.append("registration_fields[%d].type 不受支持" % index)
        if any(term in field_title for term in IDENTITY_TERMS):
            identity_fields.append(field_title)
    poster = draft.get("poster_path")
    if poster and not Path(str(poster)).expanduser().is_file():
        errors.append("poster_path 文件不存在")
    if paid:
        warnings.append("包含付费票；发布前必须确认收款、退款、发票和服务费规则")
    if identity_fields:
        warnings.append("包含证件字段：%s；必须确认必要性、授权和保存范围" % "、".join(identity_fields))
    if draft.get("custom_privacy"):
        warnings.append("包含自定义隐私协议；发布前需核对文本和主体")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "title": title,
            "mode": mode,
            "visibility": draft.get("visibility", "public"),
            "ticket_count": len(tickets),
            "paid": paid,
            "registration_field_count": len(fields),
            "identity_fields": identity_fields,
        },
    }


def cmd_doctor(args: argparse.Namespace) -> None:
    checks = {"python": {"ok": sys.version_info >= (3, 9), "version": sys.version.split()[0]},
              "network": {"ok": False, "url": BASE_URL},
              "browser_command": {"ok": os.name == "nt" or any(shutil.which(x) for x in ("open", "xdg-open"))}}
    try:
        checks["network"]["ok"] = "活动行" in fetch(BASE_URL, timeout=10)
    except HdxError as exc:
        checks["network"]["error"] = str(exc)
    try:
        bridge = CDPBridge(args.proxy)
        checks["cdp"] = bridge.status()
        checks["cdp"]["ok"] = True
        try:
            current_auth = auth_status(bridge)
            checks["cdp"]["auth"] = {
                "ok": True,
                "authenticated": bool(current_auth.get("authenticated")),
                "organizer_access": bool(current_auth.get("organizer_access")),
                "temporary_tab_closed": bool(
                    current_auth.get("browser_bridge", {}).get("temporary_tab_closed")
                ),
            }
        except BrowserBridgeError as exc:
            checks["cdp"]["auth"] = {"ok": False, "error": str(exc)}
    except BrowserBridgeError as exc:
        checks["cdp"] = {"ok": False, "proxy": args.proxy, "error": str(exc)}
    checks["ready_public"] = checks["python"]["ok"] and checks["network"]["ok"]
    checks["ready_browser_routing"] = checks["browser_command"]["ok"]
    checks["ready_logged_in_reads"] = bool(
        checks["cdp"].get("ok")
        and checks["cdp"].get("auth", {}).get("authenticated")
    )
    checks["status"] = (
        "healthy" if checks["ready_public"] and checks["ready_logged_in_reads"]
        else "degraded" if checks["ready_public"] or checks["ready_logged_in_reads"]
        else "unavailable"
    )
    checks["local_config"] = {"directory": str(DEFAULT_CONFIG_DIR)}
    for key in ("profile", "policy", "signup"):
        checks["local_config"][key] = config_file_status(DEFAULT_CONFIG_DIR / (key + ".json"))
    output(checks, args)


def cmd_routes(args: argparse.Namespace) -> None:
    rows = [{"name": name, **route, "url_template": route.get("url") or BASE_URL + route["path"]}
            for name, route in ROUTES.items() if not args.domain or route["domain"] == args.domain]
    output(rows, args)


def cmd_search(args: argparse.Namespace) -> Optional[int]:
    strict = strict_filter_requested(args)
    if not strict:
        url = build_search_url(args)
        events = [asdict(x) for x in parse_search(fetch(url))[:args.limit]]
        payload = {"source_url": url, "source_urls": [url], "filter_mode": "platform-only",
                   "count": len(events), "events": events}
        output(payload, args)
        return None
    wanted = max(args.limit, min(args.candidate_limit, 50))
    urls, summaries = collect_candidates(args, wanted)
    candidate_count = len(summaries)
    events, dropped, errors, prefiltered = [], {}, [], []
    for summary in summaries:
        reasons = summary_prefilter_reasons(summary, args)
        if reasons:
            for reason in reasons:
                dropped[reason] = dropped.get(reason, 0) + 1
        else:
            prefiltered.append(summary)
    for summary, event, error in enrich_summaries(prefiltered, args.workers):
        if error or event is None:
            errors.append({"id": summary.id, "reason": "detail_unverified", "error": error})
            continue
        reasons = event_filter_reasons(event, args)
        if reasons:
            for reason in reasons:
                dropped[reason] = dropped.get(reason, 0) + 1
            continue
        events.append(search_record(summary, event))
        if len(events) >= args.limit:
            break
    rate_limited = has_rate_limit_error(errors)
    payload = {"source_url": urls[0] if urls else build_search_url(args), "source_urls": urls,
               "filter_mode": "detail-verified", "candidate_count": candidate_count,
               "complete": not rate_limited, "rate_limited": rate_limited,
               "count": len(events), "dropped": dropped, "errors": errors, "events": events}
    output(payload, args)
    return 2 if rate_limited else None


def cmd_detail(args: argparse.Namespace) -> None:
    output(detail_data(normalize_event_id(args.event)), args)


def cmd_recommend(args: argparse.Namespace) -> Optional[int]:
    wanted = max(args.limit, min(args.candidate_limit, 50))
    urls, summaries = collect_candidates(args, wanted)
    candidate_count = len(summaries)
    profile, results, dropped, errors, prefiltered = load_profile(args.profile), [], {}, [], []
    for summary in summaries:
        reasons = summary_prefilter_reasons(summary, args) if getattr(args, "strict", True) else []
        if reasons:
            for reason in reasons:
                dropped[reason] = dropped.get(reason, 0) + 1
        else:
            prefiltered.append(summary)
    for summary, event, error in enrich_summaries(prefiltered, args.workers):
        if error or event is None:
            errors.append({"id": summary.id, "reason": "detail_unverified", "error": error})
            continue
        reasons = event_filter_reasons(event, args) if getattr(args, "strict", True) else []
        if reasons:
            for reason in reasons:
                dropped[reason] = dropped.get(reason, 0) + 1
            continue
        event["recommendation"] = recommendation_score(event, profile)
        results.append(event)
    results.sort(key=lambda x: x["recommendation"]["score"], reverse=True)
    results = results[:args.limit]
    rate_limited = has_rate_limit_error(errors)
    output({"source_url": urls[0] if urls else build_search_url(args), "source_urls": urls,
            "filter_mode": "detail-verified" if getattr(args, "strict", True) else "platform-only",
            "candidate_count": candidate_count, "complete": not rate_limited, "rate_limited": rate_limited,
            "count": len(results), "dropped": dropped,
            "errors": errors, "events": results}, args)
    return 2 if rate_limited else None


def cmd_signup_plan(args: argparse.Namespace) -> None:
    event = detail_data(normalize_event_id(args.event))
    profile, policy = load_profile(args.profile), load_policy(args.policy)
    signup = load_signup_data(args.signup_data)
    risks = event_risks(event, profile)
    coverage = signup_field_coverage(event, signup)
    blockers = []
    if event["wechat_only"]:
        blockers.append("仅支持微信流程")
    if event["requires_real_name"]:
        blockers.append("需要实名信息")
    if event["requires_review"]:
        blockers.append("提交后需主办方审核")
    if not event["is_free"]:
        blockers.append("收费活动，付款前必须单独确认")
    decision, policy_source = "ask", "default"
    if "identity_document" in risks or "excluded_topic" in risks:
        decision, policy_source = "deny", "hard_safety"
    elif "marketing_risk" in risks:
        decision, policy_source = policy["marketing_risk"], "marketing_risk"
    elif "paid" in risks:
        decision, policy_source = policy["paid_events"], "paid_events"
    elif "real_name" in risks:
        decision, policy_source = policy["real_name"], "real_name"
    elif "wechat_required" in risks:
        decision, policy_source = policy["wechat_required"], "wechat_required"
    elif "requires_review" in risks:
        decision, policy_source = policy["requires_review"], "requires_review"
    else:
        decision, policy_source = policy["free_events"], "free_events"
    hard_auto_blocks = [risk for risk in risks if risk in {
        "paid", "real_name", "identity_document", "marketing_risk", "wechat_required", "excluded_topic"
    }]
    if coverage["missing_required_fields"]:
        blockers.append("本地 signup.json 缺少必填字段值：%s" % "、".join(coverage["missing_required_fields"]))
    auto_eligible = bool(
        decision == "auto_submit_if_safe" and not hard_auto_blocks
        and not coverage["missing_required_fields"] and event.get("pricing") == "free"
    )
    effective_decision = decision if auto_eligible or decision != "auto_submit_if_safe" else "ask"
    output({"event": {k: event[k] for k in ("id", "title", "url", "start", "address", "is_free", "price")},
            "tickets": event["tickets"], "required_fields": [f for f in event["registration_fields"] if f["required"]],
            "all_fields": event["registration_fields"], "blockers": blockers, "risk_flags": risks,
            "field_coverage": coverage, "signup_values_exposed": False,
            "policy_source": policy_source, "configured_policy_decision": decision,
            "policy_decision": effective_decision, "hard_auto_blocks": hard_auto_blocks,
            "auto_submit_eligible": auto_eligible, "risk": "commit",
            "requires_confirmation": not auto_eligible,
            "verify_after_submit": policy["verify_after_submit"],
            "next_action": "按本地 policy 决策；浏览器提交前刷新字段和票价，提交后验证成功页、订单、电子票或待审核状态。"}, args)


def cmd_auth_status(args: argparse.Namespace) -> None:
    output(auth_status(CDPBridge(args.proxy)), args)


def cmd_me_tickets(args: argparse.Namespace) -> None:
    output(my_tickets(CDPBridge(args.proxy)), args)


def cmd_host_events(args: argparse.Namespace) -> None:
    output(organizer_events(CDPBridge(args.proxy)), args)


def cmd_browser_read(args: argparse.Namespace) -> None:
    route = ROUTES[args.route]
    url = route_url(args.route, args.event)
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != "www.huodongxing.com":
        raise HdxError("browser-read 仅支持 www.huodongxing.com 登录态路由；外部域名请使用 open-route")
    sensitive = route["risk"] in ("sensitive-read", "paid-commit", "security-commit") or route["domain"] in (
        "account", "finance", "users"
    )
    include_forms = args.route in {
        "create-event", "create-online-event", "event-edit", "account-settings", "host-page",
        "event-channel", "event-invite-code", "event-whitelist", "event-coupon",
    }
    result = page_snapshot(CDPBridge(args.proxy), url, sensitive=sensitive, include_forms=include_forms)
    result.update({"route": args.route, "domain": route["domain"], "risk": route["risk"],
                   "note": "仅返回脱敏页面结构和可用动作，不包含表单值、Cookie、名单行或财务值。"})
    output(result, args)


def cmd_event_draft(args: argparse.Namespace) -> None:
    if args.draft_action == "template":
        output(EVENT_DRAFT_TEMPLATE, args)
        return
    if not args.file:
        raise HdxError("event-draft %s 需要 JSON 文件" % args.draft_action)
    draft = load_event_draft(args.file)
    result = validate_event_draft(draft)
    if args.draft_action == "validate":
        output(result, args)
        if not result["valid"]:
            raise HdxError("活动草稿校验失败")
        return
    result["route"] = "create-event"
    result["url"] = route_url("create-event")
    result["risk"] = "commit"
    result["requires_confirmation"] = True
    result["browser_sections"] = [
        "基础信息与海报", "时间和线下/线上地点", "活动亮点与详情", "嘉宾模块",
        "票种和名额", "报名字段与限制", "展示/语言/隐私", "售后联系方式与协议",
    ]
    result["verification"] = ["主办方活动列表出现新记录", "活动状态符合预期", "公开页字段逐项回读"]
    result["note"] = "plan 只生成可执行填表计划；创建活动按钮仍需对本次草稿明确确认。"
    output(result, args)


def cmd_open_route(args: argparse.Namespace) -> None:
    url = route_url(args.route, args.event)
    opened = False if args.print_only else bool(webbrowser.open(url))
    note = "仅返回路由，未打开页面" if args.print_only else "页面已打开但未提交任何操作"
    print(json.dumps({"opened": opened, "adapter": "none" if args.print_only else "system", "url": url,
                      "note": note}, ensure_ascii=False))


def cmd_action_plan(args: argparse.Namespace) -> None:
    action = ACTIONS[args.action]
    if args.action in EVENT_SCOPED_ACTIONS and not args.event:
        raise HdxError("action %s 需要 --event" % args.action)
    event = normalize_event_id(args.event) if args.event else None
    route = action.get("route")
    if route and "{event}" in (ROUTES[route].get("path") or "") and not event:
        raise HdxError("action %s 需要 --event" % args.action)
    token = "CONFIRM:%s:%s" % (args.action, event or "account")
    scope = "event" if args.action in EVENT_SCOPED_ACTIONS else "new-event" if args.action == "publish-event" else "account"
    payload = {"action": args.action, "scope": scope, "event": event, "risk": action["risk"], "impact": action["impact"],
               "requires_confirmation": True, "route": route,
               "url": route_url(route, event) if route else ("%s/event/%s" % (BASE_URL, event) if event else None),
               "preflight": ["重新读取目标对象", "核对作用范围和对象", "核对费用与个人数据", "说明回滚或不可逆性"],
               "confirmation_prompt": "请确认执行 %s%s" % (args.action, "，活动 %s" % event if event else ""),
               "confirmation_token": token, "cli_commits_directly": False,
               "verification": action["verify"]}
    output(payload, args)


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
    parser.add_argument("-o", "--output")


def add_search_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--city", default="全国")
    parser.add_argument("-q", "--keyword")
    parser.add_argument("--tag")
    parser.add_argument("--time", choices=tuple(TIME_CODES), default="all")
    parser.add_argument("--from", dest="date_from", type=iso_date)
    parser.add_argument("--to", dest="date_to", type=iso_date)
    parser.add_argument("--price", choices=tuple(RANGE_CODES), default="all")
    parser.add_argument("--mode", choices=tuple(EVENT_TYPES), default="all")
    parser.add_argument("--verified", action="store_true")
    parser.add_argument("--order", choices=tuple(ORDER_CODES), default="relevance")
    parser.add_argument("--page", type=positive_int, default=1)
    parser.add_argument("--limit", type=positive_int, default=10)
    parser.add_argument("--candidate-limit", type=candidate_count, default=12,
                        help="详情验证前最多读取的候选活动数，最大 20")
    parser.add_argument("--max-pages", type=page_count, default=3,
                        help="候选不足时最多读取的搜索页数，最大 5")
    parser.add_argument("--workers", type=worker_count, default=3,
                        help="详情并发数，最大 4")
    strict = parser.add_mutually_exclusive_group()
    strict.add_argument("--strict", dest="strict", action="store_true", default=True,
                        help="按详情页二次验证城市、时间、形式和价格（默认）")
    strict.add_argument("--no-strict", dest="strict", action="store_false",
                        help="只信任平台搜索参数，速度快但推广卡片可能越过筛选")


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("必须是大于等于 1 的整数")
    return number


def bounded_positive_int(value: str, maximum: int, label: str) -> int:
    number = positive_int(value)
    if number > maximum:
        raise argparse.ArgumentTypeError("%s 最大为 %d" % (label, maximum))
    return number


def worker_count(value: str) -> int:
    return bounded_positive_int(value, 4, "workers")


def candidate_count(value: str) -> int:
    return bounded_positive_int(value, 20, "candidate-limit")


def page_count(value: str) -> int:
    return bounded_positive_int(value, 5, "max-pages")


def iso_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError("日期必须使用 YYYY-MM-DD 格式")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hdx", description="活动行全平台 CLI 控制面")
    parser.add_argument("--version", action="version", version="hdx %s" % VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor"); p.add_argument("--proxy", default=os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456")); add_output_options(p); p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("routes"); p.add_argument("--domain"); add_output_options(p); p.set_defaults(func=cmd_routes)
    p = sub.add_parser("search"); add_search_options(p); add_output_options(p); p.set_defaults(func=cmd_search)
    p = sub.add_parser("detail"); p.add_argument("event"); add_output_options(p); p.set_defaults(func=cmd_detail)
    p = sub.add_parser("recommend"); add_search_options(p); p.add_argument("--profile"); add_output_options(p); p.set_defaults(func=cmd_recommend)
    p = sub.add_parser("signup-plan"); p.add_argument("event"); p.add_argument("--profile"); p.add_argument("--policy"); p.add_argument("--signup-data"); add_output_options(p); p.set_defaults(func=cmd_signup_plan)
    p = sub.add_parser("auth-status"); p.add_argument("--proxy", default=os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456")); add_output_options(p); p.set_defaults(func=cmd_auth_status)
    p = sub.add_parser("me-tickets"); p.add_argument("--proxy", default=os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456")); add_output_options(p); p.set_defaults(func=cmd_me_tickets)
    p = sub.add_parser("host-events"); p.add_argument("--proxy", default=os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456")); add_output_options(p); p.set_defaults(func=cmd_host_events)
    p = sub.add_parser("browser-read"); p.add_argument("route", choices=tuple(ROUTES)); p.add_argument("--event"); p.add_argument("--proxy", default=os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456")); add_output_options(p); p.set_defaults(func=cmd_browser_read)
    p = sub.add_parser("event-draft"); p.add_argument("draft_action", choices=("template", "validate", "plan")); p.add_argument("file", nargs="?"); add_output_options(p); p.set_defaults(func=cmd_event_draft)
    p = sub.add_parser("open-route"); p.add_argument("route", choices=tuple(ROUTES)); p.add_argument("--event");
    p.add_argument("--print-only", action="store_true", help="只输出 URL，不调用系统浏览器")
    p.set_defaults(func=cmd_open_route)
    p = sub.add_parser("action-plan"); p.add_argument("action", choices=tuple(ACTIONS)); p.add_argument("--event");
    add_output_options(p); p.set_defaults(func=cmd_action_plan)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        result = args.func(args)
        return int(result or 0)
    except (HdxError, BrowserBridgeError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "用户中断"}, ensure_ascii=False), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
