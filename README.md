# 02-batchgate（闸序）

Batchgate — 离线作业依赖编排：作业定义 → 依赖就绪检查 → 执行/失败重试 → 产出水位与对账。

与 Feedstitch（多源 Feed 归并）主链路不同，禁止做成 Feed 解析/冲突/回看换皮。

## 启动

```bash
docker compose up --build
```

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:5200 |
| API | http://localhost:10200 |

## 主链

配置作业与依赖 → 触发一次编排 Run → 按依赖顺序执行夹具作业 → 写入尝试记录与产出水位 → 报告对账

## 编排模式：正常 vs 分区回补

| 模式 | 触发方式 | 产出写入 | 主水位 |
| --- | --- | --- | --- |
| 正常 `normal` | `POST /api/orchestrations`（无 partition） | `watermarks`（每作业一行主水位） | 推进 |
| 回补 `backfill` | `POST /api/orchestrations`，body 带 `{"partition":"2026-11-08"}` | `partition_watermarks`（按 作业×分区 记录） | **不动** |

- 回补只消费夹具 `partition_data` 中对应业务日的数据；夹具没有该分区时该作业记 `failed`，下游按依赖闸记 `skipped_dep`。
- 编排记录与尝试详情都带 `mode` / `partition`；报告的 succeeded/failed/skipped 直接由尝试记录汇总，两者必然一致。
- 主水位 `GET /api/watermarks` 与分区水位 `GET /api/partition-watermarks?partition=...` 分表分开查；刷新/重启后分区结果持久保留。
- 前端「编排台」可发起带分区的回补，「产出水位」页上下两块分别展示主水位与分区水位。

## 种子说明

- **ingest_orders**：无依赖，写出订单水位。
- **dim_customer**：无依赖，写出客户维表水位。
- **fact_order_daily**：依赖上两者成功且水位推进后才可执行（底座仅做“上游成功”检查，严格水位闸与重试预算留给 0-1 题）。

## 技术栈

Python 3.12 + FastAPI + SQLite；Vue 3 + Vite + Nginx。

## 0-1 切口（未实现）

`dep_gate` / `retry_budget` / `watermark_reconcile` / `sla_breach`
