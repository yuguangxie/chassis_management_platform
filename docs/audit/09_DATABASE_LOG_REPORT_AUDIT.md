# 数据库、日志与报告审计

## SQLite

- 11 个要求表全部存在，`integrity_check=ok`，journal_mode=WAL，主要 session/frame/signal/step 索引存在。
- 审计独立连接显示 foreign_keys=false；生产 Database 初始化脚本执行 `PRAGMA foreign_keys=ON`，但该设置只对单连接有效。
- 业务行数：test_sessions/test_steps/test_assertions/raw_can_frames/decoded_signals/signal_statistics/alarms/reports/software_versions 全部 0。
- operator_actions=206，config_history=53，说明仅配置/部分操作审计实际落库。
- Database 每次 `execute` 立即 commit，无事务 context；shutdown 没有 close。

完整 schema、列、索引与行数：[database_audit.json](evidence/tests/database_audit.json)。

## 日志

- RawLogWriter 每帧同步 open/append/close `data/logs/raw_can_current.csv`。
- 审计时该单文件约 119.08MB；无轮转、压缩、会话切分和最大空间控制。
- SignalLogWriter 是 no-op；解码信号未落 CSV/Parquet。
- 应用日志存在，但 trace_id 不统一；高频 backend runtime log 达数 MB。

## 报告

实际生成 15 JSON、15 DOCX、15 PDF；未生成 CSV。抽检 normal PASS 和 low-SOC FAIL：

| 检查 | PASS 报告 | FAIL 报告 |
| --- | --- | --- |
| JSON 可打开 | 是 | 是 |
| DOCX 可打开 | 是，但中文乱码 | 是，但中文乱码 |
| PDF 可打开 | 是，1页/1526B | 是，1页/1524B |
| PDF 中文 | 方块/不可读 | 方块/不可读 |
| software_version | 缺失 | 缺失 |
| dbc_hash | 缺失 | 缺失 |
| config version/hash | 缺失 | 缺失 |
| operator | 有 | 有 |

证据：[report_validation.json](evidence/tests/report_validation.json)、[PASS 渲染](evidence/screenshots/current/generated_normal_pass_report_page1.png)、[FAIL 渲染](evidence/screenshots/current/generated_bms_low_soc_report_page1.png)。

报告 API 的预览是固定模板；打印、导出、重新生成、打开目录为 Stub；报告表没有记录，目录扫描结果不能可靠关联会话。
