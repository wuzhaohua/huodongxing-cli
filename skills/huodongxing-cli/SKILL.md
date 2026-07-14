---
name: "huodongxing-cli"
metadata: {"version":"3.0.0"}
description: "通过 hdx CLI 使用活动行（huodongxing.com）：搜索、严格筛选、详情、推荐、报名预检、个人票券、主办方活动、登录态后台页面、活动草稿、名单/营销/财务/账号操作计划。用于用户提到活动行、找活动、报名活动、我的票券、发布或管理活动、参与者名单、签到、退款、营销、票款，或要求 OpenClaw/Codex/Claude Code 共用活动行能力时。"
---

# 活动行 CLI v3

使用 `scripts/hdx` 作为唯一确定性入口。把平台分成三层：公开 HTTP 数据、登录态 CDP 脱敏读取、浏览器确认后写入。不要从页面私有请求反推或固化未授权写 API。

## 选择最短安全路径

1. 首次使用或环境变化时运行 `scripts/hdx doctor`。
2. 搜索、详情、推荐和报名预检使用公开命令。筛选默认在详情页二次校验，避免推广卡片越过城市、形式或价格条件。
3. 读取“我的票券”或主办方后台前，加载 `web-access` Skill 并完成其 CDP 前置检查，再运行 `auth-status`、`me-tickets`、`host-events` 或 `browser-read`。
4. 创建活动先生成或校验 JSON 草稿，再运行 `event-draft plan`。创建按钮属于写操作。
5. 报名前运行 `signup-plan`。个人画像、策略和报名资料只能放在 `~/.config/hdx/` 或显式外部路径。
6. 所有写操作先运行 `action-plan`，刷新对象并核对范围、费用和个人数据；最终提交必须使用真实浏览器并取得结果证据。

## 常用命令

```bash
# 环境与全平台能力地图
scripts/hdx doctor
scripts/hdx routes --format markdown

# 公开发现；严格筛选为默认值
scripts/hdx search --city 杭州 -q AI --time month --mode offline --price free --limit 6
scripts/hdx detail EVENT_ID
scripts/hdx recommend --city 全国 -q Agent --profile ~/.config/hdx/profile.json
scripts/hdx signup-plan EVENT_ID --policy ~/.config/hdx/policy.json --signup-data ~/.config/hdx/signup.json

# 登录态读取；命令创建自己的后台标签页并在结束后关闭
scripts/hdx auth-status
scripts/hdx me-tickets
scripts/hdx host-events
scripts/hdx browser-read event-overview --event EVENT_ID
scripts/hdx browser-read event-attendees --event EVENT_ID

# 活动创建草稿
scripts/hdx event-draft template -o event-draft.json
scripts/hdx event-draft validate event-draft.json
scripts/hdx event-draft plan event-draft.json

# 精确路由和两阶段写操作
scripts/hdx open-route event-attendees --event EVENT_ID --print-only
scripts/hdx action-plan send-message --event EVENT_ID
scripts/hdx action-plan refund --event EVENT_ID
scripts/hdx action-plan publish-event
```

完整参数读取 [cli-reference.md](references/cli-reference.md)。按业务场景复用 [workflow-templates.md](references/workflow-templates.md)。

## 公开读取规则

- `search` 在存在城市、时间、形式、价格或认证筛选时，默认抓取有限候选并以详情字段二次过滤；`--price free` 只保留全部票种均免费的活动，混合票价不会混入。
- 公开详情缓存到 `~/.cache/hdx/details/`，默认 30 分钟，只含公开活动字段。缓存用于减少三个 Agent 重复请求。
- 默认最多 12 个详情候选、3 个并发；硬上限为 20 个候选、4 个并发。
- 遇到活动行频控、验证码、403 或 429 立即停止。不要循环重试、提高并发或绕过控制。
- 推荐分数只用于排序。始终同时展示风险、置信度、使用了哪些画像字段，以及未能评估的偏好。

## 登录态读取规则

- `auth-status` 只判断参与者/主办方访问能力，不返回昵称、账号或 Cookie。
- `me-tickets` 返回活动、状态、订单数量和可用动作，不返回订单号、二维码或报名资料。
- `host-events` 返回当前页活动运营摘要；名单、用户、财务和账号页面属于敏感读取。
- `browser-read` 只返回标题、结构、表单字段名、可用动作和相关路由，不返回表单值、名单行或财务值。
- 不操作用户已有标签页；CLI 创建并关闭自己的后台标签页。完整机制读取 [browser-bridge.md](references/browser-bridge.md)。

## 写操作硬边界

把操作分成 `read`、`sensitive-read`、`prepare`、`commit`、`paid-commit`、`destructive-commit` 和 `security-commit`。

- 免费报名仍会提交个人数据。只有本地策略明确允许、全部必填值已存在、活动纯免费，且不存在收费、实名、证件、异常营销、排除主题或微信流程时，才可标记为 `auto_submit_eligible`。
- 收费、实名、证件、支付、退款、提领、群发、删除、拉黑、权限和账号安全操作永远不能被策略文件自动放行。
- `action-plan` 只生成影响、确认令牌、精确路由和验收方式；CLI 不直接执行最终点击。
- 打开页面、点击按钮、提交、待审核和成功是不同状态。没有成功页、订单、电子票、后台状态或流水回读时，结果必须标为未知。

执行任何提交前读取 [safety.md](references/safety.md)；报名策略读取 [registration-policy.md](references/registration-policy.md)；活动草稿读取 [event-draft.md](references/event-draft.md)。

## 多 Agent 适配

公开命令在 OpenClaw、Codex 和 Claude Code 中原生一致。登录态读取统一调用本机 CDP 代理，不在 Skill 中写死某个 Agent 的浏览器工具名。若当前 Agent 没有 CDP 能力，使用 `open-route --print-only` 返回精确地址并明确说明未读取页面。

安装、调用和浏览器差异读取 [agent-adapters.md](references/agent-adapters.md)。平台域、路由和实现等级读取 [platform-map.md](references/platform-map.md)。字段含义读取 [data-model.md](references/data-model.md)。

## 完成报告

公开读取报告命令、来源 URL、筛选模式、候选数、丢弃原因、结果数和未验证字段。登录态读取报告适配器、最终路由、是否登录、是否包含敏感值。写操作报告确认范围、最终可见状态、费用或个人数据影响、成功/待审核/失败/未知和剩余人工步骤。

禁止在 Skill、Git、共享经验或对话中写入密码、Cookie、Token、验证码、身份证、支付信息或完整参与者名单。
