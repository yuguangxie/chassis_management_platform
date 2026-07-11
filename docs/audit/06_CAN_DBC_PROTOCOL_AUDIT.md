# CAN、DBC 与 USR-CAN115 协议审计

## DBC

- `assets/*.dbc` 自动扫描：已验证。
- 实际加载：`Yunle_CAN_integrated_candb_jd.dbc`，SHA 前缀 `387ae48bd84852c8`，39 messages、170 signals。
- cantools 加载成功；无文件/解析失败路径会进入 raw-only。
- 0x101 枚举实测：0 idle、1 charging、2 discharging、3 reserved。
- 0x102 输入 `0x8001` 解为无符号 bitmap 32769；但 individual bool 未在 known decoder 中展开。
- override 配置明确 0x121 int8、0x102 unsigned、0x104~0x109 可变 cell、Torque 为相电流 A。

## 13 字节协议

实测 packet：`08 00 00 01 21 40 C4 3C 14 02 00 00 00`。

| 检查 | 结果 |
| --- | --- |
| 长度 13 | 通过 |
| Byte0 FF/RTR/保留位/DLC | 编解码存在 |
| Byte1~4 CAN ID 大端 | 0x00000121，正确 |
| Byte5~12 固定 8 byte | 正确 |
| DLC > 8 | 标记 `dlc_error` |
| 保留位非 0 | 标记 `reserved_bits_error` |
| 粘包两帧 + 5 字节余量 | 解出 0x121/0x77，余 5 |
| UDP 半包跨 datagram | **失败**：拼成伪 0x121 且 parse_status=ok，无重同步 |

完整结果：[protocol_probe.json](evidence/tests/protocol_probe.json)。

## 0x121

| 输入 | 补码 | payload 中转角字节 |
| --- | --- | --- |
| -120 | 0x88 | 88 |
| -60 | 0xC4 | C4 |
| 0 | 0x00 | 00 |
| 60 | 0x3C | 3C |
| 120 | 0x78 | 78 |

单元测试和 loopback 实发均通过；超速与急停时 send-once 返回 409。但 UI 的 `bytes_hex` 展示与 authoritative `data`/实发 payload 不一致，见 SAFE-006。

## 通道、统计和缓存

- CAN1/CAN2 独立 UDP socket 和统计对象；控制通道配置默认为 CAN2。
- `recent_frames` 为两通道共享 2,000 帧，低于文档建议；SignalStore 每信号 3,000 点。
- fps 为启动以来累计平均，不是滚动实时帧率。
- `asyncio.create_task(on_frame)` 无界，导致处理积压和在线时效错误。
- 0x123/0x126/NMT 默认关闭；非维护模式 gate 和 0x126 126..525 范围测试通过。没有发现默认发送这些报文。

## 结论

基础 13-byte codec 与 0x121 补码是当前较可靠部分；UDP 边界处理、0x102 信号化、实时统计和高负载背压尚不满足车辆控制要求。
