# 本工作包修改文件

## Backend

- API/类型：`backend/app/api/alarms.py`、`control.py`、`models.py`
- CAN：`backend/app/can_gateway/manager.py`、`statistics.py`、`udp_gateway.py`、`usr_can115.py`
- 控制与安全：`backend/app/control/override_service.py`、`safe_stop.py`、`safety_interlock.py`、`tx_scheduler.py`
- 配置/DBC：`backend/app/core/config.py`、`backend/app/dbc/loader.py`、`service.py`
- EOL：`backend/app/eol/assertions.py`、`models.py`
- 生命周期/存储：`backend/app/services/app_state.py`、`lifecycle.py`、`backend/app/storage/schema.sql`

## 配置、Simulator 与桌面 API 类型

- `configs/safety_interlock.yaml`、`configs/station.yaml`
- `simulator/can_frame_simulator.py`、`simulator/tests/test_simulator.py`
- `desktop/src/api/types.ts`

## 测试

- 新增：`backend/tests/test_safety_can_p0p1.py`、`test_eol_assertions_complete.py`
- 更新：`test_usr_can115.py`、`test_phase01_can_boundary.py`、`test_phase01_runtime_profile.py`、`test_phase01_safe_stop.py`

## 文档

- 仓库内：`docs/API.md`、`SAFETY_INTERLOCK.md`、`CAN_PROTOCOL.md`、`CONFIGURATION.md` 及本证据目录。
- 实施资料包：外层 `docs/07_api_spec.md`、`09_can_gateway_design.md`、`12_safety_interlock_design.md`、`14_test_assertion_standards.md`、`20_risk_and_open_questions.md`。

说明：开始工作前已存在多项桌面页面、图表、布局及样式改动；这些用户改动被保留，未列为本工作包实现。
