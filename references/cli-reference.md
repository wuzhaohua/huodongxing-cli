# hdx 2.0 命令参考

## 安装和诊断

要求 Python 3.9+。公共命令仅使用标准库。登录态页面由 `open-route` 打开，再由 `web-access` 读取和操作。

```bash
chmod +x scripts/hdx scripts/hdx.py
scripts/hdx --version
scripts/hdx doctor
```

## 路由地图

```bash
scripts/hdx routes
scripts/hdx routes --domain public --format markdown
scripts/hdx routes --domain event --format csv -o routes.csv
```

`risk=read` 可直接读取；`prepare` 只打开或预检；`commit` 在最终动作前必须确认。

## 搜索

```bash
scripts/hdx search --city 杭州 -q AI --time week --limit 10
scripts/hdx search --city 全国 --tag 企业服务 --price free --verified
scripts/hdx search --city 上海 --from 2026-07-13 --to 2026-07-31 --mode offline
```

参数映射：

| CLI | 平台参数 |
|---|---|
| `-q/--keyword` | `qs` |
| `--time week/weekend/month` | `d=t1/t4/t5` |
| `--from` + `--to` | `d=ts&date=...&dateTo=...` |
| `--price free/paid` | `range=1/2` |
| `--mode offline/online` | `eventType=1/2` |
| `--verified` | `auth=1` |
| `--order relevance/newest/popular/participants` | `orderby=o/n/v/r` |

## 详情、推荐与报名预检

```bash
scripts/hdx detail EVENT_ID
scripts/hdx detail 'https://www.huodongxing.com/event/EVENT_ID' --format markdown
scripts/hdx recommend --city 杭州 -q AI --time month --limit 5
scripts/hdx recommend --city 全国 -q Agent --profile profile.json
scripts/hdx signup-plan EVENT_ID
```

详情输出包括时间、地址、价格区间、票种、余量、审核、实名、隐藏地址、报名字段和主办方。`signup-plan` 永不提交。

## 登录态页面路由

```bash
scripts/hdx open-route me-tickets
scripts/hdx open-route host-dashboard
scripts/hdx open-route host-events
scripts/hdx open-route event-overview --event EVENT_ID
scripts/hdx open-route event-attendees --event EVENT_ID
```

CLI 只解析并打开精确页面，不读取 Cookie 或私有接口。Agent 使用 `web-access` 从登录态页面回读；默认不要输出手机号、邮箱、身份证或完整名单。

## 路由和写操作预检

```bash
scripts/hdx action-plan signup --event EVENT_ID
scripts/hdx action-plan send-message --event EVENT_ID
scripts/hdx action-plan refund --event EVENT_ID
scripts/hdx action-plan publish-event

scripts/hdx open-route event-attendees --event EVENT_ID
scripts/hdx open-route create-event
```

`open-route` 使用系统默认浏览器，只打开页面，不点击提交。

## 输出

数据命令支持：

```bash
--format json|csv|markdown
-o FILE
```

JSON 用于 Agent 和程序；CSV 用于表格；Markdown 用于报告。CSV 中的嵌套对象会编码成 JSON 字符串。

## 退出码

- `0`：命令完成。
- `2`：参数、网络或页面解析错误。
- `130`：用户中断。

出现 403、429、验证码或异常登录时停止，不自动高频重试。
