# 测试、覆盖率与证据审计

## 1. 本审计重新执行的命令

所有 Python 测试由 `scripts/run_quality.py` 分配随机 loopback UDP 端口并使用临时 `data_root`。没有访问真实硬件或非回环地址。

| 命令 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage` | PASS；backend 197，simulator 3 |
| `cd desktop; npm.cmd run lint` | PASS；0 warning |
| `cd desktop; npm.cmd run typecheck` | PASS |
| `cd desktop; npm.cmd run test` | PASS；20 files / 139 tests |
| `cd desktop; npm.cmd run build` | PASS；2271 modules |
| `cd desktop; npm.cmd run test:bundle` | PASS |
| `cd desktop; npm.cmd run test:sidecar` | PASS；4 tests |

## 2. 覆盖率结果

### Backend

- 197 passed，5 个 deprecation warnings。
- 总覆盖率 78.72%，高于 60% 门槛。
- 安全核心覆盖较好：codec 97%、SafetyInterlock 93%、Override 94%、assertions 91%、migration 96%、configuration service 94%。
- 需要优先补强：TX scheduler 49%、control API 57%、EOL API 47%、CAN API 52%、WebSocket endpoint 44%、sidecar entry 46%、repositories 46%。

warnings 来自 FastAPI `on_event` 和 Starlette TestClient/httpx 迁移，不影响本次通过，但应在依赖升级前处理。

### Simulator

- 3 passed。
- 覆盖率 42.98%，高于 40% 门槛。
- profile 行为测试存在，但 CLI、持续发送、异常网络和更多故障组合覆盖不足。

### Frontend

- 20 个测试文件、139 条测试通过。
- statements 56.50%，branches 58.36%，functions 67.05%，lines 58.54%。
- 纳入覆盖率的 charts 表现较好；CAN/signals stores 约 37%～40% line coverage，页面大量行为主要由契约和 Electron E2E 覆盖，纯单测覆盖仍不足。

## 3. 构建与 bundle

- Vite production build 成功，2271 modules transformed。
- main gzip 23,524 B，预算 100,000 B。
- ECharts vendor gzip 367,892 B，预算 380,000 B。
- JS 总 gzip 518,458 B，预算 800,000 B。
- ECharts 原始 chunk 1,117,948 B，触发 Vite 的 500 kB 提示；未突破项目 gzip 门禁，但余量较小。
- Electron sidecar 测试证明动态 TCP 端口、四个 loopback UDP endpoint、凭据脱敏和启动失败有界重试。

## 4. Electron 11 页证据复核

本审计复核了当前工作树生成的：

- `docs/verification/ui-consistency-closure-2026-07-23/e2e/e2e-summary.json`
- `docs/verification/ui-consistency-closure-2026-07-23/e2e/screenshots/page_capture_metrics.json`
- 22 张 1366×768 / 1920×1080 截图
- backend、simulator、renderer 日志

机器可读结论：

| 断言 | 结果 |
|---|---|
| `passed` | true |
| 页面/视口 | 11 × 2 |
| 页面级滚动失败 | 0 |
| 页面/section/内部滚动/底部空白 | 全通过 |
| segmented/图表/action text/灯色边界 | 全通过 |
| renderer console/page errors | 0 |
| 非回环请求 | 0 |
| 60 秒信号样本 | 60；quality 仅 good |
| Auto/Alarm 主按钮稳定 | true/true |
| 未登录/刷新/Electron重启/403 | 全通过 |
| simulator 停止后 offline | CAN1/CAN2 false |
| offline control | HTTP 409 |

安全交互只包含路由、筛选、暂停、Mock 会话/报告、偏好保存、配置 dry-run 和本地表单；没有通过 UI 发送真实车辆命令。

## 5. 安装包与远程 CI 证据

### 已有证据

- phase-06 曾生成 `Chassis-EOL-Setup-1.0.2-unsigned-internal-x64.exe`。
- NSIS 安装/启动/11页/sidecar 恢复/二次启动/卸载/数据保留在本机 Windows 上通过。
- runtime PATH 不依赖 Node/Python/uv/互联网；8800 被占用时使用动态 localhost 端口。
- simulator 不运行时通道 offline 且控制 409。
- 生成 SBOM、npm/pip audit、artifact hash、release manifest；Authenticode 为 NotSigned 且明确标记 unsigned-internal。
- 较早 UI page closure 的远程 Windows CI `#29938962298` 在提交 `df4d15f` 上通过 quality、renderer-e2e、installer jobs。

