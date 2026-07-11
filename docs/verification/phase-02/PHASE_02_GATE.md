# 阶段二门禁结论

审定时间：2026-07-10 15:37:02 +08:00  
范围：真实 EOL 与全链路持久化  
网络边界：仅 `127.0.0.1` loopback  
真实车辆：未连接

## 前置门禁

阶段一门禁已通过。依据为 `docs/verification/phase-01/PHASE_01_GATE.md` 及其 loopback、stale-online、RBAC、急停和安全停车证据。阶段二没有放宽阶段一联锁，也没有启用 `0x123`、`0x126`、CANopen NMT 或 PID debug。

## Profile 结果

| Profile | 预期 | 实际 | 失败步骤 | 步骤数 | 停车结果 | Session ID | Report ID | 结论 |
|---|---|---|---|---:|---|---|---|---|
| normal_pass | PASS / 12 步 | PASSED | - | 12 | - | EOL-9087E04A67CA | 33a907fd | 通过 |
| bms_low_soc | BMS 步骤 FAIL | FAILED | bms_check | 3 | STOP_CONFIRMED | EOL-23651704E26A | 88b91a16 | 通过 |
| warning_fault | 告警复查 FAIL 并停车 | FAILED | alarm_recheck | 11 | STOP_CONFIRMED | EOL-25FADA061DF9 | 735dd250 | 通过 |
| steering_no_response | 转向步骤 FAIL | FAILED | steering_check | 8 | STOP_CONFIRMED | EOL-52F8E0E7E318 | 3dc78ec1 | 通过 |
| brake_fail | 制动步骤 FAIL | FAILED | brake_stop_check | 10 | SAFE_STOP_TIMEOUT，保持锁存 | EOL-CCE9FBEBCAB2 | 6bf8e0b6 | 通过 |

`brake_fail` 的安全停车因制动反馈持续缺失而超时，系统没有错误确认停车，保持锁存并生成严重告警。这是预期的保守失败路径。

## 数据关联

| Profile | sessions | steps | assertions | raw frames | decoded signals | statistics | alarms | reports | actions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| normal_pass | 1 | 12 | 26 | 5,939 | 48,992 | 19 | 0 | 4 | 5 |
| bms_low_soc | 1 | 3 | 10 | 200 | 1,570 | 19 | 1 | 4 | 3 |
| warning_fault | 1 | 11 | 16 | 420 | 3,282 | 19 | 2 | 4 | 3 |
| steering_no_response | 1 | 8 | 19 | 3,182 | 26,237 | 19 | 0 | 4 | 3 |
| brake_fail | 1 | 10 | 22 | 7,262 | 59,689 | 19 | 1 | 4 | 3 |

每个 profile 均生成并打开验证了 JSON、DOCX、PDF、CSV 四类报告记录。报告包含结果、步骤、软件版本、DBC hash、配置 profile、测试计划 ID 和版本。

## 异常与生命周期门禁

| 场景 | 实际结果 | 结论 |
|---|---|---|
| CAN1/CAN2 启动前断开 | `409 INTERLOCK_BLOCKED` | 通过 |
| 运行中断开 CAN | `FAILED`，失败于 `low_speed_drive_check`；停车通道离线时保持安全锁存 | 通过 |
| DBC 未加载 | 启动诊断后首步 `power_on_self_check` FAIL，未进入运动步骤 | 通过 |
| 数据库不可写 | `409 INTERLOCK_BLOCKED` | 通过 |
| pause / resume | pause 期间步骤不推进，resume 后继续 | 通过 |
| abort | 终态保持 `ABORTED`，后台任务未覆盖 | 通过 |
| emergency-stop | 终态保持 `EMERGENCY_STOPPED`，停车确认成功 | 通过 |
| 同工位第二会话 | `409` 拒绝 | 通过 |
| 进程异常重启 | RUNNING 会话恢复为 `ABORTED`，原因 `service restart recovery` | 通过 |
| 步骤/断言事务故障 | 事务回滚，不留下半完成步骤 | 通过 |
| EOL WebSocket | `test.session_progress` 使用真实 session ID、12 步及真实终态 | 通过 |

## 自动化测试

- 后端：`77 passed, 5 warnings`，退出码 0。
- 仿真器：`3 passed`，退出码 0。
- 前端类型检查：通过。
- 前端构建：通过，退出码 0；存在约 1.395 MB 主 bundle 警告，不属于阶段二阻塞项。
- 最终检查后 8234、8235、8800、12341、12342 均无残留监听进程。

## 问题关闭

本阶段目标问题 `EOL-001`、`EOL-002`、`DB-001`、`DB-003`、`DB-004`、`DBC-002` 均达到本阶段验收标准，关闭依据见 `issue_closure.csv`。

## 残余限制

- Parquet 写入策略已实现为可选路径，但当前配置使用 CSV，且未安装可选 `pyarrow`，因此 Parquet 实际文件写入未验证。
- 未进行真实车辆、真实 USR-CAN115、封闭台架或生产 profile 验证。
- 未做多进程并发、长时间压力、日志轮转和磁盘耗尽测试。
- FastAPI `on_event` 有弃用警告；前端主 bundle 超过 500 kB。

## 门禁判定

**阶段二门禁通过。** `steering_no_response`、`brake_fail`、断链、DBC 未加载和数据库不可写均未产生 PASS；正常 profile 完成 12 步并形成可追溯持久化闭环。

该结论仅允许进入路线图阶段三，不构成生产就绪或连接真实车辆的许可。
