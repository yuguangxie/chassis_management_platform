# 五阶段推荐实施 Prompt

## 使用说明

以下 Prompt 应按顺序分别用于 5 个独立实施任务。每次只执行一个阶段，不要把五个阶段合并到同一次大改中。

执行每个 Prompt 前，应确保：

- 当前工作目录为 `chassis_management_platform/`。
- 已阅读 `docs/reference/PROJECT_FOLLOWUP_ROADMAP.md`。
- 上一阶段验收门禁已经通过。
- 原始 `docs/audit/evidence/` 已保留且不被覆盖。
- 没有明确证据时，不得写“已完成”或“已通过”。

---

## Prompt 1：安全控制与可信边界

```text
当前项目位于 chassis_management_platform/。

本任务只实施《docs/reference/PROJECT_FOLLOWUP_ROADMAP.md》的“阶段一：安全控制与可信边界”。不要提前实现阶段二到阶段五，不要大范围重做 UI。

开始前必须读取：
- docs/audit/00_EXECUTIVE_SUMMARY.md
- docs/audit/10_SECURITY_SAFETY_AUDIT.md
- docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- docs/reference/PROJECT_FOLLOWUP_ROADMAP.md
- ../docs/09_can_gateway_design.md
- ../docs/10_dbc_decode_encode_design.md
- ../docs/11_control_121_design.md
- ../docs/12_safety_interlock_design.md
- backend/app/eol/engine.py
- backend/app/api/control.py
- backend/app/control/*
- backend/app/can_gateway/*
- backend/app/services/lifecycle.py
- backend/app/api/config.py
- backend/app/api/reports.py
- desktop/src/pages/ManualControlPage.vue
- desktop/src/stores/control.ts

目标问题：SAFE-001~SAFE-008、SIM-001、DBC-001。

必须完成：
1. 为 EOL session 保存真实 asyncio task/cancel token，使 pause、resume、abort、emergency-stop 在步骤边界可靠生效；abort/emergency 结果不能被后台 PASS 覆盖。
2. 急停走独立最高优先级路径：停止普通周期发送，锁存急停，周期下发零速+制动，读取反馈确认停车；超时保持锁存并返回明确原因。
3. 安全停车实现有超时、重试、反馈确认和审计的状态机，不能只 send_once。
4. SafetyInterlockService 成为控制和 EOL 的唯一安全判定入口。GET /control/status 和 /control/interlock-status 返回真实 evaluate 结果。
5. 在线状态使用原始 receive timestamp。建立有界接收队列，过期/积压帧不能维持在线，也不能触发控制允许。
6. UDP 按 datagram 校验长度必须为 13*n；禁止跨 datagram 拼半包。TCP 流解析与 UDP 解析分离。
7. 0x121 preview、field notes、UI Byte0~Byte7 和真实发送只使用一套 authoritative encoder；增加 golden vectors 和 loopback 对比。
8. 实现服务端可信认证和 RBAC。不得信任请求 body 中的 role 或 x-role header；默认用户不得是 admin。
9. 控制、维护、危险配置、人工放行和报告删除必须由服务端权限保护并写 operator_actions。
10. 建立 dev/mock/production 配置隔离。开发仿真默认只允许 127.0.0.1，不得向 [REDACTED_CAN1_GATEWAY]/99 发包；生产配置必须显式选择。
11. 0x123、0x126、NMT、PID debug 默认关闭；本阶段不得为了测试开启真实危险发送。

安全限制：
- 禁止连接真实车辆。
- 只能使用 Mock、Python simulator 和 loopback。
- 不得通过降低联锁规则来让测试通过。
- 任何不确定情况必须保守失败。

测试至少覆盖：
- pause 不推进、resume 后继续。
- abort/emergency 不再执行下一步骤且最终状态保持。
- CAN1/CAN2 断开时 EOL 和控制被拒绝。
- simulator 停止后 2 秒内离线，5 秒后控制仍为 409。
- -120/-60/0/60/120 编码，以及 UI preview=API data=simulator RX。
- UDP 截断包不会与下一 datagram 合并。
- 未认证/越权维护、控制、删除全部失败。
- 伪造 role/x-role 无效。
- 急停和安全停车成功、超时、反馈缺失三条路径。

执行：
- pytest backend/tests
- pytest simulator/tests（从项目根也必须可执行）
- npm run typecheck
- npm run build
- 使用审计中的 loopback 和 stale-online 场景复测

把新证据保存到 docs/verification/phase-01/，不要覆盖 docs/audit/evidence/。

完成输出必须包含：修改文件、关闭的问题、未关闭的问题、测试结果、危险路径证据、是否满足阶段一门禁。只要任一 P0 动态测试失败，就明确写“阶段一未完成”。
```

