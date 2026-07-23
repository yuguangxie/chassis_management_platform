# 11 个桌面 UI 页面完整功能审计

## 1. 总体结论

当前 11 页已不再是纯静态大屏：主要读写操作均可追到 store/页面状态、API、后端 service、持久化/审计和错误状态。最新工作树还完成了按钮统一、中文状态字典、双分辨率布局、图表防溢出、REST/WS 信号同形、五种灯效、Network 草稿开关和后台刷新防闪烁。

页面平均软件完成度约 89.5%。这个分数不代表车辆可上线：Manual、Auto Test、Network 等页面的最终有效性取决于 production 配置权威、真实反馈、物理安全链、DBC 和硬件验证。

统一页面能力：

- `PageDataState` 表达 loading、empty、error、stale、permission-denied；背景 refreshing 不替换页面主状态。
- principal 来自后端 `/auth/me`；Router roles 与 API 401/403 双重生效。
- `IndustrialButton`/`IndustrialActionButton` 统一主要按钮；危险操作保留红色语义和 disabled/focus/hover 状态。
- `uiStatusLabels.ts` 统一 online/offline、quality、EOL、角色、模式和开关中文标签。
- 1366×768 与 1920×1080 均无页面级滚动，密集表格/列表使用内部滚动。
- Mock/offline/stale/invalid 不显示为新鲜真实数据；停止 simulator 后控制返回 409。

## 2. 页面总表

| 页面 | 核心读链路 | 核心写链路 | 权限 | 软件完成度 | 生产完成度 |
|---|---|---|---|---:|---:|
| 总览 | `/overview/summary` | 报告扫描、安全停车、路由快捷入口 | viewer 读；operator 写 | 92% | 72% |
| 网络配置 | `/config/channels`、diagnostics、statistics | 草稿 apply/rollback、connect/disconnect/self-test/defaults | engineer 页面；admin apply | 82% | 40% |
| CAN 监控 | latest/decoded/statistics/history | clear/export/load/delete；暂停仅本地 | viewer 读；operator/engineer 写 | 87% | 58% |
| 信号仪表盘 | dashboard + WS、watchlist | layout/watchlist/snapshot | viewer 读；operator 写 | 94% | 70% |
| 实时曲线 | config/timeseries；history replay/fault | pause、selection、CSV/snapshot、seek | viewer 读；operator 写 | 91% | 68% |
| 手动控制 | status/interlock/feedback/curves | preview、send once/periodic/stop/safe-stop/e-stop/reset | engineer/admin | 92% | 35% |
| 一键检测 | EOL dashboard/session/steps/assertions/logs | create/start/pause/resume/abort/e-stop/report | operator+ | 84% | 45% |
| 告警诊断 | dashboard/current/history/charts | ack、override、export、定位、layout、safe-stop | viewer/operator/admin 分层 | 90% | 62% |
| 报告管理 | dashboard/preview/files/printers/jobs | scan/export/print/cancel/retry/archive/delete | viewer/operator/admin 分层 | 91% | 62% |
| 历史追溯 | filters/list/detail/timeline/audit/charts | export/download/open/replay | viewer 读；operator 写 | 92% | 68% |
| 系统设置 | system/DBC/storage/config history | signed import/export/apply、backup/restore/cleanup/maintenance | engineer 页面；admin 危险写 | 89% | 50% |

## 3. 总览页 `OverviewPage.vue`

### 控件到后端追踪

| 控件/功能 | store/状态 | API/service | 持久化/审计 | 失败状态 |
|---|---|---|---|---|
| KPI、当前车辆、CAN、最近会话、统计图 | 页面 `loadSummary` | `GET /overview/summary`，overview 聚合服务 | SQLite 会话/报告/告警查询 | 错误槽；fallback 明确 mock；离线 FPS/曲线清空 |
| 新建检测/继续会话 | Router | 跳 `/auto-test` | 后续由 EOL API 记录 | 路由权限拒绝到 403 |
| 打开报告目录 | Router/API action | 报告目录接口 | 操作审计 | API 错误 Toast + PageDataState |
| 报告扫描 | 页面 action | `POST /reports/scan` / ReportService | 报告索引、操作审计 | 失败不提示成功 |
| 安全停车 | 页面 action | `POST /control/safe-stop` / SafeStopService | 控制审计、停车结果 | 409/504 明确呈现 |
| CAN/Manual/History/Reports 快捷入口 | Router | 页面路由 | 无业务写入 | roles 守卫 |

