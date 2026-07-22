# 软件安全联锁（P0/P1 收口基线）

更新日期：2026-07-21。本文描述当前实现，不构成真实车辆或台架准入批准。所有自动化验证仅使用 Mock 与 `127.0.0.1` 回环。

## 总体原则

- 普通 0x121 控制在任一不确定状态下 fail-closed；HTTP 控制接口返回 409。
- 主动发送仍只允许 CAN2 的 `0x121`。`0x123`、`0x126`、`0x710`、`0x715` 和 CANopen NMT 未启用。
- UI 不能绕过 `SafetyInterlockService`；一次发送和周期发送在每次发送前重新评估。
- 安全拒绝写入 `operator_actions`，包含操作、非秘密作用域、命令以及完整失败规则。
- 软件联锁和软件急停不能替代物理急停、安全 PLC/继电器或独立断能设计。

## Command-to-feedback 依赖矩阵

矩阵由 `configs/safety_interlock.yaml` 配置，Pydantic 模型为 `FeedbackDependencyMatrix`。下列是安全默认值。

| 组 | 触发条件 | 强制反馈 | 来源 | 新鲜度 | 合理值 |
|---|---|---|---|---:|---|
| base | 每个非停车 0x121 | 车辆速度、0x704 心跳、0x703 心跳 | CAN1；0x51/0x168、0x704、0x703 | 500 ms | 速度 0..51.1 km/h；心跳 0..255 |
| drive | 挡位非 N 或目标速度非零 | 实际挡位、驱动状态 | CAN1 0x51 | 500 ms | 挡位 0/1/3；驱动状态 0..3 |
| steering | 前或后转向命令非零 | 前/后转角；断连、锁止、失控、故障状态 | CAN1 0xE1、0x77 | 500 ms | 转角 -168..168；四项状态均为 0 |
| brake | `brake_enable=true` | 制动反馈、制动故障状态；同时继承 base 的速度与心跳 | CAN1 0x51、0x77 | 500 ms | 制动反馈为 bool；制动故障为 0 |

手动状态查询或 EOL 启动没有具体命令可供裁剪依赖，因此保守评估全部四组。解除急停/安全停车锁存要求 base 与 brake 组，并额外要求可信速度绝对值不超过停车阈值且制动反馈为 `true`。

### 未涉及轴/功能为何不强制依赖

具体命令未涉及的 drive、steering 或 brake 组不额外阻断，例如仅灯光/N 挡/零速/无制动命令不要求转角或制动反馈。理由是依赖必须与本次命令的危险输出存在因果关系，否则一个无关传感器会阻止关闭灯光、归零或其他降风险操作。base 组始终保留，因此任何普通命令仍要求车辆速度和两路控制器心跳可信。安全停车是独立的受限路径，仅允许 N 挡、零速、零转角和制动命令形状。

## 单条反馈的五项检查

每条反馈同时检查：

1. `present`：存在候选信号；
2. `fresh`：接收单调时钟 age 不超过配置；
3. `quality_valid`：仅接受 `quality=good`；
4. `source_valid`：通道和 CAN ID 均匹配配置；
5. `value_valid`：值为有限数/批准枚举且处于合理范围。

missing、stale、invalid、错误通道/ID、NaN/Inf 或越界均阻断。每条规则固定返回 `rule`、`label`、`current`、`threshold`、`blocking` 和 `status`，便于 API、UI 与审计复用。

## production DBC 身份

production 必须同时满足：DBC 成功加载且非 raw-only、配置了完整 64 位 SHA-256、实际 hash 完全匹配、从文件名识别的车型与批准车型匹配。缺失、hash 不符、车型不符均阻断所有普通控制与 EOL。

dev/mock/test 可以按配置进入 raw-only，但联锁结果明确返回 `profile` 与 `degraded_mode=true`，不得显示成真实硬件模式。production 还要求安全停车发送保持策略已通过硬件验证；当前提交配置的 `hardware_validated=false`，所以 production 默认仍拒绝普通控制。

## Override 边界

Override 是持久化、默认拒绝的双人授权：

- 工程师申请，管理员批准；申请人与批准人不得为同一用户；
- 精确限定一个告警、被授权用户、会话、操作、车辆和 30..900 秒有效期；
- 当前批准操作仅为 `manual`；EOL 不接受告警 Override；
- 状态为 `PENDING_REVIEW`、`APPROVED`、`REVOKED` 或 `EXPIRED`；支持管理员撤销；
- 每次周期发送都重新检查状态、有效期和全部作用域；
- 只可能放行“恰好一个已批准的严重告警”规则。

Override 永远不能绕过 DBC/hash/车型、数据库不可写、急停/安全停车锁存、CAN 离线/队列异常、关键反馈缺失/陈旧/无效/越界、控制通道或命令限值。申请、批准、撤销、成功使用及拒绝均可通过操作审计追溯；请求模型不包含 token 或秘密。

## Safe-stop 确认后策略

配置支持：

- `stop_transmission`：速度可信归零且制动可信激活后停止继续发送；当前安全默认值。
- `hold_brake_until_release`：确认后继续按 `hold_period_ms` 发送同一安全停车帧，直到人工解除。

两种策略均只在 Mock 中表达和测试。production 必须将 `hardware_validated=true` 才能进入普通控制；该标记只能在真实控制器看门狗、断网、进程崩溃、适配器断电和解除流程完成审批验证后设置。

## 当前真实环境结论

代码层软件收口不等于真实环境可运行批准。当前仍只能视为 Mock/回环可验证；没有物理急停、安全 PLC、真实 USR-CAN115 只监听证据、看门狗/保持语义、车型标定和目标工控机调度证据时，禁止连接可运动执行器。
