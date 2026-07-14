# 活动行数据模型

## 搜索摘要

`id`, `title`, `time_text`, `location`, `organizer`, `followers`, `url`, `image`。

搜索页摘要用于候选发现，不作为严格筛选的最终证据。推广卡片可能越过城市、价格和线上/线下参数；同一活动也可能重复出现。始终按 `id` 去重。

严格搜索在摘要后补充：`start`, `end`, `city`, `address`, `mode`, `pricing`, `is_free`, `has_free_ticket`, `has_paid_ticket`, `price`, `detail_verified`。

## 活动详情

详情页当前内嵌 `ativityJson`, `eventTicketsJson`, `formItemsJson`, `OrganizerList`。优先读取这些公开结构化变量，不从登录态私有请求猜接口。

### 基础字段

- `start`, `end`, `time_text`：绝对时间和展示文本。
- `province`, `city`, `address`, `address_hidden_until_signup`：地点。
- `mode`：根据平台城市/地址判断为 `online` 或 `offline`；平台没有明确混合枚举时不猜测 `hybrid`。
- `category`, `tags`, `summary`：主题信息。
- `capacity`, `registered`, `views`, `follows`, `status`：公开运营指标。

### 价格

- `price.lowest`, `price.highest`：票种价格区间。
- `pricing=free`：全部票种为 0。
- `pricing=paid`：全部票种大于 0。
- `pricing=mixed`：同时存在免费和收费票。
- `is_free` 仅在 `pricing=free` 时为真。
- `has_free_ticket`, `has_paid_ticket` 用于表达混合票种，避免把有一张免费票的收费活动称为纯免费。

### 报名与票种

- `requires_participant_details`, `requires_real_name`, `requires_review`, `wechat_only`, `refund_type`。
- ticket：`sn`, `title`, `price`, `status`, `quantity`, `sold`, `remaining`, `min_order`, `max_order`, `requires_review`。
- registration field：`key`, `title`, `type`, `required`, `multiple`, `options`。
- `Subitems` 在真实页面中可能是对象数组，也可能是字符串数组；解析器兼容两种结构。

## 严格筛选证据

`filter_mode=detail-verified` 表示已按详情复核。`dropped` 按原因统计：

- `city_summary`, `mode_summary`：摘要阶段已明显不符，未继续请求详情。
- `city`, `mode`, `price`, `verified`, `time`：详情阶段不符。
- `time_unverified`：详情缺少可验证时间。
- `detail_unverified`：详情获取失败，不在严格结果中冒充合格。

## 推荐

总分维度：主题 30、业务目标 15、主办方 15、地点 15、时间 10、形式与类型 10、规模 5，再减风险分。默认画像保持中性。

`profile_coverage.used` 列出实际参与判断的画像字段；`not_evaluated` 列出因缺少事实数据而没有计分的字段。分数是排序辅助，不代表真实性、质量或商业价值事实。

## 登录态读取

### `me-tickets`

按 `valid`, `incomplete`, `cancelled`, `refund` 分组。每条只含活动、时间、状态、订单数量和动作；`pii_included=false`, `order_ids_included=false`。

### `host-events`

每条含活动 ID、标题、公开 URL、时间摘要、运营指标、状态和可用动作。`current_page_only=true` 时只声称读取当前页。

### `browser-read`

含 `title`, `headings`, `actions`, `related_routes`, `form_schema`, `authenticated`, `login_required`, `sensitive`。固定 `values_included=false`。

## 状态解释

- 免费 ≠ 无审核或无个人数据。
- 已提交 ≠ 已通过；待审核必须单独标识。
- 页面打开 ≠ 登录成功。
- 按钮存在 ≠ 操作有权限或有余额。
- 点击完成 ≠ 业务成功；必须回读结果对象。