### 完成与缺口

- 已完成：核心汇总、最近会话可达、真实路由、安全停车 API、双分辨率、图表边界、离线陈旧状态。
- 禁用：自定义布局，明确标注“尚未实现”，没有用 Toast 伪装成功。
- 残余：富模拟 fallback 仍含逼真车辆标识，production 应改为空状态；汇总值依赖后端固定版本元数据的修复。

## 4. 网络配置页 `NetworkConfigPage.vue`

### 控件到后端追踪

| 控件/功能 | store/状态 | API/service | 持久化/审计 | 失败状态 |
|---|---|---|---|---|
| CAN1/CAN2 页签、IP/端口/协议 | `config` 草稿 + `appliedConfig` 快照 | `GET /config/channels` | 当前 runtime/config 文件 | initial/error/stale 固定槽 |
| 通道启用 switch | `ToggleSwitch v-model` | 仅保存并应用时 PUT | 配置与历史 | 未应用变更标记；失败恢复快照 |
| 默认控制通道 radio | 互斥草稿 | 服务端拒绝多控制通道 | 配置审计 | CAN1 不可选并显示安全锁定原因 |
| 主动发送安全状态 | 只读策略展示 | manager allowlist/control_channel | 无可扩大写入口 | CAN1 锁定；CAN2 仅 0x121 |
| 保存并应用 | actionPending | `PUT /config/channels` / CanGatewayManager | 原子替换、操作审计 | 后端/前端双回滚，中文错误 |
| connect/disconnect/stop all | action | `/can/channels/*` | 操作审计 | transport 失败明确显示 |
| 重新检测/self-test | refreshing | diagnostics/self-test/statistics | 诊断结果 | ping 未测量用 null，不显示固定 0.0 |
| 恢复默认 | admin action | `/config/channels/restore-defaults` | 配置与审计 | 失败保留旧配置 |

### 完成与缺口

- 已完成：真实 switch 键盘/ARIA、草稿/应用语义、CAN1 锁定、CAN2 唯一控制、诊断、内部滚动、失败回滚。
- 禁用：联机帮助、网卡选择、图表时间范围，均明确“尚未实现”。
- P0：production 的普通 PUT 绕过签名配置包；页面在 production 不应直接使用这条路径。
- P1：`enabled`/`tx_enabled` 语义仍混淆；重建 manager 丢失未授权来源安全告警 callback；实际 Windows 网卡未核验。

## 5. CAN 监控页 `CanMonitorPage.vue`

### 功能链路

- 读取：`useCanStore` 调用 latest frames、decoded frames、statistics、monitor history/file APIs；WebSocket 增量更新实时帧。
- 筛选：通道“全部/CAN1/CAN2”、方向“全部/接收/发送”、进制“十六进制/十进制”、CAN ID、状态、排序和暂停显示在前端真实生效。
- 写操作：clear display 清 runtime buffer；raw/CSV 导出生成 data_root 文件；加载/删除历史文件经过后端校验、权限和审计。
- 错误：offline 时 RX/TX FPS 显示“—（数据陈旧）”；列表/统计 error、empty、stale 分离。
- 响应式：1366 filter 自适应重排；segmented 子按钮 rect 和文字宽度有 E2E 断言。

### 缺口

- 后端最新帧和 store fallback 可能写入固定 `S20260401-001`，必须改为实际 EOL session 或 `-`。
- `message_name` 未知时显示 `Unknown`，可改为“未知报文”，但 CAN/DBC 技术缩写可以保留。
- 原始数据/DBC/发送历史独立页签、帧详情全屏/关闭均禁用并标注未实现。
- 页面 TX 记录只负责观察；不能被误解为 UI 能主动发帧。

## 6. 信号仪表盘 `SignalDashboardPage.vue`

### 功能链路

