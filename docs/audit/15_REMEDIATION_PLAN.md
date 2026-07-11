# 分阶段整改计划

| 任务 | Issue | 目标 | 修改文件 | 前端 | 后端 | 测试 | 验收 | 依赖 | 工作量 | 风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-01 | SAFE-001/002/005 | 重写 EOL 可取消状态机与急停停车闭环 | engine.py, api/eol.py, control/* | 状态与确认 UI | task cancel、safe stop、interlock | 故障注入+硬超时 | pause/abort/e-stop 不再执行下一步且车辆反馈为 0 | SafetyInterlock | L | 高 |
| A-02 | SAFE-003/PERF-001 | 消除积压导致的伪在线 | udp_gateway.py, lifecycle.py, statistics.py | 显示 source age | 有界队列、节流、receive timestamp | 1000fps+断链 | 5s 内离线且控制 409 | 队列设计 | L | 高 |
| A-03 | SAFE-004 | 服务端认证和 RBAC | main.py, api/*, desktop auth | 登录/锁屏/角色显示 | token/session/RBAC | 越权/API 安全 | 伪造 role/header 无效 | 部署身份源 | L | 高 |
| A-04 | SAFE-006/007/008 | 统一预览、实际编码和联锁状态 | api/control.py, control_121.py | 只展示 authoritative bytes | 统一 DTO 和停车状态机 | loopback golden vectors | UI byte=实发 byte，停车有反馈 | A-02 | M | 高 |
| B-01 | EOL-001/002 | 按 YAML 实现 12 步真实断言 | eol/*, configs/test_plan.yaml | 实时步骤/断言 | 动作、采样窗、阈值、失败策略 | 五 profile+断链/DBC/DB | 全部预期一致 | A 阶段 | XL | 高 |
| B-02 | DB-001/003/004 | 会话 UoW 与全链路持久化 | storage/*, lifecycle.py, eol/* | 历史读取真实 source | 事务、批量写、恢复 | 回滚/并发/重启 | 核心表完整且可追溯 | schema migration | L | 中 |
| B-03 | REPORT-001/002 | 生产报告与真实预览 | reports/*, api/reports.py | 真实 PDF/JSON/CSV preview | 模板/字体/元数据/DB | 渲染 diff、可打开 | PASS/FAIL 报告内容完整 | B-02 | L | 中 |
| B-04 | SIM-001 | dev/prod 配置隔离 | configs, scripts/dev_* | 明确 Mock banner | profile 强制 loopback | 禁止生产 IP 测试 | 默认联调不触碰真实网段 | 认证配置 | M | 高 |
| C-01 | UI-001/005 | 逐页 1366 和像素校准 | pages/*.vue, styles | 全部 | 无 | 双分辨率截图 diff | 1920 一屏；1366 核心可操作 | B 阶段数据契约 | L | 低 |
| C-02 | UI-002/003/004/006 | 修复状态源、曲线选择、表单和图表初始化 | stores, pages, chart components | 交互和主题 | 状态契约 | Playwright | 无矛盾状态/白控件/空图 | API source metadata | M | 中 |
| D-01 | API-002/004 | 替换 dashboard/diagnostic Mock 与 TCP 假配置 | api/can.py, signals.py | 来源标记 | 真实统计/诊断/TCP或拒绝 | 契约/E2E | 生产无无标识 fallback | B-02 | L | 中 |
| D-02 | API-003/005/006 | 统一 API 契约与错误 | main.py, api models, http.ts | 统一错误 toast | response model/trace_id/404 | OpenAPI contract | 错误可追踪且删除安全 | A-03 | M | 中 |
| D-03 | 历史/报告/导出 Stub | 实现文件导出、下载、回放和审批 | api/history.py, reports.py, signals.py | 真实下载进度 | 安全文件服务 | 文件/权限 E2E | 按钮无 stub | B-02/B-03 | L | 中 |
| E-01 | API-001/PERF-002 | WebSocket 节流、背压和生命周期 | ws manager, lifecycle, websocket.ts | 取消订阅/重连 | topic cadence/queue | 10min soak | 无重复订阅且频率达标 | A-02 | L | 中 |
| E-02 | DB-002/CAN-001/002 | 日志轮转与实时统计 | raw_log_writer.py, statistics.py | 真实缓冲/磁盘告警 | 批量 IO/滚动 fps | 1000fps 10min | 无 backlog/磁盘失控 | E-01 | M | 中 |
| E-03 | DEPLOY-001/002/003/PERF-003 | Windows 安装包和依赖升级 | desktop package/electron, build scripts | 懒加载 | backend packaging/process manager | 干净机安装/升级 | 离线启动、崩溃恢复 | A-03 | L | 中 |
| F-01 | TEST-001/002/003 | 建立 CI 和覆盖率门槛 | tests, package scripts | Vitest/Playwright | pytest/coverage | 全套 CI | 根目录一键复现 | 前述阶段 | M | 低 |
| F-02 | 全部 P0/P1 | 封闭台架生产验收 | 验收脚本/记录 | 操作员验收 | 硬件故障注入 | 24h soak/断电/断链 | 独立签字后仅 PILOT_READY | A-E 全完成 | XL | 高 |

## 阶段门禁

- 阶段 A：P0 安全和车辆控制。完成前禁止真实台架和车辆。
- 阶段 B：P1 生产阻塞和错误结论。完成后才可申请封闭台架。
- 阶段 C：UI 高还原和关键可操作性，不得掩盖真实状态。
- 阶段 D：Mock/Stub 替换为真实服务。
- 阶段 E：性能、可靠性、打包和部署。
- 阶段 F：生产验收；至少 normal/全部故障/断链/断电/DB失败/DBC失败/急停以及 24h soak。

## 时间优先级

- 立即必须修复：全部 P0，EOL-001，PERF-001，API-001。
- 上台架前必须修复：全部 P0/P1，DBC-001，API-003，DB-001/003/004。
- 量产前必须修复：全部 P0/P1/P2、安装包、报告模板、24h 稳定性和权限审计。
- 可延期：纯像素级 P3、进一步 bundle 优化，但不能延期 ECharts 空图和根测试可复现性。
