# 本工作包改动文件

以下按职责列出生产身份、前端路由守卫和配置生命周期的主要改动。工作树还包含同一审计周期的安全联锁/CAN 收口文件，其证据位于相邻 `safety-can-p0p1-2026-07-21` 目录。

## 后端身份与授权

- `backend/app/security/auth.py`
- `backend/app/api/auth.py`
- `backend/app/api/errors.py`
- `backend/app/api/router.py`
- `backend/app/main.py`
- `backend/app/services/lifecycle.py`
- `backend/app/services/app_state.py`
- `backend/app/storage/schema.sql`
- `backend/app/websocket/endpoint.py`
- `backend/app/websocket/manager.py`
- `backend/app/api/alarms.py`
- `backend/app/api/can.py`
- `backend/app/api/config.py`
- `backend/app/api/control.py`
- `backend/app/api/dbc.py`
- `backend/app/api/eol.py`
- `backend/app/api/history.py`
- `backend/app/api/overview.py`
- `backend/app/api/reports.py`
- `backend/app/api/signals.py`

## 配置与诊断

- `backend/app/configuration/__init__.py`
- `backend/app/configuration/models.py`
- `backend/app/configuration/service.py`
- `backend/app/configuration/diagnostics.py`
- `backend/app/core/config.py`
- `configs/production-config.template.json`
- `.env.example`
- `scripts/dev_backend.py`
- `scripts/sign_configuration.py`
- `scripts/generate_api_docs.py`

## 桌面端

- `desktop/src/api/http.ts`
- `desktop/src/api/types.ts`
- `desktop/src/api/websocket.ts`
- `desktop/src/stores/auth.ts`
- `desktop/src/router/index.ts`
- `desktop/src/main.ts`
- `desktop/src/App.vue`
- `desktop/src/components/layout/AppShell.vue`
- `desktop/src/components/layout/SidebarNav.vue`
- `desktop/src/components/layout/TopStatusBar.vue`
- `desktop/src/pages/LoginPage.vue`
- `desktop/src/pages/LockScreenPage.vue`
- `desktop/src/pages/ForbiddenPage.vue`
- `desktop/src/pages/SystemSettingsPage.vue`
- `desktop/src/pages/NetworkConfigPage.vue`
- `desktop/electron/phase04_capture.cjs`
- `desktop/scripts/phase05-e2e.mjs`

## 测试

- `backend/tests/conftest.py`
- `backend/tests/test_auth_sessions.py`
- `backend/tests/test_api_auth_inventory.py`
- `backend/tests/test_configuration_lifecycle.py`
- `backend/tests/test_network_diagnostics.py`
- `backend/tests/test_cors_boundary.py`
- 既有 API 测试中新增会话头和 401/403 断言的文件
- `desktop/src/api/http.test.ts`
- `desktop/src/api/websocket.test.ts`
- `desktop/src/stores/auth.test.ts`
- `desktop/src/router/index.test.ts`
- `desktop/src/components/layout/AppShell.test.ts`
- `desktop/src/components/layout/SidebarNav.test.ts`

## 文档与证据

- `README.md`
- `docs/API.md`
- `docs/CONFIGURATION.md`
- `docs/IDENTITY_AND_ACCESS.md`
- `docs/DEVELOPMENT.md`
- `docs/20_risk_and_open_questions.md`
- `docs/openapi.json`
- `docs/api-authorization-matrix.csv`
- `docs/production-configuration.schema.json`
- `docs/verification/production-identity-config-2026-07-22/`
