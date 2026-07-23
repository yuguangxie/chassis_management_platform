# UI 实现说明

## 2026-07-23 production 状态收口

Network 在 production 为只读：显示签名 endpoint/source allowlist、Windows adapter name/index/MAC/bind IP、实际诊断与 drift，编辑入口进入签名包 import/dry-run/diff/apply。dev/mock 才显示通道启用草稿和回滚；发送策略始终只读，CAN1 不可选。

Auto Test 不再生成隐式 demo identity，改为扫码/工单字段、校验/确认，并仅在非 production 显示带 Mock 标识的“生成模拟会话”。CAN source session 无活动会话时为 `-`；Settings 的 release/config/plan/DBC 与 hardware acceptance 都来自后端，未知即未知。hardware acceptance 只读且逐条展示 409 blocking 原因，不提供 `hardware_validated=true` 开关。

UI 参考 `ui_reference` 深蓝工业风，以真实 Vue 组件实现侧边栏、顶部状态栏、卡片、表格和 ECharts 图表。

# 数据生命周期 UI 收口（2026-07-22）

- `SystemSettingsPage` 将 data_root、SQLite、应用日志、Raw CAN、解码信号和报告派生路径显示为只读；不能再用目录选择器制造分叉数据根。
- admin 可从系统设置执行 SQLite 一致性备份、选择最近有效备份并输入完整恢复确认、执行 retention dry-run/二次确认以及存储健康复检。
- 自动清理在 UI 明确显示为禁用；未归档报告、活动会话和审计保护由后端再次强制。
- `ReportManagementPage` 在打印前弹出打印机选择和 PDF 预览确认；打印 job 持久化并可由 store 查询、取消和重试。
- 后端离线 Mock 的容量全部为 0，并带 `measurement_error`，不再展示 512/236 GB 等伪测量。

# 11 页面 Stub 收口（2026-07-22）

- 统一使用 `PageDataState` 展示 loading、empty、error、stale 和 permission-denied；错误和权限拒绝优先于 fallback。
- Network 改用 OS/runtime 诊断和真实 CAN monitor statistics，并保留已应用快照以表达失败回滚；Vue Proxy 不再直接传给 `structuredClone`。
- Manual Control 展示逐项反馈的 present/age/quality/channel/range/blocking，offline/stale 时隐藏实时反馈和曲线，发送按钮 fail-closed。
- Report Management 展示打印任务全生命周期、spooler job id、失败原因、取消和重试。
- History 的操作员/工位改为动态选项，默认日期不再写死；失败查询不再显示成功。
- 不能在本工作包安全实现的控件均 disabled，并用 title 和可见文字标注“尚未实现”。详细清单和页面追踪矩阵见 `docs/verification/ui-page-stub-closure-2026-07-22/`。

# UI 一致性与稳定性收口（2026-07-23）

- 新增 `IndustrialButton`（32/36 px）和 `IndustrialActionButton`（70 px），统一 neutral/primary/success/warning/danger、7 px 圆角、160 ms hover、focus-visible、disabled 和 loading。窄操作栏保留完整原生 `title`，避免省略文字失去语义。
- `ToggleSwitch` 使用原生 button + `role=switch`、`aria-checked`、`aria-disabled` 和 `update:modelValue`。Network 的通道启用只修改草稿；主动发送权限独立展示，CAN1 永久锁定，CAN2 仅保留既有 `0x121`。
- `uiStatusLabels.ts` 是页面状态和诊断枚举的中文真源。CAN/DBC/BMS/VIN/SOC/UDP/TCP/PDF/CSV 与 DBC signal key 可保留；用户状态、角色、模式、quality 和诊断结果必须先转换为中文。
- Signals REST 与 WebSocket 使用同一 dashboard envelope；前端 merge-normalize 不因增量 payload 缺字段把已有 good 覆盖为 unavailable。stale/invalid/unavailable 清除五个灯光组件的点亮效果。
- 实时曲线不再包含虚构 session。实时模式只读取 curve config/timeseries；history 模式必须有显式 session_id，历史错误只占用回放区域。
- 页面根节点使用固定 shell 高度和 `minmax(0,1fr)`；仅表格、列表、配置和诊断区允许内部滚动。1366 的实时曲线使用活动分组，低高度手动控制图隐藏会重叠的轴标签。
- 一键检测与告警 store 分离 `initialLoading`、`refreshing` 和 `actionPending`，WebSocket 更新优先，GET 合并去重；背景刷新不改变主要按钮 DOM、disabled 或 opacity。
- 最终逐页证据见 `docs/verification/ui-consistency-closure-2026-07-23/`。
