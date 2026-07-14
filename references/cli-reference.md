# hdx 3.0 命令参考

## 全局约定

- Python 3.9+；公开命令只使用标准库。
- 数据命令支持 `--format json|csv|markdown` 和 `-o FILE`。
- JSON 为 Agent 默认；CSV 对 `= + - @` 等公式起始字符自动加前缀，降低表格公式注入风险。
- 退出码：`0` 完成，`2` 参数/网络/解析/安全门错误，`130` 用户中断。

## 诊断和能力地图

```bash
scripts/hdx --version
scripts/hdx doctor [--proxy http://127.0.0.1:3456]
scripts/hdx routes [--domain DOMAIN]
```

`doctor` 检查 Python、活动行网络、系统浏览器、CDP 代理、真实登录态和本地配置权限。以 `status=healthy|degraded|unavailable` 以及三个 `ready_*` 字段判断能力；`local_config.*.private=false` 时，使用者应把对应文件权限改为仅本人可读写。

## 搜索

```bash
scripts/hdx search --city 杭州 -q AI --time week --limit 10
scripts/hdx search --city 全国 --tag 企业服务 --price free --verified
scripts/hdx search --city 上海 --from 2026-07-14 --to 2026-07-31 --mode offline
```

筛选参数：

| CLI | 平台参数/含义 |
|---|---|
| `-q/--keyword` | `qs` |
| `--tag` | `tag` |
| `--time week` | 平台 `d=t1`；详情复核今天到本周日 |
| `--time weekend` | 平台 `d=t4`；详情复核最近周六、周日 |
| `--time month` | 平台 `d=t5`；CLI 解释为未来 30 天，不称“自然月” |
| `--from` + `--to` | 自定义闭区间，必须同时提供 |
| `--price free` | 严格模式只保留全部票种均免费 |
| `--price paid` | 保留纯收费和免费/收费混合票种 |
| `--mode offline/online` | 详情以城市和地址字段复核 |
| `--verified` | 至少一个主办方已认证 |
| `--order` | `relevance/newest/popular/participants` |
| `--page` | 搜索起始页 |
| `--limit` | 最终结果数 |

严格模式是默认值。页面推广卡片可能不遵守 `city/range/eventType`，因此 CLI 先用搜索摘要预过滤，再读取有限详情候选复核。

```bash
--candidate-limit 12   # 默认 12，最大 20
--max-pages 3          # 默认 3，最大 5
--workers 3            # 默认 3，最大 4
--no-strict            # 只信任平台参数，可能混入推广活动
```

输出包含 `filter_mode`、`candidate_count`、`dropped`、`errors` 和 `events`。严格模式下每条结果含 `detail_verified=true`。

## 详情和缓存

```bash
scripts/hdx detail EVENT_ID
scripts/hdx detail https://www.huodongxing.com/event/EVENT_ID
```

公开详情缓存到 `~/.cache/hdx/details/`，默认有效 1800 秒。使用 `HDX_CACHE_DIR` 和 `HDX_CACHE_TTL` 覆盖。缓存只保存公开活动字段，不保存账号、票券或报名资料。

遇到 `verify.huodongxing.com`、操作过于频繁、403、429 或验证码立即失败并熔断当批剩余详情请求。

## 推荐

```bash
scripts/hdx recommend --city 杭州 -q AI --time month --limit 5
scripts/hdx recommend --city 全国 -q Agent --profile ~/.config/hdx/profile.json
```

推荐沿用搜索参数、严格筛选、候选预算和并发上限。输出包含分数、等级、理由、维度、风险、置信度和画像覆盖情况。`max_travel_minutes` 在没有出发地/路程数据时明确列入 `not_evaluated`，不伪造出行分数。

## 报名预检

```bash
scripts/hdx signup-plan EVENT_ID \
  --profile ~/.config/hdx/profile.json \
  --policy ~/.config/hdx/policy.json \
  --signup-data ~/.config/hdx/signup.json
```

输出票种、价格、必填字段、字段覆盖、风险、策略来源、硬阻断、是否可自动和验收要求。只输出哪些字段已覆盖，不输出值。

以下风险在代码层禁止自动放行：收费、实名、身份证/护照、异常营销、用户排除主题、微信专属流程。必填答案缺失或混合票价也要求确认。

## 登录态读取

先按 `web-access` Skill 启动 CDP 代理并确认 Chrome 已登录。

```bash
scripts/hdx auth-status [--proxy URL]
scripts/hdx me-tickets [--proxy URL]
scripts/hdx host-events [--proxy URL]
scripts/hdx browser-read ROUTE [--event EVENT_ID] [--proxy URL]
```

- `auth-status`：只返回参与者/主办方访问能力。
- `me-tickets`：按有效、未完成、已取消、退票申请分组；不返回订单号和报名资料。
- `host-events`：返回主办方当前页活动运营摘要。
- `browser-read`：返回后台页面结构、动作、相关路由和表单 schema；不返回值。

每个命令使用自己的后台标签页并自动关闭。可用 `HDX_CDP_PROXY` 覆盖代理地址。

## 活动草稿

```bash
scripts/hdx event-draft template -o event-draft.json
scripts/hdx event-draft validate event-draft.json
scripts/hdx event-draft plan event-draft.json
```

`validate` 检查标题、时间、形式、地点、票种、名额、报名字段和本地文件；`plan` 添加页面区块、风险、精确路由和验收要求。详见 [event-draft.md](event-draft.md)。

## 路由和动作计划

```bash
scripts/hdx open-route ROUTE [--event EVENT_ID] [--print-only]
scripts/hdx action-plan ACTION [--event EVENT_ID]
```

`open-route` 只打开/打印页面，不提交。`action-plan` 返回影响、风险、精确路由、确认令牌、预检和验收；`cli_commits_directly=false` 是固定边界。

除 `publish-event`、`withdraw`、`pay` 和 `account-change` 外，动作都属于具体活动，必须提供 `--event EVENT_ID`；CLI 不允许生成对象不明确的活动级执行计划。

动作覆盖报名/取消/退票、发布/编辑/复制/删除/隐私、邀请/群发、名单新增/审核/拒绝/取消/退款/签到/标签/拉黑、刷新/置顶、渠道码/邀请码/白名单/优惠码、协作成员、支付/提领和账号安全。
