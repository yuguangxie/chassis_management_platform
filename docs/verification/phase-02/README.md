# Phase 02 Verification

本目录保存《PROJECT_FOLLOWUP_ROADMAP》阶段二“真实 EOL 与全链路持久化”的独立验证证据。验证时间为 2026-07-10，运行边界为 `dev` 配置、Python simulator 和 `127.0.0.1` loopback；未连接真实车辆，也未向 `[REDACTED_CAN1_GATEWAY]/99` 发送数据。

## 结论

- 阶段一前置门禁：已通过，依据 `../phase-01/PHASE_01_GATE.md`。
- 阶段二门禁：通过，详见 [PHASE_02_GATE.md](PHASE_02_GATE.md)。
- 生产状态：仍为实验室/仿真可用，不代表允许连接真实车辆。
- 五个 profile、断链、DBC 未加载、数据库不可写、中止、急停、并发拒绝和重启恢复均有动态证据。

## 入口

- [阶段门禁](PHASE_02_GATE.md)
- [变更文件](CHANGED_FILES.md)
- [证据清单](EVIDENCE_MANIFEST.md)
- [问题关闭矩阵](issue_closure.csv)
- [机器可读结果](phase02_results.json)

## 主要证据

- `gate-final/phase02_eol_results.json`：五个 profile 和安全守卫的完整响应。
- `gate-final/summary.txt`：profile、失败步骤、停车结果、报告 ID 和数据库行数摘要。
- `database-final/restart_recovery_result.json`：异常重启后未完成会话安全终止。
- `database/report_validation_final.json`：PASS/FAIL 报告文件和数据库关联验证。
- `tests/backend_pytest_gate_final.txt`：后端 77 项测试。
- `tests/simulator_pytest_gate_final.txt`：仿真器 3 项测试。
- `tests/desktop_typecheck_gate_final.txt`、`tests/desktop_build_exit_final.txt`：前端类型检查和构建。

JSON 文件使用 UTF-8 无 BOM。Windows PowerShell 5.1 读取时应显式使用 `Get-Content -Encoding UTF8`。
