# 活动行 CLI 与 OpenClaw Skill

活动行（huodongxing.com）的安全命令行工具与 OpenClaw Skill，当前版本为 **v2.0.0**。

## 能做什么

- 搜索活动、读取详情、生成推荐和报名预检
- 输出 JSON、CSV 或 Markdown，便于 AI 与自动化流程调用
- 为登录态页面解析精确路由，由浏览器完成读取或最终操作
- 对报名、发布、退款、消息发送等写操作执行“两阶段确认”

## 快速开始

要求 Python 3.9+，公共数据命令仅使用 Python 标准库。

```bash
chmod +x scripts/hdx scripts/hdx.py
scripts/hdx --version
scripts/hdx doctor
scripts/hdx search --city 杭州 -q AI --time month --limit 10
```

完整命令见 [`references/cli-reference.md`](references/cli-reference.md)，平台路由见 [`references/platform-map.md`](references/platform-map.md)。

## 目录

```text
.
├── SKILL.md
├── scripts/
│   ├── hdx
│   ├── hdx.py
│   └── test_hdx.py
└── references/
```

## 安全边界

- 搜索、详情、推荐和报名预检使用公开 HTTP 数据。
- 登录态页面只解析路由，不读取或输出 Cookie、Token、密码、本地存储或参与者隐私。
- 免费报名同样会提交个人信息，必须在最终提交前明确确认。
- 遇到 403、429、验证码、异常登录或意外支付页面时立即停止。

完整规则见 [`references/safety.md`](references/safety.md)。

## 下载

GitHub Releases 中提供两个交付包：

- `hdx-cli-2.0.0.zip`：独立 CLI
- `huodongxing-cli-skill-v2.0.0.zip`：完整 OpenClaw Skill
