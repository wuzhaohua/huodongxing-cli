# 安全与质量评估

评估版本：v2.2.0。

## 结论

CLI 适合公开活动发现、详情读取、推荐和报名预检。它不持有账号凭据，不实现平台写入，也不尝试绕过登录、验证码、支付或风控。涉及账号、参与者、财务和活动管理的能力，本质上是“路由解析 + Agent 浏览器操作”，不是官方 API 集成。

v2.2.0 的个人画像、报名策略和报名资料位于 `~/.config/hdx/` 等 Skill 外部目录，不进入 Release。CLI 只读取画像和策略，不读取报名资料；最终提交仍由具备真实登录态的浏览器 Agent 执行。

## 已修复问题

- v2.0.0 默认城市为杭州，公开使用会产生地域偏差；v2.1.0 改为全国。
- v2.0.0 内置 AI、杭州、上海等推荐偏好；v2.1.0 改为空白中性配置，偏好必须由使用者提供。
- v2.0.0 搜索 CSV 将全部活动压入单个 JSON 字段；v2.1.0 改为每个活动一行。
- v2.0.0 `open-route` 总是尝试打开系统浏览器；v2.1.0 增加 `--print-only`，适配无界面 Agent 和沙箱。
- v2.0.0 只有 OpenClaw 根 Skill；v2.1.0 增加 Codex 元数据、Claude Code 插件/市场结构、构建校验和 CI。
- v2.0.0 缺少明确开源许可证；v2.1.0 增加 MIT License。

## 剩余风险

1. 活动行公开页面结构不是稳定 API。CSS class 或内嵌变量改变后，搜索和详情解析可能失败。
2. 路由表来自当前网页能力地图，活动行改版后可能跳转、失效或改变风险等级。
3. 推荐分数是启发式排序，不代表活动质量、真实性或投资价值。
4. CLI 无法证明登录态页面已成功加载；浏览器 Agent 必须自行验证页面内容和账号范围。
5. 活动信息来自第三方主办方，CLI 不验证内容真实性。
6. Windows 可以运行 Python CLI，但 `scripts/hdx` 是 POSIX shell 包装器；Windows 用户应运行 `python scripts/hdx.py`。

## 发布门槛

- 单元测试、语法检查和真实公开页面烟雾测试通过。
- OpenClaw 显示 Skill eligible、model-visible 和 command-visible。
- Codex Skill 通过 `quick_validate.py`，且 `agents/openai.yaml` 可解析。
- Claude Code 插件通过 `claude plugin validate . --strict`。
- Release 压缩包不包含 `.env`、凭据、Cookie、Token、数据库或用户资料。
- 发布前检查 Git diff、压缩包清单和 SHA-256。
