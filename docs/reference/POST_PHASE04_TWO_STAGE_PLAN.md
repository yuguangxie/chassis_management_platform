# 阶段四后的两阶段收尾计划

## 依据与前提

本计划以以下已存在资料为依据：

- `docs/reference/PROJECT_FOLLOWUP_ROADMAP.md`
- `docs/verification/phase-04/README.md`
- `docs/audit/11_TEST_QUALITY_AUDIT.md`
- `docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md`
- `docs/audit/13_PACKAGING_DEPLOYMENT_AUDIT.md`
- `docs/audit/14_ISSUE_REGISTER.md`

开始任一阶段前，必须确认阶段四证据中的安全回归、1000 fps loopback、stale-online 控制拒绝和双分辨率 UI 检查均为通过。两个阶段均不得改变已验证的 SafetyInterlock、0x121 编码、RBAC 或 API 错误契约；任何必要变更必须重新执行阶段一至四相关回归。

| 阶段 | 名称 | 目标 | 主要遗留风险 | 完成门禁 |
| --- | --- | --- | --- | --- |
| 05 | 质量工程与可复现交付 | 让测试、静态检查、E2E、依赖和性能验证成为一条可重复 CI 流水线 | 缺少前端 test/lint、覆盖率和统一根命令；ECharts vendor 仍偏大 | 干净环境中一条命令完成质量门禁，安全失败路径自动化覆盖 |
| 06 | 打包部署与封闭台架准入 | 交付可安装、可恢复、可运维的 Windows 桌面系统，并完成受控台架 soak | 安装包、后端托管、升级/回滚、路径权限、生产配置和长期运行尚未完整验收 | 干净 Windows 与封闭台架验收通过；达到 `PILOT_READY` 前仍不连接真实车辆 |

## 阶段 05：质量工程与可复现交付

### 明确目标

1. 建立项目根目录的一致测试入口，避免运行中的 UDP 服务与 `TestClient` 争用 8234/8235。
2. 为 Vue 建立 Vitest、ESLint 和关键组件/Pinia 单测；为 Electron 建立可重复的页面切换、重连和截图 E2E。
3. 在 CI 中执行 Python、simulator、前端类型检查、lint、单元测试、构建、OpenAPI contract、loopback 安全回归和证据归档。
4. 设定并落实核心安全、控制、EOL、协议、数据库、报告和权限模块的覆盖率门禁；覆盖失败路径而非只覆盖 happy path。
5. 收口阶段四遗留性能债务：按需引入 ECharts，保留 bundle 基线与回归阈值；不以关闭日志、联锁或审计换取性能。
6. 清理高风险依赖告警，固定 Python/Node/npm 锁定版本，并输出可复现的开发与 CI 环境说明。

### 工作包

| 编号 | 工作内容 | 关键产物 |
| --- | --- | --- |
| Q1 | 测试隔离和根命令 | `scripts/test_all.*`、独立端口/临时目录 fixture、明确服务启动顺序 |
| Q2 | 前端质量体系 | `vitest`、`eslint`、测试覆盖率、`npm run test`/`lint`/`test:e2e` |
| Q3 | 安全与契约回归 | 0x121、联锁、stale-online、RBAC、OpenAPI、WebSocket cadence 自动化 |
| Q4 | Electron UI E2E | 11 页路由、1920x1080/1366x768、无大红错误/白底控件/页面滚动的机器检查 |
| Q5 | 依赖和 bundle 治理 | lockfile、`npm audit`、Python 依赖审计、bundle size 基线和 ECharts 按需加载 |
| Q6 | CI 与证据 | CI 配置、JUnit/coverage/截图/日志归档、`docs/verification/phase-05/` |

### 验收门禁

- 根目录可执行后端、simulator、前端全套测试，且不会与已运行实例共享 UDP 端口、数据库或日志目录。
- `npm run test` 和 `npm run lint` 存在并通过；`npm run typecheck`、`npm run build` 通过。
- Python 和前端覆盖率阈值写入 CI。安全、控制、EOL、协议、权限、数据库事务和报告的失败路径必须有明确覆盖。
- CI 中任何控制/安全测试失败即阻断构建；Mock 仅能用于显式 Mock profile。
- 11 页 E2E 通过，截图与阶段四相比没有安全状态、深色主题、页面级滚动和错误横幅回归。
- 构建产物的主入口和 ECharts/vendor 大小有基线；超阈值会失败或需要书面豁免。
- 所有证据写入 `docs/verification/phase-05/`，不覆盖审计或阶段四证据。

