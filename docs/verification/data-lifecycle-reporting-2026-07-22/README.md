# 生产数据生命周期与报告闭环验证证据

## 范围与代码基线

- 工作包：P1-06、P1-07、P1-08、P1-10、P1-11。
- 验证日期：2026-07-22（Asia/Shanghai）。
- 工作树基线 commit：`3c6c838d1a2275d0b0d463ad3f04ac62293dfa0e`。
- 交付状态：当前修改位于未提交工作树；本次未创建、推送或改写 Git commit。
- 动态边界：所有数据库、备份、恢复、清理和报告测试均使用 pytest 临时目录；CAN 与 Electron 仅使用 Mock/`127.0.0.1`；打印仅使用虚拟后端。未访问真实 CAN、现场打印机或用户现有 data。

## 关键安全断言

1. 运行时只有一个 `data_root`，数据库、应用日志、原始 CAN、解码数据、报告、导出、临时、备份、打印状态、认证和活动配置目录均由固定布局推导；派生路径不能被单独改写。
2. `data_root` 在启动前完成规范化、目录包含关系、可创建、可写和最小剩余空间检查；数据库写失败、锁定、损坏或存储健康检查失败会令 `database_writable=false`，从而继续阻断运动控制。
3. SQLite schema 当前版本为 3；迁移记录名称与校验和，旧库迁移前执行在线一致性备份，失败时恢复，不把部分迁移报告为成功。
4. 备份 manifest 记录软件、schema、DBC/config/plan 版本及逐文件 SHA-256；恢复要求管理员、精确确认、manifest/hash/integrity 校验、无活跃检测会话，并先保留回滚副本。
5. 清理默认只 dry-run；未归档报告、活跃检测会话、全部认证会话与操作审计受保护。执行要求管理员和精确确认，使用批事务、进度、取消、文件隔离及失败回放。
6. 打印必须先得到 PDF 预览确认；生产 profile 禁止虚拟打印后端。任务持久化 spooler job id、状态、操作者与报告 hash，并支持取消和重试。
7. PDF 使用独立的 ReportLab 生成链路，不把 DOCX 改名为 PDF；若配置 DOCX→PDF 转换器但依赖缺失，启动/打包检查会给出可操作错误并 fail-closed。

## 验证命令与结果

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量与覆盖率 | `cd backend; python -m pytest -q --cov=app --cov-report=term-missing` | PASS：174 passed；总覆盖率 79%；仅 FastAPI 生命周期弃用告警 |
| Simulator | `python -m pytest simulator/tests -q` | PASS：3 passed |
| 数据生命周期/API 定向用例 | 纳入上述后端全量：`test_data_lifecycle.py`、`test_storage_lifecycle_api.py` | PASS：新/旧库迁移、迁移失败恢复、中文/空格路径、权限/低空间、锁/损坏、hash 篡改、恢复、清理保护/取消/失败回放、虚拟打印状态、转换依赖 |
| 四格式报告回归 | 纳入上述后端全量：`test_pass_and_fail_reports_are_complete_readable_and_previewed` | PASS：JSON、DOCX、PDF、CSV；PASS/FAIL 报告、内容、hash 与 PDF 预览均验证 |
| 报告依赖 | `python scripts/check_report_dependencies.py` | PASS：原生 PDF/DOCX 依赖 ready；未配置时不要求外部转换器 |
| OpenAPI/角色矩阵 | `python scripts/generate_api_docs.py` | PASS：生成 `docs/openapi.json` 和 `docs/api-authorization-matrix.csv`，150 个 HTTP 操作 |
| 前端 lint | `cd desktop; npm.cmd run lint` | PASS |
| 前端单测与覆盖率 | `cd desktop; npm.cmd run test` | PASS：13 files，35 tests；58.25% statements，60.73% lines |
| 前端类型检查 | `cd desktop; npm.cmd run typecheck` | PASS |
| 前端生产构建 | `cd desktop; npm.cmd run build` | PASS；只有 Vite chunk-size 提示 |
| Bundle 预算 | `cd desktop; npm.cmd run test:bundle` | PASS：gzip 总计 506480 bytes |
| Electron 回环 E2E | `cd desktop; npm.cmd run test:e2e` | PASS：Electron v43.1.0，11 页面×2 视口、22 截图；0 非回环请求；会话、刷新、重启和 stale 联锁断言通过 |
| 工作树格式检查 | `git diff --check` | PASS；仅 Git 的 LF→CRLF 环境提示，无空白错误 |

