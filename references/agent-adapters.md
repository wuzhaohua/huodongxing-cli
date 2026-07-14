# Agent 适配说明

## 共同模型

三种 Agent 共享完整 Skill 正文和 `scripts/hdx`：

1. 公开读取由 Python CLI 执行。
2. 登录态读取统一连接 `web-access` 的本机 CDP 代理；Cookie 永远留在 Chrome。
3. `open-route --print-only` 是 CDP 不可用时的只读降级。
4. 写操作统一经过 `signup-plan`、`event-draft plan` 或 `action-plan`，最终由真实浏览器确认和验收。
5. 工具缺失时报告缺口，不把其他 Agent 的工具名当作当前能力。

## 本机统一 Skill 系统

本机以 `~/.agents/skills/huodongxing-cli` 为唯一活动主源。Codex 和 Claude Code 的个人 Skill 入口应链接到该目录；OpenClaw 原生读取共享主库。修改时遵守 `shared-skill-system` 的锁、快照、验证和经验记录流程。

公开发行包仍分别提供 OpenClaw、Codex 和 Claude Code 的标准安装结构；它们的正文由同一规范源构建。

## OpenClaw

- 安装：`openclaw skills install git:wuzhaohua/huodongxing-cli@v3.0.0 --global`。
- 验证：`openclaw skills info huodongxing-cli` 和 `openclaw skills check`。
- 登录态：先加载共享 `web-access`，再运行 `scripts/hdx auth-status`。
- 不再从旧 `huodongxing` Skill 读取账号密码或个人档案；旧名称只作为兼容别名。

## OpenAI Codex

- 个人入口：`~/.codex/skills/huodongxing-cli`。
- 项目入口：`.agents/skills/huodongxing-cli`。
- `agents/openai.yaml` 只提供 UI 元数据，不增加权限。
- 当前会话若尚未发现新版本，启动新任务或重新加载 Skill 列表。

## Claude Code

- 插件市场：`/plugin marketplace add wuzhaohua/huodongxing-cli`，再安装 `huodongxing@wuzhaohua-tools`。
- 显式调用：`/huodongxing:huodongxing-cli`。
- 插件包包含 Skill、CLI、浏览器桥和 references；用 `claude plugin validate . --strict` 验证。

## 通用 Agent Skills 客户端

保留 `SKILL.md`、`agents/`、`scripts/` 和 `references/` 相对结构。需要 Python 3.9+ 才能运行公开 CLI；需要兼容的本机 CDP 代理才能运行登录态命令。缺少这些依赖时仍可读取方法和路由，但不能声称执行成功。
