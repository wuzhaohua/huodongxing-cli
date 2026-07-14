---
name: "huodongxing-cli"
description: "活动行全平台安全 CLI：搜索、详情、推荐、报名预检及主办方路由管理。"
---

# 活动行 CLI

Use `scripts/hdx` as the single entry point. Prefer structured data over copying visible page text. Keep public HTTP reads separate from logged-in browser reads and from writes.

## Run the shortest safe path

1. Run `scripts/hdx doctor` when the environment is unknown.
2. Run `scripts/hdx routes` when the requested platform area is unclear.
3. Use public commands for discovery and event intelligence.
4. For logged-in account or organizer pages, use `open-route` to resolve the exact page, then use `web-access` for readback in the user's logged-in browser. Keep attendee PII out of chat output.
5. For any write, run `action-plan` first. Show the exact object, scope, personal data, fee, and reversibility to the user.
6. Only after explicit confirmation, use `open-route` to open the final browser page and complete the action with `web-access`. Re-read the page immediately before the irreversible click and verify the resulting state afterward.

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
scripts/hdx signup-plan EVENT_ID

# Logged-in browser routing
scripts/hdx open-route me-tickets
scripts/hdx open-route host-dashboard
scripts/hdx open-route host-events
scripts/hdx open-route event-overview --event EVENT_ID
scripts/hdx open-route event-attendees --event EVENT_ID

# Browser routing and two-phase writes
scripts/hdx action-plan signup --event EVENT_ID
scripts/hdx action-plan publish-event
scripts/hdx open-route create-event
scripts/hdx open-route event-attendees --event EVENT_ID
```

All data commands support `--format json|csv|markdown` and `-o FILE` where applicable. JSON is the default for automation. Read [references/cli-reference.md](references/cli-reference.md) for the complete syntax.

## Choose the adapter

- Use public HTTP for `search`, `detail`, `recommend`, and `signup-plan`. These require no login and no browser.
- Use `open-route` plus `web-access` for account, ticket, organizer, event-management, marketing, user, finance, and account pages. Never read or print cookies, authorization headers, passwords, or local storage.
- Use the browser UI for final writes because Activity Line does not expose a stable public write API for ordinary accounts. CLI orchestration remains the control plane; the UI is the verified last-mile adapter.
- Stop on 403, 429, CAPTCHA, abnormal-login prompts, or unexpected payment pages. Do not loop or bypass controls.

## Enforce write safety

Classify actions before execution:

- `read`: search, detail, dashboard readback, route inspection, export of non-sensitive public data. Execute directly.
- `prepare`: signup precheck, create-event draft planning, message/refund/check-in planning, opening the exact management page. Execute without submitting.
- `commit`: submit registration or PII, publish/edit event, send message, check in attendee, change privacy, issue refund, delete, pay, withdraw funds, change account/security. Require explicit confirmation for the exact action and object.

Treat free registration as a write because it submits personal data. Treat “待审核” as pending, not successful. Treat a clicked button as unverified until the success page, order, ticket, or changed record is visible.

Read [references/safety.md](references/safety.md) before any `commit` action.

## Interpret platform data carefully

- Platform-generated search parameters are authoritative. Current mappings include `qs`, `d=t1|t4|t5`, `range=1|2`, `eventType=1|2`, `auth=1`, and `orderby=o|n|v|r`.
- Re-check start time, location, price, ticket status, review requirement, real-name requirement, and fields on the detail page before registration.
- Deduplicate by event ID. Search and homepage cards may repeat promoted events.
- A free ticket can still require review, real-name data, WeChat, or hidden-address disclosure.
- Recommendation scores are decision aids, not facts about quality. Separate extracted facts from scoring and assumptions.

Read [references/platform-map.md](references/platform-map.md) for the eight platform domains and [references/data-model.md](references/data-model.md) for field meanings.

## Report completion

For reads, report the command, record count, source URL, and any fields that could not be verified. For writes, report:

1. intended action and confirmed scope;
2. final visible state;
3. whether the result is successful, pending review, failed, or unknown;
4. fee or personal-data impact;
5. any remaining manual step.

Never include passwords, cookies, verification codes, payment details, identity numbers, or attendee PII in skill files, logs, or chat output.
