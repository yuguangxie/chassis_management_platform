# UI 视觉还原审计

## 方法

实际运行 Vite/Electron renderer，在 1920×1080 与 1366×768 采集 22 张截图；前 10 页将当前 1920 图缩放至参考图 1672×941 后生成绝对差异和三联图。像素差异受窗口标题栏、动态时间和数据变化影响，仅作证据，不直接换算评分。系统设置按需求文档和统一设计语言评分。

| 路由 | 页面 | 评分 | 等级 | 优先级 |
| --- | --- | --- | --- | --- |
| /overview | 总览工作台 | 91 | 基本还原 | P2 |
| /network-config | 网络配置 | 90 | 基本还原 | P2 |
| /can-monitor | CAN 报文监控 | 84 | 部分还原 | P1 |
| /signal-dashboard | 信号仪表盘 | 83 | 部分还原 | P2 |
| /realtime-curve | 实时曲线 | 84 | 部分还原 | P1 |
| /manual-control | 手动控制 | 89 | 基本还原 | P0 |
| /auto-test | 一键检测 | 87 | 基本还原 | P0 |
| /alarm-diagnosis | 告警诊断 | 88 | 基本还原 | P1 |
| /report-management | 报告管理 | 86 | 基本还原 | P1 |
| /history | 历史记录 | 89 | 基本还原 | P1 |
| /system-settings | 系统设置 | 86 | 基本还原 | P1 |

平均还原度：**87.0/100**。前 10 页像素 MAD 为 18.743~25.333，超过 10 灰度差的像素为 28.680%~39.951%。原始指标：[visual_diff_metrics.csv](evidence/screenshots/diff/visual_diff_metrics.csv)，运行尺寸指标：[ui_runtime_metrics.json](evidence/screenshots/current/ui_runtime_metrics.json)。

## 共享结论

- 1920×1080：11 页 document 均等于 viewport，未见页面级滚动和大红 Failed to fetch；ECharts 均有非零 canvas。
- 1366×768：CAN 监控、信号仪表盘最稳定；其余多页裁切或改为页面内部滚动，未满足“核心内容一屏”。
- Electron：`frame:false`、`Menu.setApplicationMenu(null)`、深色自定义标题栏实际存在，无 Windows 原生菜单/白标题栏。
- 离线：抽查 5 页均显示 Mock/离线状态，无 Failed to fetch 横幅，见 `offline_*` 截图和 [offline_runtime_metrics.json](evidence/screenshots/current/offline_runtime_metrics.json)。
- 控制台：2 条 ECharts 宽高为 0 的警告，见 [browser_console_warnings.json](evidence/screenshots/current/browser_console_warnings.json)。


## 01. 总览工作台 `/overview` — 91/100

- 当前 1920：[截图](evidence/screenshots/current/01_overview_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/01_overview_1366x768.png)
- 参考：[evidence/screenshots/reference/01_overview.png](evidence/screenshots/reference/01_overview.png)
- 差异图：[evidence/screenshots/diff/01_overview_reference_current_diff.png](evidence/screenshots/diff/01_overview_reference_current_diff.png)
- 分项：布局/30=28, 组件/20=19, 内容/15=14, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=3
- 像素证据：MAD=22.366; |diff|>10 的像素=39.333%。
- 差异：状态卡与图表区比参考图更紧凑；顶部状态的新开页初始化偶发显示 CAN 离线；若数据库为空，多数业务指标来自 fallback。
- 缺失：没有真实数据库产能统计；最近会话为 fallback。
- 多余/新增：自定义无框标题栏占用 32px，参考图没有独立评估该高度。
- 1920×1080：一屏显示，document 1080px，无页面级滚动；无 Failed to fetch 横幅。
- 1366×768：页面根内容约 814px，高于约 610px 可用区且 overflow 隐藏，底部内容存在裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P2。


## 02. 网络配置 `/network-config` — 90/100

- 当前 1920：[截图](evidence/screenshots/current/02_network_config_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/02_network_config_1366x768.png)
- 参考：[evidence/screenshots/reference/02_network_config.png](evidence/screenshots/reference/02_network_config.png)
- 差异图：[evidence/screenshots/diff/02_network_config_reference_current_diff.png](evidence/screenshots/diff/02_network_config_reference_current_diff.png)
- 分项：布局/30=27, 组件/20=19, 内容/15=14, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=3
- 像素证据：MAD=19.428; |diff|>10 的像素=31.297%。
- 差异：四卡结构接近参考图，但诊断数值均为 Stub；TCP 可选但后端只有 UDP gateway。
- 缺失：真实 Ping、回环、协议合法率、DLC/保留位诊断。
- 多余/新增：Mock 状态提示是当前实现新增的必要降级信息。
- 1920×1080：一屏显示，无页面级滚动。
- 1366×768：页面根内容约 852px，发生隐藏裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P2。


