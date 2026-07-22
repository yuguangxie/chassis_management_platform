# 日志、归档与保留策略

应用日志写入 `<data_root>/logs/application`，Raw CAN 写入 `<data_root>/logs/raw_can`，解码信号写入 `<data_root>/logs/decoded_signals`。数据库同时保存 Raw CAN、解码信号、步骤、断言、告警和操作审计。

Raw CAN writer 只负责批量写入、按会话/日期/大小轮转和可选 gzip，不再自行删除历史文件。所有删除统一进入 retention service。

## 报告归档

`POST /api/v1/reports/{report_id}/archive` 校验报告路径和 SHA-256，在 `<data_root>/exports/report-archives` 写归档 manifest，再在同一数据库事务中写 `archived_at`、manifest hash 和操作审计。manifest 写入或事务失败会清除半成品。

归档仅表示报告已经进入允许 retention 的状态，不代表已完成异地灾备；工厂可在此基础上增加备份介质复制流程。

## Retention 操作

1. admin 调用 `/storage/cleanup/preview`；
2. 核对受保护规则、时间范围、行数和字节数；
3. 发送同一 cutoff，并附 `confirmation=CLEANUP`；
4. 轮询 `/storage/cleanup/{job_id}`；
5. 需要时调用 `/storage/cleanup/{job_id}/cancel`。

单个 Raw CAN 文件的人工删除也要求 admin、`confirmation=DELETE` 和至少两字符原因。文件先移动到 temp 隔离区；审计写入失败会恢复文件。

禁止直接删除 SQLite 行、报告目录、备份目录或 audit 表。
