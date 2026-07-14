# 活动行工作流模板

## 杭州本周线下纯免费 AI 活动

```bash
scripts/hdx search --city 杭州 -q AI --time week --mode offline --price free --limit 8
scripts/hdx recommend --city 杭州 -q AI --time week --mode offline --price free --limit 5 \
  --profile ~/.config/hdx/profile.json
```

检查 `filter_mode=detail-verified`；混合票价、线上推广卡和外地卡片不会进入最终结果。若触发频控，停止并使用已有缓存，不立即重跑。

## 未来 30 天：杭州优先、上海补充

`--time month` 表示未来 30 天，不是自然月。

```bash
scripts/hdx recommend --city 杭州 -q AI --time month --mode offline --limit 8
scripts/hdx recommend --city 上海 -q AI --time month --mode offline --limit 5
```

跨结果按活动 ID 去重。需要自然月时使用明确日期：

```bash
scripts/hdx recommend --city 杭州 -q AI --from 2026-08-01 --to 2026-08-31 --limit 8
```

## 线上活动单独发现

```bash
scripts/hdx search --city 全国 -q Agent --mode online --time month --limit 8
```

线上活动不混入本地线下清单。`city=全国` 时用 `mode` 作为主要形式条件。

## 重点大会核验

1. 用 `search/recommend` 找候选。
2. 用 `detail` 获取票价、字段、实名和审核要求。
3. 对 WAIC、云栖大会等重点活动再核对主办方官网一手入口、议程、嘉宾、截止时间和退票规则。
4. 活动行只作为线索来源时明确说明，不把聚合页当官方证明。

## 报名

```bash
scripts/hdx signup-plan EVENT_ID \
  --profile ~/.config/hdx/profile.json \
  --policy ~/.config/hdx/policy.json \
  --signup-data ~/.config/hdx/signup.json
```

只有 `auto_submit_eligible=true` 才表示可使用本地安全免费报名预授权；仍须在浏览器刷新票种和字段并验收。收费、混合票价、实名、证件、营销风险、微信流程和必填答案缺失永远需要确认或停止。

## 我的票券

```bash
scripts/hdx auth-status
scripts/hdx me-tickets
```

报告有效、未完成、已取消和退款申请数量；不输出订单号、二维码和报名资料。取消或退款先运行对应 `action-plan`。

## 主办方活动巡检

```bash
scripts/hdx host-events
scripts/hdx browser-read event-overview --event EVENT_ID
scripts/hdx browser-read event-attendees --event EVENT_ID
```

先看活动状态和可用动作，再进入名单/营销/财务。`host-events.current_page_only=true` 时不要声称覆盖全部分页。

## 创建活动

```bash
scripts/hdx event-draft template -o event-draft.json
scripts/hdx event-draft validate event-draft.json
scripts/hdx event-draft plan event-draft.json
scripts/hdx action-plan publish-event
```

最终创建前确认可见性、票种、退款、报名字段、隐私、售后联系方式和平台协议。创建后回读主办方列表与详情页。

## 统一状态词

使用：`候选`、`严格筛选通过`、`信息不足`、`可报名`、`需确认`、`已提交`、`待审核`、`已报名`、`退款申请中`、`成功`、`失败`、`未知`。不要用“页面已打开”代替业务状态。
