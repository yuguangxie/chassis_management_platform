# 模块与功能完成度审计

## 1. 评分说明

下表的“软件完成度”评价代码、测试、错误路径和文档；“生产完成度”再考虑正式签名发行、现场参数、硬件、长期运行和运维闭环。分数是审计估算，P0 阻断项不会因平均分较高而降级。

## 2. 核心模块矩阵

| 模块 | 已实现功能 | 主要缺口/风险 | 软件 | 生产 |
|---|---|---|---:|---:|
| 应用启动与生命周期 | FastAPI startup/shutdown、服务装配、存储健康、DBC/CAN/EOL/报告初始化 | 使用已弃用 `on_event`；启动依赖矩阵虽有测试但缺生产长运行 | 92% | 70% |
| Electron 主进程 | 单实例、最小 IPC、动态 localhost 端口、短期 sidecar 凭据、日志脱敏、readiness、崩溃有界重启、优雅停止 | 当前工作树尚未重新打 installer；普通用户/企业 AV 独立 VM 证据不足 | 94% | 68% |
| Vue shell/router | hash 路由、11 业务页、登录/锁屏/403、角色 meta、侧栏按 principal 显示 | 当前 UI 收口未进入可追溯提交/远程 CI | 95% | 78% |
| HTTP/WS client | session bearer、统一错误、401 事件、WS 4401 停止重连、退避/恢复 | 缺少更长网络抖动和 sidecar 反复重启 soak | 92% | 70% |
| 身份账户库 | 一次性 bootstrap、本地账户、scrypt、随机短 session、hash 存储、失败锁定、撤销/过期/锁屏 | 本地签名密钥/账户库的 Windows ACL/DPAPI 运维仍需现场固化 | 92% | 72% |
| API RBAC | 约 150 个 OpenAPI operation；健康最小公开，敏感读要求 viewer，写按 operator/engineer/admin | 必须持续以契约测试防止新增 endpoint 漏鉴权 | 94% | 82% |
| 配置 schema/签名生命周期 | production schema、HMAC、版本/diff/dry-run/apply、健康检查、回滚、历史和审计 | `PUT /config/channels` 在 production 绕过签名路径；safe-stop 硬件验收不在签名 schema | 80% | 42% |
| 网络诊断 | bind/端口占用、endpoint、TCP connect、最后收帧年龄、通道统计、非伪 ping | 没有核对 Windows adapter_name/MAC/接口索引；production 直接应用路径健康检查不足 | 84% | 50% |
| USR-CAN115 codec | 13 字节、标准/扩展 ID 边界、保留位、DLC、RTR、数据长度严格校验 | 需真实设备固件/粘包/丢包/异常帧互操作记录 | 97% | 62% |
| UDP transport | 来源 IP/端口 allowlist、先拒绝后更新、队列/陈旧/非法源统计和告警 | 直接通道重配后缺安全事件回调；需真实网卡与防火墙验收 | 93% | 55% |
| TCP transport | 连接、流重组、收发与统计 | 无 reconnect/backoff、半开/EOF恢复、连接状态机；production 不可用 | 48% | 20% |
| CAN manager/pipeline | 双通道、缓冲、批处理、统计、仅 control channel 发送、CAN ID allowlist | 最新帧来源会话硬编码；运行时 endpoint 配置路径分裂 | 88% | 53% |
| DBC loader/service | cantools 加载、SHA-256、车型、overrides、raw-only 显式退化、production fail-closed | 只随包一份 JD DBC；未完成全部车型和实车信号语义签字；设置页缺省计数伪值 | 88% | 48% |
| Signal store/dashboard | 信号质量/来源/时间、REST/WS 同形、stale 规则、watchlist/layout/export、五灯语义 | 现场真实周期/合理范围需按车型标定；production 应避免富模拟 fallback | 91% | 65% |
| SafetyInterlockService | command-to-feedback 依赖矩阵、present/age/quality/source/range、409 详情、DB/告警/急停/队列/DBC fail-closed | 物理急停/安全 PLC/看门狗未接入；真实时序和阈值未验证 | 94% | 36% |
| 0x121 控制编码 | int8 补码、边界/裁剪、转角比例、preview、single/periodic | Python asyncio 20 ms 调度抖动未在目标 IPC/负载下测量 | 96% | 52% |
| TX scheduler | 单次/周期、stale command、stop、联锁前置和队列状态 | 覆盖率约 49%；周期异常/系统休眠/高负载恢复证据不足 | 78% | 40% |
| SafeStopService | 零速+制动、重试、新鲜反馈确认、超时、锁存、确认后策略 | `hardware_validated=false`；无真实制动曲线/watchdog/断电行为证据 | 88% | 25% |
| OverrideService | 双人审批、session/operation/vehicle/TTL、默认拒绝、撤销/过期、不可绕过规则 | 仅 severe alarm 可放行是合理边界；仍需现场 SOP、审计复核和授权治理 | 93% | 68% |
| EOL plan/models | 版本化 12 步计划、禁止扩展报文、失败策略、manual review | 会话创建有演示默认 ID；无工单/扫码/唯一性/车型-plan 自动匹配 | 85% | 42% |
| Assertions engine | 全部运算符、边界、missing/stale/invalid、窗口聚合和错误输入测试 | 实车 tolerance/窗口阈值、GR&R、金样件未验证 | 95% | 48% |
| EOL engine/UoW | create/start/pause/resume/abort/emergency、步骤/断言/日志、恢复、报告 | 未证明产线节拍、断电恢复和跨班次规模；主 API 覆盖仍偏低 | 87% | 48% |
| Alarm service | 当前/历史、级别、确认、布局、导出、CAN 定位、safe-stop 联动 | 历史分页未实现；现场故障映射/去抖/洪泛策略未标定 | 88% | 60% |
| SQLite 与 migration | 新库、v1→v2→v3、幂等、失败备份恢复、integrity、禁止降级 | 多 GB 数据、异常掉电、杀毒文件锁长期验证不足 | 92% | 67% |
| data_root/路径 | 所有业务路径派生、规范化、穿越防护、可写/空间检查 | 配置允许相对 data_root 后再 resolve；建议 production 明确强制绝对路径 | 91% | 70% |
| 原始/解码记录 | raw CSV 轮转/压缩框架、signal CSV/Parquet、telemetry 持久化 | 压缩配置键不匹配；Parquet append 全量重写；长时间吞吐未证实 | 74% | 38% |
| Retention/cleanup | dry-run、数量/时间/字节、保护规则、分批、进度、取消、审计 | 多类保留天数未自动执行；应用日志无轮转；reports/decoded policy 未真正消费 | 75% | 42% |
| Backup/restore | SQLite 在线一致备份、manifest/hash、恢复验证、回滚副本、管理员确认 | 需在目标磁盘/大库/断电/空间不足场景验证和恢复演练 | 92% | 68% |
| Storage health interlock | 只读、磁盘不足、损坏、写失败告警并阻止新运动 | 需现场文件锁、杀毒隔离、网络/BitLocker/磁盘故障注入 | 91% | 62% |
| Report generator | DOCX/PDF/JSON/CSV、追溯元数据、中文字体、失败报告 | 需质检模板签字、真实大报告、打印版式和签章流程 | 94% | 68% |
| Print service | 枚举/default、preview确认、job/spooler id、状态、取消/重试、hash审计、虚拟后端 | 真实 Windows 打印机/驱动/spooler 权限未验收 | 82% | 35% |
| History/export | 动态筛选、分页、详情、日志/断言、导出、下载、曲线回放 | 数据量和保留后引用完整性需生产规模验证 | 90% | 67% |
| 可观测性/审计 | trace_id、结构化 API 错误、operator_actions、config history、受控 sidecar 日志 | 审计写失败被吞；应用日志无 rotation；告警/指标无外部运维接入 | 76% | 42% |
| Mock simulator | normal/timeout/alarm/BMS/转角/速度/DB 等 profile，回环 E2E | 不是 HIL；覆盖率 42.98%，行为模型不能替代真实控制器 | 88% | 不适用 |
| Windows packaging | Electron Builder/NSIS、PyInstaller、离线依赖、字体/DBC/config、SBOM/audit/hash/manifest | unsigned；旧 dirty 基线；当前改动未重新打包；正式升级链未验证 | 87% | 51% |
| CI/测试门禁 | backend 197、frontend 139、simulator 3、双分辨率 E2E、installer job | 当前 dirty 工作树未远程验证；可选 1000 fps/10 min 未运行；无真实 HIL | 89% | 63% |

