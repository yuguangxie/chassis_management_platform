# 阶段四证据清单

## 运行与吞吐

- `stress-10m/stress_1000fps.json`: 10 分钟、1000 fps loopback 原始采样。
- `stress-10m/summary.json`: 压测结论摘要。
- `stress-10m/log_rotation_snapshot*.json`: 原始 CAN gzip 轮转实物快照。
- `runtime/final_runtime_metrics.json`: 验证结束前的在线、queue、buffer 和 writer 指标。
- `runtime/create_task_inventory.txt`: 生命周期、网关和 WS 的 task 创建点审阅记录。

## WebSocket 与重连

- `runtime/runtime_websocket_metrics_final.json/runtime_websocket_metrics.json`: 原始 topic 频率记录。
- `runtime/runtime_websocket_summary.json`: 10 Hz/1 Hz/opt-in raw 结论。
- `runtime/reconnect-attempt6/`: 最终有效的 FastAPI 重启、现存 Electron 渲染器重连、客户端队列归零证据。
- `runtime/navigation/`: 单窗口连续切换 11 个路由及 WS client 生命周期证据。

## 安全降级

- `runtime/stale-online-final/pre_stop_channels.json`: 停止 simulator 前状态。
- `runtime/stale-online-final/result.json`: 2.2 秒后双通道 offline 与控制 `409`。
- `runtime/stale-online-final/channels_after_restore.json`: normal_pass 恢复后状态。

## UI

- `screenshots/final/`: 11 页 x 1920x1080、1366x768 截图与自动检查。
- `screenshots/final/summary.json`: 无页面滚动、白色表单或大红错误横幅的汇总。
- `screenshots/manual-final/`: 稳定真实联锁状态下的手动控制补充截图。
- `screenshots/reference/`: 未改动的参考图副本。
- `screenshots/final-diff2/visual_diff_metrics.json`: Pillow 图像差异及 composite 图片。

## 测试与构建

- `tests_backend_full_isolated.txt`: 90 个后端测试通过。
- `tests_simulator_root.txt`: 3 个 simulator 测试通过。
- `tests_frontend_typecheck_final.txt`: TypeScript 检查通过。
- `tests_frontend_build_final.txt`: 生产构建通过，包含 chunk size warning。
- `tests_frontend_test.txt`、`tests_frontend_lint.txt`: 未配置前端 test/lint script 的真实输出。
