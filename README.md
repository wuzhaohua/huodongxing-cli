# 活动行 CLI 与多 Agent Skill

[English summary](#english-summary)

`hdx` 是面向 [活动行](https://www.huodongxing.com) 的非官方、安全优先 CLI 和 Agent Skill。v3.0.0 不再只是搜索脚本或后台 URL 列表，而是统一覆盖：

- 公开活动搜索、严格筛选、详情、推荐和报名预检；
- Chrome 真实登录态下的个人票券、主办方活动和后台页面脱敏读取；
- 发布活动 JSON 草稿校验；
- 报名、名单、营销、签到、退款、财务和账号动作的两阶段计划；
- OpenClaw、OpenAI Codex、Claude Code 和通用 `SKILL.md` Agent。

项目不是活动行官方 SDK。普通网页账号的最终写操作仍在真实浏览器 UI 中完成；CLI 不把未公开页面请求包装成“官方 API”，也不绕过验证码、审核、支付或风控。

## 架构

| 层 | 负责内容 | 凭据 | 写入 |
|---|---|---|---|
| 公开 HTTP | 搜索、详情、推荐、报名预检 | 不需要 | 无 |
| 本机 CDP 浏览器桥 | 我的票券、主办方活动、后台页面结构 | Cookie 留在 Chrome 内 | 只读、脱敏 |
| 两阶段浏览器操作 | 报名、发布、名单、消息、退款、支付等 | Chrome 登录态 | 明确确认后由 UI 执行 |

CDP 命令每次创建自己的后台标签页，读取后关闭；不会导出 Cookie、Authorization、local storage、密码或验证码。

## v3 解决的问题

- 平台的推广卡片可能越过 `city/range/eventType`。严格模式现在以详情页二次复核城市、时间、形式、价格和认证。
- `--price free` 只保留全部票种均免费的活动；免费/收费混合活动不会再伪装成纯免费。
- 收费、实名、证件、异常营销、微信流程和用户排除主题在代码层禁止自动报名，策略文件不能覆盖。
- 报名预检读取 `signup.json` 的字段覆盖情况，但永不输出值。
- 推荐真正使用业务目标、形式、类型和时间偏好；无法评估的出行分钟数会明确披露。
- 登录态页面从“只返回 URL”升级为 CLI 原生脱敏读取。
- 公开详情有 30 分钟缓存、详情预算、并发上限和验证码熔断，减少多 Agent 重复访问。
- CSV 防止 `= + - @` 公式起始值被表格软件执行。
- 三个 Agent 发行包由同一规范源构建，并在 CI 中验证。

## 安装

要求 Python 3.9 或更高版本。公开命令只使用 Python 标准库。

### 独立 CLI

从 [GitHub Releases](https://github.com/wuzhaohua/huodongxing-cli/releases) 下载 `hdx-cli-3.0.0.zip`：

```bash
unzip hdx-cli-3.0.0.zip
chmod +x hdx hdx.py hdx_browser.py
./hdx doctor
```

或克隆仓库：

```bash
git clone https://github.com/wuzhaohua/huodongxing-cli.git
cd huodongxing-cli
scripts/hdx doctor
```

### OpenClaw

```bash
openclaw skills install git:wuzhaohua/huodongxing-cli@v3.0.0 --global
openclaw skills info huodongxing-cli
openclaw skills check
```

### OpenAI Codex

下载 `huodongxing-codex-skill-3.0.0.zip`，把 `huodongxing-cli` 放入 `~/.codex/skills/`。项目级安装可以放到 `.agents/skills/`。

`agents/openai.yaml` 提供 Codex UI 名称和默认提示，不增加权限。

### Claude Code

```text
/plugin marketplace add wuzhaohua/huodongxing-cli
/plugin install huodongxing@wuzhaohua-tools
/reload-plugins
```

显式调用：

```text
/huodongxing:huodongxing-cli
```

也可下载 `huodongxing-claude-code-plugin-3.0.0.zip` 并用 `claude --plugin-dir <目录>` 加载。

## 快速开始

### 1. 环境和能力

```bash
scripts/hdx --version
scripts/hdx doctor
scripts/hdx routes --format markdown
```

### 2. 公开活动

```bash
# 杭州未来 30 天、线下、纯免费 AI 活动
scripts/hdx search --city 杭州 -q AI --time month --mode offline --price free --limit 6

# 结构化详情
scripts/hdx detail EVENT_ID

# 画像推荐
scripts/hdx recommend --city 全国 -q Agent --limit 5 \
  --profile ~/.config/hdx/profile.json
```

严格搜索输出 `candidate_count`、`dropped`、`errors` 和 `filter_mode=detail-verified`。如果只追求速度并接受推广卡片污染，可显式使用 `--no-strict`。

### 3. 报名预检

```bash
scripts/hdx signup-plan EVENT_ID \
  --profile ~/.config/hdx/profile.json \
  --policy ~/.config/hdx/policy.json \
  --signup-data ~/.config/hdx/signup.json
```

输出包括票种、价格、实名/审核/微信要求、必填字段覆盖、硬阻断、策略来源、`auto_submit_eligible` 和验收方式。不会点击提交，也不会输出报名值。

配置示例见：

- [profile.example.json](references/profile.example.json)
- [policy.example.json](references/policy.example.json)
- [signup.example.json](references/signup.example.json)

请把真实文件设为仅本人可读写，并始终放在仓库和 Skill 之外。

### 4. 登录态读取

登录态命令依赖本机 Chrome 和 `web-access` CDP 代理。先按该 Skill 完成依赖检查，再运行：

```bash
scripts/hdx auth-status
scripts/hdx me-tickets
scripts/hdx host-events
scripts/hdx browser-read event-overview --event EVENT_ID
scripts/hdx browser-read event-attendees --event EVENT_ID
```

`me-tickets` 不返回订单号、二维码或报名资料；`browser-read` 不返回表单值、名单行或财务值。详见 [登录态浏览器桥](references/browser-bridge.md)。

### 5. 创建活动草稿

```bash
scripts/hdx event-draft template -o event-draft.json
scripts/hdx event-draft validate event-draft.json
scripts/hdx event-draft plan event-draft.json
scripts/hdx action-plan publish-event
```

草稿覆盖标题、形式、时间、地点、线上入口、摘要、正文、海报、可见性、名额、票种、报名字段、语言、隐私和售后联系方式。最终“创建活动”仍需确认。详见 [活动创建草稿](references/event-draft.md)。

### 6. 运营动作

```bash
scripts/hdx action-plan send-message --event EVENT_ID
scripts/hdx action-plan refund --event EVENT_ID
scripts/hdx action-plan checkin --event EVENT_ID
scripts/hdx action-plan delete-event --event EVENT_ID
```

动作计划会返回风险、影响、精确路由、确认令牌和验收方式，固定 `cli_commits_directly=false`。打开页面不等于提交成功。

## 平台覆盖

已验证能力包括：

- 参与者：票券、订单状态、收藏、个人主页和账户设置；
- 主办方：仪表盘、活动列表、主页、认证、广告、短信、邮件、用户、评论、发票、票款、充值和账号；
- 单活动：概览、编辑、邀请、推广、渠道/邀请码/白名单/优惠码、名单、通知、签到、协作、结算、嵌入和复制；
- 创建页：模板、AI 识别、主办方、海报、时间地点、直播、详情、嘉宾、票种、报名字段、隐私和售后。

完整分级见 [平台能力地图](references/platform-map.md)。套餐受限功能存在于页面不代表当前账号有权执行。

## 风控和缓存

- 默认详情候选 12、并发 3；硬上限为 20 和 4。
- 摘要明显不符合城市/形式时不请求详情。
- 详情缓存位于 `~/.cache/hdx/details/`，默认 1800 秒，只保存公开字段。
- 遇到操作过于频繁、验证页、403、429 或验证码立即熔断，不循环重试。
- 可用 `HDX_CACHE_DIR`、`HDX_CACHE_TTL` 和 `HDX_CDP_PROXY` 覆盖本机运行参数。

## 安全边界

- 不读取或保存账号密码。
- 不输出 Cookie、Token、验证码、身份证、支付信息或完整名单。
- 不把页面私有请求固化成未授权 API。
- 免费报名也属于个人数据写入。
- 收费、实名、证件、支付、退款、提领、群发、删除、拉黑、权限和账号安全始终逐次确认。
- 没有成功页、订单、电子票、后台状态或流水证据时，结果为“未知”。

详见 [安全说明](references/safety.md) 和 [独立安全与质量评估](docs/SECURITY_AND_QUALITY_REVIEW.md)。

## 开发与验证

```bash
python3 tests/test_hdx.py -v
python3 -m py_compile scripts/hdx.py scripts/hdx_browser.py tests/test_hdx.py
python3 tools/build_release.py --check
claude plugin validate . --strict
```

构建发行包：

```bash
python3 tools/build_release.py
```

产物写入 `dist/`。GitHub Actions 对测试、语法、发行结构、Skill 和隐私模式执行基础检查；真实网站和登录态烟雾测试仍在发布前人工运行，避免 CI 高频访问平台。

## 目录

```text
.
├── SKILL.md
├── agents/openai.yaml
├── scripts/hdx
├── scripts/hdx.py
├── scripts/hdx_browser.py
├── references/
├── tests/
├── skills/huodongxing-cli/
├── .claude-plugin/
├── .github/workflows/
├── tools/build_release.py
└── docs/SECURITY_AND_QUALITY_REVIEW.md
```

## 许可证与免责声明

MIT License。活动行及其商标归相应权利人所有。本项目为社区工具，使用者需要遵守活动行服务条款、隐私规则和适用法律。页面结构变化可能导致解析失效。

## English summary

`hdx` v3 is an unofficial, safety-first Huodongxing CLI and portable Agent Skill. It provides strict public event filtering, structured details and recommendations, privacy-preserving reads from the user's logged-in Chrome session through a local CDP bridge, event-draft validation, and two-phase plans for registrations and organizer operations. It supports OpenClaw, OpenAI Codex, Claude Code, and generic `SKILL.md` agents. The project does not bypass login, CAPTCHA, review, payment, rate limits, or private APIs; final mutations require explicit confirmation and browser readback.