## 03. CAN 报文监控 `/can-monitor` — 84/100

- 当前 1920：[截图](evidence/screenshots/current/03_can_monitor_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/03_can_monitor_1366x768.png)
- 参考：[evidence/screenshots/reference/03_can_monitor.png](evidence/screenshots/reference/03_can_monitor.png)
- 差异图：[evidence/screenshots/diff/03_can_monitor_reference_current_diff.png](evidence/screenshots/diff/03_can_monitor_reference_current_diff.png)
- 分项：布局/30=25, 组件/20=17, 内容/15=12, 样式/15=13, 细节/10=8, 1920/5=5, 1366/5=4
- 像素证据：MAD=22.14; |diff|>10 的像素=36.03%。
- 差异：主表和详情位置正确，但详情信号及底部统计由固定数据生成，不是实时 DBC 解码结果；同 ID 跨通道被合并。
- 缺失：真实导出、历史文件、实时统计、按实际帧值解码详情。
- 多余/新增：帧更新次数列增加了可观测性。
- 1920×1080：一屏显示，表格内部滚动正常。
- 1366×768：主要结构仍能放入可用区，是兼容性较好的页面之一。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。


## 04. 信号仪表盘 `/signal-dashboard` — 83/100

- 当前 1920：[截图](evidence/screenshots/current/04_signal_dashboard_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/04_signal_dashboard_1366x768.png)
- 参考：[evidence/screenshots/reference/04_signal_dashboard.png](evidence/screenshots/reference/04_signal_dashboard.png)
- 差异图：[evidence/screenshots/diff/04_signal_dashboard_reference_current_diff.png](evidence/screenshots/diff/04_signal_dashboard_reference_current_diff.png)
- 分项：布局/30=25, 组件/20=17, 内容/15=12, 样式/15=13, 细节/10=7, 1920/5=5, 1366/5=4
- 像素证据：MAD=18.743; |diff|>10 的像素=28.68%。
- 差异：卡片矩阵、底盘示意和 Watchlist 基本齐全；趋势与缺失信号大量回填固定值，实时/Mock 边界不清楚。
- 缺失：真实布局保存和真实关注信号持久化。
- 多余/新增：页面级离线徽标。
- 1920×1080：一屏显示。
- 1366×768：核心结构可见，密度明显高于参考图但未发现页面级滚动。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P2。


## 05. 实时曲线 `/realtime-curve` — 84/100

- 当前 1920：[截图](evidence/screenshots/current/05_realtime_curve_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/05_realtime_curve_1366x768.png)
- 参考：[evidence/screenshots/reference/05_realtime_curve.png](evidence/screenshots/reference/05_realtime_curve.png)
- 差异图：[evidence/screenshots/diff/05_realtime_curve_reference_current_diff.png](evidence/screenshots/diff/05_realtime_curve_reference_current_diff.png)
- 分项：布局/30=25, 组件/20=17, 内容/15=13, 样式/15=13, 细节/10=7, 1920/5=5, 1366/5=4
- 像素证据：MAD=19.724; |diff|>10 的像素=37.315%。
- 差异：六图矩阵完整，但页面显示 0/256 已选时曲线仍全部存在；采样、降采样和历史回放多为 UI/Mock。
- 缺失：选择信号对 series 的真实约束、真实 CSV/快照、回放 seek。
- 多余/新增：离线曲线状态徽标。
- 1920×1080：一屏显示，图表均非空。
- 1366×768：根 scrollHeight 约 764px、clientHeight 约 610px且隐藏，底部回放区裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。


## 06. 手动控制 `/manual-control` — 89/100

- 当前 1920：[截图](evidence/screenshots/current/06_manual_control_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/06_manual_control_1366x768.png)
- 参考：[evidence/screenshots/reference/06_manual_control.png](evidence/screenshots/reference/06_manual_control.png)
- 差异图：[evidence/screenshots/diff/06_manual_control_reference_current_diff.png](evidence/screenshots/diff/06_manual_control_reference_current_diff.png)
- 分项：布局/30=27, 组件/20=18, 内容/15=14, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=3
- 像素证据：MAD=21.886; |diff|>10 的像素=38.83%。
- 差异：视觉结构接近参考，但控制状态卡使用硬编码 allow；页面预览字节与实际发帧不一致。
- 缺失：真实反馈和曲线、可证明的停车闭环。
- 多余/新增：4 个控件计算样式为白底，破坏统一深色表单。
- 1920×1080：一屏显示。
- 1366×768：根内容约 906px，明显裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P0。


## 07. 一键检测 `/auto-test` — 87/100

