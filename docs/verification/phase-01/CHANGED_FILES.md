# 阶段一修改文件

## 后端运行代码

- `backend/app/core/config.py`
- `backend/app/security/__init__.py`
- `backend/app/security/auth.py`
- `backend/app/services/app_state.py`
- `backend/app/services/audit.py`
- `backend/app/services/lifecycle.py`
- `backend/app/services/signal_store.py`
- `backend/app/main.py`
- `backend/app/websocket/endpoint.py`
- `backend/app/can_gateway/models.py`
- `backend/app/can_gateway/statistics.py`
- `backend/app/can_gateway/usr_can115.py`
- `backend/app/can_gateway/udp_gateway.py`
- `backend/app/can_gateway/tcp_gateway.py`
- `backend/app/can_gateway/manager.py`
- `backend/app/control/control_121.py`
- `backend/app/control/safety_interlock.py`
- `backend/app/control/tx_scheduler.py`
- `backend/app/control/safe_stop.py`
- `backend/app/eol/engine.py`
- `backend/app/alarms/service.py`
- `backend/app/api/control.py`
- `backend/app/api/eol.py`
- `backend/app/api/config.py`
- `backend/app/api/can.py`
- `backend/app/api/dbc.py`
- `backend/app/api/alarms.py`
- `backend/app/api/reports.py`

## 配置与仿真器

- `configs/channels.dev.yaml`
- `configs/channels.mock.yaml`
- `simulator/can_frame_simulator.py`
- `scripts/verify_phase01_loopback.py`

生产 `configs/channels.yaml` 未改为开发地址；只有显式 `CHASSIS_RUNTIME_PROFILE=production` 才会加载它。

## 桌面端安全接入

- `desktop/src/api/http.ts`
- `desktop/src/api/websocket.ts`
- `desktop/src/pages/ManualControlPage.vue`
- `desktop/src/mocks/fallbackData.ts`
- `desktop/src/mocks/systemSettings.ts`

未重做页面布局。改动仅包括认证 token、急停解除确认 payload、权威预览 fallback 和离线保守禁止状态。

## 测试

- `backend/tests/conftest.py`
- `backend/tests/test_alarm_dashboard.py`
- `backend/tests/test_report_dashboard.py`
- `backend/tests/test_safety_interlock.py`
- `backend/tests/test_system_settings.py`
- `backend/tests/test_phase01_auth_rbac.py`
- `backend/tests/test_phase01_can_boundary.py`
- `backend/tests/test_phase01_control_121_authority.py`
- `backend/tests/test_phase01_eol_lifecycle.py`
- `backend/tests/test_phase01_runtime_profile.py`
- `backend/tests/test_phase01_safe_stop.py`
- `simulator/tests/conftest.py`
- `simulator/tests/test_simulator.py`

## 生成证据

证据文件均位于 `docs/verification/phase-01/`，未修改或覆盖 `docs/audit/evidence/`。
