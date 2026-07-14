# 活动行数据模型

## 搜索摘要

`id`, `title`, `time_text`, `location`, `organizer`, `followers`, `url`, `image`。

同一活动可能在搜索页重复出现；以 `id` 去重。推广参数可保留用于溯源，但业务关联以活动 ID 为主。

## 活动详情

详情页当前内嵌 `ativityJson`, `eventTicketsJson`, `formItemsJson`, `OrganizerList`。优先解析这些结构化变量。

关键字段：

- `Start`, `End`, `StartShort`, `EndShort`：时间。
- `City`, `Address`, `Setting.ShowAddressAfterRegister`：地点和隐藏地址。
- `IsFree`, ticket `Price`：费用。
- `MaxInstance`, `InstanceNumber`, `VisitNumber`：容量、报名、浏览。
- ticket `StatusStr`, `Quantity`, `SoldNumber`, `MinOrder`, `MaxOrder`：票种状态与数量。
- ticket `NeedApply` / `Setting.ApplyReject`：审核。
- `Setting.RealnameRegistration`：实名。
- `Setting.RequireParticipant`：多票参与者资料。
- `Setting.IsOnlyWeixin`：仅微信流程。
- `formItemsJson`：报名字段、必填、类型和选项。

## 状态解释

- 免费 ≠ 无审核。
- 已提交 ≠ 已通过。
- 按钮可点击 ≠ 有余票。
- 页面打开 ≠ 登录成功。
- 搜索页时间词（今天/明天/本周）需要详情页绝对时间复核。

## 推荐分数

总分 100：主题 40、主办方 20、时间 15、地点 15、规模 10。默认偏好为空，不内置城市、兴趣或业务目标；使用 `--profile` 提供偏好后，主题和地点维度才会获得个性化加分。分数只用于排序；不要把粉丝数、认证或大规模直接等同于活动质量。
