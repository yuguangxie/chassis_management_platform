# 性能与可靠性审计

## 启动与负载

- FastAPI 首次审计启动约 1.3s；DBC 和两个 UDP socket 可初始化。
- Electron 进程在 6s 检查点存活且 4 个进程 responding；未取得可靠首屏 paint timing，因此不写“首屏通过”。
- 60s 目标总 1045fps：实际后端处理增量约 345.9fps；后端工作集 152.62→152.71MB；HTTP 最大 85ms、0 failures；raw log 增长 2.8MB。
- backend CPU 采样为全机归一 5%，不能解释为无压力；吞吐和积压证据显示事件循环处理不过来。

完整数据：[stress summary](evidence/tests/stress_1000fps_60s_summary.json)、[CSV](evidence/tests/stress_1000fps_60s.csv)。

## 可靠性问题

- 每帧 create_task，无界任务数量和时效。
- 每帧同步文件 I/O；每帧 7 次 WebSocket 序列广播。
- statistics payload 包含 recent frames，进一步放大序列化。
- simulator 停止后仍处理积压，在线/周期统计错误。
- WebSocket 无重连/off/backpressure，页面切换累积 handler。
- SQLite 每语句 commit，无事务、无 shutdown close。
- 单文件日志无轮转；长期运行数据增长无界。

## 未执行

未继续 10 分钟 1000fps：60 秒已证明无界 backlog 和磁盘增长，继续会放大主机/磁盘风险而不增加结论强度。未做真实硬件 socket/防火墙/丢包压力。该项明确为未执行，不判通过。

性能可靠性结论：当前适合低速演示数据，不适合资料包目标高帧率长期运行。
