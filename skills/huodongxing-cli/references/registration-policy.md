# 本地报名配置与安全策略

## 文件位置

默认放在 Skill 和 Git 之外：

```text
~/.config/hdx/profile.json
~/.config/hdx/policy.json
~/.config/hdx/signup.json
```

目录权限建议 `0700`，文件权限建议 `0600`。可用 `HDX_CONFIG_DIR`、`HDX_PROFILE`、`HDX_POLICY`、`HDX_SIGNUP` 或命令参数覆盖。

不得把这些文件提交到 Git、打进 Release、写入共享经验、测试快照或对话输出。

## profile.json

```json
{
  "interests": ["AI", "企业服务"],
  "preferred_cities": ["杭州", "上海"],
  "business_goals": ["客户拓展", "合作伙伴"],
  "preferred_formats": ["offline"],
  "preferred_event_types": ["峰会", "闭门会"],
  "excluded_topics": ["加盟"],
  "time_preferences": ["工作日", "下午"],
  "max_travel_minutes": 60
}
```

`interests`, `business_goals`, `preferred_cities`, `preferred_formats`, `preferred_event_types` 和 `time_preferences` 会参与评分。`max_travel_minutes` 只有在未来提供可信出发地和路程数据后才能计分；当前输出会明确列为未评估。

## signup.json

可以使用根对象或 `fields` 对象。键可以是页面字段 key、完整标题或常见别名。

```json
{
  "fields": {
    "姓名": "本地填写",
    "mobile": "本地填写",
    "email": "本地填写",
    "公司": "本地填写",
    "参会目标": "本地填写"
  }
}
```

`signup-plan` 只输出已覆盖/缺失的字段名，不输出值。浏览器 Agent 也只在最终填表时按最小必要原则读取。

## policy.json

策略值：

- `auto_submit_if_safe`：只允许用于 `free_events` 和 `requires_review`；仍须通过代码硬安全门。
- `ask`：逐次确认。
- `notify_only`：只报告，不进入提交。
- `skip`：跳过。
- `deny`：禁止。

示例：

```json
{
  "free_events": "auto_submit_if_safe",
  "paid_events": "notify_only",
  "requires_review": "auto_submit_if_safe",
  "real_name": "ask",
  "wechat_required": "ask",
  "identity_document": "deny",
  "marketing_risk": "skip",
  "verify_after_submit": true
}
```

## 代码硬安全门

即使策略文件写错，以下情况也不能得到免确认自动提交：

- 纯收费或免费/收费混合票种；
- 实名报名；
- 身份证、护照或证件号字段；
- 异常营销、招商加盟、卖课/搞钱等风险；
- 用户排除主题；
- 微信专属或需要切换微信的流程；
- 任一必填字段没有本地值；
- 票价、字段、余量或最终提交状态无法验证。

对不允许自动值的策略键写入 `auto_submit_if_safe` 时，CLI 直接报配置错误，不静默放行。

## 自动资格不等于自动成功

`auto_submit_eligible=true` 只表示本地预检通过。浏览器提交前仍须刷新票价、票种和字段；提交后必须看到成功页、订单、电子票或待审核记录。验证码、异常登录、支付页或新字段出现时立即停止。
