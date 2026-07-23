# 审计基线、资料遍历与方法

## 1. 基线

- 审计时间：2026-07-23，Asia/Shanghai。
- 仓库：`chassis_management_platform`。
- HEAD：`ba47b0aaebc62eae3131d23ed9d318fdb4721130`（`docs: record remote Windows verification`）。
- 审计对象：HEAD 加当前未提交工作树；不是只审计最后一次 commit。
- 动态边界：临时目录、Mock、test profile、`127.0.0.1`；未访问真实硬件或非回环 endpoint。

## 2. 工作树状态

审计开始时有 37 个 tracked 文件修改，约 1710 insertions/541 deletions，并有共享按钮、信号灯、状态字典、UI consistency tests/docs/screenshots 等 untracked 文件。改动集中在：

- backend signals/control/lifecycle 和相关测试；
- Electron capture/E2E；
- 11 个页面、stores、API types、共享状态/按钮/开关/样式；
- UI/API/config/testing/risk 文档与 verification evidence。

本审计保留这些用户改动，没有 reset/checkout/覆盖。完成度以实际工作树为准，同时将“未提交/未远程验证/未重新打包”作为发布风险。

## 3. 已遍历的必要文档

### 工程规范

- 根 `AGENTS.md`。

### 2026-07-20 外层完整审计资料包

- `00_AUDIT_INDEX.md`
- `01_FULL_PROJECT_AUDIT.md`
- `02_DESKTOP_UI_PAGE_FUNCTION_AUDIT.md`
- `03_REAL_ENVIRONMENT_READINESS.md`
- `04_REMEDIATION_BACKLOG.md`
- `05_TEST_AND_EVIDENCE_INDEX.md`
- `06_MODULE_COMPLETION_MATRIX.md`
- `07_FOLLOWUP_IMPLEMENTATION_PROMPT.md`

这些文档对应更早 commit，许多 P0/P1 已经关闭，因此只作为历史问题清单和评分对照。

### 仓库审计与风险

- `docs/audit/00_EXECUTIVE_SUMMARY.md`
- `docs/audit/10_SECURITY_SAFETY_AUDIT.md`
- `docs/audit/11_TEST_QUALITY_AUDIT.md`
- `docs/audit/12_PERFORMANCE_RELIABILITY_AUDIT.md`
- `docs/audit/13_PACKAGING_DEPLOYMENT_AUDIT.md`
- `docs/audit/15_REMEDIATION_PLAN.md`
- `docs/audit/16_DESKTOP_UI_CONSISTENCY_AUDIT_2026-07-23.md`
- `docs/20_risk_and_open_questions.md`

`00`～`15` 多为早期状态，不能取代本轮当前审计。

### 当前设计/运行文档

- 架构、API/OpenAPI、CAN、DBC、安全联锁、身份与访问控制。
- 配置 schema/生命周期、data_root/数据库/migration/备份/cleanup。
- logging、reporting/printing、deployment、Windows installation/upgrade/troubleshooting。
- testing、UI implementation notes、启动说明与 `.env.example`。

### verification 证据

- safety/CAN P0/P1 closure。
- identity/config closure。
- data lifecycle/report closure。
- phase-05 renderer/runtime/remote Windows CI。
- phase-06 installer/clean-machine/release manifest/SBOM/audit/signing。
- UI page stub closure 的 traceability/stub/test evidence。
- UI consistency audit 基线 22 张截图。
- UI consistency closure 的实施/验收矩阵、22 张最终截图、60 秒稳定性和 E2E JSON/log。

## 4. 已遍历的代码和配置范围

### Backend

- `api/`：auth、overview、can、signals、control、eol、alarms、reports、history、config、storage、dbc、errors/models/router。
- `security/`：account/session/bootstrap/RBAC。
- `can_gateway/`：models、codec、UDP/TCP、manager、statistics。
- `dbc/`：loader/service/overrides。
- `control/`：0x121 encoder、safety interlock、tx scheduler、safe-stop、override。
- `eol/`：models/plan/assertions/engine。
- `storage/`：paths、database/migrations/repositories/UoW、raw/signal/telemetry、backup/retention/health。
- `reports/`：dependencies/generator/service/printing/templates。
- `configuration/`：models/signature/service/diagnostics。
- `services/`：lifecycle/app state/audit/preferences/history/file access/signal store。
- `websocket/`、main/sidecar/sidecar runtime。
- 36 个 backend test 文件。

### Desktop/Electron

- router、auth 和所有 Pinia stores/API types/http/websocket。
- 11 个业务页面及 Login/Lock/403。
- shared PageDataState、IndustrialButton、IndustrialActionButton、ToggleSwitch、SignalLightItem、charts、layout、status dictionary、industrial theme。
- Electron main/preload/sidecar/diagnostics/capture，Vite/package/electron-builder/PyInstaller/release scripts。
- frontend unit/contract tests 和 Electron E2E scripts。

### 配置/资产/CI

- channels dev/mock/test/production template。
- production-config template、safety_interlock、thresholds、DBC overrides、12-step test plan、storage/report/station/theme。
- 随包 JD DBC 和报告字体/依赖配置。
- GitHub Actions workflow、quality/bundle/sidecar/installer/release scripts、SBOM/hash/manifest。

## 5. 规模快照

| 范围 | 文件数（审计时） |
|---|---:|
| backend/app Python | 78 |
| backend/tests Python | 36 |
| desktop/src | 78 |
| desktop/electron CJS | 8 |
| simulator Python | 3 |
| docs Markdown | 73（不含本轮新增审计） |

项目不是“只有 UI 的空壳”；后端约 8,416 个受 coverage 统计的语句，前端包含完整 store/API/component/page/test 链路。但功能规模也放大了配置漂移、审计一致性和现场验证的风险。

## 6. 审计方法

1. 文档对照：历史 backlog 与当前代码/verification 逐项复核，不因旧报告未更新而重复判未实现。
2. 静态追踪：页面控件→store/页面状态→API→service→persistence/audit→错误状态。
3. 安全数据流：UI→RBAC→SafetyInterlock→TxScheduler→CanGateway；feedback→source/codec/DBC/signal→interlock。
4. 失败路径：missing/stale/invalid/source/range、DB/磁盘、告警/急停、队列、配置/DBC、打印/转换、sidecar。
5. 配置权威：repository default、signed active package、Network direct update、runtime state 和文件路径交叉核对。
6. 供应链：commit/dirty、CI run、manifest、SBOM、hash、signing、installer 证据一致性。
7. 动态验证：后端/模拟器/前端 lint/test/typecheck/build/bundle/sidecar；复核 Electron E2E JSON 和截图。
8. 机密检查：只检查 tracked/ignored 路径和日志策略，不读取或输出 secret 内容。

## 7. 证据限制

- 没有执行真实 CAN、USR-CAN115、车辆、PLC、物理急停或打印机测试。
- 没有在本审计再次运行 60 秒 Electron E2E；复核的是同日当前工作树已经生成的机器可读证据和日志。
- 没有重新构建 installer；现有 phase-06 artifact 属于更早 dirty 基线。
- 没有访问远程 CI 网络状态；远程结论来自仓库内已记录的 run/commit 证据。
- 百分比是工程估算，不是功能安全等级、ISO 26262/机械安全/网络安全认证。

## 8. 结论使用规则

如果后续代码、配置、DBC、test plan、Electron/sidecar、migration 或 installer 有任何变更，应重新计算相关模块完成度并生成新的 current audit；不得直接把本文件的 89%/52%/28% 复制到新版本。
