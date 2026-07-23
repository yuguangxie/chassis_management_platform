# 后续整改 Backlog 与工作建议

## 1. 执行原则

1. P0 软件问题未关闭前，不进入真实 CAN。
2. 每个安全修复先加失败测试，再实现；不通过 UI 绕开后端真源。
3. 每个 release candidate 必须来自 clean commit；SBOM、hash、manifest、安装证据必须引用同一 commit。
4. 真实验证按“无 CAN→只监听→断能静态→封闭低速”逐级升级，任何失败回退上一门禁。
5. 默认继续 Mock/127.0.0.1；CAN2 仅 0x121，CAN1 和 0x123/0x126/NMT 不开放。

## 2. P0 软件收口

### P0-01 production 配置单一权威（M）

范围：`backend/app/api/config.py`、configuration models/service/diagnostics、Network/System Settings、API 类型与测试。

工作：

- production 下 `PUT /config/channels`、restore-defaults 直接返回结构化 409，例如 `SIGNED_CONFIG_REQUIRED`。
- dev/mock/test 仍只允许 loopback，并保留草稿/apply/rollback体验。
- production Network 页面只读展示 endpoint/诊断；修改动作跳入签名包 import→dry-run→diff→apply。
- 签名 apply 后构造 manager 必须带 `on_can_security_event`。
- apply 健康检查包含 bind、transport、批准来源在线、DBC、data_root/DB、控制 idle；失败恢复 old manager/config/active package/callback。
- 删除/拒绝 `allow_tx` 等未知误导字段；配置 model `extra='forbid'`。

验收：production 所有未签名通道变更被拒绝且写审计；CAN1 仍锁定、CAN2 whitelist 仍 `{0x121}`；未授权 UDP source 在重配后仍告警但不更新缓存。

### P0-02 控制审计原子性（L）

范围：audit service、database migration、control/safe-stop/EOL/override、storage interlock、测试和文档。

工作：

- 新增 `control_intents`/outbox：PENDING、AUTHORIZED、SENT、CONFIRMED、FAILED、AUDIT_FAILED。
- 在发送前事务写入 principal、session/vehicle、command hash、safety evaluation、trace_id 和 UTC 时间。
- 发送结果与审计状态更新；更新失败时锁存 DB fault、停止 periodic、触发受限 safe-stop/报警，不返回完整成功。
- 安全拒绝、override、emergency/release 同样必须可追溯。
- 日志不得记录 token/secret，command 内容按最小必要原则。

验收：数据库在 intent 前失败则 409 且无 TX；发送后状态更新失败则能证明发送事实、进入 fail-closed 且 API 不谎报成功；重启可恢复/关闭未决 intent。

### P0-03 hardware acceptance artifact（L，需现场团队）

工作：

- 定义 pydantic schema：artifact version、station、vehicle series、controller/firmware、DBC/config/plan/release hash、safe-stop policy、physical safety checklist、test evidence hashes、approver pair、valid_from/to、revocation。
- 使用独立受控签名，不允许普通配置签名 key 自行生成硬件批准。
- SafetyInterlock production 普通运动要求 artifact valid 且所有 hash/工位/车型匹配。
- UI 仅展示状态和原因，不提供单人“开启硬件已验证”开关。

验收：missing、签名错、过期、撤销、车型/工位/release/hash 不符均 409；同人审批拒绝；无法 override。

### P0-04 当前版本正式发行闭环（M，需证书）

工作：审查并提交当前 UI 改动；运行远程 Windows CI；从 clean commit 构建正式签名 installer；生成同源 SBOM、漏洞报告、SHA-256、manifest；独立普通用户干净 VM 安装/升级/回滚/卸载。

验收：Authenticode valid、publisher/时间戳可信；manifest dirty=false 且 commit 与 CI/installer 一致；首次启动无 simulator、无现场连接、控制 409；卸载数据策略符合文档。

## 3. P1 生产功能收口

### P1-01 真实追溯输入（M）

- 删除 production 的 demo 默认 chassis/VIN/serial/operator/station。
- Auto Test 增加扫码/工单输入、确认和重复件策略；operator 永远来自 principal，station 来自签名配置。
- VIN/底盘/序列号/车型/plan schema、唯一性和工单绑定由后端校验。
- 报告、CAN source session、历史、审计使用同一 session identity。

### P1-02 运行元数据真实性（S）

- 移除 CAN `S20260401-001` 默认值。
- System Settings 从 `state.config.config_version/test_plan_version`、实际 DBC status、release manifest 读取。
- build time 不得使用请求时间；Node packaged renderer 应显示“不适用/构建依赖版本”或 manifest 值。
- DBC unavailable 时 hash/count/loaded_at 使用 null/0/“未知”，不能显示 48/312 固定值。

### P1-03 TCP transport（M/L）

两种合法方案二选一：

1. 完成 reconnect/backoff/half-open/状态机、取消、队列策略和 E2E；或
2. 在 production schema 和 UI 明确禁止 TCP，只保留 UDP，直到实现完毕。

禁止以当前一次性连接实现宣称 TCP production-ready。