## 3. API 与权限盘点

当前 OpenAPI 约 150 个 operation。源代码路由层对 auth、overview、can、signals、control、eol、alarms、reports、history、config、storage、dbc 均设置了 principal/role 依赖；全局路由对业务读取至少要求 viewer，health/readiness 只公开最小信息。

角色语义：

| 能力 | viewer | operator | engineer | admin |
|---|---:|---:|---:|---:|
| 总览、CAN、信号、曲线、告警、报告、历史读取 | 是 | 是 | 是 | 是 |
| 执行 EOL、普通导出、报告扫描、告警确认 | 否 | 是 | 是 | 是 |
| 手动 0x121、控制预览、网络诊断 | 否 | 否 | 是 | 是 |
| 通道应用、签名配置 apply、备份恢复、cleanup、删除报告、审批 | 否 | 否 | 否 | 是 |

前端菜单/按钮隐藏只改善体验；直接 API 调用仍由后端返回 401/403。E2E 已验证未登录跳登录、viewer 直达 Network 跳 403、刷新保留 session 和新 Electron 进程重新登录。

## 4. CAN 主动发送面审计

| CAN ID/功能 | 当前状态 | 审计结论 |
|---|---|---|
| CAN2 0x121 | 唯一普通控制白名单 | 保留；所有 UI 操作必须走 SafetyInterlock 和审计 |
| CAN1 主动发送 | manager 受 control_channel 限制；页面显示策略锁定 | 不得通过 Network 的 enabled/tx_enabled 语义重新开放 |
| 0x123 / 0x126 | DBC override 和维护状态默认禁用；EOL plan validator 禁止 | 保持禁用；本轮没有上线理由 |
| 0x710 / 0x715 / NMT | `DISABLED_CONTROL_IDS`/维护状态禁止 | 保持禁用 |
| safe-stop 0x121 | 特殊操作仍走专用服务和基础条件 | 软件策略可测，真实硬件行为未证实 |

