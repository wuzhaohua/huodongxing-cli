# 本地报名策略

个人画像、报名资料和自动报名策略必须放在 Skill 目录之外，默认路径为：

```text
~/.config/hdx/profile.json
~/.config/hdx/policy.json
~/.config/hdx/signup.json
```

也可通过 `HDX_CONFIG_DIR`、`HDX_PROFILE`、`HDX_POLICY` 指定路径。不得把这些文件提交到 Git、打进 Release 或写入共享经验账本。

`signup.json` 由浏览器 Agent 按最小必要原则读取；CLI 不读取或输出报名资料。

策略值：

- `auto_submit_if_safe`：仅在所有安全条件满足时允许浏览器继续。
- `ask`：提交前询问。
- `notify_only`：只通知，不进入提交。
- `skip`：跳过。
- `deny`：禁止。

免费不等于安全。微信、实名、证件、审核问答、异常营销、时间冲突和未知收费都会阻止无提示自动提交。
