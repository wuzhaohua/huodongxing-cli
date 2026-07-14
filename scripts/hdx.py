#!/usr/bin/env python3
"""Safe, CLI-first control plane for Huodongxing.

Public reads use the Python standard library. Logged-in pages are routed to the
user's browser. Mutating actions are deliberately two-phase: this CLI prepares
and routes; the final browser action requires explicit confirmation.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_URL = "https://www.huodongxing.com"
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
    "discover": {"domain": "public", "risk": "read", "path": "/events", "description": "发现和筛选活动"},
    "organizers": {"domain": "public", "risk": "read", "path": "/zhubanfang", "description": "查找主办方"},
    "rank": {"domain": "public", "risk": "read", "path": "/ranklist", "description": "活动人气榜"},
    "topics": {"domain": "public", "risk": "read", "path": "/topic", "description": "精选专题"},
    "venues": {"domain": "public", "risk": "read", "url": "https://bbx.huodongxing.com/venue", "description": "场地服务"},
    "me-tickets": {"domain": "attendee", "risk": "read", "path": "/user/regevents", "description": "我的票券"},
    "me-profile": {"domain": "attendee", "risk": "read", "path": "/user/index", "description": "个人主页"},
    "account-settings": {"domain": "account", "risk": "commit", "path": "/account/profile", "description": "账户设置"},
    "host-dashboard": {"domain": "organizer", "risk": "read", "path": "/console/home", "description": "主办方仪表盘"},
    "host-events": {"domain": "organizer", "risk": "read", "path": "/console/eventadmin", "description": "主办方活动列表"},
    "create-event": {"domain": "organizer", "risk": "prepare", "path": "/createv3", "description": "创建活动表单"},
    "host-page": {"domain": "organizer", "risk": "commit", "path": "/console/orgnizers", "description": "主办方主页设置"},
    "host-users": {"domain": "users", "risk": "read", "path": "/console/fans", "description": "全部用户"},
    "host-comments": {"domain": "users", "risk": "read", "path": "/console/commentlist?type=2", "description": "咨询与评价"},
    "host-invoices": {"domain": "finance", "risk": "read", "path": "/console/invoicemanagement", "description": "发票开具"},
    "host-contract": {"domain": "finance", "risk": "commit", "path": "/console/agent", "description": "票务代理合作签约"},
    "host-finance": {"domain": "finance", "risk": "commit", "path": "/console/finance", "description": "票款提领"},
    "host-balance": {"domain": "finance", "risk": "commit", "path": "/console/balance", "description": "充值与消费"},
    "host-subaccounts": {"domain": "account", "risk": "commit", "path": "/console/ChildAccount", "description": "子账号"},
    "host-accounts": {"domain": "account", "risk": "commit", "path": "/console/Account", "description": "账号管理"},
    "event-overview": {"domain": "event", "risk": "read", "path": "/myevent/home?id={event}", "description": "活动概览"},
    "event-edit": {"domain": "event", "risk": "commit", "path": "/myevent/edit?view=editbase&id={event}", "description": "编辑活动"},
    "event-invite": {"domain": "event", "risk": "commit", "path": "/myevent/inviteattendees?id={event}", "description": "邀请报名"},
    "event-promote": {"domain": "marketing", "risk": "commit", "path": "/myevent/promote?id={event}&tab=8", "description": "推广和刷新置顶"},
    "event-marketing": {"domain": "marketing", "risk": "commit", "path": "/myevent/marketingtools?id={event}&tab=6", "description": "渠道码、邀请码、白名单和优惠码"},
    "event-attendees": {"domain": "event", "risk": "read", "path": "/myevent/attendees?id={event}", "description": "名单管理"},
    "event-checkin": {"domain": "event", "risk": "commit", "path": "/myevent/signnote?id={event}&tab=1", "description": "现场验票"},
    "event-collaborators": {"domain": "event", "risk": "commit", "path": "/myevent/subaccount?id={event}", "description": "协作成员"},
    "event-settlement": {"domain": "finance", "risk": "read", "path": "/myevent/salesdetail?id={event}", "description": "票款结算"},
    "event-embed": {"domain": "event", "risk": "read", "path": "/myevent/webpageembedd?id={event}", "description": "嵌入官网"},
}


ACTIONS: Dict[str, Dict[str, Any]] = {
    "signup": {"risk": "commit", "route": None, "impact": "提交个人资料并创建报名/待审核记录", "verify": "成功页、订单或电子票"},
    "publish-event": {"risk": "commit", "route": "create-event", "impact": "公开或私密发布活动", "verify": "活动列表中的新状态和公开页"},
    "edit-event": {"risk": "commit", "route": "event-edit", "impact": "修改已存在活动及参与者看到的信息", "verify": "重新读取活动详情"},
    "invite": {"risk": "commit", "route": "event-invite", "impact": "向外部对象发送邀请", "verify": "发送记录和正确收件范围"},
    "send-message": {"risk": "commit", "route": "event-attendees", "impact": "向参与者发送短信或邮件并可能消耗余额", "verify": "发送记录、人数和费用"},
    "checkin": {"risk": "commit", "route": "event-checkin", "impact": "改变参与者签到状态", "verify": "名单中的签到时间/状态"},
    "cancel-registration": {"risk": "commit", "route": "me-tickets", "impact": "取消票券，可能影响退款", "verify": "票券状态"},
    "refund": {"risk": "commit", "route": "event-attendees", "impact": "退款或取消票券，涉及资金", "verify": "退款单和票券状态"},
    "delete-event": {"risk": "commit", "route": "host-events", "impact": "删除活动，可能不可恢复", "verify": "活动列表和公开页"},
    "change-privacy": {"risk": "commit", "route": "host-events", "impact": "改变活动公开可见性", "verify": "列表中的公开/私密状态"},
    "withdraw": {"risk": "commit", "route": "host-finance", "impact": "提领票款，涉及资金和收款账户", "verify": "提领记录"},
    "pay": {"risk": "commit", "route": "host-balance", "impact": "支付、充值或购买服务", "verify": "订单和余额"},
    "account-change": {"risk": "commit", "route": "account-settings", "impact": "修改账号、权限或安全设置", "verify": "账号设置回读"},
}


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
            return response.read().decode(charset, errors="replace")
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


def detail_data(event_id: str) -> Dict[str, Any]:
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
    return {
        "id": str(activity.get("Id", event_id)), "title": activity.get("Title"), "url": url,
        "start": ms_date(activity.get("Start")), "end": ms_date(activity.get("End")),
        "time_text": " ~ ".join(x for x in (activity.get("StartShort"), activity.get("EndShort")) if x),
        "province": setting.get("Province"), "city": activity.get("City"), "address": activity.get("Address"),
        "address_hidden_until_signup": bool(setting.get("ShowAddressAfterRegister")),
        "category": activity.get("Category"),
        "tags": [x.strip() for x in (activity.get("Tag") or "").split(",") if x.strip()],
        "summary": setting.get("Summary"), "is_free": bool(activity.get("IsFree", lowest == 0 and highest == 0)),
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
                     "min_order": t.get("MinOrder"), "max_order": t.get("MaxOrder"),
                     "requires_review": bool(t.get("NeedApply"))} for t in tickets],
        "registration_fields": [{"key": f.get("Key"), "title": f.get("Title"), "type": f.get("Type"),
                                 "required": bool(f.get("Required")), "multiple": bool(f.get("Multiple")),
                                 "options": [s.get("Title") or s.get("Value") for s in (f.get("Subitems") or [])]}
                                for f in forms if not f.get("IsHide")],
    }


def load_profile(path: Optional[str]) -> Dict[str, Any]:
    profile = {"interests": ["AI", "人工智能", "大模型", "Agent", "企业服务", "SaaS", "数字化转型", "创业"],
               "preferred_cities": ["杭州", "上海"], "business_goals": ["客户拓展", "技术学习", "人脉积累"]}
    if path:
        with open(path, encoding="utf-8") as handle:
            profile.update(json.load(handle))
    return profile


def recommendation_score(event: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(str(event.get(k) or "") for k in ("title", "summary", "tags"))
    hits = [x for x in profile.get("interests", []) if x.lower() in text.lower()]
    topic = min(40, 12 + len(hits) * 7) if hits else 5
    organizer = (event.get("organizers") or [{}])[0]
    followers = int(organizer.get("followers") or 0)
    org_score = 20 if followers >= 30000 else 16 if followers >= 10000 else 12 if followers >= 1000 else 7
    city, preferred = event.get("city") or "", profile.get("preferred_cities", [])
    location = 15 if preferred and city == preferred[0] else 10 if city in preferred else 6
    capacity = int(event.get("capacity") or 0)
    scale = 10 if capacity >= 500 else 8 if capacity >= 100 else 6 if capacity >= 50 else 4
    time_score = 8
    try:
        days = (datetime.fromisoformat(event["start"]).date() - datetime.now().astimezone().date()).days
        time_score = 15 if 0 <= days <= 5 else 10 if 6 <= days <= 9 else 8 if 10 <= days <= 14 else 5
    except (TypeError, ValueError, KeyError):
        pass
    total = max(0, min(100, topic + org_score + location + scale + time_score))
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
    return {"score": total, "level": level, "reasons": reasons,
            "dimensions": {"topic": topic, "organizer": org_score, "time": time_score,
                           "location": location, "scale": scale}}


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


def render(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    rows = data if isinstance(data, list) else [data]
    if fmt == "csv":
        flattened = []
        for row in rows:
            row = asdict(row) if hasattr(row, "__dataclass_fields__") else row
            flattened.append({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
        if not flattened:
            return ""
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(flattened[0].keys()))
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


def cmd_doctor(args: argparse.Namespace) -> None:
    checks = {"python": {"ok": sys.version_info >= (3, 9), "version": sys.version.split()[0]},
              "network": {"ok": False, "url": BASE_URL},
              "browser_command": {"ok": any(shutil.which(x) for x in ("open", "xdg-open"))}}
    try:
        checks["network"]["ok"] = "活动行" in fetch(BASE_URL, timeout=10)
    except HdxError as exc:
        checks["network"]["error"] = str(exc)
    checks["ready_public"] = checks["python"]["ok"] and checks["network"]["ok"]
    checks["ready_browser_routing"] = checks["browser_command"]["ok"]
    output(checks, args)


def cmd_routes(args: argparse.Namespace) -> None:
    rows = [{"name": name, **route, "url_template": route.get("url") or BASE_URL + route["path"]}
            for name, route in ROUTES.items() if not args.domain or route["domain"] == args.domain]
    output(rows, args)


def cmd_search(args: argparse.Namespace) -> None:
    url = build_search_url(args)
    events = [asdict(x) for x in parse_search(fetch(url))[:args.limit]]
    payload = {"source_url": url, "count": len(events), "events": events}
    output(payload, args)


def cmd_detail(args: argparse.Namespace) -> None:
    output(detail_data(normalize_event_id(args.event)), args)


def cmd_recommend(args: argparse.Namespace) -> None:
    url = build_search_url(args)
    summaries = parse_search(fetch(url))[:args.limit]
    profile, results = load_profile(args.profile), []
    for summary in summaries:
        try:
            event = detail_data(summary.id)
            event["recommendation"] = recommendation_score(event, profile)
            results.append(event)
        except HdxError as exc:
            results.append({**asdict(summary), "error": str(exc), "recommendation": {"score": 0, "level": "D", "reasons": ["详情获取失败"]}})
    results.sort(key=lambda x: x["recommendation"]["score"], reverse=True)
    output({"source_url": url, "count": len(results), "events": results}, args)


def cmd_signup_plan(args: argparse.Namespace) -> None:
    event = detail_data(normalize_event_id(args.event))
    blockers = []
    if event["wechat_only"]:
        blockers.append("仅支持微信流程")
    if event["requires_real_name"]:
        blockers.append("需要实名信息")
    if event["requires_review"]:
        blockers.append("提交后需主办方审核")
    if not event["is_free"]:
        blockers.append("收费活动，付款前必须单独确认")
    output({"event": {k: event[k] for k in ("id", "title", "url", "start", "address", "is_free", "price")},
            "tickets": event["tickets"], "required_fields": [f for f in event["registration_fields"] if f["required"]],
            "all_fields": event["registration_fields"], "blockers": blockers,
            "risk": "commit", "requires_confirmation": True,
            "next_action": "确认票种、字段、费用和审核状态；获得明确授权后再在浏览器提交。"}, args)


def cmd_open_route(args: argparse.Namespace) -> None:
    url = route_url(args.route, args.event)
    opened = bool(webbrowser.open(url))
    print(json.dumps({"opened": opened, "adapter": "system", "url": url,
                      "note": "页面已打开但未提交任何操作"}, ensure_ascii=False))


def cmd_action_plan(args: argparse.Namespace) -> None:
    action = ACTIONS[args.action]
    event = normalize_event_id(args.event) if args.event else None
    route = action.get("route")
    if route and "{event}" in (ROUTES[route].get("path") or "") and not event:
        raise HdxError("action %s 需要 --event" % args.action)
    payload = {"action": args.action, "event": event, "risk": action["risk"], "impact": action["impact"],
               "requires_confirmation": True, "route": route,
               "url": route_url(route, event) if route else ("%s/event/%s" % (BASE_URL, event) if event else None),
               "preflight": ["重新读取目标对象", "核对作用范围和对象", "核对费用与个人数据", "说明回滚或不可逆性"],
               "confirmation_prompt": "请确认执行 %s%s" % (args.action, "，活动 %s" % event if event else ""),
               "verification": action["verify"]}
    output(payload, args)


def add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
    parser.add_argument("-o", "--output")


def add_search_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--city", default="杭州")
    parser.add_argument("-q", "--keyword")
    parser.add_argument("--tag")
    parser.add_argument("--time", choices=tuple(TIME_CODES), default="all")
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    parser.add_argument("--price", choices=tuple(RANGE_CODES), default="all")
    parser.add_argument("--mode", choices=tuple(EVENT_TYPES), default="all")
    parser.add_argument("--verified", action="store_true")
    parser.add_argument("--order", choices=tuple(ORDER_CODES), default="relevance")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--limit", type=int, default=10)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hdx", description="活动行全平台 CLI 控制面")
    parser.add_argument("--version", action="version", version="hdx 2.0.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor"); add_output_options(p); p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("routes"); p.add_argument("--domain"); add_output_options(p); p.set_defaults(func=cmd_routes)
    p = sub.add_parser("search"); add_search_options(p); add_output_options(p); p.set_defaults(func=cmd_search)
    p = sub.add_parser("detail"); p.add_argument("event"); add_output_options(p); p.set_defaults(func=cmd_detail)
    p = sub.add_parser("recommend"); add_search_options(p); p.add_argument("--profile"); add_output_options(p); p.set_defaults(func=cmd_recommend)
    p = sub.add_parser("signup-plan"); p.add_argument("event"); add_output_options(p); p.set_defaults(func=cmd_signup_plan)
    p = sub.add_parser("open-route"); p.add_argument("route", choices=tuple(ROUTES)); p.add_argument("--event");
    p.set_defaults(func=cmd_open_route)
    p = sub.add_parser("action-plan"); p.add_argument("action", choices=tuple(ACTIONS)); p.add_argument("--event");
    add_output_options(p); p.set_defaults(func=cmd_action_plan)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except (HdxError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": "用户中断"}, ensure_ascii=False), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