---

## Prompt 2：真实 EOL 与全链路持久化

```text
当前项目位于 chassis_management_platform/。

本任务只实施《docs/reference/PROJECT_FOLLOWUP_ROADMAP.md》的“阶段二：真实 EOL 与全链路持久化”。开始前确认阶段一门禁已通过；如果没有阶段一验证证据，停止实施并报告阻塞。

必须读取：
- docs/audit/08_EOL_TEST_ENGINE_AUDIT.md
- docs/audit/09_DATABASE_LOG_REPORT_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- docs/reference/PROJECT_FOLLOWUP_ROADMAP.md
- ../docs/06_database_design.md
- ../docs/13_eol_test_plan.md
- ../docs/14_test_assertion_standards.md
- ../docs/15_logging_and_storage.md
- configs/test_plan.yaml
- configs/thresholds.yaml
- backend/app/eol/*
- backend/app/storage/*
- backend/app/services/signal_store.py
- backend/app/dbc/*
- backend/app/api/eol.py

目标问题：EOL-001、EOL-002、DB-001、DB-003、DB-004、DBC-002。

必须完成：
1. 使用 Pydantic 定义并校验测试计划模型，从 configs/test_plan.yaml 加载步骤，禁止 engine 内写死步骤动作和阈值。
2. 实现 12 步真实执行器。每步必须包含前置条件、CAN/控制动作、采样窗口、断言、timeout、失败策略、清理动作和安全停车策略。
3. 测量值必须来自 SignalStore 且带 timestamp、quality、source CAN ID；过期、invalid、DBC 缺失不能当有效值。
4. 实现转向跟随、制动停止、低速驱动、档位、BMS、告警、心跳和通信断言。
5. 人工步骤支持等待、操作员确认、超时、中止和审计。
6. 限制同工位运动测试并发，明确拒绝或排队策略。
7. 建立 session Unit of Work 和数据库事务。一次步骤/断言写入失败必须回滚并使会话安全失败。
8. 持久化 test_sessions、test_steps、test_assertions、raw_can_frames、decoded_signals、signal_statistics、alarms、reports、operator_actions 和 software_versions。
9. 实现 SignalLogWriter 的批量 CSV/Parquet 策略，所有记录带 session_id。
10. 0x102 按 override 展开 unsigned bool 和 bitmap；不允许把 signed 负值当保护告警。
11. 支持异常重启后的会话恢复，或在启动时安全终止未完成会话并留下原因。
12. EOL dashboard 和 WebSocket 必须来自实际 session，不再显示固定 RUNNING/BMS mock。

必须测试的场景：
- normal_pass -> PASS，12 步。
- bms_low_soc -> 在 BMS 步骤 FAIL。
- warning_fault -> 在正确告警步骤 FAIL，并按策略停车。
- steering_no_response -> FAIL。
- brake_fail -> FAIL。
- CAN 断开、DBC 未加载、数据库不可写 -> 不得 PASS。
- pause/resume/abort/emergency。
- 同时启动两个会话。
- 数据库事务回滚、进程重启恢复。
- 每种结果的数据库关联完整性。

不要修改无关 UI；只做 EOL 页面接入新真实状态所需的最小改动。禁止连接真实车辆。

执行完整 pytest、仿真 profile、typecheck 和 build。证据写入 docs/verification/phase-02/。

完成时报告每个 profile 的预期/实际、失败步骤、停车结果、数据库行和报告 ID。只要 steering_no_response、brake_fail、断链或数据库不可写仍可 PASS，就明确写“阶段二未完成”。
```

---

## Prompt 3：真实业务数据、API 与报告

