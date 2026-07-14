# 活动行平台能力地图

## 八个域

| 域 | 主要对象 | CLI 路由/命令 | 默认风险 |
|---|---|---|---|
| 公共发现 | 活动、主办方、榜单、专题、场地 | `search`, `detail`, `recommend`, `routes --domain public` | read |
| 参与者 | 我的票券、收藏、个人主页 | `open-route me-tickets`, `open-route me-profile` | read；取消票券为 commit |
| 主办方 | 工作台、活动列表、主页、创建活动 | `open-route host-dashboard`, `open-route host-events`, `open-route create-event` | read / prepare / commit |
| 单活动运营 | 概览、编辑、邀请、名单、签到、协作者、嵌入 | `event-*` routes | read / commit |
| 营销 | 广告、短信、邮件、渠道码、邀请码、白名单、优惠码 | `event-promote`, `event-marketing` | commit，可能付费 |
| 用户 | 全部用户、咨询、评价、标签、拉黑 | `host-users`, `host-comments`, `event-attendees` | read / commit |
| 财务 | 合作签约、票款、充值、发票、单活动结算 | `host-contract`, `host-finance`, `host-balance`, `host-invoices`, `event-settlement` | read / commit / paid |
| 账号 | 账户设置、子账号、账号管理、认证 | `account-settings`, `host-subaccounts`, `host-accounts` | commit |

## 单活动管理导航

真实页面已验证存在以下能力：活动概览、编辑活动、邀请报名、推广活动、营销工具、名单管理、现场验票、协作成员、票款结算、嵌入官网。

名单管理页还包含：添加名单、审核、取消/退票、导出名单、签到提示、备注、标签、拉黑、API 接口、群发通知。它们不是同一风险级别：导出本地名单属于隐私读取；群发、审核、退票、签到、拉黑属于外部写操作。

## 创建活动字段

当前创建页覆盖：主办方、公开/私密、海报、单次/多场时间、线下地点/线上同步、亮点、富文本详情、嘉宾、免费/付费票、总名额、报名字段、实名制、报名限制、人数展示、相关推荐、语言、隐私协议、售后联系方式。

创建页的“保存”和“创建活动”都可能改变平台状态。AI 导入链接或图片会上传外部内容；使用前确认资料授权。

## 能力实现层级

1. `native-public`：公共 HTML 中的活动列表和详情结构化变量，稳定性最高。
2. `browser-read`：CLI 解析精确路由，由 `web-access` 在用户登录态浏览器中读取可见状态。
3. `browser-commit`：最终写入通过真实 UI 完成。CLI 负责路由、预检、确认提示和验收，不伪装成不存在的官方 API。

如企业账号开通“数据 API 接口”，应单独获取官方接口文档、认证方式和授权范围，再新增 API adapter；不要从页面请求反推并固化私人接口。
