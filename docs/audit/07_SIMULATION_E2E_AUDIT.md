# 仿真与端到端审计

> **历史基线 / 已被后续审计取代。** 当前结论见 [`current_audit_2026-07-23`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 和本轮 [P0/P1 验证索引](../verification/software-p0-p1-closure-2026-07-23/README.md)。

## 运行链路

实际启动 FastAPI、Python simulator、Vite renderer，并用 loopback 配置补做 0x121 双向控制。后端监听 127.0.0.1:8234/8235，仿真器设备端为 127.0.0.1:12341/12342。默认生产配置的发送端仍是 [REDACTED_CAN1_GATEWAY]/99:1234，因此标准开发命令并非完整双向闭环。

normal profile 收到/展示主要 ID 包括 0x51、0x77、0x100~0x105、0x121、0x168、0xE1、0x703、0x704；DBC status loaded，SignalStore 和 WebSocket 有更新。证据：[latest frames](evidence/simulation/normal_pass_latest_frames.json)、[signals](evidence/simulation/normal_pass_signals.json)、[channels](evidence/simulation/normal_pass_channels.json)。

| Profile | 预期 | 实际 | 判定 | 执行步数 | 报告 | 安全停车 |
| --- | --- | --- | --- | --- | --- | --- |
| normal_pass | PASS | PASS | 一致 | 12 | 已生成 | 否 |
| bms_low_soc | FAIL | FAIL | 结果一致但错误地在第1步失败 | 1 | 已生成 | 未触发/未证明 |
| warning_fault | FAIL | FAIL | 结果一致但错误地在第1步失败 | 1 | 已生成 | 未触发/未证明 |
| steering_no_response | FAIL | PASS | 不一致 | 12 | 生成错误 PASS | 否 |
| brake_fail | FAIL | PASS | 不一致 | 12 | 生成错误 PASS | 否 |

## 控制闭环

专用 loopback 配置下，仿真器实际收到 10 个 0x121 帧，覆盖 send-once、periodic 和 safe-stop；-60/60 编码为 C4/3C，超速和急停阻断返回 409。见 [control_loopback_e2e.json](evidence/simulation/control_loopback_e2e.json) 与 [simulator RX](evidence/simulation/control_loopback_simulator_rx.txt)。该证据不代表默认生产配置可安全使用。

## 降级与停止

- 后端停止：抽查 5 页完整 fallback，无大红横幅，见 offline 截图。
- simulator 停止：低负载最终会离线；高负载下因处理积压，5 秒后 CAN2 仍在线并允许控制。
- WebSocket：实际推送存在，但频率远超规范。

## 结论

仿真报文能够真正进入后端和页面，不是仅进程启动；但故障 profile 判定只有 2/4 符合预期，安全停车没有由 EOL 故障自动触发，默认双向端口配置不一致。仿真评分 40/100。
