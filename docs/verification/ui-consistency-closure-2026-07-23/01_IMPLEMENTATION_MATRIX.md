# 桌面端 UI 一致性收口实施矩阵

- 日期：2026-07-23（Asia/Shanghai）
- 基线 commit：`ba47b0a`
- 动态边界：仅 Mock、临时 `data_root` 与 `127.0.0.1` 回环
- 安全边界：CAN1 不获得主动发送权限；主动白名单仍仅为 CAN2 `0x121`；`0x123`、`0x126`、CANopen NMT 保持关闭

本矩阵在修改代码前建立。当前未提交内容仅包括专项审计、风险索引和 22 张基线截图；没有未提交 UI 实现需要覆盖。

| 编号 | 页面/组件 | 当前文件与行号（修改前） | 问题 | 实施动作 | 验证 |
|---|---|---|---|---|---|
| UI-C01 | 全局状态 | `desktop/src/components/layout/TopStatusBar.vue:2-27`、`SidebarNav.vue:22-27`、11 页模板 | `online/Normal/admin/PASS/stale` 等原始英文直接可见 | 新建唯一中文状态字典；状态、角色、质量、模式、结果统一经字典显示 | 字典单测、静态模板扫描、11 页 DOM 断言 |
| UI-C02 | 全局按钮 | 11 页各自的 action/button CSS；告警页 `AlarmDiagnosisPage.vue:134-137` 为基线 | 高度、圆角、hover、focus、disabled 不一致 | 新建 `IndustrialButton`（32/36 px）和 `IndustrialActionButton`（70 px），保留危险操作红色层级 | 组件 hover/focus/disabled/loading/permission 单测；页面共享组件断言 |
| UI-C03 | 全局状态槽 | `desktop/src/components/PageDataState.vue:1-50` | 状态节点反复插入/移除造成标题区位移 | 保留固定尺寸状态槽；背景刷新不进入初始 loading | 组件稳定 DOM 单测、E2E 节点引用采样 |
| UI-C04 | Network | `NetworkConfigPage.vue:54-85,201-212` | `ToggleVisual` 仅为 `span`；`enabled` 被误称发送允许 | 使用可访问 `ToggleSwitch` 修改草稿；重命名为“通道启用”；独立展示主动发送安全策略 | 鼠标/Space/Enter、dirty 标记、权限与回滚测试 |
| UI-C05 | Network | `NetworkConfigPage.vue:76-83,114-123` | 默认控制通道非互斥真实控件；CAN1 锁定原因不清 | 使用互斥 radio；CAN1 永久不可选并显示锁定原因；CAN2 为唯一批准控制通道 | DOM/ARIA、安全策略与后端多控制通道拒绝断言 |
| UI-C06 | Network | `NetworkConfigPage.vue:408,999` | 1366 固定高度使配置和操作区越界 | 通道页签 + 弹性网格 + 明确内部滚动；关键端点和应用按钮始终可达 | 1366/1920 page/content rect、内部滚动首尾断言 |
| UI-C07 | Signals/API | `backend/app/api/signals.py:309-315`、`backend/app/services/lifecycle.py:113-114`、`desktop/src/stores/signals.ts:112-120` | REST 顶层 `quality` 与 WS `status.quality` 不同形，WS 全量覆盖良好状态 | 后端共用 dashboard envelope；前端做缺字段合并与质量归一化 | API/WS 模型测试、60 秒稳定采样 |
| UI-C08 | Signals | `SignalDashboardPage.vue:90-94,286-298` | 灯效由静态 `active/danger` 决定 | 新建状态驱动灯组件；ON/OFF/0/1/boolean 归一化；stale/invalid 清灯效 | 五类信号 ON/OFF/stale/invalid 单测与截图 |
| UI-C09 | CAN | `CanMonitorPage.vue:20-65,553-576,986` | ALL/RX/TX/Hex/Dec 英文且按钮最小宽导致截断 | 中文优先标签；选项等分；1366 自适应两行过滤栏 | 每个子按钮 rect 与文本 scrollWidth E2E 断言 |
| UI-C10 | Curves | `RealtimeCurvePage.vue:240-275,412`、`stores/signals.ts:85-108` | 硬编码虚构会话；实时模式无条件加载历史 API；历史错误污染全页 | 删除默认会话；实时/历史请求分流；独立历史错误；切回实时清理回放状态 | 零历史请求、空 ID、合法会话、404、超时、模式切换测试 |
| UI-C11 | Curves/charts | `RealtimeCurvePage.vue:502,854,1044` 与各图表 option | 1366 将 6 图压成 3 行，图例和坐标轴重叠 | 1920 保留 2×3；紧凑视口使用分组视图；滚动图例、`containLabel`、`hideOverlap`、刻度限制 | 双分辨率截图、图表容器边界断言 |
| UI-C12 | EOL/Alarms | `stores/eol.ts:14-53`、`stores/alarms.ts:20-67`、`AutoTestPage.vue:316-355`、`AlarmDiagnosisPage.vue:229-265` | 后台 GET 与写操作共用 loading，WS 触发重复 GET | 拆分 `initialLoading/refreshing/actionPending`，请求合并；WS leading/trailing 节流 | 60 秒按钮 DOM、disabled、opacity 稳定采样 |
| UI-C13 | Overview | `OverviewPage.vue` 根网格及 1366 media | 页面根节点比 content 高约 158 px，最近会话不可达 | 将固定行高改为 `minmax(0,1fr)` 分配，压缩小视口间距而不隐藏内容 | 最近会话可达、page/section rect 断言 |
| UI-C14 | Manual | `ManualControlPage.vue:428,1071-1082` | 1920 底部约 89 px 空白；英文模式/陈旧状态 | 弹性网格吸收剩余高度；模式/反馈中文化；安全联锁与 fail-closed 不变 | 底部空白阈值、控制 409 回归、安全状态 DOM |
| UI-C15 | Auto Test | `AutoTestPage.vue:419,1082-1144` | 1920 底部约 79 px 空白；WAIT/RUNNING/PASS 英文；刷新闪烁风险 | 弹性结果/列表区；状态字典；共享动作按钮与独立 action pending | 运行态按钮稳定、图表边界、状态中文化 |
| UI-C16 | Alarms | `AlarmDiagnosisPage.vue:312,698-699` | 基线按钮未抽取；Normal/Warning 等英文；图表标签密集 | 抽取共享动作按钮；状态字典；饼图/时间轴标签约束 | 刷新稳定、中文标签、图表边界 |
| UI-C17 | Reports | `ReportManagementPage.vue:326-347` | PASS/FAIL 与打印状态混合英文；动作样式自有 | 统一结果/打印状态中文；扫描/导出/打印/删除使用共享按钮并保持危险层级 | 打印状态回归、权限与布局断言 |
| UI-C18 | History | `HistoryPage.vue:1-168` | PASS/FAIL/RUNNING 英文；筛选和会话动作按钮不统一 | 中文状态字典；工具栏/会话动作使用共享组件 | 查询、回放、权限、双分辨率断言 |
| UI-C19 | Settings | `SystemSettingsPage.vue:1-321` | 角色与 Mock 英文；按钮样式最多；危险操作层级不统一 | 角色/环境中文化；共享按钮；Mock/维护/恢复保持 warning/danger | 角色矩阵、危险操作颜色、布局断言 |
| UI-C20 | E2E | `desktop/scripts/phase05-e2e.mjs` | 旧检查只验证 document 无滚动，无法发现被 `overflow:hidden` 裁切 | 增加 page/content/section rect、底部空白、内部滚动、segmented、图表、中文与稳定采样 | 11 页 × 2 视口 + 60 秒专项场景 |

## 安全决策

1. 本工作包不增加任何 CAN 发送 API、报文 ID 或白名单项。
2. Network 的“通道启用”只修改既有通道配置草稿；“主动发送权限”是只读安全状态，不把 `ChannelConfig.enabled` 伪装成发送授权。
3. CAN1 主动发送与默认控制通道选择永久锁定；CAN2 仍只允许后端批准的 `0x121`。
4. stale、invalid、unavailable、Mock 或后端离线数据只用于展示，不能作为安全判断中的新鲜有效反馈。
5. 所有动态验证只运行 Mock、临时数据目录和 `127.0.0.1`，不连接真实设备。
