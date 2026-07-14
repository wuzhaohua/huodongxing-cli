# 活动行平台能力地图

以下能力于 2026-07-14 使用真实登录态页面验证。页面和账号套餐可能变化；以 `scripts/hdx routes` 的当前输出和 `browser-read` 回读为准。

## 实现等级

| 等级 | 含义 |
|---|---|
| `native-public` | CLI 直接读取公开 HTML/结构化变量 |
| `native-cdp-read` | CLI 经本机 CDP 在 Chrome 登录态内读取并脱敏 |
| `browser-prepare` | CLI 校验、生成计划和打开精确页面，不提交 |
| `browser-commit` | 只能在真实 UI 中确认后提交并回读 |
| `official-api-only` | 只有账号开通官方数据 API 且取得文档/授权后才实现 |

## 公共发现

| 能力 | 路由/命令 | 等级 |
|---|---|---|
| 活动搜索和筛选 | `search`, `discover` | native-public |
| 活动详情和票种 | `detail` | native-public |
| 个性化推荐 | `recommend` | native-public |
| 报名预检 | `signup-plan` | native-public + local config |
| 主办方、榜单、专题 | `organizers`, `rank`, `topics` | route/read |
| 场地、百宝箱 | `venues`, `toolbox` | external route |

## 参与者与账号

| 能力 | 路由/命令 | 风险/等级 |
|---|---|---|
| 登录状态 | `auth-status` | native-cdp-read |
| 我的票券和订单状态 | `me-tickets` | sensitive-read |
| 收藏/关注 | `me-favorites` | sensitive-read |
| 个人主页 | `me-profile` | sensitive-read |
| 账户资料 | `account-settings` | security commit |
| 手机/邮箱重绑 | `account-contact` | security commit + verification |
| 取消报名/申请退款 | `action-plan cancel-registration/request-refund` | commit/paid commit |

## 主办方全局后台

| 能力 | route | 风险 |
|---|---|---|
| 仪表盘、活动列表 | `host-dashboard`, `host-events` | sensitive-read |
| 新建线下/线上活动 | `create-event`, `create-online-event` | prepare → commit |
| 主办方主页、认证 | `host-page`, `host-authentication` | commit/security |
| 广告、短信、邮件素材、多活动关联 | `host-ads`, `host-sms`, `host-email`, `host-groups` | commit/paid/external |
| 全部用户、咨询、评价 | `host-users`, `host-comments`, `host-reviews` | sensitive-read；回复/标签为 commit |
| 发票、签约、票款、充值 | `host-invoices`, `host-invoice-requests`, `host-contract`, `host-finance`, `host-balance` | sensitive/paid/security |
| 子账号、账号管理 | `host-subaccounts`, `host-accounts` | security commit |
| 平台通知 | `host-notices` | read |

## 单活动运营

导航已验证包含：

- `event-overview`：活动概览；
- `event-edit`：编辑活动；
- `event-invite`：邀请报名；
- `event-attendees`：名单管理；
- `event-checkin`：现场验票；
- `event-collaborators`：协作成员；
- `event-settlement`：票款结算；
- `event-embed`：嵌入官网；
- `event-copy`：复制活动；
- `event-notification-records`：发送记录。

名单页已验证存在：群发通知、添加/导入名单、审核、取消/退票、导出名单、签到提示、备注、标签、拉黑、API 接口、排序。除只读结构和脱敏汇总外，均按具体动作分级；导出完整名单本身也是敏感数据导出。

## 推广与营销

| 能力 | route | 风险 |
|---|---|---|
| 一键通知 | `event-notify` | paid/external commit |
| 一键刷新 | `event-refresh` | commit，可能消耗权益 |
| 活动置顶 | `event-top` | paid commit |
| 邀请函/海报 | `event-poster` | prepare；上传素材为 commit |
| 分销管理 | `event-distribution` | commit |
| 渠道码 | `event-channel` | commit |
| 邀请码 | `event-invite-code` | commit |
| 白名单 | `event-whitelist` | sensitive commit |
| 优惠码 | `event-coupon` | paid/business commit |
| 优先审核 | `event-priority-review` | commit |

## 创建活动字段

真实创建页覆盖：标准/高级模板、外部链接 AI 识别、主办方、标题、海报、单次/多场时间、线下地址、报名后显示地址、线上同步直播、亮点、富文本详情、嘉宾、免费/付费票、名额、审核、报名限制、自定义字段、人数展示、相关推荐、语言、隐私协议、售后联系方式和平台协议。

`event-draft` 覆盖可离线校验的字段；页面专属动态设置必须在提交前回读。

## 不固化的边界

- 普通网页账号没有被本项目授权的稳定写 API。
- 页面出现“数据 API 接口”权益不等于当前账号已开通，也不等于可以逆向调用。
- 只有取得活动行官方接口文档、认证方式和授权范围后，才新增 `official-api` adapter。
- 验证码、风控、审核、支付确认和套餐限制不得绕过。
