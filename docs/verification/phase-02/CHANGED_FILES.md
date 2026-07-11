# 阶段二变更文件

当前目录不是 Git 工作区，无法通过 commit diff 自动生成清单。以下清单按本阶段实际编辑记录整理。

## 配置与模型

- `configs/test_plan.yaml`：12 步 YAML 测试计划、动作、采样、断言、超时和失败策略。
- `backend/app/eol/models.py`：Pydantic 测试计划、动作、人工步骤和断言模型。
- `backend/app/eol/plan_loader.py`：测试计划加载、校验和阈值引用解析。
- `backend/pyproject.toml`：可选 Parquet 依赖组。

## EOL 执行与 API

- `backend/app/eol/engine.py`：YAML 驱动的 12 步执行器、生命周期、并发、人工步骤、停车和报告。
- `backend/app/eol/assertions.py`：来自 SignalStore 的时效、质量、来源感知断言。
- `backend/app/api/eol.py`：真实 session dashboard、生命周期和人工确认 API。
- `backend/app/control/safety_interlock.py`：EOL 诊断与运动阶段统一安全判定。
- `backend/app/control/tx_scheduler.py`：EOL 运动发送期间持续联锁复核。

## 信号、DBC 与仿真

- `backend/app/services/signal_store.py`：timestamp、quality、source CAN ID/channel 和采样窗口。
- `backend/app/dbc/service.py`：RX-only 信号入库、0x102 unsigned bool/bitmap、反馈语义修正。
- `backend/app/api/can.py`：0x102 监控详情读取真实解码位。
- `simulator/can_frame_simulator.py`：档位、灯光、制动和故障 profile 反馈。

## 数据库、日志与报告

- `backend/app/storage/schema.sql`：会话追溯和断言来源字段。
- `backend/app/storage/database.py`：WAL、外键、事务、回滚和关闭。
- `backend/app/storage/uow.py`：session Unit of Work、同工位占用、原子步骤和恢复。
- `backend/app/storage/raw_log_writer.py`：按 session 批量原始 CAN CSV。
- `backend/app/storage/signal_log_writer.py`：按 session 批量信号 CSV/可选 Parquet。
- `backend/app/storage/telemetry.py`：有界异步持久化队列和批处理。
- `backend/app/reports/generator.py`：PASS/FAIL JSON、DOCX、PDF、CSV 和 traceability。
- `backend/app/services/lifecycle.py`：服务启动、恢复、writer/telemetry drain 和 DB close。
- `backend/app/services/app_state.py`：UoW、telemetry 和 writer 状态。
- `backend/app/services/audit.py`：EOL operator action 的 session 关联。
- `backend/app/websocket/manager.py`：无订阅者时避免无效广播处理。

## 前端最小接入

- `desktop/src/api/types.ts`：EOL 步骤支持真实 `SKIPPED` 状态。

## 测试与验证脚本

- `backend/tests/test_phase01_eol_lifecycle.py`
- `backend/tests/test_phase02_plan_persistence.py`
- `backend/tests/test_phase02_signal_dbc.py`
- `backend/tests/test_phase02_engine_guards.py`
- `backend/tests/test_phase02_eol_api.py`
- `scripts/verify_phase02_eol.py`
- `scripts/verify_phase02_recovery.py`
- `scripts/verify_phase02_reports.py`

## 证据文档

- `docs/verification/phase-02/README.md`
- `docs/verification/phase-02/PHASE_02_GATE.md`
- `docs/verification/phase-02/CHANGED_FILES.md`
- `docs/verification/phase-02/EVIDENCE_MANIFEST.md`
- `docs/verification/phase-02/phase02_results.json`
- `docs/verification/phase-02/issue_closure.csv`
- `docs/verification/phase-02/evidence_checksums.sha256`
