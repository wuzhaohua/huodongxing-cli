---
name: "huodongxing-cli"
description: "使用活动行 CLI 发现、筛选、推荐和报名活动，支持按城市/本周/本月/主题查询、用户兴趣与业务目标匹配、免费与收费活动分流、报名安全预检，以及 OpenClaw/Codex/Claude Code 浏览器适配。"
---

# 活动行 CLI v2.2

使用 `scripts/hdx` 作为唯一入口。优先读取结构化数据，并严格区分公开读取、登录态浏览器读取和写操作。

## Run the shortest safe path

1. 环境未知时运行 `scripts/hdx doctor`。
2. 平台区域不明确时运行 `scripts/hdx routes`。
3. 活动发现、详情、推荐和报名预检使用公开命令。常见查询直接复用 [workflow-templates.md](references/workflow-templates.md)。
4. 登录态页面先运行 `open-route --print-only` 获取精确 URL，再使用当前 Agent 可用的浏览器工具读取。若没有浏览器工具，只向用户返回 URL，不声称已经读取页面。
5. 报名前运行 `signup-plan --profile ... --policy ...`。个人画像、报名资料和策略放在 `~/.config/hdx/`，不得进入 Skill 或 Git；详见 [registration-policy.md](references/registration-policy.md)。
6. 只有 `policy_decision=auto_submit_if_safe` 或用户明确确认本次动作时，才通过真实浏览器提交；提交前刷新页面，提交后验证最终状态。

## Command map

```bash
# Environment and platform map
scripts/hdx doctor
scripts/hdx routes
scripts/hdx routes --domain organizer

# Public discovery
scripts/hdx search --city 杭州 -q AI --time month --limit 10
scripts/hdx detail EVENT_ID
scripts/hdx recommend --city 全国 -q Agent --limit 5 --profile profile.json
scripts/hdx signup-plan EVENT_ID --profile profile.json --policy policy.json

# Logged-in browser routing
scripts/hdx open-route me-tickets --print-only
scripts/hdx open-route host-dashboard --print-only
scripts/hdx open-route host-events --print-only
scripts/hdx open-route event-overview --event EVENT_ID --print-only
scripts/hdx open-route event-attendees --event EVENT_ID --print-only

# Browser routing and two-phase writes
scripts/hdx action-plan signup --event EVENT_ID
scripts/hdx action-plan publish-event
scripts/hdx open-route create-event
scripts/hdx open-route event-attendees --event EVENT_ID
```

数据命令支持 `--format json|csv|markdown` 和 `-o FILE`。自动化默认使用 JSON。完整语法见 [references/cli-reference.md](references/cli-reference.md)。

## Choose the adapter

- `search`、`detail`、`recommend` 和 `signup-plan` 使用公开 HTTP，不需要登录或浏览器。
- 账号、票券、主办方、单活动运营、营销、用户、财务页面使用 `open-route` 加当前 Agent 的浏览器能力。绝不读取或输出 Cookie、Authorization header、密码或 local storage。
- 普通账号没有稳定的公开写入 API，最终写入必须通过浏览器 UI 完成。CLI 只负责路由、预检和验收。
- 遇到 403、429、验证码、异常登录或意外支付页面立即停止，不循环重试或绕过控制。

不同 Agent 的加载方式和浏览器适配见 [references/agent-adapters.md](references/agent-adapters.md)。

## Enforce write safety

Classify actions before execution:

- `read`: search, detail, dashboard readback, route inspection, export of non-sensitive public data. Execute directly.
- `prepare`: signup precheck, create-event draft planning, message/refund/check-in planning, opening the exact management page. Execute without submitting.
- `commit`: submit registration or PII, publish/edit event, send message, check in attendee, change privacy, issue refund, delete, pay, withdraw funds, change account/security. Require explicit confirmation for the exact action and object.

Treat free registration as a write because it submits personal data. A local policy may pre-authorize safe free registrations, but paid, identity-document, unexpected PII, payment and suspicious marketing cases still stop. Treat “待审核” as pending, not successful. Treat a clicked button as unverified until the success page, order, ticket, or changed record is visible.

Read [references/safety.md](references/safety.md) before any `commit` action.

## Interpret platform data carefully

- Platform-generated search parameters are authoritative. Current mappings include `qs`, `d=t1|t4|t5`, `range=1|2`, `eventType=1|2`, `auth=1`, and `orderby=o|n|v|r`.
- Re-check start time, location, price, ticket status, review requirement, real-name requirement, and fields on the detail page before registration.
- Deduplicate by event ID. Search and homepage cards may repeat promoted events.
- A free ticket can still require review, real-name data, WeChat, or hidden-address disclosure.
- Recommendation scores are decision aids, not facts about quality. Always show risk flags and confidence with the score. Read [recommendation-framework.md](references/recommendation-framework.md) for important recommendations.

Read [references/platform-map.md](references/platform-map.md) for the eight platform domains and [references/data-model.md](references/data-model.md) for field meanings.

## Report completion

For reads, report the command, record count, source URL, and any fields that could not be verified. For writes, report:

1. intended action and confirmed scope;
2. final visible state;
3. whether the result is successful, pending review, failed, or unknown;
4. fee or personal-data impact;
5. any remaining manual step.

Never include passwords, cookies, verification codes, payment details, identity numbers, or attendee PII in skill files, logs, or chat output.