- 当前 1920：[截图](evidence/screenshots/current/07_auto_test_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/07_auto_test_1366x768.png)
- 参考：[evidence/screenshots/reference/07_auto_test.png](evidence/screenshots/reference/07_auto_test.png)
- 差异图：[evidence/screenshots/diff/07_auto_test_reference_current_diff.png](evidence/screenshots/diff/07_auto_test_reference_current_diff.png)
- 分项：布局/30=27, 组件/20=18, 内容/15=13, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=2
- 像素证据：MAD=24.03; |diff|>10 的像素=38.302%。
- 差异：12 步和高密度区域基本还原，但 dashboard 展示固定会话；运行引擎与 UI 状态没有真实闭环。
- 缺失：真实测量/断言/日志/曲线持久化，可靠暂停、中止和急停。
- 多余/新增：Mock 会话状态可与实际引擎状态并存。
- 1920×1080：一屏显示。
- 1366×768：根内容约 893px，底部按钮与统计区裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P0。


## 08. 告警诊断 `/alarm-diagnosis` — 88/100

- 当前 1920：[截图](evidence/screenshots/current/08_alarm_diagnosis_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/08_alarm_diagnosis_1366x768.png)
- 参考：[evidence/screenshots/reference/08_alarm_diagnosis.png](evidence/screenshots/reference/08_alarm_diagnosis.png)
- 差异图：[evidence/screenshots/diff/08_alarm_diagnosis_reference_current_diff.png](evidence/screenshots/diff/08_alarm_diagnosis_reference_current_diff.png)
- 分项：布局/30=27, 组件/20=18, 内容/15=14, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=2
- 像素证据：MAD=21.049; |diff|>10 的像素=39.375%。
- 差异：0x77、0x102 和 bitmap 布局完整，但历史、建议、图表和多数详情来自 Mock。
- 缺失：真实诊断导出、人工放行工作流、告警持久化。
- 多余/新增：跳转前先调用 Stub API。
- 1920×1080：一屏显示。
- 1366×768：根内容约 762px，底部区域裁切。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。


## 09. 报告管理 `/report-management` — 86/100

- 当前 1920：[截图](evidence/screenshots/current/09_report_management_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/09_report_management_1366x768.png)
- 参考：[evidence/screenshots/reference/09_report_management.png](evidence/screenshots/reference/09_report_management.png)
- 差异图：[evidence/screenshots/diff/09_report_management_reference_current_diff.png](evidence/screenshots/diff/09_report_management_reference_current_diff.png)
- 分项：布局/30=26, 组件/20=18, 内容/15=13, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=2
- 像素证据：MAD=25.333; |diff|>10 的像素=39.951%。
- 差异：报告预览器视觉完整，但并未打开真实 PDF/DOCX；操作按钮多为 Stub，删除请求不携带角色头。
- 缺失：真实预览、打印、导出、重新生成、目录打开。
- 多余/新增：Mock 预览纸张在任意文件类型下均可显示。
- 1920×1080：一屏显示。
- 1366×768：页面改为内部 overflow:auto，需要页面滚动才能看完，不满足一屏要求。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。


## 10. 历史记录 `/history` — 89/100

- 当前 1920：[截图](evidence/screenshots/current/10_history_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/10_history_1366x768.png)
- 参考：[evidence/screenshots/reference/10_history.png](evidence/screenshots/reference/10_history.png)
- 差异图：[evidence/screenshots/diff/10_history_reference_current_diff.png](evidence/screenshots/diff/10_history_reference_current_diff.png)
- 分项：布局/30=27, 组件/20=19, 内容/15=14, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=2
- 像素证据：MAD=20.979; |diff|>10 的像素=38.894%。
- 差异：两栏时间线、下载卡、Pareto 和分页均接近参考图，但数据库无业务记录，展示源是 Mock。
- 缺失：真实会话、时间线、文件下载和历史导出。
- 多余/新增：自动刷新控件为当前实现补充。
- 1920×1080：一屏显示。
- 1366×768：页面内部滚动，底部统计无法同时可见。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。


## 11. 系统设置 `/system-settings` — 86/100

- 当前 1920：[截图](evidence/screenshots/current/11_system_settings_1920x1080.png)
- 当前 1366：[截图](evidence/screenshots/current/11_system_settings_1366x768.png)
- 参考：无独立参考图；按 `docs/ui/pages/11_system_settings.md` 与统一设计语言审计
- 差异图：不适用
- 分项：布局/30=26, 组件/20=18, 内容/15=13, 样式/15=14, 细节/10=8, 1920/5=5, 1366/5=2
- 像素证据：无独立参考，不做像素差分。
- 差异：按需求文档形成三行网格与七按钮，但角色矩阵没有认证支撑，维护模式只保存进程内状态。
- 缺失：真实文件选择/导入/导出、身份认证、生产配置发布闭环。
- 多余/新增：系统设置没有独立参考图，使用统一风格与 11_system_settings.md 评估。
- 1920×1080：一屏显示。
- 1366×768：使用页面内部滚动，不能同时显示全部卡片和底部按钮。
- 建议：优先修复功能真实性与 1366 裁切，再按 diff 校准尺寸；优先级 P1。
