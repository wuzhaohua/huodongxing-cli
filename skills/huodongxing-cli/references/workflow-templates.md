# 活动发现与报名模板

## 最近一周：本地线下活动

```bash
scripts/hdx search --city 杭州 -q AI --time week --mode offline --limit 20
scripts/hdx recommend --city 杭州 -q AI --time week --mode offline --limit 10
```

先搜索再推荐。推荐会抓取详情，适合只对候选活动运行。

## 本月：杭州优先、上海补充

分别搜索两个城市，按活动 ID 去重，再综合用户画像排序：

```bash
scripts/hdx recommend --city 杭州 -q AI --time month --mode offline --limit 15
scripts/hdx recommend --city 上海 -q AI --time month --mode offline --limit 15
```

不要把线上活动当作本地活动；需要线上活动时单独使用 `--mode online`。

## 重点大会核验

活动行只作为线索来源。WAIC、云栖大会等重点活动必须进一步核对主办方官网的一手报名入口、票价、截止时间和实名要求。

## 免费活动自动报名

1. 运行 `signup-plan EVENT_ID`。
2. 仅当 `policy_decision=auto_submit_if_safe` 且不存在收费、实名证件、异常营销或未知字段时继续。
3. 检查日历冲突和用户本地报名资料。
4. 使用当前 Agent 的真实登录态浏览器提交。
5. 回读成功页、订单、电子票或“待审核”。

CLI 不负责点击提交。没有浏览器能力时只返回精确 URL 和预检结果。

## 收费活动

只报告价格、票种、价值、报名截止时间与官方链接。除非用户明确确认本次购买，否则不进入支付或提交。

## 输出状态

统一使用：`强烈推荐`、`可报名`、`已报名`、`待审核`、`收费待确认`、`不建议参加`、`信息不足待验证`。
