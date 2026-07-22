# 页面功能自动化与证据

## 自动化分层

1. `desktop/src/pages/pageFunctionContracts.test.ts`：11 页逐页检查成功读取、主要写链路、失败/超时处理、empty/stale、路由角色元数据和未实现控件禁用契约。
2. `desktop/src/components/PageDataState.test.ts`：验证 loading/empty/stale/error/permission-denied 以及 fail-closed 优先级。
3. `backend/tests/test_desktop_page_function_matrix.py`：11 个页面读取 API 的认证成功断言、主要写 API/角色/非 Stub 断言，以及 Manual 反馈字段完整性。
4. `desktop/electron/phase04_capture.cjs` + `desktop/scripts/phase05-e2e.mjs`：真实 Electron renderer，双分辨率、实际点击、Mock 会话/报告、配置 dry-run、403、模拟器离线控制 409。

## Electron 安全交互矩阵

| 页面 | 实际交互 | 断言 |
|---|---|---|
| 总览 | 点击“查看更多” | 路由进入 History，随后恢复并截图 |
| Network | 点击“重新检测” | 端口/设备诊断行存在，不出现伪 `0.0 ms` |
| CAN | 输入 CAN ID 筛选、暂停显示、展开历史 | pause 状态生效，未改变 CAN 发送 |
| Signal | 点击保存关注配置 | API 成功反馈；写入偏好与审计 |
| Curve | 暂停、继续 | 页面状态与反馈更新 |
| Manual | 只选择 N 挡本地表单 | 反馈 rule 可见；明确未点击发送 |
| Auto Test | 读取预建 Mock 会话并点击关联日志 | Mock 底盘可见，日志 API 返回 |
| Alarm | 保存诊断布局 | 偏好写入并审计 |
| Report | 扫描、选中 Mock 报告、切换 JSON 摘要 | 报告行被选中，预览可用 |
| History | 输入筛选、查询、下一页 | 分页控件与查询链路生效 |
| System Settings | 向隐藏文件输入注入本轮后端导出的签名包 | dry-run diff 对话框出现，未点击 APPLY |

附加边界：viewer 直接访问 Network 必须到 403；未登录进入业务页必须到 Login；刷新保持当前短期会话；新 Electron 窗口不继承 sessionStorage；停止 simulator 后等待 stale，再向真实 `/control/121/send-once` 发请求，必须 409 且两个通道均 offline。

## 证据位置

- 汇总：`docs/verification/phase-05/e2e/e2e-summary.json`
- 页面交互与布局指标：`docs/verification/phase-05/e2e/screenshots/page_capture_metrics.json`
- 22 张截图：`docs/verification/phase-05/e2e/screenshots/*.png`
- backend / simulator / renderer 日志：`docs/verification/phase-05/e2e/*.log`
- 配置 dry-run 输入：运行时随机签名后写入 evidence 目录；不包含账号、token、现场 IP 或固定密钥。

## 命令与结果

| 命令 | 结果 |
|---|---|
| `backend/.venv/Scripts/python.exe scripts/run_quality.py --suite all --coverage --artifact-dir docs/verification/ui-page-stub-closure-2026-07-22/quality-final` | backend `193 passed`，覆盖率 `78.66%`；simulator `3 passed`，覆盖率 `42.98%` |
| `npm.cmd run lint` | 通过，0 warning |
| `npm.cmd run test` | `15` 个测试文件、`65` 项测试通过；前端纳入门禁文件的语句覆盖率 `57.23%` |
| `npm.cmd run typecheck` | 通过 |
| `npm.cmd run build` | 通过；生产 renderer 构建完成 |
| `npm.cmd run test:bundle` | 通过；main gzip `22,309 B`，ECharts gzip `367,892 B`，总 JS gzip `511,676 B` |
| `npm.cmd run test:e2e` | 通过；11 页全部实际点击，22 张截图，双分辨率无页面级滚动，viewer→403，Mock 会话/报告、配置 dry-run、离线控制 409 均通过 |
| `npm.cmd run test:integration` | 通过；Electron `v43.1.0`，仅 `127.0.0.1`，WebSocket/回环 runtime 证据 `passed=true` |
| `npm.cmd run test:e2e:verify` | 通过；截图 22、交互页 11、离线控制 409 |

质量证据位于 `quality-final/` 与 `docs/verification/phase-05/e2e/`。测试只使用临时 `data_root`、Mock 和 `127.0.0.1`；`nonLoopbackRequests=0`，没有执行真实硬件测试。

- 实现提交：`8c0b16ac7ab8192451eb284a926f92c32511e2ef`
- 分支：`codex/ui-page-stub-closure`
- 远程 Windows CI：推送后通过 `quality-gates` 的 `workflow_dispatch` 验证；运行号与最终结论将在 CI 完成后补记。
