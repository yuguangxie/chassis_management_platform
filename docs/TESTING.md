# 测试

## 2026-07-23 P0/P1 工作包

新增 `backend/tests/test_20260723_p0p1_closure.py`，覆盖 production 未签名直改拒绝与审计、intent 前写/后写故障和重启恢复、hardware artifact 的全部主要失败模式、production TCP 拒绝、Windows adapter drift、EOL 身份防篡改/重复、source session 和真实元数据。data lifecycle 测试新增 retention 删除审计事务、文件恢复、应用日志轮转/gzip/写失败 callback、strict storage schema 和 production Parquet 拒绝。

最终证据以 `docs/verification/software-p0-p1-closure-2026-07-23/README.md` 为索引。所有动态测试只允许临时 data_root、Mock 和 `127.0.0.1`；证据必须记录 `nonLoopbackRequests=0`，并明确“未执行真实硬件/HIL/运动/打印测试”。

运行 `pytest backend/tests -q`、`pytest simulator/tests -q`、`npm --prefix desktop run typecheck`、`npm --prefix desktop run build`。

# 数据生命周期工作包

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_data_lifecycle.py -q
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_storage_lifecycle_api.py -q
backend\.venv\Scripts\python.exe scripts/check_report_dependencies.py
```

测试只使用 pytest 临时目录、临时 SQLite 和 VirtualPrintBackend。禁止把测试的 `data_root` 指向用户现有目录，也禁止在本工作包中连接真实 CAN 或打印机。

# 桌面 UI 一致性收口

```powershell
cd desktop
npm.cmd run lint
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:bundle
$env:CHASSIS_E2E_OUTPUT='docs/verification/ui-consistency-closure-2026-07-23/e2e'
npm.cmd run test:e2e
```

Electron E2E 必须在回环 Mock 下覆盖 11 页和 1366×768/1920×1080，并校验 page/content/section rect、内部滚动首尾、底部空白、segmented 子按钮和图表边界。信号、一键检测、告警并行采样 60 秒；信号质量不得在 good/unavailable 间跳变，两个主要按钮节点及 disabled/opacity 不得因背景刷新改变。

灯效组件对左转、右转、位置、近光、制动请求逐项覆盖 ON、OFF、stale、invalid；E2E 同时读取实际 lamp 计算色，检查开启色和关闭/未知中性色。Network 覆盖草稿、应用、非法端口回滚、CAN1 锁定和 CAN2 `0x121`。模拟器停止后通道必须 offline，控制必须 409。

完整结果、截图和日志位于 `docs/verification/ui-consistency-closure-2026-07-23/`。