### 不能外推的部分

- phase-06 manifest 的源码 commit 是 `3c6c838`，且 `source.dirty=true`、dirty_file_count=209。
- 当前 HEAD 是 `ba47b0a`，并有 37 个 tracked 修改以及多项 untracked UI/证据文件。
- 当前 UI consistency closure 尚未形成与其完全一致的 remote CI run 或 installer artifact。
- unsigned 内测包不是正式签名 production release。

因此“已有安装证据通过”只能证明打包机制和一个历史工作树可运行，不能证明当前源码已具备正式发行供应链闭环。

## 6. 测试覆盖到的高风险路径

- CAN ID 标准/扩展边界、保留位、DLC、RTR、长度。
- 非授权 UDP source 不更新 online、last_frame 和 signal cache。
- 反馈 missing/stale/invalid/out-of-range/source/range，心跳 stale，DB 不可写、严重告警、急停、队列异常。
- production DBC 缺失/hash/车型不符。
- override 同人审批、过期、撤销和不可绕过规则。
- assertions 全运算符、边界、窗口、missing/stale/invalid 和错误输入。
- migration 每个旧版本、失败恢复、backup 篡改、cleanup 保护/中断。
- 虚拟打印 queued→completed/failed/cancelled/retry 和四格式报告。
- 登录成功/失败/锁定/过期/撤销、角色路由/API、WS 过期。
- 配置合法/非法/旧版本/签名错误/apply 回滚。
- 11 页读/写/错误/empty/stale/permission 以及双分辨率布局。

## 7. 仍缺的测试

| 缺口 | 优先级 | 说明 |
|---|---|---|
| production 普通 channel update 必须被拒绝 | P0 | 当前缺陷还存在，先写失败测试再修复 |
| 审计写失败时控制不得报告成功 | P0 | 需 fault injection/outbox/补偿测试 |
| hardware acceptance artifact | P0 | 签名、过期、撤销、车型/工位不符、不可绕过 |
| EOL 标识输入 | P1 | 空/默认/demo/VIN非法/重复/工单不符 |
| source_session/版本/DBC 元数据不伪造 | P1 | 无 active session、DBC unavailable、manifest 缺失 |
| TCP reconnect 状态机 | P1 | EOF/half-open/server restart/backoff/jitter/cancel |
| log rotation/retention/compression | P1 | 磁盘满、锁、压缩、保护、重启恢复 |
| 当前 clean commit 远程 Windows CI | P1 | quality/E2E/installer 全套 |
| 8～24 小时/1000 fps soak | P1 | 内存、GPU、CPU、磁盘、队列、周期 jitter |
| 真实设备/HIL | External P0 | 只监听→静态→封闭低速，逐门禁执行 |

## 8. 可复现性建议

项目根应把以下作为唯一开发质量入口，并让 CI 调用同一脚本：

```powershell
backend\.venv\Scripts\python.exe scripts\run_quality.py --suite all --coverage
cd desktop
npm.cmd run lint
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:bundle
npm.cmd run test:sidecar
```

Electron E2E/installer 验证应始终使用新的空 evidence 目录和临时 data_root；运行后检查 `nonLoopbackRequests=0`，并避免把 bootstrap secret/session token 归档到 docs 或 CI artifact。
