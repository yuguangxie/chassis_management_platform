# 生产身份、路由守卫与配置生命周期验证证据

验证日期：2026-07-22（Asia/Shanghai）。结论：本工作包在 Mock/`127.0.0.1` 边界内通过，覆盖 P0-05、P0-06、P1-05、P1-09、P1-15、P1-20 的软件收口；不构成真实车辆、真实 CAN 设备或产线投产批准。

## 版本与证据边界

- 分支：`main`。
- 验证基线 commit：`3c6c838d1a2275d0b0d463ad3f04ac62293dfa0e`。
- 本工作包为该 commit 上尚未提交的工作树改动；该 hash 仅用于标识验证基线，不能误称为已经包含本工作包的提交。
- E2E 后端、Vite、Electron、simulator 和 UDP 全部绑定 `127.0.0.1`；`e2e-summary.json` 记录 `nonLoopbackRequests=0`。
- 未访问真实 USR-CAN115、真实 CAN 总线、现场 IP、打印机或可运动执行器；未启用 0x123、0x126 或 NMT。
- 自动化所需 bootstrap、签名 key、密码和 session 均在进程内随机生成；令牌不写日志，运行态数据库和 bootstrap 文件已从交付证据中清除。

## 验证结果

| 命令 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage --keep-artifacts --artifact-dir docs\verification\production-identity-config-2026-07-22\python` | PASS；backend 160 passed，78.80%；simulator 3 passed，42.98% |
| `cd desktop; npm.cmd run test` | PASS；13 files / 35 tests；statements 58.25%，lines 60.73% |
| `cd desktop; npm.cmd run lint` | PASS；0 warnings/errors |
| `cd desktop; npm.cmd run typecheck` | PASS |
| `cd desktop; npm.cmd run build` | PASS；仅有既有 ECharts chunk > 500 kB 提示 |
| `backend\.venv\Scripts\python.exe scripts\generate_api_docs.py` | PASS；生成 OpenAPI、production schema 与 136 项 API 鉴权矩阵 |
| `cd desktop; $env:CHASSIS_E2E_OUTPUT='docs\verification\production-identity-config-2026-07-22\e2e-final'; npm.cmd run test:e2e` | PASS；Electron 43.1.0，11 页面 × 2 视口，共 22 张截图；脚本始终从项目根解析该输出路径 |

后端测试存在 FastAPI `on_event` 和 TestClient/httpx2 的上游弃用提示，不影响本次结果，已作为后续维护事项保留。覆盖率文件位于 `python/`；Electron 状态、认证断言、离线后 409 和页面断言位于 `e2e-final/e2e-summary.json`。

## 已验证的关键安全行为

- 一次性管理员 bootstrap、登录成功/失败限制、账户临时锁定、短 session、锁屏换发、登出、过期和管理员撤销。
- viewer/operator/engineer/admin API 权限、路由元数据、菜单和危险按钮可见性；直接访问越权路由进入 403，API 仍独立返回 401/403。
- 刷新时以 `/auth/me` 重验 session；Electron 重启不保留 session；WebSocket 4401 后停止重连并进入重新登录流程。
- 敏感读取统一要求 viewer 以上；公开健康探针只返回最小 `status`；写操作按 operator/engineer/admin 分级。
- 签名配置的 schema、版本、签名、profile、diff、dry-run、admin 权限、预检、应用、健康检查和失败回滚。
- production 缺少签名 active package、全零/不匹配 DBC hash 或错误 profile 时 fail-closed；仓库模板不能直接充当生产配置。
- 网络诊断使用真实 socket bind/TCP connect 和运行统计；UDP 不伪造 ping，仅批准来源可更新 online、last frame 与缓存。

## 尚需现场/硬件确认

- USR-CAN115 实际 UDP 源端口稳定性、TCP 连接与断线行为、网卡/防火墙及交换网络隔离。
- 物理急停、安全 PLC/继电器、底盘看门狗和 safe-stop 发送保持策略。
- Windows 服务账户 ACL、秘密存储与轮换、安装包/代码签名、CSP、升级回滚和干净机安装演练。
- 现场批准的车型、DBC、测试方案、endpoint/source allowlist、数据根和打印机。

详细身份状态机、威胁模型和干净机初始化步骤见 `docs/IDENTITY_AND_ACCESS.md`；配置生命周期见 `docs/CONFIGURATION.md`；残余风险见 `docs/20_risk_and_open_questions.md`。
