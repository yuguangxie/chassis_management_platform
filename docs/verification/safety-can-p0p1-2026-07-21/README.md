# 软件安全联锁与 CAN P0/P1 验证证据

## 证据身份与边界

- 日期：2026-07-21（Asia/Shanghai）
- 基线 commit：`3c6c838d1a2275d0b0d463ad3f04ac62293dfa0e`
- 交付状态：基线之上的未提交工作树；未为本工作包创建 commit，避免混入用户已有的桌面端改动
- Runtime profile：`test`
- 网络边界：仅 `127.0.0.1` Mock/UDP 回环
- 隔离 UDP 端口基数：`42595`（最终 quality run 动态分配）
- 未访问真实 USR-CAN115、CAN 总线、车辆、执行器、PLC 或安全继电器
- 主动发送边界未扩大：仅 CAN2/0x121；未启用 0x123/0x126/NMT

## 命令与结果

| 命令 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage --artifact-dir docs\verification\safety-can-p0p1-2026-07-21\python` | PASS；backend 139 passed；simulator 3 passed |
| 后端 coverage | 78.39%，门槛 60% |
| simulator coverage | 42.98%，门槛 40% |
| `backend\.venv\Scripts\python.exe -m compileall -q backend\app simulator` | PASS |
| `npm.cmd --prefix desktop run typecheck` | PASS |
| `npm.cmd --prefix desktop run lint` | PASS，0 warning |
| `git diff --check -- backend configs desktop/src/api/types.ts simulator docs` | PASS |

后端测试出现 5 条已知弃用警告：Starlette `httpx` TestClient 兼容警告，以及 FastAPI `on_event` lifespan 迁移警告。它们不影响本次结果，但仍属于既有 P2-09。

## 证据文件

- `python/quality-manifest.json`：profile、隔离数据目录、动态端口和 suite exit code。
- `python/backend-coverage.json`：后端逐文件/逐行覆盖率。
- `python/simulator-coverage.json`：模拟器覆盖率。
- `verification_results.json`：本工作包门禁摘要。
- `CHANGED_FILES.md`：本工作包修改范围；不包含用户此前已有的桌面 UI 工作树修改。

## 关键验证映射

| 验收点 | 证据测试 |
|---|---|
| 转向/制动/心跳/quality/source/range fail-closed 与 409 详情 | `backend/tests/test_safety_can_p0p1.py` |
| production DBC 缺失/hash/车型不符 | `backend/tests/test_safety_can_p0p1.py`、`test_phase01_runtime_profile.py` |
| 标准/扩展 CAN ID、保留位、DLC、RTR、数据长度 | `backend/tests/test_usr_can115.py`、`test_phase01_can_boundary.py` |
| 非授权 UDP source 不更新在线/缓存 | `backend/tests/test_safety_can_p0p1.py` |
| Override 同人审批、作用域、过期、撤销、不可绕过 | `backend/tests/test_safety_can_p0p1.py` |
| DB/严重告警/急停/队列异常与正常 Mock 0x121 | `backend/tests/test_safety_can_p0p1.py` |
| EOL 每个运算符、边界、错误输入和窗口 | `backend/tests/test_eol_assertions_complete.py` |
| safe-stop 停止发送/保持制动策略 | `backend/tests/test_phase01_safe_stop.py` |
| simulator 源端口行为 | `simulator/tests/test_simulator.py` |

## 结论

本证据证明软件在 Mock/回环范围内通过门禁，不证明真实环境安全或可运行。P1-19 的硬件部分、物理安全链、USR-CAN115 只监听、车型标定、目标工控机时序和真实故障注入仍待完成；production 的 `hardware_validated` 应保持 `false`。
