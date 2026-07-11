# 阶段二证据清单

## 前置条件

- `baseline/phase01_gate.txt`：阶段一门禁文本快照。
- `../phase-01/PHASE_01_GATE.md`：阶段一正式门禁。

## 最终动态场景

- `gate-final/phase02_eol_results.json`：聚合结果。
- `gate-final/summary.txt`：可读摘要。
- `gate-final/<scenario>_result.json`：各 profile/guard API、会话、停车和 DB 结果。
- `gate-final/<scenario>_backend.log`：各场景 FastAPI 日志。
- `gate-final/<scenario>_simulator.log`：各场景仿真器日志。

最终 profile：`normal_pass`、`bms_low_soc`、`warning_fault`、`steering_no_response`、`brake_fail`。

最终守卫：`can_disconnected_start`、`can_disconnect_mid_session`、`dbc_unloaded`、`database_unwritable`、`lifecycle_abort`、`lifecycle_emergency_stop`。同工位并发和 pause/resume 记录在 `normal_pass_result.json`。

## 数据库与报告

- `database-final/restart_recovery_result.json`：重启恢复前后数据库记录。
- `database-final/recovery_backend_before.log`、`recovery_backend_after.log`：重启日志。
- `database/report_validation_final.json`：五个 profile 的报告记录、文件打开和追溯字段。

## 测试与构建

- `tests/backend_pytest_gate_final.txt`：77 passed，退出码 0。
- `tests/simulator_pytest_gate_final.txt`：3 passed。
- `tests/desktop_typecheck_gate_final.txt`：Vue TypeScript 检查。
- `tests/desktop_build_exit_final.txt`：Vite 构建及明确退出码 0。
- `tests/ports_after.json`：验证后端口释放情况。

## 历史迭代证据

`profiles/`、`profiles-final/`、`database/` 以及不带 `gate_final` 的测试输出保留了调试迭代过程，不作为最终门禁依据，也未删除或覆盖。

## 完整性说明

- 所有 JSON 已用 UTF-8 显式解析校验。
- `evidence_checksums.sha256` 保存最终关键证据的 SHA-256。
- 最终门禁依据优先级：`gate-final/` > `database-final/` > `database/report_validation_final.json` > `tests/*gate_final*`。
- 未采集真实车辆或真实硬件证据，且本阶段安全限制明确禁止该行为。
