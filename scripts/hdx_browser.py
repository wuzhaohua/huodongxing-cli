#!/usr/bin/env python3
"""Privacy-preserving CDP bridge for logged-in Huodongxing reads.

The bridge talks to the local web-access CDP proxy. It never exports browser
cookies, local storage, authorization headers, passwords, or verification
codes. Every command opens its own background tab and closes it afterwards.
"""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Optional


BASE_URL = "https://www.huodongxing.com"
DEFAULT_PROXY = os.environ.get("HDX_CDP_PROXY", "http://127.0.0.1:3456").rstrip("/")


class BrowserBridgeError(RuntimeError):
    """Raised when the local CDP proxy or logged-in browser is unavailable."""


def _raise_if_verification(result: Dict[str, Any]) -> None:
    location = " ".join(str(result.get(key) or "") for key in (
        "source_url", "final_url", "base_url", "title", "error",
    ))
    if result.get("rate_limited") or "verify.huodongxing.com" in location or "操作过于频繁" in location:
        raise BrowserBridgeError("活动行触发访问频控或验证码；已停止登录态读取，请稍后再试，不要循环重试")


class CDPBridge:
    def __init__(self, proxy_url: str = DEFAULT_PROXY, timeout: int = 35) -> None:
        self.proxy_url = proxy_url.rstrip("/")
        self.timeout = timeout
        self.last_tab_closed: Optional[bool] = None

    def _request(self, path: str, data: Optional[str] = None) -> Any:
        method = "POST" if data is not None else "GET"
        request = urllib.request.Request(
            self.proxy_url + path,
            data=data.encode("utf-8") if data is not None else None,
            method=method,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BrowserBridgeError(
                "无法连接本机 CDP 代理 %s；请先按 web-access Skill 运行依赖检查。原始错误：%s"
                % (self.proxy_url, exc)
            )
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise BrowserBridgeError("CDP 代理返回了无效 JSON: %s" % exc)

    def status(self) -> Dict[str, Any]:
        targets = self._request("/targets")
        if not isinstance(targets, list):
            raise BrowserBridgeError("CDP 代理 targets 响应格式异常")
        return {
            "proxy": self.proxy_url,
            "connected": True,
            "browser_targets": len([item for item in targets if item.get("type") == "page"]),
            "huodongxing_targets": len(
                [item for item in targets if "huodongxing.com" in str(item.get("url") or "")]
            ),
        }

    def new_tab(self, url: str = BASE_URL) -> str:
        result = self._request("/new", url)
        target = result.get("targetId") if isinstance(result, dict) else None
        if not target:
            raise BrowserBridgeError("CDP 代理未返回新标签页 targetId")
        return str(target)

    def close_tab(self, target: str) -> bool:
        quoted = urllib.parse.quote(target, safe="")
        try:
            self._request("/close?target=" + quoted)
            return True
        except BrowserBridgeError:
            # Cleanup failure must not hide the command's useful result.
            return False

    def eval(self, target: str, expression: str) -> Any:
        quoted = urllib.parse.quote(target, safe="")
        result = self._request("/eval?target=" + quoted, expression)
        if not isinstance(result, dict) or "error" in result:
            raise BrowserBridgeError("浏览器页面执行失败：%s" % (result.get("error") if isinstance(result, dict) else result))
        value = result.get("value")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @contextlib.contextmanager
    def temporary_tab(self, url: str = BASE_URL) -> Iterator[str]:
        target = self.new_tab(url)
        try:
            yield target
        finally:
            self.last_tab_closed = self.close_tab(target)

    def run_json(self, expression: str, url: str = BASE_URL) -> Any:
        with self.temporary_tab(url) as target:
            result = self.eval(target, expression)
        if isinstance(result, dict):
            result["browser_bridge"] = {"temporary_tab_closed": self.last_tab_closed is True}
        return result


def auth_status(bridge: CDPBridge) -> Dict[str, Any]:
    expression = r'''(async()=>{
      if(location.hostname==="verify.huodongxing.com"||document.title.includes("操作过于频繁"))return JSON.stringify({rate_limited:true,authenticated:false,organizer_access:false,attendee_access:false,account_data_exposed:false,adapter:"cdp",base_url:location.origin});
      const read=async path=>{const r=await fetch(path,{credentials:"include"});const t=await r.text();return {r,d:new DOMParser().parseFromString(t,"text/html")}};
      const user=await read("/user/regevents");
      const authenticated=!!user.d.querySelector('a[href*="/logout"]');
      let organizer=false;
      if(authenticated){const host=await read("/console/home");organizer=!!host.d.querySelector('a[href*="/console/eventadmin"]')&&!host.r.url.includes("/login");}
      return JSON.stringify({authenticated,organizer_access:organizer,attendee_access:authenticated,account_data_exposed:false,adapter:"cdp",base_url:location.origin});
    })()'''
    result = bridge.run_json(expression)
    if not isinstance(result, dict):
        raise BrowserBridgeError("登录态检测结果格式异常")
    _raise_if_verification(result)
    if not all(key in result for key in ("authenticated", "organizer_access", "attendee_access")):
        raise BrowserBridgeError("登录态检测未返回完整字段；页面可能仍在跳转或结构已经变化")
    return result


def page_snapshot(bridge: CDPBridge, url: str, sensitive: bool = False, include_forms: bool = False) -> Dict[str, Any]:
    expression = r'''(()=>{
      const requested=__URL__;
      const d=document;
      const clean=s=>(s||"").replace(/\s+/g," ").trim();
      const redact=s=>clean(s).replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,"[email]").replace(/1[3-9]\d{9}/g,"[phone]").replace(/\b\d{15,18}[0-9Xx]\b/g,"[identity]");
      const uniq=xs=>Array.from(new Set(xs.filter(Boolean)));
      const visible=x=>{const s=getComputedStyle(x);return s.display!=="none"&&s.visibility!=="hidden"&&x.getAttribute("aria-hidden")!=="true"};
      const usable=x=>visible(x)&&!x.closest('.modal,[role="dialog"],el-dialog,.el-dialog,.drawer,.el-drawer');
      const authenticated=!!d.querySelector('a[href*="/logout"]');
      const loginRequired=location.pathname.startsWith("/login")||(!authenticated&&requested.includes("huodongxing.com/")&&!requested.match(/\/(events|event\/|ranklist|topic|zhubanfang)/));
      const headings=uniq(Array.from(d.querySelectorAll("h1,h2,h3,h4,[role=tab],.nav-tabs li,.hdx-admin-nav-item-top")).filter(usable).map(x=>redact(x.innerText||x.textContent)).filter(x=>x&&x.length<=120)).slice(0,80);
      const actions=uniq(Array.from(d.querySelectorAll("button,input[type=submit],a.btn,.el-button")).filter(usable).map(x=>redact(x.innerText||x.textContent||x.getAttribute("value"))).filter(x=>x&&x.length<=80&&x!=="×")).slice(0,100);
      const related=Array.from(d.querySelectorAll("a[href]")).filter(usable).map(a=>{try{const u=new URL(a.getAttribute("href"),location.href);return {text:redact(a.innerText||a.textContent),url:u.origin+u.pathname+u.search}}catch(_){return null}}).filter(x=>x&&x.text&&x.url.startsWith("https://www.huodongxing.com/")&&!x.url.includes("/logout")&&(/\/(user|account|console|myevent|create|event)\b/.test(x.url))).slice(0,120);
      const fields=__INCLUDE_FORMS__?Array.from(d.querySelectorAll("input,select,textarea")).filter(usable).map(x=>({tag:x.tagName.toLowerCase(),type:x.getAttribute("type"),name:x.getAttribute("name"),placeholder:redact(x.getAttribute("placeholder"))})).filter(x=>x.type!=="hidden").slice(0,120):[];
      return JSON.stringify({ok:true,status:null,ready_state:d.readyState,requested_url:requested,final_url:location.href,title:redact(d.title),authenticated,login_required:loginRequired,sensitive:__SENSITIVE__,headings,actions,related_routes:related,form_schema:fields,values_included:false});
    })()'''.replace("__URL__", json.dumps(url, ensure_ascii=False)).replace(
        "__SENSITIVE__", "true" if sensitive else "false"
    ).replace("__INCLUDE_FORMS__", "true" if include_forms else "false")
    result = bridge.run_json(expression, url=url)
    if not isinstance(result, dict):
        raise BrowserBridgeError("页面快照结果格式异常")
    _raise_if_verification(result)
    if result.get("login_required"):
        raise BrowserBridgeError("当前 Chrome 未登录活动行，无法读取该登录态页面")
    return result


def my_tickets(bridge: CDPBridge) -> Dict[str, Any]:
    expression = r'''(async()=>{
      const r=await fetch("/user/regevents",{credentials:"include"});
      const d=new DOMParser().parseFromString(await r.text(),"text/html");
      const clean=s=>(s||"").replace(/\s+/g," ").trim();
      const authenticated=!!d.querySelector('a[href*="/logout"]');
      const defs=[
        ["user-ticket-success","valid"],
        ["user-ticket-undone","incomplete"],
        ["user-ticket-abort","cancelled"],
        ["user-ticket-refund","refund"]
      ];
      const groups={};
      for(const [id,status] of defs){
        const pane=d.getElementById(id);const rows=[];
        if(pane){for(const li of pane.querySelectorAll("ul.user-event-admin-tickets > li")){
          const links=Array.from(li.querySelectorAll('a[href*="/event/"]'));
          const titleLink=links.find(a=>clean(a.textContent));
          const match=(titleLink?.href||links[0]?.href||"").match(/\/event\/(\d+)/);
          if(!match)continue;
          const actions=Array.from(li.querySelectorAll("a,button")).map(x=>clean(x.textContent)).filter(x=>x&&x!==clean(titleLink?.textContent)&&x.length<=40);
          rows.push({event_id:match[1],title:clean(titleLink?.textContent),time_text:clean(li.querySelector(".time")?.textContent),status_label:clean(li.querySelector("label")?.textContent),order_count:li.querySelectorAll("table tbody tr").length,order_detail_available:!!li.querySelector('a[href*="/user/tikcets"]'),available_actions:Array.from(new Set(actions)).slice(0,20)});
        }}
        groups[status]=rows;
      }
      const counts=Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,v.length]));
      return JSON.stringify({authenticated,source_url:r.url,sensitive:true,counts,tickets:groups,pii_included:false,order_ids_included:false});
    })()'''
    result = bridge.run_json(expression)
    if not isinstance(result, dict):
        raise BrowserBridgeError("票券读取结果格式异常")
    _raise_if_verification(result)
    if not result.get("authenticated"):
        raise BrowserBridgeError("当前 Chrome 未登录活动行，无法读取我的票券")
    return result


def organizer_events(bridge: CDPBridge) -> Dict[str, Any]:
    expression = r'''(async()=>{
      const r=await fetch("/console/eventadmin",{credentials:"include"});
      const d=new DOMParser().parseFromString(await r.text(),"text/html");
      const clean=s=>(s||"").replace(/\s+/g," ").trim();
      const authenticated=!!d.querySelector('a[href*="/logout"]');
      const events=[];
      for(const card of d.querySelectorAll(".center-tabs-content")){
        const manage=card.querySelector('a[href*="/myevent/home?id="]');
        const id=(manage?.getAttribute("href")||"").match(/[?&]id=(\d+)/)?.[1];
        if(!id)continue;
        const publicLink=card.querySelector('.hd-title-content a[href*="/event/"]');
        const title=clean(card.querySelector(".clamp-text")?.textContent||publicLink?.textContent);
        const blocks=Array.from(card.querySelectorAll(":scope > .table-nav-content > .hd-apply-content")).map(x=>clean(x.textContent));
        const state=Array.from(card.querySelectorAll(".hd-state-content")).map(x=>clean(x.textContent)).filter(Boolean);
        const actions=Array.from(card.querySelectorAll(".hd-space-content a")).map(x=>clean(x.textContent)).filter(Boolean);
        events.push({id,title,public_url:publicLink?.href||null,schedule:blocks[0]||null,details:clean(card.querySelector(".hd-title-content")?.textContent),metrics:blocks.slice(1),state,available_actions:Array.from(new Set(actions))});
      }
      return JSON.stringify({authenticated,source_url:r.url,sensitive:true,count:events.length,events,pii_included:false,current_page_only:true});
    })()'''
    result = bridge.run_json(expression)
    if not isinstance(result, dict):
        raise BrowserBridgeError("主办方活动读取结果格式异常")
    _raise_if_verification(result)
    if not result.get("authenticated"):
        raise BrowserBridgeError("当前 Chrome 未登录活动行，无法读取主办方活动")
    return result


def discover_proxy_status(proxy_url: Optional[str] = None) -> Dict[str, Any]:
    return CDPBridge(proxy_url or DEFAULT_PROXY).status()


__all__: List[str] = [
    "BrowserBridgeError",
    "CDPBridge",
    "auth_status",
    "discover_proxy_status",
    "my_tickets",
    "organizer_events",
    "page_snapshot",
]