### 非目标和安全边界

- 不接入真实车辆或生产 CAN 设备。
- 不为提升覆盖率而 Mock 掉 SafetyInterlock、数据库失败或 UDP 边界。
- 不修改业务页面的视觉方案，除非 E2E 证明存在回归。

## 阶段 06：打包部署与封闭台架准入

### 明确目标

1. 交付能在无 Node、无 Vite、无系统 Python 的干净 Windows 工控机上安装和运行的 Electron 桌面包。
2. 将 FastAPI 作为受监管的 sidecar 进程启动、健康检查、崩溃恢复和退出清理；禁止 renderer 直接访问本地文件或 CAN。
3. 将 dev/mock/production 配置、DBC、SQLite、日志和报告目录隔离为明确可写的运行时路径，确保升级不破坏历史数据。
4. 建立安装、首次初始化、升级、回滚、备份、日志收集、端口冲突、证书/签名和故障恢复运行手册。
5. 在批准的封闭 loopback/台架环境完成 24 小时 soak、断电/重启/磁盘空间/数据库不可写/仿真器断链和急停保守失败验证。
6. 形成独立复审包和试点准入结论；真实车辆连接需另行获得书面安全批准，不由本阶段自动授权。

### 工作包

| 编号 | 工作内容 | 关键产物 |
| --- | --- | --- |
| D1 | Windows 打包与签名 | electron-builder/等价配置、签名与 SHA-256、离线安装包 |
| D2 | 后端 sidecar 生命周期 | Python runtime 打包、健康检查、PID/端口管理、退出清理、崩溃重启 |
| D3 | 运行时路径与配置 | `%ProgramData%`/用户数据路径、迁移、备份、权限检查、dev/mock/prod 分离 |
| D4 | 运维与恢复 | 安装/升级/回滚/日志/数据库修复/端口/防火墙 runbook |
| D5 | 干净机与封闭台架验证 | 安装脚本、24 小时 soak、故障注入、性能和安全证据 |
| D6 | 独立准入复审 | 风险接受记录、P0/P1 复核、`PILOT_READY` 或拒绝理由 |

### 验收门禁

- 安装包在干净 Windows 目标机可离线安装、启动、停止和卸载，且不依赖开发服务器。
- Electron 只在开发模式访问 Vite；生产模式加载打包产物，并由主进程托管后端。
- Sidecar 启动、健康等待、异常退出、重复启动、端口冲突和应用退出都有可观测且保守的行为。
- DBC、配置、SQLite、原始 CAN、信号、报告和审计日志均使用可写运行时目录；升级/回滚后历史数据仍可读取。
- 封闭台架/loopback 24 小时 soak 内无未解释的内存、句柄、socket、数据库或磁盘失控；断链和故障注入仍拒绝运动控制。
- 急停、安全停车、RBAC、审计、0x123/0x126/NMT 默认禁用在打包环境重新验证。
- 所有证据写入 `docs/verification/phase-06/`，独立复审结论至少为 `PILOT_READY` 才可讨论有限试点。

### 非目标和安全边界

- `PILOT_READY` 不等于允许连接真实车辆；真实车辆、道路或非封闭区域测试必须另有安全责任人书面批准。
- 不在生产 profile 中启用 Mock、0x123、0x126、CANopen NMT 或 PID debug。
- 不接受通过跳过日志、审计、数据库校验或安全联锁获得的“稳定运行”。

## 依赖关系与顺序

1. 阶段 05 完成并通过后，才允许冻结依赖和开始打包；否则安装包只会固化未受控质量问题。
2. 阶段 06 的干净机验证必须使用阶段 05 生成的受控构建和 CI 产物。
3. 任一阶段出现 P0/P1 安全问题时，停止后续准入，回到对应代码阶段修复并重跑相关验证。

推荐实施提示词见：[POST_PHASE04_TWO_STAGE_PROMPTS.md](POST_PHASE04_TWO_STAGE_PROMPTS.md)。