```text
当前项目位于 chassis_management_platform/。

本任务只实施《docs/reference/PROJECT_FOLLOWUP_ROADMAP.md》的“阶段三：真实业务数据、API 与报告”。阶段一和阶段二必须已经通过。

必须读取：
- docs/audit/03_PAGE_FUNCTION_AUDIT.md
- docs/audit/05_BACKEND_API_AUDIT.md
- docs/audit/09_DATABASE_LOG_REPORT_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- ../docs/07_api_spec.md
- ../docs/08_websocket_spec.md
- ../docs/15_logging_and_storage.md
- ../docs/16_report_generation.md
- backend/app/api/*
- backend/app/reports/*
- backend/app/storage/repositories.py
- desktop/src/api/*
- desktop/src/stores/*
- 报告、历史、告警、CAN监控、信号仪表盘和实时曲线页面

目标问题：REPORT-001、REPORT-002、API-002~API-006，以及页面功能审计中对应的生产 Stub/Mock。

必须完成：
1. 为公共 API 建立集中 Pydantic request/response models；统一错误为 code/message/details/trace_id。
2. 每个 dashboard 返回 data_source、mock、quality、updated_at；生产模式禁止静默 fallback。
3. 前端 API 层解析结构化错误，保留 trace_id，统一 toast/错误状态。
4. TCP 若本阶段无法真实实现，API 和 UI 必须明确标记 unsupported 并拒绝保存，不能接受后仍运行 UDP。
5. CAN latest decoded 使用实际最新帧和 DBC 信号，0x77/0x121/0x102 详情不得使用固定值。
6. CAN 统计、信号 Watchlist、曲线、告警、总览 KPI、历史和报告从真实数据库/运行服务读取。
7. 生成 JSON、DOCX、PDF、CSV，包含完整会话、步骤、断言、软件版本、DBC hash、配置 hash、计划版本和操作员。
8. 使用可部署中文字体，修复 DOCX 乱码和 PDF 方块。
9. 报告 preview 必须读取真实文件；JSON摘要和CSV前100行来自实际内容。
10. 实现扫描、导出 Word/PDF、打印任务、重新生成、目录打开、删除、关联数据和报告状态。
11. 实现历史筛选、分页、时间线、操作日志、文件下载、曲线回放元数据和导出历史。
12. 文件操作做路径规范化、目录白名单、权限校验和审计；不存在资源返回 404。
13. 删除所有目标生产路径的“接口已预留”响应；保留 Mock 时必须只在显式 Mock 模式使用。

测试至少覆盖：
- OpenAPI contract 与返回模型。
- 统一 4xx/5xx 和 trace_id。
- 真实帧详情与 DBC 解码值一致。
- PASS/FAIL 报告 JSON/DOCX/PDF/CSV 可打开、中文可读、元数据完整。
- 报告预览与磁盘文件一致。
- 历史筛选/空结果/分页/下载/回放。
- 未认证、非管理员删除失败；管理员删除有审计。
- 路径穿越和不存在资源。
- 后端离线时前端只显示明确 Mock/离线状态。

证据写入 docs/verification/phase-03/，至少包含 API 响应、报告渲染截图、数据库关联查询和按钮 E2E 结果。

完成输出必须区分真实实现、显式 Mock 和仍未实现项。只要生产页面仍把固定数据伪装为真实数据，阶段三不得标记完成。
```

---

## Prompt 4：实时性能、可靠性与 UI 收口

```text
当前项目位于 chassis_management_platform/。

本任务只实施《docs/reference/PROJECT_FOLLOWUP_ROADMAP.md》的“阶段四：实时性能、可靠性与 UI 收口”。不要改回阶段一到三已经验证的安全语义和 API 契约。

必须读取：
- docs/audit/02_UI_FIDELITY_AUDIT.md
- docs/audit/04_FRONTEND_ARCHITECTURE_AUDIT.md
- docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- ../docs/08_websocket_spec.md
- ../docs/09_can_gateway_design.md
- ../docs/ui/UI_STYLE_GUIDE.md 和 ../docs/ui/pages/*.md
- backend/app/services/lifecycle.py
- backend/app/websocket/*
- backend/app/can_gateway/*
- backend/app/storage/raw_log_writer.py
- desktop/src/api/websocket.ts
- desktop/src/components/charts/*
- desktop/src/components/layout/*
- desktop/src/pages/*

目标问题：PERF-001/002/003、API-001、DB-002、CAN-001/002、UI-001~UI-006。

必须完成：
1. CAN pipeline 使用有界 queue、批处理和可监控 drop/backpressure 策略，不得无界 create_task。
2. WebSocket 按 topic 节流和批量推送：信号约10Hz、统计约1Hz；raw frame 仅向显式订阅客户端发送。
3. 慢客户端不能阻塞 CAN 接收；每客户端队列有上限和断开策略。
4. 前端直接消费 batch payload，不得在每个 WebSocket 消息上重新 GET timeseries/dashboard。
5. WsClient 实现单例、连接状态、指数退避重连、unsubscribe/off、路由清理和重复连接保护。
6. Raw CAN/decoded signal 日志异步批量写，按会话/日期/大小轮转，支持压缩、保留和磁盘告警。
7. fps 使用滚动窗口；buffer 按通道配置，统计包含 source receive age 和 queue depth。
8. Router 改为懒加载，拆分 ECharts/vendor，减少主 bundle。
9. TopStatusBar 使用唯一状态源，禁止主体 online 而顶部 offline。
10. 实时曲线 selected signals 实际控制 series；暂停不继续刷新 UI。
11. 图表改用 ResizeObserver，在容器非零后初始化并正确 dispose。
12. 统一深色表单，清除白底原生控件。
13. 逐页对照 ui_reference：1920x1080 无页面级滚动；1366x768 核心状态和安全按钮可见，只允许局部滚动。

必须执行：
- 1000fps 持续 10 分钟。
- simulator 停止后的离线与控制拒绝测试。
- WebSocket topic 实际频率统计。
- 页面切换/重连/后端重启测试。
- 内存、句柄、socket、queue depth、日志增长监控。
- 11页 1920x1080 和 1366x768 截图、runtime metrics、视觉 diff。
- npm typecheck/build/test/lint（若阶段五前脚本仍未建立，明确记录）。

验收要求：无持续 backlog；停止 simulator 2 秒内离线；无 handler/连接累积；日志轮转有效；11页无大红错误横幅、白底控件、空图和状态冲突。

证据写入 docs/verification/phase-04/。不得为了吞吐关闭联锁、日志审计或丢弃关键安全帧。任一安全回归失败，阶段四未完成。
```