### P1-04 通道语义与真实网卡诊断（M）

- `enabled` 明确为收发 transport 启用；`control_enabled` 只表示唯一 control channel；active TX policy 只读且服务端固定。
- 校验 Windows adapter 名称、index、MAC、bind IP；配置漂移或 IP 不在该 adapter 时 preflight 失败。
- Network 显示 transport connected、approved source online、last frame age、unauthorized count，不显示伪 ping。

### P1-05 日志/retention/压缩（M）

- 使用 Rotating/TimedRotating handler，写入 data_root/logs，压缩与保留可配置。
- 修复 `compress_rotated`/`compress_after_days` schema；拒绝未知字段。
- 将 raw、decoded、reports、exports、temp、backup、app log 保留策略接入 dry-run/job；保留 audit、活跃会话、未归档报告。
- production 自动任务默认可只生成建议/dry-run；真正删除仍需管理员确认，除非组织批准无人值守策略。

### P1-06 大数据与恢复（M）

- Parquet 分区追加或 production 禁用；执行 8～24h/1000fps 压测。
- 大 SQLite、文件锁、杀毒隔离、磁盘满、断电、migration failure、backup/restore 演练。
- 指标：队列 drop=0（批准负载内）、内存稳定、周期 jitter 达标、恢复时间/恢复点满足目标。

### P1-07 真实 DBC/EOL 质量系统（L，需车辆/质量团队）

- 每车型/固件的 DBC hash、信号语义、周期、范围、阈值、test plan 和兼容矩阵。
- 金样/坏样、重复性/再现性、误判/漏判、量产节拍和报告抽查。
- 只有批准版本可进入 signed config；现场变更走 change control。

### P1-08 真实打印与报告批准（M，需现场资产）

- 目标打印机普通用户测试；默认/指定、脱机、卡纸、取消、重试、重启后 job 状态。
- 中文字体、1366/打印预览、纸张、页码、签章、FAIL 高亮、hash 一致。
- 质检批准模板版本并纳入 report/release manifest。

## 4. P2 工程质量改进

- production renderer 不加载逼真 fallback 数据，Mock profile 才允许示例。
- 扩大前端 coverage include；为 pages/stores/router/http 增加行为测试。
- 为 control/eol/can/config/ws/tx scheduler 补异常分支，安全关键模块单独设更高门槛。
- 优化 ECharts tree-shaking/懒加载，给 gzip 预算留余量。
- FastAPI 迁移 lifespan，消除 deprecation warnings。
- 给历史审计加 superseded 标识，统一当前审计索引。
- 把 runtime env 与 verification-only token/env 文档拆分。
- 逐项实现 disabled UI 控件；若业务价值不足可正式移除，而不是永久占位。

## 5. 建议迭代顺序

| 迭代 | 内容 | 进入条件 | 退出条件 |
|---|---|---|---|
| R1 | P0-01、P0-02、P1-02、通道语义 | 当前 Mock 基线通过 | 全测试/回环 E2E；production 未签名变更与 audit fault 注入通过 |
| R2 | hardware artifact、追溯输入、TCP决策、日志/retention | R1 clean commit | signed config/acceptance/identity/long-run 软件门禁通过 |
| R3 | clean RC、正式签名 installer、独立 VM | R2 remote CI | 同 commit 的 SBOM/hash/install/upgrade/rollback 全通过 |
| H1 | USR-CAN115 只监听 | R3 + 现场配置批准 | 源校验/DBC/拔线/异常帧/防火墙通过，无 TX |
| H2 | 断能静态安全台架 | H1 + physical safety | 急停/PLC/watchdog/safe-stop/故障注入通过 |
| H3 | 封闭低速 | H2 安全签字 | 边界/失联/制动/转向/驱动及终止条件通过 |
| P1 | 产线试点 | H3 + 质量批准 | GR&R、节拍、打印、追溯、备份恢复通过 |

## 6. 工作组织建议

- 安全/控制 owner：P0-02、P0-03、硬件测试设计。
- 平台/后端 owner：P0-01、P1-01～06、API/schema/migration。
- Desktop owner：production Network/Settings UX、追溯输入、状态真实性。
- Release owner：clean commit、CI、签名、SBOM、安装/升级。
- 车辆/CAN owner：DBC/firmware/USR-CAN115/反馈阈值。
- 质量/产线 owner：EOL plan、GR&R、报告模板、SOP、放行签字。

安全与生产放行不应由单一开发者独立批准。

## 7. 每个工作包的 Definition of Done

- 有明确 threat/safety impact 和不变边界。
- Pydantic/TypeScript 类型、API/OpenAPI 和错误码一致。
- 权限、操作审计、失败回滚和 UTC ISO8601 完整。
- backend unit/integration、frontend unit/typecheck/lint/build/bundle、Electron E2E 通过。
- 只用临时目录、Mock/回环进行软件验证；硬件测试单独受控。
- 文档、风险、配置示例和 verification 证据更新。
- commit clean；CI、artifact、manifest、hash 指向同一 commit。
- 不包含账号、token、secret、现场 IP、bootstrap 凭据或用户运行数据。
