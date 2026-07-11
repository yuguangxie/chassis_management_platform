# 阶段四验证记录：实时性能、可靠性与 UI 收口

验证时间：2026-07-10（Asia/Shanghai）  
运行边界：仅 `127.0.0.1`、`normal_pass` Python simulator；未连接真实车辆或真实 CAN 设备。

## 门禁结论

**阶段四门禁通过。** 本阶段未发现阶段一至三安全语义或 API 契约回归。最终 stale-online 场景中，停止仿真器 2.2 秒后 CAN1/CAN2 均离线，`POST /api/v1/control/121/send-once` 返回 `409`，控制未被放行。

## 已验证项

| 项目 | 结果 | 主要证据 |
| --- | --- | --- |
| 1000 fps、10 分钟 loopback 压测 | 通过：600,000 帧，500 fps/通道，队列和 drop 均为 0 | [stress_1000fps.json](stress-10m/stress_1000fps.json)、[summary.json](stress-10m/summary.json) |
| 异步日志批量/轮转/压缩 | 通过：3 次 rotation、3 个 gzip archive | [summary.json](stress-10m/summary.json)、[log_rotation_snapshot_02.json](stress-10m/log_rotation_snapshot_02.json) |
| WS 节流和 raw opt-in | 通过：4 秒内 signal 35 批、statistics 4 批；未订阅 raw 为 0，显式订阅 raw batch 为 18 | [runtime_websocket_summary.json](runtime/runtime_websocket_summary.json) |
| 后端重启/现存渲染器重连 | 通过：重启期间端口确实离线；恢复后服务端看到 1 个订阅客户端、队列 0；窗口退出后客户端归零 | [reconnect_summary.json](runtime/reconnect-attempt6/reconnect_summary.json)、[orchestration.json](runtime/reconnect-attempt6/orchestration.json)、[server_metrics_while_renderer_alive.json](runtime/reconnect-attempt6/server_metrics_while_renderer_alive.json)、[server_metrics_after_renderer_exit.json](runtime/reconnect-attempt6/server_metrics_after_renderer_exit.json) |
| 单窗口 11 页连续路由切换 | 通过：11/11 路由加载；无 `Failed to fetch`、无页面级滚动；退出后无 WS client 残留 | [summary.json](runtime/navigation/summary.json)、[single_window_navigation.json](runtime/navigation/single_window_navigation.json) |
| simulator 停止安全降级 | 通过：2.2 秒后两个通道离线，控制 409 | [result.json](runtime/stale-online-final/result.json) |
| 11 页视觉采集 | 通过：22 张截图；1920x1080 和 1366x768 均无页面级滚动、白色原生表单或大红请求失败横幅 | [summary.json](screenshots/final/summary.json)、[screenshots](screenshots/final) |
| 视觉差异基线 | 已生成 10 页参考图差异；系统设置页没有可信独立参考图 | [visual_diff_metrics.json](screenshots/final-diff2/visual_diff_metrics.json) |
| 手动控制稳定状态 | 通过：真实联锁归并为 7 项概览；1366x768 下急停与安全停车可见 | [manual screenshot](screenshots/manual-final/manual-control_1366x768.png) |

## 测试结果

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| `python -m pytest backend/tests -q` | 90 passed, 5 warnings | [tests_backend_full_isolated.txt](tests_backend_full_isolated.txt) |
| `python -m pytest simulator/tests -q`（项目根） | 3 passed | [tests_simulator_root.txt](tests_simulator_root.txt) |
| `npm.cmd run typecheck` | 通过 | [tests_frontend_typecheck_final.txt](tests_frontend_typecheck_final.txt) |
| `npm.cmd run build` | 通过 | [tests_frontend_build_final.txt](tests_frontend_build_final.txt) |
| `npm.cmd run test` | 未配置该 script | [tests_frontend_test.txt](tests_frontend_test.txt) |
| `npm.cmd run lint` | 未配置该 script | [tests_frontend_lint.txt](tests_frontend_lint.txt) |

首次在运行中的 UDP 后端上执行后端测试时，`TestClient` 与 8234/8235 发生端口冲突；完整失败输出保留在 [tests_backend_full.txt](tests_backend_full.txt)。关闭运行实例后重新执行并通过的隔离输出是最终判据。

## 实现摘要

- CAN 接收采用通道接收队列加共享 pipeline 队列；关键安全帧优先等待容量，非关键帧在满载时按计数丢弃；统计公开 queue depth、capacity、drop、receive age 和有界 recent buffer。
- 生命周期服务将帧解码、遥测持久化与 WebSocket 推送解耦。`RealtimePublisher` 以 10 Hz 批发信号/最新帧，以 1 Hz 推送统计；raw batch 只面向显式订阅者。
- WebSocket 每客户端拥有 256 条上限队列和发送任务；慢客户端溢出后断开，不能反压 CAN 接收。
- 原始 CAN 与解码信号写入转为异步批量策略；原始 CSV 按会话/日期/大小轮转并 gzip 归档。
- 前端 WS client 是带 `on/off`、unsubscribe、指数退避和单例保护的唯一连接；stores 直接消费 batch payload。
- 路由改为按页面懒加载，ECharts/Vue/icon 分包；图表使用 `ResizeObserver` 和 dispose；全局表单控件固定深色主题。
- 手动控制把真实后端的 9 条联锁规则归并为 7 条紧凑安全概览，仅改变展示，不改变 SafetyInterlockService 结论。

## 已知限制与后续项

1. `echarts-vendor` 仍为 1.03 MB（gzip 343 KB），主 bundle 已降为约 53 KB；后续可按 ECharts 图表组件做更细粒度按需导入。
2. `desktop/package.json` 尚未定义 `test` 与 `lint` scripts，应在后续质量阶段补齐，不应将“未配置”视作通过。
3. 视觉像素差异包含不同截图尺寸缩放、实时数据、文字抗锯齿，不能直接作为 UI 分数。报告管理的差异最大，仍建议在后续 UI 精修阶段人工逐项比对。
4. 1366x768 下部分非核心图表区域会被紧凑布局隐藏；安全状态、急停和安全停车仍可见。`signal-dashboard` 使用 SVG sparkline，故无 canvas 是预期结果。
5. 本验证只覆盖 loopback 仿真；不构成真实硬件、真实车辆、长时间磁盘满载或生产网络部署验收。
