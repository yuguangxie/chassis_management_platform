# 执行摘要

> **历史基线 / 已被后续审计取代。** 当前结论请从 [`docs/current_audit_2026-07-23/00_AUDIT_INDEX.md`](../current_audit_2026-07-23/00_AUDIT_INDEX.md) 与 [`docs/verification/software-p0-p1-closure-2026-07-23/README.md`](../verification/software-p0-p1-closure-2026-07-23/README.md) 进入；本文不得单独用于 release 或真实车辆放行。

## 总结

项目可在 Windows 开发环境启动 FastAPI、Vite 和 Electron；DBC 可真实加载，UDP 仿真报文可进入后端，0x121 在专用 loopback 配置下可真实到达仿真器。然而 EOL、安全联锁、持久化、报告和生产打包存在阻断性缺陷，**不建议连接真实车辆，也不建议上真实台架**。在修复 P0 前仅允许静态审查或隔离 Mock 环境。

| 指标 | 结果 | 证据/口径 |
| --- | --- | --- |
| 项目启动 | 开发模式可启动 | evidence/commands/backend_startup.txt；evidence/commands/electron_runtime_probe.json |
| 仿真运行 | 可收帧；默认双向配置不匹配 | evidence/simulation/normal_pass_startup.txt；SIM-001 |
| 11 页 UI 平均还原度 | 87.0% | 22 张双分辨率截图；10 页像素 diff；系统设置按文档 |
| 功能总体完成度 | 46.1% | REAL=1, PARTIAL=.5, MOCK=.25, STUB=.1 的 148 项加权 |
| 真实功能实现率 | 15.5% (23/148) | 仅 REAL 计入 |
| Mock/Stub 比例 | 36.5% | MOCK 36 + STUB 18 |
| 核心规范 API 路由覆盖 | 100% (31/31) | 真实语义实现估计 8/31=25.8%；路由存在不等于完成 |
| 测试 | 后端 30/30；仿真器 1/1（正确 cwd） | 根目录仿真测试收集失败；无前端 test/lint/coverage |
| normal_pass | 实际 PASS，与预期一致 | evidence/simulation/normal_pass_eol_result.json |
| 故障仿真 | 2/4 故障正确 FAIL；2/4 错误 PASS | steering_no_response、brake_fail 错误 PASS |
| 报告 | 文件生成但不可交付 | DOCX 乱码、PDF 中文方块、元数据缺失 |
| 安全红线 | 不满足 | P0 共 5 项 |
| 问题数量 | P0=5 / P1=12 / P2=19 / P3=6 | 共 42 项 |
| 总体评分 | 48/100 | UI 87、功能 46、真实实现 15.5、API 100、测试55、安全28、仿真40、部署20 加权 |
| 生产就绪 | NOT_READY | 不能用于真实硬件 |

## 最关键的 10 个问题

1. EOL 暂停、中止、急停不终止任务，最终可被覆盖为 PASS。
2. CAN 全断开时 EOL 仍执行 12 步并 PASS。
3. 高负载积压帧使仿真器停机 5 秒后 CAN2 仍被判在线并允许控制。
4. 无认证且后端默认 admin；维护和删除权限可由请求字段/头伪造。
5. 急停不下发零速/制动帧，安全停车也只有一次发送。
6. steering_no_response 与 brake_fail 两种故障 profile 错误 PASS。
7. 约 1045fps 输入下只处理约 345.9fps，WebSocket 每帧广播 7 类消息。
8. 核心会话、步骤、断言、帧、信号、告警和报告表均无业务记录。
9. 生成报告中文乱码/方块，PDF 内容不足且缺 DBC/config/software 元数据。
10. Electron 无生产 dist 入口、后端拉起、安装包和 Python runtime 打包。

## 建议

下一阶段先冻结 UI 扩展，完成 P0 状态机/断链/急停/认证修复；随后完成真实断言、持久化、报告、吞吐和部署。P0 全部通过故障注入测试前，不允许连接真实车辆。
