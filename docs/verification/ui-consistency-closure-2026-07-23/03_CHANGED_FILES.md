# 改动文件清单

基线：`ba47b0aaebc62eae3131d23ed9d318fdb4721130`。以下为本工作包实现或验证涉及的文件；工作树尚未创建新 commit。

## 后端与测试

- `backend/app/api/signals.py`
- `backend/app/services/lifecycle.py`
- `backend/app/api/control.py`
- `backend/tests/test_phase03_contract_data.py`
- `backend/tests/test_desktop_page_function_matrix.py`

## 桌面基础设施、共享组件与状态

- `desktop/src/api/http.ts`
- `desktop/src/api/types.ts`
- `desktop/src/ui/uiStatusLabels.ts`
- `desktop/src/ui/uiStatusLabels.test.ts`
- `desktop/src/components/PageDataState.vue`
- `desktop/src/components/forms/ToggleSwitch.vue`
- `desktop/src/components/forms/ToggleSwitch.test.ts`
- `desktop/src/components/common/IndustrialButton.vue`
- `desktop/src/components/common/IndustrialActionButton.vue`
- `desktop/src/components/common/IndustrialButton.test.ts`
- `desktop/src/components/signals/SignalLightItem.vue`
- `desktop/src/components/signals/SignalLightItem.test.ts`
- `desktop/src/components/layout/SidebarNav.vue`
- `desktop/src/components/layout/TopStatusBar.vue`
- `desktop/src/stores/signals.ts`
- `desktop/src/stores/signals.test.ts`
- `desktop/src/stores/eol.ts`
- `desktop/src/stores/alarms.ts`
- `desktop/src/styles/industrial-theme.css`

## 11 个业务页面与页面契约

- `desktop/src/pages/OverviewPage.vue`
- `desktop/src/pages/NetworkConfigPage.vue`
- `desktop/src/pages/CanMonitorPage.vue`
- `desktop/src/pages/SignalDashboardPage.vue`
- `desktop/src/pages/RealtimeCurvePage.vue`
- `desktop/src/pages/ManualControlPage.vue`
- `desktop/src/pages/AutoTestPage.vue`
- `desktop/src/pages/AlarmDiagnosisPage.vue`
- `desktop/src/pages/ReportManagementPage.vue`
- `desktop/src/pages/HistoryPage.vue`
- `desktop/src/pages/SystemSettingsPage.vue`
- `desktop/src/pages/pageFunctionContracts.test.ts`
- `desktop/src/pages/uiConsistencyContracts.test.ts`

## Electron 验收与构建证据

- `desktop/electron/phase04_capture.cjs`
- `desktop/scripts/phase05-e2e.mjs`
- `docs/verification/phase-05/bundle-report.json`（`test:bundle` 自动更新）
- `docs/verification/ui-consistency-closure-2026-07-23/`（矩阵、汇总、日志、JSON 指标和 22 张 PNG）

## 文档

- `docs/UI_IMPLEMENTATION_NOTES.md`
- `docs/API.md`
- `docs/CONFIGURATION.md`
- `docs/TESTING.md`
- `docs/20_risk_and_open_questions.md`

## 开始前已有且已保留的用户改动

- `docs/audit/16_DESKTOP_UI_CONSISTENCY_AUDIT_2026-07-23.md`
- `docs/reference/DESKTOP_UI_OPTIMIZATION_PROMPT_2026-07-23.md`
- `docs/verification/ui-consistency-audit-2026-07-23/`
- `docs/audit/AUDIT_INDEX.md`
- `docs/20_risk_and_open_questions.md`（在保留原内容基础上追加本轮结论）

证据目录未保留临时数据库、测试账户/session、bootstrap 凭据、签名 key 或 runtime data root。