Electron 的机器可读输出位于相邻历史 Phase-05 E2E 证据目录的 `e2e-summary.json`；本次输出明确记录 `boundary=127.0.0.1 loopback only`、`nonLoopbackRequests=0` 和 `passed=true`。

## 本工作包主要改动文件

- 路径与存储：`backend/app/core/paths.py`、`backend/app/core/logging.py`、`backend/app/storage/database.py`、`backend/app/storage/migrations.py`、`backend/app/storage/lifecycle.py`、`backend/app/storage/schema.sql`、`backend/app/storage/telemetry.py`、`backend/app/storage/raw_log_writer.py`、`backend/app/storage/signal_log_writer.py`。
- 生命周期集成与 API：`backend/app/services/lifecycle.py`、`backend/app/services/app_state.py`、`backend/app/services/history_service.py`、`backend/app/api/storage.py`、`backend/app/api/config.py`、`backend/app/api/reports.py`、`backend/app/api/can.py`、`backend/app/api/alarms.py`、`backend/app/api/signals.py`、`backend/app/api/models.py`、`backend/app/api/router.py`。
- 报告与打印：`backend/app/reports/generator.py`、`backend/app/reports/service.py`、`backend/app/reports/printing.py`、`backend/app/reports/dependencies.py`、`scripts/check_report_dependencies.py`。
- 配置与 UI：`.env.example`、`configs/storage_config.yaml`、`configs/report_config.yaml`、`desktop/src/api/types.ts`、`desktop/src/stores/reports.ts`、`desktop/src/stores/settings.ts`、`desktop/src/pages/ReportManagementPage.vue`、`desktop/src/pages/SystemSettingsPage.vue`、`desktop/src/mocks/fallbackData.ts`、`desktop/src/mocks/systemSettings.ts`。
- 测试：`backend/tests/test_data_lifecycle.py`、`backend/tests/test_storage_lifecycle_api.py` 及为新打印确认/固定路径合同调整的既有报告和系统设置测试。
- 文档：`docs/DATA_LIFECYCLE.md`、`docs/DATABASE_AND_MIGRATIONS.md`、`docs/LOGGING_AND_RETENTION.md`、`docs/REPORTING_AND_PRINTING.md`、`docs/DEPLOYMENT.md`、`docs/API.md`、`docs/CONFIGURATION.md`、`docs/TESTING.md`、`docs/UI_IMPLEMENTATION_NOTES.md`、`docs/20_risk_and_open_questions.md`、`docs/openapi.json`、`docs/api-authorization-matrix.csv`。

## 仍需现场/硬件确认

- 在目标 Windows 工控机上安装并验证 pywin32，使用真实受支持打印机完成 spooler job 状态、缺纸、离线、取消和重试验收；本次只验证虚拟后端。
- 若现场要求 DOCX→PDF 转换，需选定并随包安装 LibreOffice 或批准的 Word 自动化组件，再运行依赖检查和中文字体/分页验收；当前默认使用独立原生 PDF，不依赖转换器。
- 用生产服务账户验证目标磁盘 ACL、杀毒/备份软件锁竞争、实际最低剩余空间阈值、数据库恢复耗时和批量 retention 吞吐。
- 在正式投产前执行一次隔离环境的备份恢复演练，并由管理员核对 DBC/config/plan 版本与报告归档策略。
- 本工作包没有验证真实 CAN 或车辆运动行为，也没有扩大主动发送白名单。