---

## Prompt 5：测试体系、打包部署与试点验收

```text
当前项目位于 chassis_management_platform/。

本任务实施《docs/reference/PROJECT_FOLLOWUP_ROADMAP.md》的“阶段五：测试体系、打包部署与试点验收”。必须先确认前四阶段均有通过证据。

必须读取：
- docs/audit/11_TEST_QUALITY_AUDIT.md
- docs/audit/13_PACKAGING_DEPLOYMENT_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- ../docs/17_deployment_plan.md
- ../docs/20_risk_and_open_questions.md
- desktop/package.json
- desktop/electron/*
- backend/pyproject.toml
- simulator/pyproject.toml
- README.md 和所有启动脚本

目标问题：TEST-001~TEST-003、DEPLOY-001~DEPLOY-003，并完成全项目最终复审。

必须完成：
1. 从项目根提供可重复的 install、test、dev、build 命令，修复 simulator import/PYTHONPATH 问题。
2. 后端启用 pytest coverage；前端增加 Vitest、ESLint、Playwright/Electron E2E。
3. 为 CAN协议、DBC、0x121、安全联锁、EOL、数据库、报告、权限、WebSocket 和11页UI建立 CI 门禁。
4. 升级 Electron、Vite、ECharts 等依赖，处理 npm audit high/critical；不能仅添加 ignore。
5. 使用 electron-builder/forge 或等价方案生成 Windows 安装包。
6. 生产 Electron 使用 loadFile(dist/index.html)，开发模式才连接 Vite。
7. 打包/安装后端 Python runtime；Electron 负责启动后端、健康等待、异常提示、退出清理和崩溃重启。
8. 生产配置、DBC、数据库、日志、报告路径使用可写应用数据目录；支持首次初始化和迁移。
9. 完成端口冲突、防火墙、自动启动、离线安装、升级、回滚和崩溃恢复设计。
10. 在干净 Windows 机器验证无 Node、无系统 Python、无 Vite 时安装和启动。
11. 执行 24 小时 soak，覆盖后端重启、断网、CAN断链、数据库失败、磁盘阈值、急停和恢复。
12. 仅在项目安全负责人批准的封闭台架执行硬件验收；不得自动连接真实车辆。
13. 重新执行完整工程审计，更新总体评分、真实实现率、问题登记和生产就绪等级。

CI/验收至少包含：
- 后端/仿真器/前端单元测试和覆盖率。
- API contract、权限越权、路径安全。
- 五个 profile、CAN/DBC/DB 故障注入。
- Electron 启动后端、退出清理和崩溃恢复。
- 干净机安装、升级、回滚、离线启动。
- 1000fps、24小时稳定性和磁盘增长。
- 11页双分辨率 E2E 截图。

证据写入 docs/verification/phase-05/。最终输出必须包括安装包路径/hash、CI结果、覆盖率、24小时资源趋势、封闭台架结果、未解决风险和建议就绪等级。

只有全部 P0/P1 关闭、干净机和24小时验收通过、独立复审至少为 PILOT_READY 时，才可建议有限试点。不得自行评为 PRODUCTION_READY，也不得把有限试点等同于允许连接真实车辆。
```
