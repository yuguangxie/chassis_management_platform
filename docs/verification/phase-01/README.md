# Phase 01 Verification Evidence

审验时间：2026-07-10（Asia/Shanghai）

本目录仅对应 `PROJECT_FOLLOWUP_ROADMAP.md` 的“阶段一：安全控制与可信边界”。所有动态控制验证均使用 `127.0.0.1`、Python simulator 和 USR-CAN115 loopback；未连接真实车辆或真实 CAN 转换器。

## 结论

**阶段一门禁：通过。** 本阶段涉及的 P0 动态测试全部通过，可以开始阶段二；这不代表项目可连接真实车辆，也不代表项目达到生产就绪。

详细结论见 [PHASE_01_GATE.md](PHASE_01_GATE.md)，修改范围见 [CHANGED_FILES.md](CHANGED_FILES.md)，问题关闭状态见 [issue_closure.csv](issue_closure.csv)。

## 主要证据

- [loopback_results.json](loopback/loopback_results.json)：完整 loopback、EOL 终态、RBAC、stale-online、停车和 UDP 边界结果。
- [backend_loopback.log](loopback/backend_loopback.log)：FastAPI 动态请求与状态码日志。
- [simulator_normal_pass.log](loopback/simulator_normal_pass.log)：模拟器实际接收 0x121 的日志。
- [simulator_brake_fail.log](loopback/simulator_brake_fail.log)：制动反馈失败场景日志。
- [backend_pytest.txt](tests/backend_pytest.txt)：后端 62 项测试结果。
- [simulator_pytest.txt](tests/simulator_pytest.txt)：仿真器从项目根执行的 3 项测试结果。
- [desktop_typecheck.txt](tests/desktop_typecheck.txt)：Vue/TypeScript 类型检查。
- [desktop_build.txt](tests/desktop_build.txt)：桌面端生产构建。
- [operator_actions.json](api/operator_actions.json)：服务端认证主体写入操作审计的样例。
- [git_status_before.txt](baseline/git_status_before.txt)：项目不是 Git 工作树的基线记录。

## 复现命令

```powershell
cd chassis_management_platform

backend\.venv\Scripts\python.exe -m pytest backend/tests -q
backend\.venv\Scripts\python.exe -m pytest simulator/tests -q

cd desktop
npm.cmd run typecheck
npm.cmd run build
cd ..

backend\.venv\Scripts\python.exe scripts\verify_phase01_loopback.py `
  --output docs\verification\phase-01\loopback
```

动态脚本会自行启动和停止 FastAPI、`normal_pass` 与 `brake_fail` simulator。脚本强制设置 `CHASSIS_RUNTIME_PROFILE=dev`，并断言所有 CAN 地址均为 loopback。

## 基线差异

修改前后端测试为 30 项且全部通过，但未覆盖本阶段 P0；仿真器测试从项目根因 `ModuleNotFoundError` 无法收集。修改后后端 62 项、仿真器 3 项全部通过，且动态 loopback 脚本 `all_passed=true`。

桌面构建成功，但 Vite 仍报告主 bundle 大于 500 kB。该项属于路线图阶段四，不影响本阶段安全门禁。
