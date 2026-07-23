# 后续完整实施 Prompt

以下 Prompt 面向下一轮 Codex/开发实施，目标是先关闭本审计发现的软件 P0/P1，并形成可进入真实 CAN“只监听”验收的干净 release candidate。它不授权真实车辆运动测试。

```text
你正在维护“低速无人车线控底盘生产下线管理平台”。请基于当前仓库关闭 2026-07-23 完整审计中的软件 P0/P1，形成可追溯、可签名、可进入真实 CAN 只监听验收的 Windows release candidate。

开始前必须完整阅读：
1. 根 AGENTS.md；
2. docs/current_audit_2026-07-23/00_AUDIT_INDEX.md；
3. docs/current_audit_2026-07-23/01_FULL_PROJECT_AUDIT.md；
4. docs/current_audit_2026-07-23/02_MODULE_AND_FUNCTION_COMPLETION.md；
5. docs/current_audit_2026-07-23/03_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md；
6. docs/current_audit_2026-07-23/04_REAL_ENVIRONMENT_READINESS.md；
7. docs/current_audit_2026-07-23/05_SECURITY_DATA_DEPLOYMENT_FINDINGS.md；
8. docs/current_audit_2026-07-23/06_TEST_AND_EVIDENCE.md；
9. docs/current_audit_2026-07-23/07_REMEDIATION_BACKLOG.md；
10. backend config/configuration/control/safety/audit/CAN/EOL/storage/logging，desktop Network/Auto Test/CAN/System Settings/router/stores/api，Electron packaging/sidecar，相关测试与现有 verification。

开始实现前：
- 运行 git status --short、git diff --stat、git diff，逐项审查现有未提交改动；保留其意图，不覆盖用户修改。
- 记录 HEAD、工作树状态和本轮变更范围。
- 先建立“问题 → 文件/行号 → API/schema → 测试 → 文档”的实施矩阵。

安全边界：
- 动态验证只使用临时 data_root、Mock 和 127.0.0.1；不得访问真实 CAN、车辆、打印机或非回环 endpoint。
- 默认控制通道仍是 CAN2，主动发送白名单只能是 {0x121}。
- CAN1 主动发送永久锁定；不得启用 0x123、0x126、0x710、0x715、CANopen NMT 或新的主动发送路径。
- UI 不直接发送 CAN；所有控制必须经过后端 RBAC、SafetyInterlock、审计和 TxScheduler/SafeStop。
- missing/stale/invalid/out-of-range、来源错误、DBC/车型/hash 不符、数据库不可写、严重告警、急停、队列异常、审计不可写均 fail-closed。
- 不提交账号、token、secret、签名 key、bootstrap secret、现场 IP、用户 data、测试 session token。
- 不把 Mock/fallback/stale/unknown/固定值显示为真实新鲜数据。
- 本工作包不执行真实硬件/HIL/运动测试。

A. production 配置必须只有签名包一条权威路径
1. production 下拒绝 PUT /config/channels 和 /config/channels/restore-defaults 的普通直接应用，返回结构化 409 SIGNED_CONFIG_REQUIRED 并写拒绝审计。
2. dev/mock/test 保留 Network 草稿、loopback 校验、保存应用和失败回滚。
3. production Network 页面只读展示当前 signed endpoint、allowlist、diagnostics 和 drift；编辑入口必须进入 import → signature/schema/version → dry-run/diff → admin confirm → apply。
4. signed apply 重建 CanGatewayManager 时必须保留 on_can_security_event；回滚也必须保持 callback。
5. production post-apply health 必须检查：实际 bind、transport、批准 source 收帧、last frame age、DBC ready/hash/vehicle、data_root/DB 可写、控制 idle；任何 blocking 失败恢复 old RuntimeConfig、old manager、old active package 和旧回调。
6. 配置 model 使用 extra='forbid'；删除/拒绝 allow_tx 等未消费字段。
7. 明确分离：channel enabled（transport/receive）、control_enabled（唯一控制通道）、active transmit policy（服务端只读安全策略）。active transmit policy 不得通过配置扩大。
8. production 签名 schema 加入经验证的 Windows adapter identity：name/index/MAC/bind IP；preflight 检查实际接口一致，drift 时 409。

B. 建立控制动作与审计的可靠事务/补偿模型
1. 设计正式 migration，新增 control_intents/outbox（或等价模型），状态至少 PENDING/AUTHORIZED/SENT/CONFIRMED/FAILED/AUDIT_FAILED/CANCELLED。
2. 运动发送前，在一个 SQLite 事务中持久化 principal、role、session、vehicle、operation、command hash/最小必要字段、safety evaluation hash/摘要、trace_id、UTC ISO8601。
3. intent 提交成功后才允许 send-once/start-periodic；发送结果必须持久化。
4. intent 前写失败：不发送，返回 409/503 并锁存 database_unwritable。
5. 发送后结果写失败：不得返回完整成功；立即锁存存储故障、阻止新运动、停止 ordinary periodic，并按批准的受限 safe-stop 策略处理；保留可恢复证据。
6. 安全拒绝、safe-stop/emergency/release、override request/approve/revoke、EOL control 都进入统一可靠审计模型。
7. 应用重启时恢复/终结未决 intent，不能悄悄丢失。
8. record_operator_action 不能再对安全/危险动作静默吞异常；普通只读偏好可采用不同可用性策略，但需明确分级。

C. 增加签名 hardware acceptance artifact，默认仍拒绝真实运动
1. 定义 pydantic schema：artifact_version、station_id、vehicle_series、controller/firmware、release/config/DBC/test-plan hash、physical e-stop/PLC/relay checklist、watchdog/safe-stop policy、evidence file hashes、requester、two approvers、valid_from/to、revoked_at/reason。
2. artifact 使用独立信任根/签名，不能由普通配置导出接口自行生成；仓库仅提交 zero/placeholder schema example。
3. production 普通运动要求有效 artifact 且 station/vehicle/release/config/DBC/plan 全匹配。
4. missing、signature error、expired、revoked、same-person approval、scope/hash mismatch 全部 409，错误含 rule/label/current/threshold/blocking。
5. override 永远不能绕过 artifact、急停、DB/审计不可写、关键反馈、DBC、队列异常。
6. UI 只读显示批准状态、范围、有效期和阻断原因，不提供普通“hardware_validated=true”开关。
7. 不在本工作包把现有 hardware_validated 默认改为 true。

D. 修复 EOL 生产追溯
1. 删除 CreateSessionRequest 的 demo 默认 chassis_no/VIN/serial_no/operator/station_id；production 字段必须显式提供。
2. operator 只能来自后端 principal；station 只能来自有效 signed config，前端不能覆盖。
3. 增加 VIN/底盘号/序列号/车型/plan 的 pydantic 类型、长度/字符/校验规则、唯一性/重复件策略和工单引用。
4. Auto Test 增加不改变现有视觉风格的扫码/工单输入、校验、确认和错误状态；Mock profile 可明确提供“生成模拟会话”按钮，但显示 Mock 标签。
5. session identity 贯穿 raw CAN、decoded signals、alarms、assertions、reports、print audit、history/export。
6. 无 active session 的 CAN source_session 显示 '-'；删除后端和前端 S20260401-001 固定值。

E. 修复运行元数据真实性
1. /system/version 从 release manifest、state.config.config_version/test_plan_version 和实际 runtime 获取；build_time 不得使用请求当前时间。
2. packaged renderer 不运行 Node 时显示“构建依赖版本”或“不适用”，不得固定 20.x；与 package engines 22.22.2 不矛盾。
3. DBC dashboard 未加载时 filename/hash/message_count/signal_count/loaded_at 使用 null/0/未知和真实 error；不得 fallback 9f31c2b7、48、312。
4. 所有报告/设置/顶栏的 software/config/DBC/plan/release hash 相互一致，并有契约测试。
5. production 不加载逼真 fallback VIN/底盘/会话/报告；只显示 empty/offline。Mock profile 才允许显式示例数据。

F. TCP transport 做出安全决策
首选短期方案：production schema 暂时只允许 UDP，UI 的 TCP 标记“开发预览/尚未完成生产重连”，不能 apply 到 production。
如本工作包实现 TCP，则必须一次完成：
- connection state machine；
- bounded exponential backoff + jitter；
- EOF/connection reset/refused/server restart/half-open/idle timeout；
- connect/read/write timeout；
- cancel/shutdown；
- reconnect 期间 online=false、last frame 不刷新、signal stale；
- 不重发陈旧 control frame；
- 与 DB/queue/safety 联锁集成；
- unit/integration/10 min loopback soak。
未满足全部条件时不要宣称 production-ready。

G. 日志、retention 和大数据
1. app log 改为大小+时间轮转，路径来自 data_root/logs；支持压缩、保留和写失败告警。
2. 为 storage_config 建 pydantic schema，extra='forbid'；统一 compress_rotated/compress_after_days，修复当前未生效配置。
3. raw CAN、decoded signals、reports、exports、temp、backups、app logs 都进入明确 retention preview/job；保护 active sessions、audit、未归档报告和 rollback backup。
4. 自动 cleanup 默认只生成 dry-run/告警，真正删除保持 admin 明确确认，除非另有批准策略。
5. Parquet 改分区/append-friendly，或 production 明确禁用；不允许每次 append 全文件重写。
6. 增加磁盘满、只读、file lock、AV quarantine、rotation、compression、restart recovery 测试；数据故障继续阻止新运动。

H. Windows release candidate
1. 保留 Electron 安全设置：nodeIntegration=false、contextIsolation/sandbox/webSecurity=true、最小 preload、localhost 动态端口、短期凭据、单实例、有界重启和优雅停止。
2. 清理 docs/verification 下被忽略的运行 data/auth/token/secret，不读取或复制其内容。
3. 从 clean commit 构建 PyInstaller sidecar + Electron Builder NSIS；运行时不下载依赖。
4. 生成 SBOM、npm/pip audit、artifact SHA-256、release manifest；manifest 必须 dirty=false，commit 与 CI 完全一致。
5. 有正式证书时执行 Authenticode + timestamp；没有证书只能产出 unsigned-internal，不能标 production。
6. 独立 Windows VM 验证：无 Node/Python/uv/互联网，普通用户/管理员，中文和空格路径，端口占用，sidecar 失败/崩溃，防火墙/AV提示，首次/二次启动，升级/回滚/卸载，data 保留。

I. 测试要求
后端新增至少覆盖：
1. production 普通 channel update/restore-defaults 被拒绝并审计；dev/mock loopback 仍成功；
2. signed apply 保留 security callback，非法 source 不更新 online/cache 且告警；
3. audit intent 写失败无 TX；发送后状态写失败 fail-closed；重启恢复未决 intent；
4. hardware artifact missing/签名错/过期/撤销/同人/范围/hash 不符和正常有效；
5. demo/空/非法/重复 VIN/底盘/序列号、principal/station 防篡改；
6. source_session 与 active session 绑定，无 session 为 '-'；
7. system/release/config/plan/DBC 元数据真实，DBC unavailable 不显示固定数；
8. TCP 被 production schema 拒绝，或完整重连状态机测试；
9. log rotation/compression/retention/保护/取消/失败恢复；
10. DB/审计不可写、严重告警、急停、关键反馈、队列异常仍保持拒绝；
11. 正常 Mock 合法 CAN2 0x121 仍允许，CAN1 和其他 ID 始终拒绝。

前端新增至少覆盖：
- production Network 只读/签名包入口；dev/mock 草稿与回滚；
- Auto Test 扫码/工单/验证/Mock 明示；
- CAN source session 无伪值；Settings 元数据 unavailable；
- hardware acceptance 只读状态与 409 原因；
- 401/403/expired、offline/stale/invalid、审计故障中文状态；
- 11 页 1366×768/1920×1080 无页面级滚动和布局回归。

执行：
backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage
cd desktop
npm.cmd run lint
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:bundle
npm.cmd run test:sidecar
npm.cmd run test:e2e

修改 API model 后重新生成/核对 OpenAPI 文档和 TypeScript 类型。远程 Windows CI 必须运行 quality、renderer E2E、unsigned/signed installer（按证书条件）和 clean-machine 验证。长稳态只用 loopback，至少 1000 fps/10 min 作为 CI 或 nightly；目标 IPC 上另做 8～24h 软件 soak。

J. 文档和证据
- 更新 API、CONFIGURATION、SAFETY、CAN、IDENTITY、DATA_LIFECYCLE、REPORTING、DEPLOYMENT、WINDOWS_INSTALLATION、TESTING、UI 和风险文档。
- 在 docs/verification 新增本工作包目录，记录 clean commit、命令、结果、覆盖率、E2E、installer、SBOM/hash/manifest、nonLoopbackRequests=0。
- 不归档 bootstrap secret、session token、配置签名 key、账号、现场 IP 或用户 data。
- 给历史 audit 00~15 加 superseded/current index 提示，避免旧结论被误用。

交付说明必须列出：
1. 改动文件；
2. migration/schema/API 变化；
3. 关键安全决策和保持不变的 CAN 边界；
4. 测试/覆盖率/CI/installer 结果；
5. release commit/hash/signing 状态；
6. 仍需现场确认的物理急停、PLC、watchdog、safe-stop、DBC/车型、真实打印、GR&R 和长稳态；
7. 明确声明本工作包未执行真实硬件或运动测试。

完成判定：
- 不能只以测试全绿、页面能打开或 Toast 成功判定。
- 必须证明 production 配置没有第二条未签名路径，危险动作审计失败会 fail-closed，所有运行元数据真实，当前 release 可追溯到 clean commit。
- 即使软件完成，本工作包仍不得把真实车辆状态标为 READY；真实只监听和运动门禁必须由后续受控硬件验收关闭。
```

## 后续硬件验收 Prompt 使用建议

上面的 Prompt 完成且生成正式签名 RC 后，再单独创建 HIL/现场任务。该任务必须由现场安全负责人提供测试台条件、物理急停证明、车辆固定方式、终止条件和授权；不要在普通软件任务中隐式扩大为真实运动测试。