- `useSignalsStore` 从 `GET /signals/dashboard` 首次加载并接收 `signals.dashboard` WS。
- REST/WS 归一化包含 quality、status.quality、mock、updated_at、data_source、trace_id；缺字段不会把已有 good 直接覆盖成 unavailable。
- signal-level 保存 value、unit、timestamp、quality、source channel/CAN ID；offline/stale 清值和 sparkline。
- watchlist/layout 通过 PreferenceService 持久化；snapshot/export 生成文件并写操作审计。
- 灯光/制动组件按 boolean、0/1、ON/OFF 归一化；左/右转黄、位置红、近光白、制动红；unknown/stale/invalid 清除光效且无持续闪烁动画。

### 缺口

- 60 秒 Mock 已证明只有 good，但真实设备的报文周期、阈值和 DBC 映射仍需车型签字。
- production 应禁用富模拟卡片 fallback，只展示明确空/离线状态，降低操作员误判风险。

## 7. 实时曲线 `RealtimeCurvePage.vue`

### 功能链路

- 实时模式只请求 curve config 和 timeseries；不再请求虚构 `EOL-20260401-0001` 的 replay/fault-events。
- 历史模式仅在 `route.query.mode=history` 且有 session_id 时请求 replay/fault；404/超时只污染回放区域。
- 切回实时清理历史错误、游标、故障事件和 metadata。
- 支持信号组选取、暂停/继续、CSV、快照、selection 偏好、历史 seek。
- 1920 使用 2×3；1366 使用活动分组/有限图表；图例 scroll、containLabel、hideOverlap、时间轴限刻度，ResizeObserver 保留。

### 缺口

- 信号列表列设置禁用并标注未实现。
- 历史入口依赖 History 页面路由；还需生产规模时序查询与长回放性能验证。

## 8. 手动控制 `ManualControlPage.vue`

### 功能链路

- 读取：control status、interlock status、manual feedback、manual curves。
- 表单：0x121 挡位/模式/目标速度/前后转角/制动，预览显示编码结果；UI 本身不构造 socket/CAN 发送。
- 安全反馈：逐项展示 present、age、quality、source channel/CAN ID、range/allowed value、threshold、blocking。
- 动作：send once、start/stop periodic、safe-stop、e-stop、release/reset，均走后端 RBAC、SafetyInterlock/TxScheduler/SafeStop 和操作审计。
- offline/stale/invalid/DB 不可写/严重告警/急停/队列异常保持拒绝；E2E 停 simulator 后请求为 409。
- 布局：主区使用 `minmax(0,1fr)`，1920 底部空白已收口。

### 缺口

- 自定义布局禁用。
- 真车 production 普通运动因 `hardware_validated=false` 被拒绝；这是正确 fail-closed，不是页面故障。
- 页面软件完成度高，但没有 physical e-stop 输入、台架时序或真实执行器确认，生产完成度低。

## 9. 一键检测 `AutoTestPage.vue`

### 功能链路

- `useEolStore` 读取 dashboard、当前 session、12 步、断言、实时测量和日志。
- 创建/开始/暂停/恢复/中止/急停/生成报告/查看日志均调用 EOL API；UoW 持久化会话、步骤、断言、动作和报告。
- initialLoading、refreshing、actionPending 分离；WS 优先增量更新，GET 合并/节流；60 秒主按钮 DOM/disabled/opacity 稳定。
- offline 禁止写动作，测量和曲线标 stale；safe-stop/失败路径保留原因。
- 内容区铺满窗口，图表/list 吸收剩余高度。

### 缺口

- 会话创建 model 带演示底盘号/VIN/序列号默认值；页面没有生产扫码/工单输入与校验闭环。
- 自定义布局禁用；检测步骤由审批 plan 固定是合理设计。
- 尚无实车 GR&R、金样/坏样、节拍和断电恢复验收。

## 10. 告警诊断 `AlarmDiagnosisPage.vue`

### 功能链路

- 读取 current/history/stats/distribution/trend；store 拆分 loading/refreshing/actionPending。
- 支持 ack、诊断导出、跳转 CAN frame、保存布局、安全停车。
- override 支持 request/approve/revoke/expired；申请人与批准人、范围、TTL 和不可绕过规则由后端保证。
- 按钮是全站 `IndustrialActionButton` 的视觉基线；60 秒背景更新不替换节点或改变 disabled/opacity。
- 图表使用 containLabel 和内部滚动，中文显示级别与确认状态。

### 缺口

- 告警历史上一页/下一页禁用，因为 dashboard 无分页契约。
- 真实故障码映射、抖动、重复告警洪泛和现场严重度需要底盘/质量团队签字。

