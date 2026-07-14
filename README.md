# 活动行 CLI 与多 Agent Skill

[English summary](#english-summary)

这是一个面向 [活动行](https://www.huodongxing.com) 的安全、无凭据 CLI 和 Agent Skill。当前版本为 **v2.1.0**，支持 OpenClaw、OpenAI Codex、Claude Code，以及兼容 `SKILL.md` 的通用 Agent。

项目不是活动行官方 SDK，也不调用未公开的私人写入接口。公开活动使用 HTTP 读取；登录态页面只解析精确路由；报名、发布、退款、群发、支付等操作必须经过用户对本次动作的明确确认，并由真实浏览器完成最终提交。

## 主要能力

- 搜索活动并按城市、时间、价格、线上/线下、认证和排序筛选。
- 读取活动详情、票种、价格、报名字段、实名与审核要求。
- 根据用户提供的偏好文件生成可解释推荐分数。
- 在报名之前输出字段、费用和风险预检，永不自动提交。
- 解析票券、主办方后台、名单、营销、财务和账号页面的精确路由。
- 输出 JSON、逐行 CSV 或 Markdown，适合 Agent 和自动化流程。
- 对外部写入、个人数据和资金动作执行统一安全门。

## 安装

要求 Python 3.9 或更高版本。公共读取只使用 Python 标准库，不需要 API Key。

### 独立 CLI

从 [GitHub Releases](https://github.com/wuzhaohua/huodongxing-cli/releases) 下载 `hdx-cli-2.1.0.zip`，解压后运行：

```bash
chmod +x hdx hdx.py
./hdx doctor
./hdx search --city 全国 -q AI --limit 5
```

也可以直接克隆仓库：

```bash
git clone https://github.com/wuzhaohua/huodongxing-cli.git
cd huodongxing-cli
scripts/hdx doctor
```

### OpenClaw

仓库根目录本身就是可安装 Skill：

```bash
openclaw skills install git:wuzhaohua/huodongxing-cli@v2.1.0
openclaw skills info huodongxing-cli
```

安装到所有本地 Agent：

```bash
openclaw skills install git:wuzhaohua/huodongxing-cli@v2.1.0 --global
```

### OpenAI Codex

下载 `huodongxing-codex-skill-2.1.0.zip`，将其中的 `huodongxing-cli` 目录放入：

```text
~/.codex/skills/huodongxing-cli
```

项目级安装可放入仓库的 `.agents/skills/huodongxing-cli`。Skill 包含 `agents/openai.yaml`，可供 Codex 的 Skill 列表和默认提示使用。

### Claude Code

仓库同时是一个 Claude Code 插件市场：

```text
/plugin marketplace add wuzhaohua/huodongxing-cli
/plugin install huodongxing@wuzhaohua-tools
/reload-plugins
```

安装后可显式调用：

```text
/huodongxing:huodongxing-cli
```

也可以下载 `huodongxing-claude-code-plugin-2.1.0.zip`，解压后使用 `claude --plugin-dir <目录>` 本地加载。

## 快速使用

```bash
# 环境检查和能力地图
scripts/hdx doctor
scripts/hdx routes --format markdown

# 公共活动读取
scripts/hdx search --city 上海 -q Agent --time month --limit 10
scripts/hdx detail EVENT_ID
scripts/hdx recommend --city 全国 -q AI
scripts/hdx signup-plan EVENT_ID

# 只解析登录态页面地址，不自动打开浏览器
scripts/hdx open-route me-tickets --print-only
scripts/hdx open-route event-attendees --event EVENT_ID --print-only

# 写操作预检，不执行提交
scripts/hdx action-plan signup --event EVENT_ID
scripts/hdx action-plan refund --event EVENT_ID
```

完整参数见 [CLI 参考](references/cli-reference.md)，字段含义见 [数据模型](references/data-model.md)，Agent 差异见 [Agent 适配说明](references/agent-adapters.md)。

## 输出与退出码

- JSON：默认格式，适合 Agent 和程序。
- CSV：搜索和推荐结果按活动逐行输出；嵌套字段编码为 JSON 字符串。
- Markdown：适合人类阅读和报告。
- 退出码 `0` 表示完成，`2` 表示参数、网络或页面解析错误，`130` 表示用户中断。

## 安全边界

- 不保存或读取账号密码、Cookie、Token、验证码和浏览器 local storage。
- 不内置个人城市、兴趣、业务目标或报名资料；推荐偏好必须由用户主动提供。
- 免费报名仍会提交个人信息，属于写操作。
- 遇到 403、429、验证码、异常登录或意外支付页面时停止。
- 页面打开、按钮点击、提交成功、审核通过是不同状态，必须通过结果页、订单、电子票或平台记录验收。

完整规则见 [安全说明](references/safety.md)。已知限制和本次审计结论见 [安全与质量评估](docs/SECURITY_AND_QUALITY_REVIEW.md)。

## 开发与验证

```bash
python3 tests/test_hdx.py
python3 -m py_compile scripts/hdx.py tests/test_hdx.py
python3 tools/build_release.py --check
claude plugin validate . --strict
```

构建 Release 包：

```bash
python3 tools/build_release.py
```

产物写入 `dist/`。Claude Code 的插件 Skill 副本由构建脚本同步，并在 CI 中检查是否与根目录规范版本一致。

## 目录结构

```text
.
├── SKILL.md                    # OpenClaw / 通用 Agent 入口
├── agents/openai.yaml          # Codex UI 元数据
├── scripts/                    # CLI 和包装器
├── tests/                      # CLI 单元测试
├── references/                 # Agent 按需读取的领域与安全资料
├── skills/huodongxing-cli/     # Claude Code 插件 Skill 副本
├── .claude-plugin/             # Claude Code 插件与市场清单
├── tools/build_release.py      # 同步、校验和打包
└── docs/                       # 面向维护者和使用者的评估说明
```

## 许可证与免责声明

本项目采用 MIT License。活动行及其商标归相应权利人所有。本项目是非官方社区工具，页面结构变化可能导致解析失效；使用者需要遵守活动行服务条款、隐私规则和适用法律。

## English summary

`hdx` is an unofficial, credential-free CLI and portable Agent Skill for Huodongxing. It supports public event search, structured detail extraction, explainable recommendations, registration preflight, and safe routing to logged-in organizer pages. OpenClaw, OpenAI Codex, Claude Code, and generic `SKILL.md` agents are supported. Mutating actions are never performed by the CLI and require explicit user confirmation in a real browser.
