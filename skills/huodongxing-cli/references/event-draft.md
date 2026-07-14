# 活动创建草稿

## 工作流

```bash
scripts/hdx event-draft template -o event-draft.json
scripts/hdx event-draft validate event-draft.json
scripts/hdx event-draft plan event-draft.json
scripts/hdx open-route create-event
```

`template` 生成无个人数据的 JSON 骨架；`validate` 检查字段；`plan` 生成对应活动行创建页的填写区块、风险和验收项。它们都不会点击“创建活动”。

## 字段

| 字段 | 规则 |
|---|---|
| `schema_version` | 当前为 `1` |
| `title` | 至少 5 个字 |
| `mode` | `offline`、`online` 或 `hybrid` |
| `start`, `end` | ISO 8601；开始早于结束 |
| `city`, `address` | 线下或混合活动必填 |
| `online_url` | 线上或混合活动建议填写；没有时产生警告 |
| `summary` | 最多 150 字，用于分享和检索摘要 |
| `content_markdown` | 活动详情、议程、嘉宾、注意事项等正文 |
| `poster_path` | 可选本地海报路径；必须存在 |
| `visibility` | `public` 或 `private` |
| `show_address_after_signup` | 是否报名后展示详细地址 |
| `capacity` | 正整数 |
| `tickets` | 至少一个票种；价格非负、数量为正整数 |
| `registration_fields` | 报名字段数组，支持文本、多行、数字、选择、日期、邮箱、手机和附件 |
| `language` | `system`、`zh` 或 `en`，创建时按页面实际选项核对 |
| `custom_privacy` | 可选自定义隐私协议文本 |
| `support_contact` | 售后手机号和邮箱；只存放在草稿外部安全位置或受控草稿中 |

## 创建页对应区块

1. 标准/高级模板和外部链接 AI 识别；
2. 主办方、活动标题和海报；
3. 单次/重复举办、开始结束时间；
4. 线下地址、报名后显示地址、线上同步直播；
5. 亮点摘要、富文本详情和嘉宾；
6. 免费/付费票、名额、审核；
7. 报名限制与自定义字段；
8. 报名人数展示、相关推荐、默认语言；
9. 自定义隐私协议和售后联系方式；
10. 平台协议和最终创建。

## 风险门

- 付费票：确认收款账号、服务费、退款、发票和税务责任。
- 身份证/护照：确认必要性、合法依据、告知、保存范围和删除机制。
- 海报、二维码、附件和名单：确认素材与个人数据授权。
- 私密活动：匿名访问验收应为不可见；公开活动反之。
- 创建成功：必须同时验证主办方列表状态和活动详情页，草稿/审核中不能称为发布成功。