`ChannelConfig.enabled` 实际是通道启用，Network API 却以 `tx_enabled` 接收再写入 `enabled`，语义仍有混淆；`configs/channels.yaml` 又含 CAN1 `allow_tx: true` 的未消费字段。生产修复必须把“通道接收启用”“作为控制通道”“主动发送安全权限”分成不可混淆的字段，并把最后一项设为服务端不可由普通配置扩大。

## 5. 数据实体与持久化闭环

| 数据 | 写入 | 查询/导出 | 保留/恢复 | 审计 |
|---|---|---|---|---|
| 用户/session | SQLite auth 表 | `/auth/me`、管理员管理 | token 过期/撤销 | 登录/初始化/管理动作 |
| EOL 会话/步骤/断言 | EOL UoW | dashboard/history/report | migration、backup、cleanup 保护活跃会话 | 操作员动作与安全停车 |
| CAN raw | RawLogWriter/内存 buffer | monitor/export/history file | rotation 框架；策略不完整 | clear/export/delete |
| 解码信号 | SignalStore/SignalLogWriter/telemetry | dashboard/timeseries/replay/export | cleanup/备份范围；长期格式待优化 | watchlist/layout/export |
| 告警/override | SQLite/runtime service | current/history/dashboard | 审计记录受保护 | request/approve/revoke/ack |
| 报告 | data_root/reports | scan/preview/download/export | 未归档保护、backup | hash/操作员/打印/删除 |
| 配置 | 签名 active package + history | dry-run/diff/export/history | apply rollback | import/apply/reject/rollback |
| 打印任务 | SQLite print_jobs | poll/cancel/retry | 随数据库备份 | operator/report hash/job id |

最大横向缺口是审计写入失败没有变成业务失败/锁存，以及 retention 配置没有形成覆盖全部数据类别的受控自动作业。

## 6. 建议的完成度管理方式

后续不要再只维护“总完成度”。每个 release candidate 至少同时维护：

1. 软件功能矩阵：代码、单测、集成、错误、权限、审计。
2. 发布矩阵：clean commit、CI run、SBOM、漏洞、签名、hash、安装/升级/卸载。
3. 现场配置矩阵：station、车型、DBC hash、plan、endpoint allowlist、data_root、printer。
4. 安全验收矩阵：物理急停、PLC/relay、watchdog、safe-stop、失联、掉电、误源、严重告警。
5. 量产质量矩阵：节拍、长稳态、GR&R、金样件、失败件、报告/追溯抽查。

只有五张矩阵都通过，生产完成度才可记为 100%。
