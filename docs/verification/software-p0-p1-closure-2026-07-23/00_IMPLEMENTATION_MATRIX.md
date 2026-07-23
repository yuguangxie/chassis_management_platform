# 2026-07-23 软件 P0/P1 收口实施矩阵

> 建立时间：2026-07-23（Asia/Shanghai）  
> 基线提交：`ba47b0aaebc62eae3131d23ed9d318fdb4721130`  
> 初始工作树：dirty；包含上一轮 UI 一致性收口及 `docs/current_audit_2026-07-23` 审计资料，必须保留。  
> 动态验证边界：仅临时 `data_root`、Mock 与 `127.0.0.1`；不访问真实 CAN、打印机、车辆或非回环端点。

本表在修改代码前建立。行号是基线定位；实现完成后以最终文件链接、测试名和证据索引为准更新。

| 审计问题 / 目标 | 基线文件与定位 | API / schema 变化 | 计划测试 | 交付文档 / 证据 |
|---|---|---|---|---|
| P0-01 production 存在未签名 channel update / restore 路径 | `backend/app/api/config.py:850-944`；`backend/app/configuration/service.py` | production 返回 `409 SIGNED_CONFIG_REQUIRED`；channel `enabled`、`control_enabled` 与只读 Tx policy 分离；请求模型 `extra=forbid` | production 拒绝且拒绝审计；mock/dev 应用与失败回滚 | CONFIGURATION、API、SAFETY；配置收口测试日志 |
| 签名 apply/rollback 保留 CAN 安全回调 | `backend/app/api/config.py:754-844`；`backend/app/can_gateway/manager.py:13-47` | manager 重建统一工厂；post-apply blocking health；回滚恢复旧 config/manager/package/callback | callback 身份及非法 UDP source 不更新 online/cache | CAN、CONFIGURATION；source rejection evidence |
| Windows adapter identity 与 drift | `backend/app/configuration/models.py:18-26`；`diagnostics.py` | production signed schema 增 name/index/MAC/bind IP；preflight 返回结构化 drift | identity 缺失/错配/匹配；非 Windows 测试注入 resolver | CONFIGURATION、DEPLOYMENT、风险 |
| TCP 生产决策 | `configuration/models.py:85-125`；`can_gateway/tcp_gateway.py` | production schema 只允许 UDP；UI 标记 TCP 为开发预览 | production TCP package 拒绝；mock loopback TCP 保留开发测试 | CAN、CONFIGURATION、UI |
| P0-02 危险动作先发送后审计且异常被吞 | `backend/app/api/control.py`；`services/audit.py`；`control/tx_scheduler.py` | migration v4 新增 `control_intents`；PENDING/AUTHORIZED/SENT/CONFIRMED/FAILED/AUDIT_FAILED/CANCELLED；严格危险审计错误 | intent 前写失败零 TX；发送后写失败锁存/停止；重启终结未决 | SAFETY、API、DATA_LIFECYCLE；事务测试证据 |
| 安全拒绝 / safe-stop / override / EOL 统一可靠审计 | `safety_interlock.py`；`safe_stop.py`；`override_service.py`；`api/eol.py` | strict audit 分级；危险动作审计不可写即 fail-closed | DB/审计故障、急停、严重告警、反馈、队列异常回归 | SAFETY、IDENTITY、风险 |
| P0-03 缺 hardware acceptance artifact | `core/config.py:123`；`safety_interlock.py` | 独立 HMAC 信任根；严格 pydantic artifact/status；只读状态 API；仓库只放零值模板 | missing/signature/expiry/revoke/同人/scope/hash/valid | SAFETY、DEPLOYMENT、API、模板说明 |
| P1 EOL demo 身份默认与前端伪会话 | `eol/models.py:24-32`；`api/eol.py`；`AutoTestPage.vue` | VIN/底盘/序列/车型/工单/plan 强类型；operator/principal 与 signed station 服务端覆盖；重复策略 | 空/demo/非法/重复；防篡改；Mock 显式生成 | API、UI、TESTING、EOL 追溯证据 |
| session identity 未贯穿 CAN/存储 | `can_gateway/manager.py:124-156`；`api/can.py`；telemetry/UOW | 无 active session 为 `-`；活跃 session 写 raw/decoded/alarm/report/print/history | active/no-active source_session；持久化 bundle 契约 | DATA_LIFECYCLE、CAN、REPORTING |
| P1 system/release/config/plan/DBC 元数据伪值 | `api/config.py:431-492`；`storage/uow.py:318-349`；`SystemSettingsPage.vue` | release manifest 真源；未知用 null/0；build_time 不取请求时间；统一 traceability model | DBC unavailable 无固定计数/hash；跨 API/report 一致性 | API、DEPLOYMENT、REPORTING、release manifest |
| production fallback Mock 数据 | `desktop/src/mocks/fallbackData.ts`；各 store/http | fallback 仅 dev/mock；production empty/offline；CAN session 无固定值 | production no-fallback 静态/组件测试 | UI、风险 |
| P1 app log 轮转/压缩/retention | `core/logging.py`；`configs/storage_config.yaml`；`storage/lifecycle.py` | strict `StorageConfig extra=forbid`；大小+时间轮转、gzip/保留；统一字段名 | rotation/compression/read-only/lock/restart | DATA_LIFECYCLE、TESTING |
| 大数据 Parquet 全量重写 | `storage/signal_log_writer.py:65-85` | 本工作包采用短期安全决策：production 禁用 Parquet，CSV append-only | production parquet 拒绝；mock CSV append 回归 | DATA_LIFECYCLE、风险 |
| retention 范围与保护规则不完整 | `storage/lifecycle.py:190-470` | preview/job 纳入 raw/decoded/reports/exports/temp/backups/logs；audit/active/unarchived/rollback 保护 | dry-run/取消/失败恢复/保护/权限 | DATA_LIFECYCLE、API |
| Windows RC dirty/unsigned/证据不一致 | `scripts/build_windows_release.ps1`；`.github/workflows/quality.yml`；Electron sidecar | clean commit manifest、SBOM/audit/hash；无证书仅 `unsigned-internal`；正式证书接口保留 | bundle/sidecar/E2E/installer/clean-machine，远程 Windows CI | DEPLOYMENT、WINDOWS_INSTALLATION、verification manifest |
| 11 页与只读 hardware/config 状态 | Network/Auto Test/CAN/Settings/router/stores/types | production Network 只读并进入 signed import；hardware acceptance 只读；中文 409 原因 | 11 页双分辨率、401/403/offline/stale/audit failure | UI、E2E 页面矩阵与截图 |

## 永久保持的 CAN 边界

- 默认控制通道只允许 CAN2；CAN1 主动发送永久锁定。
- 主动发送白名单严格等于 `{0x121}`；本工作包不新增任何发送 ID。
- 不启用 `0x123`、`0x126`、`0x710`、`0x715`、CANopen NMT。
- UI 不直接发送 CAN；所有运动动作必须依次经过 RBAC、安全联锁、可靠意图/审计和调度器。
- 本工作包只形成真实 CAN“只监听”验收前的软件 RC，不把真实车辆运动状态标记为 READY。
