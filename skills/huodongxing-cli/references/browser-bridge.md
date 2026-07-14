# 登录态浏览器桥

## 目标

让 OpenClaw、Codex 和 Claude Code 通过同一个 `hdx` 命令读取活动行登录态页面，同时不导出 Cookie、Authorization、local storage、密码或验证码。

## 前置条件

1. Chrome 已登录活动行。
2. 当前 Agent 加载 `web-access` Skill，并按其要求完成 CDP 前置检查。
3. 本机代理默认监听 `http://127.0.0.1:3456`。可用 `HDX_CDP_PROXY` 或 `--proxy` 覆盖。

只连接自己控制的本机回环代理。改成远程或第三方代理会让对方看到请求路由和脱敏后的页面结构，并获得代理所允许的浏览器控制能力；本项目不把这类地址视为可信默认值。

```bash
scripts/hdx doctor
scripts/hdx auth-status
```

`doctor.ready_logged_in_reads=true` 且 `auth-status.authenticated=true` 后再读取账户页面。

## 隔离方式

- 每次命令创建一个活动行后台标签页。
- 页面内使用 `fetch(..., {credentials: "include"})` 读取同源页面，登录凭据始终留在 Chrome 内。
- 命令只接收经过页面内结构化和脱敏后的 JSON。
- 命令结束后关闭自己创建的标签页，不关闭用户原有标签页。
- 输出中的 `browser_bridge.temporary_tab_closed` 明确记录临时标签页是否关闭成功。

## 专用读取

### 我的票券

```bash
scripts/hdx me-tickets
```

返回有效、未完成、已取消和退票申请四类活动；只包含活动 ID、标题、时间、状态、订单数量和动作名称。不会返回订单 ID、二维码、姓名、手机、邮箱或表单答案。

### 主办方活动

```bash
scripts/hdx host-events
```

返回当前页活动 ID、标题、时间地点摘要、运营指标、状态和动作。`current_page_only=true` 表示没有声称已遍历全部分页。

### 任意后台路由结构

```bash
scripts/hdx browser-read host-dashboard
scripts/hdx browser-read event-overview --event EVENT_ID
scripts/hdx browser-read event-attendees --event EVENT_ID
```

返回页面标题、标题结构、按钮、相关后台路由和非隐藏表单字段 schema。不会返回字段值、名单行或财务金额。

## 错误处理

- 代理不可用：运行 `web-access` 前置检查，不自行复制浏览器配置。
- 未登录：请用户在 Chrome 登录活动行，完成后重新运行；不要读取账号密码文件。
- 403、429、验证码或异常登录：停止，不绕过。
- 页面结构变化：保留路由和 `browser-read` 原始结构证据，更新选择器并增加回归测试。
- 清理失败：`temporary_tab_closed=false` 时只处理本命令创建且能够确认归属的标签页，不得关闭用户原有标签页。

## 隐私分级

- 普通登录态：票券状态、活动运营摘要。
- 敏感读取：参与者名单、订单、用户、评论、财务、发票、合同、账号资料。
- 高风险写入：消息、邀请、审核、退款、签到、拉黑、上传名单、支付、提领、权限、安全设置。

当前 CLI 只对前两类提供脱敏读取，对高风险写入只提供 `action-plan` 和精确路由。
