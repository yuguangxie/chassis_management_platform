from __future__ import annotations
from app.core.config import RuntimeConfig, load_config
from app.security.auth import AuthService
from app.services.signal_store import SignalStore

class AppState:
    def __init__(self) -> None:
        self.config: RuntimeConfig = load_config()
        self.auth = AuthService(self.config.profile)
        self.current_role = "operator"
        self.signals = SignalStore()
        self.db_writable = True
        self.emergency_stop = False
        self.safe_stop_active = False
        self.safe_stop_latched = False
        self.mock_enabled = False
        self.maintenance_mode = False
        self.maintenance_features = {
            "mock_can_gateway": False,
            "enable_0x123": False,
            "enable_0x126": False,
            "allow_canopen_nmt": False,
            "enable_pid_debug": False,
            "dual_control_channel_allowed": False,
        }
        self.can = None
        self.dbc = None
        self.alarms = None
        self.safety = None
        self.tx_scheduler = None
        self.eol = None
        self.database = None
        self.repositories = None
        self.eol_uow = None
        self.telemetry = None
        self.realtime_publisher = None
        self.raw_writer = None
        self.signal_writer = None
        self.reports = None
        self.report_service = None
        self.history_service = None
        self.safe_stop = None
        self.overrides = None
        self.preferences = None
        self.data_paths = None
        self.storage_health = None
        self.backups = None
        self.retention = None
        self.printing = None
        self.control_intents = None
        self.hardware_acceptance = None
        self.storage_config = None

    def snapshot(self) -> dict:
        dbc_status = self.dbc.status() if self.dbc else {"loaded": False, "raw_only": True, "version": "raw-only"}
        can_status = self.can.status() if self.can else []
        max_alarm = self.alarms.max_level() if self.alarms else 0
        return {
            "station_id": self.config.station_id,
            "operator": self.config.operator,
            "software_version": self.config.software_version,
            "database": {"type": "SQLite", "writable": self.db_writable},
            "control_channel": self.config.control_channel,
            "emergency_stop": self.emergency_stop,
            "mock_enabled": self.mock_enabled,
            "max_alarm_level": max_alarm,
            "dbc": dbc_status,
            "channels": can_status,
        }

state = AppState()