## 11. 报告管理 `ReportManagementPage.vue`

### 功能链路

- 读取 report dashboard、files、preview、printers、print jobs；支持筛选、选择和多格式预览。
- scan、Word/PDF export、regenerate/archive/delete、打开目录、下载均调用后端真实文件服务并审计。
- 打印先预览/确认，提交后显示 job id、spooler id、attempts、queued/printing/completed/failed/cancelled；支持 cancel/retry。
- 删除仅 admin 并保留审计；报告 hash/操作员进入打印审计。
- empty/error/permission/打印依赖缺失均有可操作中文提示。

### 缺口

- 列设置、密度、预览菜单、关联数据独立页签/查看图标、统计时间范围禁用并标注未实现。
- 真实打印机、驱动、spooler 权限和纸张版式未验收。
- DOCX/PDF 质检模板、签章和归档制度需产品/质量签字。

## 12. 历史追溯 `HistoryPage.vue`

### 功能链路

- 筛选项、操作员、工位从 API 数据派生；日期不再固定 2026 示例。
- 支持分页、session 详情、timeline、assertions、audit、日志、统计图。
- export/download/open session/replay 路由均调用真实 API、文件根校验和操作审计。
- 查询失败不再显示“完成”；offline 清详情/趋势；empty/stale/permission 固定槽。

### 缺口

- 需用生产数据规模验证查询索引、分页、导出体积、cleanup 后关联完整性。
- 追溯可信度受 EOL 演示默认标识和 CAN 固定 source_session 问题影响。

## 13. 系统设置 `SystemSettingsPage.vue`

### 功能链路

- 读取 basic/system version、DBC、threshold、roles、storage、maintenance、config history。
- 签名配置：export、本地文件 import、schema/signature/version/diff dry-run、管理员确认 apply、健康检查和失败回滚。
- data_root 派生路径只读展示；storage health 复检；一致性 backup、manifest/hash restore、cleanup preview/confirm/job。
- DBC status/reload/messages；危险维护操作按 admin/maintenance/confirm 分层且 0x123/0x126/NMT 默认关闭。
- 按操作维护 loading/error，不以固定 success Toast 代替后端结果。

### 缺口

- System version/DBC dashboard 有固定/伪造元数据，必须改为真实 release manifest/config/plan/DBC 状态。
- production Network 普通 PUT 绕过签名配置，破坏本页宣称的单一配置生命周期。
- 生产 DBC 文件选择、覆盖规则/版本详情禁用；生产 DBC 只能随签名包部署是合理限制。
- retention UI 能执行手工 cleanup，但多类自动保留策略和日志轮转未闭环。

## 14. 明确未实现且已禁用的控件

| 页面 | 控件 |
|---|---|
| 总览 | 自定义布局 |
| 网络 | 联机帮助、网卡选择、图表时间范围 |
| CAN | 独立原始数据/DBC/发送历史页签、帧详情全屏/关闭 |
| 曲线 | 信号列表列设置 |
| 手动控制 | 自定义布局 |
| 一键检测 | 自定义布局 |
| 告警 | 历史分页 |
| 报告 | 列设置、密度、预览菜单、关联数据独立页签/查看、统计时间范围 |
| 系统设置 | 生产 DBC 直接选择、覆盖规则/版本详情独立视图 |

这些控件当前没有伪成功；后续只有在存在 API schema、权限、审计、失败路径和自动化后才能启用。

## 15. UI 自动化判定

最新本地证据覆盖 11 页 × 2 分辨率共 22 张截图：页面级滚动 0、页面越界 0、一级 section 裁切 0、底部空白超 16 px 为 0、分段按钮越界 0、图表 canvas 越界 0、renderer console/page error 0、非回环请求 0。

60 秒共 60 个信号样本只出现 `good`；Auto Test 和 Alarm 主要按钮节点、disabled、opacity 稳定。页面安全交互覆盖路由/刷新、筛选/分页/暂停、Mock 会话与报告、配置 dry-run、权限拒绝和 simulator 离线控制 409。

限制：这些证据来自当前未提交工作树的本机回环运行；在形成干净 commit 并由远程 Windows CI/安装包复验前，不能作为正式 release acceptance。
