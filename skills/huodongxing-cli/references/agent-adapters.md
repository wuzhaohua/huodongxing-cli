# Agent 适配说明

## 共同执行模型

所有 Agent 都使用 `scripts/hdx` 作为确定性控制面：

1. `search`、`detail`、`recommend`、`signup-plan` 直接读取公开数据。
2. `open-route --print-only` 只返回登录态页面 URL。
3. Agent 有浏览器工具时，在用户已有登录态中打开该 URL；没有浏览器工具时，只返回 URL 并说明未读取页面。
4. 写操作先运行 `action-plan`，获得用户对本次准确对象和范围的明确确认后，才允许浏览器执行最终动作。
5. 提交后必须回读结果；没有证据时状态为“未知”。

## OpenClaw

- 从 Git 安装：`openclaw skills install git:wuzhaohua/huodongxing-cli@v2.2.0`。
- 使用工作区可用的浏览器 Skill 或浏览器工具处理登录态页面。
- 用 `openclaw skills info huodongxing-cli` 和 `openclaw skills check` 验证加载状态。
- OpenClaw 不会扫描 Codex 的 `$CODEX_HOME/skills`；需要分别安装或使用 OpenClaw 迁移命令。

## OpenAI Codex

- 个人安装目录：`~/.codex/skills/huodongxing-cli`。
- 项目安装目录：`.agents/skills/huodongxing-cli`。
- `agents/openai.yaml` 只提供 Codex UI 元数据，不改变 CLI 权限。
- 若当前 Codex 没有可用浏览器工具，使用 `--print-only` 返回路由，不尝试读取用户浏览器状态。

## Claude Code

- 插件技能位于 `skills/huodongxing-cli/SKILL.md`。
- 市场安装后命令为 `/huodongxing:huodongxing-cli`。
- 插件缓存只包含插件目录内文件，因此脚本和 references 必须与 Skill 一起打包。
- 本地验证运行 `claude plugin validate . --strict`；本地试用可运行 `claude --plugin-dir <repo>`。

## 通用 Agent Skills 客户端

将完整 `huodongxing-cli` 文件夹放入客户端支持的 Skills 根目录。必须保留 `SKILL.md`、`scripts/` 和 `references/` 的相对结构。若客户端不提供 shell 执行或 Python 3.9+，它只能读取说明，不能运行 CLI。
