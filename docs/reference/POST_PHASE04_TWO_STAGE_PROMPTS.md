# 阶段四后的实施提示词

以下提示词应按顺序使用。执行者必须先读取指定证据；没有门禁证据时应停止，而不是用 Mock 或口头说明替代。

## Prompt 05：质量工程与可复现交付

```text
当前项目位于 chassis_management_platform/。

本任务只实施 docs/reference/POST_PHASE04_TWO_STAGE_PLAN.md 的“阶段 05：质量工程与可复现交付”。开始前必须确认 docs/verification/phase-04/README.md 中阶段四门禁通过；如果 1000fps、stale-online 控制 409、WS cadence 或双分辨率截图任一证据缺失，停止实施并报告阻塞。

必须读取：
- docs/audit/11_TEST_QUALITY_AUDIT.md
- docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- docs/reference/PROJECT_FOLLOWUP_ROADMAP.md
- docs/reference/POST_PHASE04_TWO_STAGE_PLAN.md
- docs/verification/phase-04/README.md
- docs/verification/phase-04/EVIDENCE_MANIFEST.md
- package.json、desktop/package.json、backend/pyproject.toml 或 requirements
- backend/tests/*、simulator/tests/*、desktop/src/*、desktop/electron/*、scripts/*

目标：建立可重复、可隔离的质量门禁，不改写已验证的安全语义、API 契约或 UI 设计。

必须完成：
1. 建立从项目根目录执行的后端、simulator、前端测试入口；每个测试使用独立 UDP 端口、临时 SQLite 和临时日志目录，不得与运行服务冲突。
2. 增加并配置 npm run test、npm run lint、npm run test:e2e；前端至少使用 Vitest + ESLint，E2E 使用现有 Electron/Playwright 等可复现工具。
3. 为 Pinia stores、WsClient、图表生命周期、路由切换、离线 fallback 展示和深色表单增加前端测试；不能只测试静态组件。
4. 为 0x121、SafetyInterlock、EOL、USR-CAN115、数据库事务、RBAC、文件路径安全、报告和 OpenAPI contract 建立失败路径覆盖率门禁。
5. 将阶段四的 1000fps、WS topic cadence、slow-client、stale-online、11 页截图检查加入可选择的 CI 集成测试；禁止用降低负载或关闭日志/联锁让测试通过。
6. 将 ECharts 改为按需导入或给出受测的 bundle size 基线与阈值；不得回退路由懒加载。
7. 固定 Node/Python 依赖版本，执行 npm audit 和 Python 依赖审计；未接受的 high/critical 必须失败或有书面豁免。
8. 建立 CI：类型检查、lint、单测、覆盖率、构建、契约测试、E2E 和证据归档。任何安全回归必须阻断。

安全限制：
- 禁止连接真实车辆；只允许 Mock、Python simulator 和 127.0.0.1 loopback。
- 不得把 Mock、skip 或 xfail 计为真实安全通过。
- 不得删除 docs/audit/evidence/ 或 docs/verification/phase-04/。

测试至少执行：
- 根目录后端 pytest、simulator pytest、coverage。
- npm run typecheck、npm run lint、npm run test、npm run build、npm run test:e2e。
- OpenAPI contract、0x121 golden vectors、stale-online 409、RBAC 越权、EOL PASS/FAIL、报告读取、WS 节流和 11 页截图。

证据写入 docs/verification/phase-05/，至少包含：环境锁定、完整命令输出、coverage、bundle report、audit 输出、CI 配置、E2E 截图和安全失败路径日志。

完成输出必须说明：新增测试命令、覆盖率、CI 状态、依赖风险、bundle 指标、关闭/未关闭问题及阶段 05 门禁是否通过。任何安全动态测试失败时必须明确写“阶段 05 未完成”。
```

## Prompt 06：打包部署与封闭台架准入

```text
当前项目位于 chassis_management_platform/。

本任务只实施 docs/reference/POST_PHASE04_TWO_STAGE_PLAN.md 的“阶段 06：打包部署与封闭台架准入”。开始前必须确认 docs/verification/phase-05/ 中质量门禁已通过；若 npm test/lint、CI、安全回归、覆盖率或 E2E 证据不完整，停止实施并报告阻塞。

必须读取：
- docs/audit/13_PACKAGING_DEPLOYMENT_AUDIT.md
- docs/audit/10_SECURITY_SAFETY_AUDIT.md
- docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md
- docs/audit/14_ISSUE_REGISTER.md
- docs/reference/POST_PHASE04_TWO_STAGE_PLAN.md
- docs/verification/phase-04/README.md
- docs/verification/phase-05/README.md
- desktop/electron/*、desktop/package.json、backend/*、configs/*、scripts/*
- docs/17_deployment_plan.md、docs/15_logging_and_storage.md、docs/20_risk_and_open_questions.md

目标：在不连接真实车辆的前提下，交付可安装、可恢复、可运维的 Windows 桌面系统，并完成封闭 loopback/台架准入验证。

必须完成：
1. 用 electron-builder 或等价方案生成 Windows 安装包；生产模式 loadFile 打包前端，开发模式才可访问 Vite。
2. 打包并由 Electron 主进程监管 FastAPI sidecar：启动、健康检查、超时、端口冲突、崩溃、重复启动、退出清理和错误展示必须可观测。
3. 明确 dev/mock/production 配置与目录：DBC、SQLite、报告、原始 CAN、信号日志和审计日志使用可写运行时目录；升级/回滚不破坏历史数据。
4. 实现或完善安装、首次初始化、备份、升级、回滚、故障恢复、日志导出、端口和防火墙说明；提供 SHA-256 和签名/签名状态。
5. 在干净 Windows 环境验证离线安装：无 Node、无 Vite、无系统 Python 时能安装、启动、显示故障原因并正常卸载。
6. 在批准的封闭 loopback/台架环境执行至少 24 小时 soak：1000fps、仿真器重启、FastAPI 重启、磁盘告警、数据库不可写、日志轮转、断链、急停和安全停车。所有运动控制仍必须经过 SafetyInterlockService。
7. 在打包环境重新验证 RBAC、0x121、0x123/0x126/NMT 默认关闭、Mock 标识、审计和 stale-online 409。
8. 形成独立复审报告，给出 PILOT_READY 或 NOT_READY/LAB_ONLY 结论；真实车辆接入必须显式列为“需安全负责人书面批准”，不能自动放行。

安全限制：
- 禁止实际连接或控制真实车辆，禁止道路测试。
- 不得通过关闭安全联锁、日志、数据库校验或审计来通过 soak。
- 生产 profile 必须显式选择，禁止默认向 [REDACTED_CAN1_GATEWAY]/99 发送任何包。

必须执行：
- 打包构建、安装、启动、退出、升级、回滚、卸载和干净机验证。
- 24 小时封闭环境 soak（若受时间限制，至少提供可恢复的运行脚本和持续采集证据，不得伪报完成）。
- 所有阶段 05 测试、控制安全回归、安装包内的 DBC/config 路径验证、端口冲突和崩溃恢复测试。

证据写入 docs/verification/phase-06/，至少包含安装包 hash/签名、干净机命令和截图、sidecar 日志、24 小时指标、故障注入结果、运行手册和独立准入结论。

完成输出必须说明：安装包位置和 hash、sidecar 生命周期结果、干净机验证、soak 实际时长、失败注入结果、未关闭风险、生产就绪等级。若任何安全回归、安装恢复或 24 小时 soak 失败，必须明确写“阶段 06 未完成”。
```
