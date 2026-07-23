# 桌面端 UI 一致性专项审计证据

- 日期：2026-07-23（Asia/Shanghai）
- Git commit：`ba47b0a`
- 分支：`codex/ui-page-stub-closure`
- 范围：11 个业务页面，1366×768 和 1920×1080
- 动态边界：Mock/正常仿真数据、`127.0.0.1` 回环；未访问真实 CAN 或非回环 endpoint
- 数据边界：独立临时 `data_root`，未修改现有业务数据

## 方法

1. 确认工作树无未提交 UI 修改。
2. 复用本机 Vite `http://127.0.0.1:5173`。
3. 使用 Python 3.11 虚拟环境启动临时后端 `127.0.0.1:8800`。
4. 启动 `normal_pass` 仿真器，CAN1/CAN2 收发地址全部为 `127.0.0.1`。
5. 建立只存在于临时 data_root 的审计管理员会话；截图和文档不保存 token、密码或 bootstrap secret。
6. 对 11 页采集两个视口截图、DOM 边界、按钮计算样式和中英文状态。
7. 对信号仪表盘做 20 次约 8 秒状态采样；对一键检测/告警页做短时按钮状态采样。

## 主要证据

- 信号质量采样：20 次中 4 次无 `unavailable`，16 次出现 7 个 `unavailable`；切换周期与 2500 ms HTTP 轮询一致。
- 1366×768：总览页面根节点超出可视内容区约 158 px；网络配置约 160 px。
- 1920×1080：手动控制页面底部未利用空间约 89 px；一键检测约 79 px。
- 全站主要操作按钮高度出现 32、56、70、78、88、102、116 px；单页计算样式签名最多 17 种。
- CAN 监控过滤栏中，3 个通道按钮最小总宽 210 px 但列宽仅 148 px；方向列仅 130 px；进制两项至少 140 px 但列宽仅 100 px。
- 按钮闪烁短采样没有稳定复现，但 store/page 代码确认后台刷新会切换共享 loading，并直接改变按钮 disabled；主审计将其标为“代码确认、需要运行中长采样”。

## 截图清单

`screenshots/` 下共 22 张：

- `overview_1366x768.png` / `overview_1920x1080.png`
- `network-config_1366x768.png` / `network-config_1920x1080.png`
- `can-monitor_1366x768.png` / `can-monitor_1920x1080.png`
- `signal-dashboard_1366x768.png` / `signal-dashboard_1920x1080.png`
- `realtime-curve_1366x768.png` / `realtime-curve_1920x1080.png`
- `manual-control_1366x768.png` / `manual-control_1920x1080.png`
- `auto-test_1366x768.png` / `auto-test_1920x1080.png`
- `alarm-diagnosis_1366x768.png` / `alarm-diagnosis_1920x1080.png`
- `report-management_1366x768.png` / `report-management_1920x1080.png`
- `history_1366x768.png` / `history_1920x1080.png`
- `system-settings_1366x768.png` / `system-settings_1920x1080.png`

## 代表性截图

- [网络配置 1366×768](screenshots/network-config_1366x768.png)
- [CAN 监控 1366×768](screenshots/can-monitor_1366x768.png)
- [信号仪表盘 1366×768](screenshots/signal-dashboard_1366x768.png)
- [实时曲线 1366×768](screenshots/realtime-curve_1366x768.png)
- [手动控制 1920×1080](screenshots/manual-control_1920x1080.png)
- [一键检测 1920×1080](screenshots/auto-test_1920x1080.png)

## 结论入口

- [专项审计结果](../../audit/16_DESKTOP_UI_CONSISTENCY_AUDIT_2026-07-23.md)
- [后续优化实施 Prompt](../../reference/DESKTOP_UI_OPTIMIZATION_PROMPT_2026-07-23.md)
