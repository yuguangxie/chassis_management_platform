# UI 实现说明

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
