PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS test_sessions (
  id TEXT PRIMARY KEY,
  chassis_no TEXT NOT NULL,
  vin TEXT NOT NULL,
  serial_no TEXT,
  operator TEXT NOT NULL,
  station_id TEXT NOT NULL,
  test_plan_id TEXT NOT NULL,
  plan_version TEXT,
  vehicle_series TEXT,
  status TEXT NOT NULL,
  overall_result TEXT,
  started_at TEXT,
  ended_at TEXT,
  remarks TEXT,
  dbc_hash TEXT,
  config_hash TEXT,
  software_version TEXT,
  failure_reason TEXT,
  safe_stop_json TEXT,
  report_id TEXT,
  work_order_id TEXT,
  duplicate_policy TEXT NOT NULL DEFAULT 'reject',
  duplicate_of_session_id TEXT,
  release_hash TEXT,
  config_version TEXT,
  test_plan_hash TEXT,
  auth_session_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES test_sessions(id),
  step_id TEXT NOT NULL,
  step_order INTEGER NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  result TEXT,
  started_at TEXT,
  ended_at TEXT,
  duration_ms INTEGER,
  failure_reason TEXT,
  command_summary TEXT,
  measurement_summary TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_assertions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES test_sessions(id),
  step_id TEXT NOT NULL,
  assertion_id TEXT NOT NULL,
  description TEXT,
  signal_name TEXT,
  operator TEXT,
  threshold_json TEXT,
  measured_value TEXT,
  unit TEXT,
  result TEXT NOT NULL,
  severity TEXT,
  failure_reason TEXT,
  sample_start_at TEXT,
  sample_end_at TEXT,
  quality TEXT,
  source_can_id TEXT,
  source_channel TEXT,
  source_timestamp TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_can_frames (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  timestamp_utc TEXT NOT NULL,
  channel TEXT NOT NULL,
  direction TEXT NOT NULL,
  can_id_hex TEXT NOT NULL,
  is_extended INTEGER NOT NULL,
  is_remote INTEGER NOT NULL,
  dlc INTEGER NOT NULL,
  data_hex TEXT NOT NULL,
  packet_hex TEXT,
  source_ip TEXT,
  source_port INTEGER,
  parse_status TEXT NOT NULL,
  error_code TEXT,
  message_name TEXT,
  period_ms REAL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decoded_signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  timestamp_utc TEXT NOT NULL,
  channel TEXT NOT NULL,
  can_id_hex TEXT NOT NULL,
  message_name TEXT,
  signal_name TEXT NOT NULL,
  raw_value TEXT,
  physical_value TEXT,
  unit TEXT,
  enum_label TEXT,
  quality TEXT,
  threshold_status TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_statistics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  channel TEXT NOT NULL,
  can_id_hex TEXT NOT NULL,
  message_name TEXT,
  expected_period_ms REAL,
  avg_period_ms REAL,
  min_period_ms REAL,
  max_period_ms REAL,
  jitter_ms REAL,
  fps REAL,
  rx_count INTEGER,
  timeout_count INTEGER,
  error_count INTEGER,
  window_start_at TEXT,
  window_end_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alarms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  timestamp_utc TEXT NOT NULL,
  channel TEXT,
  can_id_hex TEXT,
  signal_name TEXT NOT NULL,
  level INTEGER NOT NULL,
  level_label TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT,
  related_step_id TEXT,
  acknowledged_by TEXT,
  acknowledged_at TEXT,
  release_reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES test_sessions(id),
  chassis_no TEXT NOT NULL,
  vin TEXT NOT NULL,
  result TEXT NOT NULL,
  report_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_size_bytes INTEGER,
  file_hash TEXT,
  generation_status TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  generated_by TEXT,
  archived_at TEXT,
  archive_manifest_hash TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS report_print_jobs (
  id TEXT PRIMARY KEY,
  report_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  status TEXT NOT NULL,
  printer_name TEXT,
  backend TEXT,
  spooler_job_id TEXT,
  report_hash TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  status_detail TEXT,
  error_message TEXT,
  completed_at TEXT,
  cancelled_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operator_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  timestamp_utc TEXT NOT NULL,
  operator TEXT NOT NULL,
  role TEXT,
  action_type TEXT NOT NULL,
  target TEXT,
  request_json TEXT,
  result TEXT NOT NULL,
  trace_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_accounts (
  username TEXT PRIMARY KEY,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
  id TEXT PRIMARY KEY,
  account_username TEXT NOT NULL REFERENCES auth_accounts(username),
  token_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  revoked_at TEXT,
  revoke_reason TEXT
);

CREATE TABLE IF NOT EXISTS safety_overrides (
  id TEXT PRIMARY KEY,
  alarm_id TEXT NOT NULL,
  status TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  request_reason TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  session_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  vehicle_id TEXT NOT NULL,
  authorized_user TEXT NOT NULL,
  duration_seconds INTEGER NOT NULL,
  approved_by TEXT,
  approval_reason TEXT,
  approved_at TEXT,
  expires_at TEXT,
  revoked_by TEXT,
  revoke_reason TEXT,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS config_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp_utc TEXT NOT NULL,
  operator TEXT NOT NULL,
  config_key TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  reason TEXT,
  config_hash TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS software_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  version TEXT NOT NULL,
  build_time TEXT,
  git_commit TEXT,
  dbc_version TEXT,
  dbc_hash TEXT,
  config_hash TEXT,
  migration_version TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backup_records (
  id TEXT PRIMARY KEY,
  manifest_path TEXT NOT NULL,
  database_path TEXT NOT NULL,
  database_hash TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  verified_at TEXT,
  restored_at TEXT
);

CREATE TABLE IF NOT EXISTS cleanup_jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  cutoff_utc TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  dry_run INTEGER NOT NULL,
  confirmation TEXT,
  candidate_json TEXT NOT NULL,
  progress_json TEXT NOT NULL,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS control_intents (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK(status IN ('PENDING','AUTHORIZED','SENT','CONFIRMED','FAILED','AUDIT_FAILED','CANCELLED')),
  principal TEXT NOT NULL,
  role TEXT NOT NULL,
  auth_session_id TEXT,
  vehicle_id TEXT,
  eol_session_id TEXT,
  operation TEXT NOT NULL,
  target TEXT NOT NULL,
  command_json TEXT NOT NULL,
  command_hash TEXT NOT NULL,
  safety_evaluation_json TEXT NOT NULL,
  safety_evaluation_hash TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  error_code TEXT,
  error_detail TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT,
  confirmed_at TEXT,
  recovery_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_can_session_time ON raw_can_frames(session_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_decoded_session_signal_time ON decoded_signals(session_id, signal_name, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_steps_session ON test_steps(session_id, step_order);
CREATE INDEX IF NOT EXISTS idx_assertions_session ON test_assertions(session_id, step_id);
CREATE INDEX IF NOT EXISTS idx_alarms_session_time ON alarms(session_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_reports_session ON reports(session_id);
CREATE INDEX IF NOT EXISTS idx_print_jobs_report ON report_print_jobs(report_id, created_at);
CREATE INDEX IF NOT EXISTS idx_actions_session_time ON operator_actions(session_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_status ON auth_sessions(token_hash, status);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_account_expiry ON auth_sessions(account_username, expires_at);
CREATE INDEX IF NOT EXISTS idx_safety_overrides_status_expiry ON safety_overrides(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_status ON cleanup_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_reports_archived ON reports(archived_at, generated_at);
CREATE INDEX IF NOT EXISTS idx_control_intents_status_time ON control_intents(status, created_at);
CREATE INDEX IF NOT EXISTS idx_control_intents_session ON control_intents(eol_session_id, created_at);
