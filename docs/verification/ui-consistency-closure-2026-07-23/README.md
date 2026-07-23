# 桌面 UI 一致性收口证据（2026-07-23）

## 范围与基线

- 项目：低速无人车线控底盘生产下线管理平台。
- Git 基线：`ba47b0aaebc62eae3131d23ed9d318fdb4721130`。
- 实施状态：工作树实现，未代替项目所有者创建提交；最终审查时应以 `git diff` 为准。
- 页面：总览、网络配置、CAN 监控、信号仪表盘、实时曲线、手动控制、一键检测、告警诊断、报告管理、历史记录、系统设置。
- 证据边界：仅 Mock、临时 data root 和 `127.0.0.1` 回环。未连接真实 CAN、车辆、USR-CAN115、打印机或现场地址。

## 安全边界确认

- CAN1 主动发送仍由安全策略永久锁定。
- 默认控制通道仍为 CAN2，主动发送白名单仍只有 `0x121`。
- 未启用 `0x123`、`0x126`、CANopen NMT 或新的主动发送路径。
- Network 页面只修改草稿；正式应用仍经过 admin 鉴权、后端校验、健康检查、失败回滚和审计。
- 手动控制仍经后端联锁；模拟器停止后，发送请求返回 409。E2E 不执行车辆运动发送。
- Mock、离线、stale、invalid、unavailable 均有显式标记，不能参与安全判断。

## 实现证据

- [实施矩阵](./01_IMPLEMENTATION_MATRIX.md)
- [11 页验收矩阵](./02_PAGE_ACCEPTANCE_MATRIX.md)
- [改动文件清单](./03_CHANGED_FILES.md)
- [Electron E2E 汇总](./e2e/e2e-summary.json)
- [页面运行指标](./e2e/screenshots/page_capture_metrics.json)
- [22 张最终截图](./e2e/screenshots/)
- [后端日志](./e2e/backend.log)
- [模拟器日志](./e2e/simulator.log)
- [renderer 日志](./e2e/renderer-capture.log)

基线截图位于 `docs/verification/ui-consistency-audit-2026-07-23/screenshots/`；最终截图沿用相同页面名与两种分辨率，可逐一对照。

## 自动化结论

Electron 回环 E2E 结论：`passed=true`，22/22 截图完成，11/11 页面执行了安全的非车辆交互；页面级滚动、页面越界、一级 section 裁切、底部空白超限、分段按钮越界、图表 canvas 越界均为 0。

60 秒稳定性窗口共采样 60 次：信号质量集合仅为 `good`；一键检测和告警诊断主要按钮 DOM 节点、disabled 与 opacity 全程稳定。未认证访问跳登录、刷新保留当前 session、Electron 新实例要求重新登录、viewer 访问 Network 跳 403 均通过。

Network 断言覆盖真实草稿修改、未应用提示、合法应用、非法端口失败回滚、CAN1 锁定原因、CAN2 仅 `0x121` 和无伪造 `0.0 ms ping`。模拟器停止约 2.3 秒后两通道 online=false，运动控制返回 409。

## 验证命令

```powershell
cd desktop
npm.cmd run lint
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:bundle
$env:CHASSIS_E2E_OUTPUT='docs/verification/ui-consistency-closure-2026-07-23/e2e'
npm.cmd run test:e2e

cd ..\backend
.\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term --cov-fail-under=60

cd ..\simulator
..\backend\.venv\Scripts\python.exe -m pytest -q
```

最终结果和覆盖率见本文件后续“最终验证”段；命令均在 Windows 回环环境执行。

## 最终验证

- Electron E2E：通过；11 页 × 2 分辨率、22 张截图、60 秒/60 样本稳定性、0 个非回环请求；离线控制 409。
- 前端 lint/typecheck：通过；unit 为 20 个测试文件、139 条测试，lines 58.54%、branches 58.36%、functions 67.05%。
- 前端 build：通过，2271 modules transformed；存在 ECharts 原始 chunk 大于 500 kB 的 Vite 提示，但 gzip 仍在批准预算内。
- bundle：通过；main gzip 23,524 B、ECharts gzip 367,892 B（预算 380,000 B）、JS 总 gzip 518,458 B（预算 800,000 B）。
- 后端完整 pytest：197 passed，coverage 75.18%（门槛 60%）；仅保留 FastAPI/Starlette 既有 deprecation warnings。
- simulator pytest：3 passed。

## 尚需工控机确认

- 100%/125%/150% Windows 缩放、触屏命中区和 ClearType 字体表现。
- 30～60 分钟持续高帧率与持续告警下 GPU、内存和图表刷新稳定性。
- 真实网卡、Windows 防火墙/杀毒、USR-CAN115 只监听诊断与批准来源端口行为。
- 物理急停、安全 PLC、底盘看门狗、safe-stop 保持行为和真实打印机。

这些事项阻断正式车辆上线批准，但不影响本工作包的 Mock/回环软件验收。
