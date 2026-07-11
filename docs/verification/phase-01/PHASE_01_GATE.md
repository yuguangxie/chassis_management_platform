# 阶段一门禁验收

## 门禁结论

**通过。** SAFE-001 至 SAFE-008、SIM-001、DBC-001 的阶段一验收条件均已有自动测试或真实 loopback 证据。P0 动态测试无失败，因此本次结论不是“阶段一未完成”。

阶段二可以启动，但继续禁止连接真实车辆。项目当前整体仍不是生产就绪状态。

## 路线图门禁逐项核验

| # | 门禁 | 结果 | 证据 |
|---|---|---|---|
| 1 | pause 后步骤不推进，resume 后继续 | PASS | `loopback_results.json` 中 `eol_pause_resume.paused_steps=1`、最终 12 步；`test_phase01_eol_lifecycle.py` |
| 2 | abort 终态保持 | PASS | `eol_abort.status=ABORTED`；后台等待后未覆盖 |
| 3 | emergency 不执行后续步骤，停车确认；超时锁存并报警 | PASS | `eol_emergency.status=EMERGENCY_STOPPED`；`stop_success`；`stop_timeout` 返回 504、`latched=true`、level 3 alarm |
| 4 | CAN1/CAN2 断开时 EOL 与控制拒绝 | PASS | `stale_online.control_after_5s.status_code=409`；`eol_start_after_5s.status_code=409` |
| 5 | simulator 停止 2 秒内离线，5 秒控制仍拒绝 | PASS | 离线检测 2.029 秒；5 秒请求 409，原因包含 `can2_online` |
| 6 | UI/API preview 与 simulator 实收一致 | PASS | bytes 均为 `[129,196,60,20,0,64,1,4]`；normal simulator 日志记录 `front=-60/rear=60/target_speed=2.0` |
| 7 | 未认证不能维护、控制或删除报告 | PASS | RBAC 结果分别为 401/403 |
| 8 | 伪造 role、x-role、用户字段无效 | PASS | body role 和 x-role 均 403；EOL 存储 operator 为 token 主体 `dev-operator` |
| 9 | UDP 截断包不得与下一包拼接 | PASS | malformed 增加 1，RX 仅增加 1；单元测试验证整包丢弃 |
| 10 | P0 全部关闭，且不接真实车辆 | PASS | SAFE-001~005 关闭；全部动态地址为 `127.0.0.1` |

## 目标 Issue 关闭说明

| Issue | 状态 | 实施结果 |
|---|---|---|
| SAFE-001 | CLOSED | EOL 保存真实 Task、暂停事件和终止令牌；abort/emergency 取消并保护终态。 |
| SAFE-002 | CLOSED | EOL start/resume/步骤边界统一调用 SafetyInterlockService；CAN1/CAN2 离线时 409。 |
| SAFE-003 | CLOSED | RX 使用原始接收时间；有界队列；过期与积压帧不进入应用且不刷新在线。 |
| SAFE-004 | CLOSED | Bearer token 服务端角色映射；默认非 admin；body/header 角色完全不参与授权。 |
| SAFE-005 | CLOSED | 急停停止普通周期发送，锁存后周期下发零速/制动，等待可信反馈；失败保留锁存。 |
| SAFE-006 | CLOSED | preview、field notes、TxScheduler 和 simulator 对比共用 `encode_control_121`。 |
| SAFE-007 | CLOSED | `/control/status` 与 `/control/interlock-status` 直接返回实时 evaluate 结果。 |
| SAFE-008 | CLOSED | 安全停车具备超时、重试、速度/制动反馈确认、审计与严重告警。 |
| SIM-001 | CLOSED | dev/mock 配置固定 loopback；production 仅显式 profile 可加载非 loopback。 |
| DBC-001 | CLOSED | UDP datagram 必须为非空 `13*n`；TCP 单独使用 stream buffer。 |

## 测试结果

- `python -m pytest backend/tests -q`：62 passed。
- `python -m pytest simulator/tests -q`：3 passed，且从项目根可执行。
- `npm run typecheck`：通过。
- `npm run build`：通过，保留 bundle size 警告。
- `verify_phase01_loopback.py`：`all_passed=true`。

## 危险路径证据摘要

- 安全停车成功：3 次以内发送后确认 `speed_kmh=0.0`、`brake=true`。
- 急停成功：停止普通发送并反馈确认，`emergency_stop=true` 保持至二次确认释放。
- 制动失败：`brake_fail` 返回 HTTP 504、`SAFE_STOP_TIMEOUT`、`latched=true`、Critical(level 3) alarm。
- 反馈缺失：单元测试返回 `FEEDBACK_MISSING`，急停和停车锁存保持。
- 通道断开：2.029 秒判离线，5 秒后控制和 EOL start 均结构化 409。
- 越权：未认证 401；viewer 控制、engineer 伪造 admin、operator 伪造 x-role 均 403。

## 未关闭但不属于阶段一的问题

- EOL-001/EOL-002：真实 YAML 步骤语义和故障 profile 正确 FAIL，属于阶段二。
- DB/报告/业务 Mock 与持久化问题属于阶段二和阶段三。
- 1000fps 10 分钟、WebSocket 节流、日志轮转和 bundle 拆分属于阶段四。
- 生产 token 供应、轮换、安装包密钥管理和封闭台架验证属于阶段五。

这些遗留项仍阻止连接真实车辆和生产使用，不得把阶段一通过解释为生产准入。
