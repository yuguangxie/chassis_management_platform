from types import SimpleNamespace
from app.control.control_121 import Control121Command
from app.control.safety_interlock import SafetyInterlockService
from app.dbc.overrides import DISABLED_CONTROL_IDS
from app.services.app_state import AppState

def ready_state() -> AppState:
    s = AppState()
    s.db_writable = True
    s.dbc = SimpleNamespace(status=lambda: {"loaded": True})
    s.alarms = SimpleNamespace(max_level=lambda: 0)
    s.can = SimpleNamespace(status=lambda: [{"channel":"CAN2","online":True}])
    return s

def test_interlock_blocks_emergency():
    s = ready_state()
    s.emergency_stop = True
    result = SafetyInterlockService(s).evaluate(Control121Command())
    assert not result["allowed"]
    assert any(r["rule"] == "emergency_released" for r in result["reasons"])

def test_interlock_blocks_overspeed():
    s = ready_state()
    result = SafetyInterlockService(s).evaluate(Control121Command(target_speed_kmh=8))
    assert not result["allowed"]
    assert any(r["rule"] == "speed_limit" for r in result["reasons"])

def test_extended_control_ids_disabled_by_default():
    assert 0x123 in DISABLED_CONTROL_IDS
    assert 0x126 in DISABLED_CONTROL_IDS


def test_runtime_transmission_allowlist_only_contains_0x121():
    state = AppState()
    assert state.config.allowed_tx_can_ids == {0x121}
