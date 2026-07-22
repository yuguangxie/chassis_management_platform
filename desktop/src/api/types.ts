export interface ChannelStatus { channel: string; protocol?: string; local_ip?: string; local_port?: number; device_ip?: string; device_port?: number; online: boolean; fps: number; error_count: number; last_frame_hex?: string }
export interface DataSourceMetadata {
  data_source?: string
  mock?: boolean
  quality?: 'good' | 'degraded' | 'unavailable' | 'mock'
  updated_at?: string
  trace_id?: string
}
export interface SignalValue { key: string; value: number | string | boolean; unit?: string; label?: string; quality: string; updated_at: string; can_id?: string; message_name?: string; channel?: string }
export interface CanFrameRow { timestamp_ns: number; channel: string; direction: string; can_id_hex: string; dlc: number; data_hex: string; message_name?: string; parse_status: string }
export interface StatusSnapshot { station_id: string; operator: string; software_version: string; control_channel: string; emergency_stop: boolean; mock_enabled: boolean; max_alarm_level: number; database: { type: string; writable: boolean }; dbc: { loaded: boolean; raw_only: boolean; version: string; error?: string }; channels: ChannelStatus[] }

export interface OverviewChannel {
  online: boolean
  local: string
  device: string
  protocol: string
  fps: number
  error_frames: number
  last_frame_ms: number
  last_data_hex: string
}

export interface OverviewSummary extends DataSourceMetadata {
  station: {
    station_id: string
    operator: string
    software_version: string
    dbc_version: string
    database: { name: string; status: string }
    control_channel: string
    mock_enabled: boolean
    current_time: string
  }
  kpi: {
    today_total: number
    pass_rate: number
    fail_count: number
    avg_duration: string
    software_version: string
  }
  channels: Record<'CAN1' | 'CAN2', OverviewChannel>
  current_vehicle: {
    chassis_no: string
    vin: string
    serial_no: string
    test_plan: string
    operator: string
    current_step: string
    session_id: string
  }
  alarm_summary: {
    max_alarm_level: number
    max_alarm_label: string
    bms_protect_status: string
    emergency_stop: boolean
    protection_items: Array<{ name: string; status: string }>
  }
  charts: {
    today_result: { total: number; items: Array<{ name: string; value: number; percent: number }> }
    hourly_output: Array<{ hour: string; value: number }>
    fps_trend: Array<{ time: string; can1: number; can2: number }>
  }
  recent_sessions: Array<{
    session_id: string
    chassis_no: string
    vin: string
    started_at: string
    ended_at: string
    result: string
    operator: string
    report: string | null
  }>
}

export interface NetworkLocalPort {
  port: number
  protocol: string
  status: string
}

export interface NetworkChannelConfig {
  name: 'CAN1' | 'CAN2'
  protocol: 'UDP' | 'TCP'
  local_ip: string
  local_port: number
  device_ip: string
  device_port: number
  tx_enabled: boolean
  rx_status: string
  period_ms: number
  control_enabled: boolean
  status: string
  bind_status?: string
  last_frame_age_ms?: number | null
  tcp_state?: string
  source_allowlist_enforced?: boolean
  approved_sources?: string[]
}

export interface NetworkConfigSummary {
  local_network: {
    host_ip: string
    dev_ip: string
    nic_name: string
    subnet_mask: string
    link_speed: string
    ports: NetworkLocalPort[]
    diagnostic_source?: string
    diagnosed_at?: string
  }
  channels: NetworkChannelConfig[]
}

export interface NetworkSelfTestResult {
  ping_latency_ms: number | null
  udp_loopback: string
  protocol_valid_rate: number
  dlc_check: string
  reserved_bits_check: string
  sticky_half_packets: { sticky: number; half: number }
  last_error: string
  stub?: boolean
  message?: string
  channels?: Array<{
    channel: string
    protocol: string
    bind_status: string
    port_in_use: boolean
    endpoint_status: string
    last_frame_age_ms: number | null
    tcp_state: string
    source_allowlist_enforced: boolean
  }>
  steps?: Array<{ rule: string; status: string; duration_ms: number; details: Record<string, unknown>; recommendation: string }>
}

export interface SignedConfigurationPackage {
  schema_version: 1
  package_id: string
  issued_at: string
  issuer: string
  configuration: {
    config_version: string
    runtime_profile: 'dev' | 'mock' | 'test' | 'production'
    network_interface: { adapter_name: string; bind_address: string }
    can_endpoints: Array<{
      channel: 'CAN1' | 'CAN2'
      protocol: 'udp' | 'tcp'
      local_ip: string
      local_port: number
      device_ip: string
      device_port: number
      source_allowlist: Array<{ ip: string; port: number }>
      enabled: boolean
      control_enabled: boolean
    }>
    vehicle_series: string
    approved_dbc_sha256: string
    test_plan_version: string
    data_root: string
    station_id: string
    printer: { name: string | null; required: boolean }
  }
  signature_algorithm: 'HMAC-SHA256'
  signature: string
}

export interface ConfigurationPreviewResult {
  ok: boolean
  dry_run: true
  signature_valid: boolean
  schema_valid: boolean
  compatible: boolean
  summary: Record<string, string | number | boolean | null>
  diff: Array<{ path: string; current: unknown; proposed: unknown }>
  health_checks: Array<{ rule: string; passed: boolean; blocking: boolean; current: unknown; threshold: unknown }>
  blocking_checks: Array<{ rule: string; passed: boolean; blocking: boolean; current: unknown; threshold: unknown }>
  message: string
}

export interface ConfigurationExportResult {
  ok: boolean
  format: 'json'
  filename: string
  package: SignedConfigurationPackage
  message: string
}

export interface CanLatestFrame {
  timestamp: string
  channel: string
  direction: string
  can_id: number
  can_id_hex: string
  frame_type: string
  dlc: number
  data_hex: string
  message_name: string
  period_ms: number | string
  status: string
  source_session: string
  frame_count: number
  last_seen_ms: number
}

export interface CanDecodedSignal {
  name: string
  start_bit: number
  length: number
  type: string
  raw: string
  raw_value: number | string | boolean
  physical_value: number | string | boolean
  unit: string
  enum: string
  remark: string
}

export interface CanDecodedFrame extends DataSourceMetadata {
  frame: CanLatestFrame
  signals: CanDecodedSignal[]
  dbc_status: string
}

export interface CanMonitorStatistics extends DataSourceMetadata {
  can_id_distribution: Array<{ can_id_hex: string; count: number; percent: number }>
  fps_trend: Array<{ time: string; can1: number; can2: number }>
  period_jitter: Array<{ time: string; id_121: number; id_51: number; id_100: number }>
  error_summary: { timeout_count: number; error_frame_count: number; protocol_error_count: number }
  history_files: Array<{ file_id: string; file_name: string; session_id: string; started_at: string; size: string }>
  footer_status: { recording: boolean; uptime: string; buffer_usage: number; rx_fps: number; tx_fps: number }
}

export interface SignalDashboardSummary extends DataSourceMetadata {
  status: {
    overall: string
    updated_at: string
    mock: boolean
  }
  bms: {
    status: string
    total_voltage: number
    current: number
    soc: number
    ntc_temperature: number
    cell_max_voltage: number
    cell_min_voltage: number
    cell_delta_mv: number
    charge_discharge_state: string
    trend: {
      voltage: number[]
      current: number[]
      soc: number[]
      ntc: number[]
    }
  }
  vehicle: {
    status: string
    gear: string
    drive_mode: string
    ignition: string
    parking: string
    speed: number
  }
  wheel_speed: {
    status: string
    unit: string
    front_left: number
    front_right: number
    rear_left: number
    rear_right: number
  }
  steering: {
    status: string
    front_cmd: number
    front_feedback: number
    rear_cmd: number
    rear_feedback: number
    front_trend: number[]
    rear_trend: number[]
  }
  motor: {
    status: string
    speed_rpm: number
    phase_current_a: number
    heartbeat: string
    heartbeat_status: string
    speed_trend: number[]
    current_trend: number[]
  }
  lights_brake: {
    left_turn: string
    right_turn: string
    position_light: string
    low_beam: string
    brake_request: string
  }
  alarm: {
    status: string
    level: number
    label: string
    thresholds: Array<{ name: string; status: string }>
  }
  watchlist: Array<{
    signal_name: string
    can_id: string
    channel: string
    value: number | string
    unit: string
    threshold: string
    quality: string
    updated_at: string
    trend: number[]
  }>
}

export interface CurveGroup {
  key: string
  label: string
  count: number
}

export interface CurveSignal {
  name: string
  can_id: string
  unit: string
  color: string
  current_value: number | null
  selected: boolean
}

export interface CurveConfig extends DataSourceMetadata {
  groups: CurveGroup[]
  signals: CurveSignal[]
  default_window: string
  default_sample_rate: string
  default_downsample: string
  default_playback_speed: string
}

export interface CurveSeries {
  name: string
  unit: string
  data: Array<number | null>
  color?: string
  y_axis?: number
}

export interface CurveChart {
  x_axis: string[]
  series: CurveSeries[]
}

export interface CurveTimeseries extends DataSourceMetadata {
  mode: 'live' | 'history'
  updated_at: string
  charts: {
    speed_vs_vehicle: CurveChart
    speed_vs_wheels: CurveChart
    steering: CurveChart
    bms: CurveChart
    motor: CurveChart
    alarm_timeline: CurveChart
  }
}

export interface ReplayMetadata {
  session_id: string
  data_source: string
  timezone: string
  start_time: string
  end_time: string
  duration: string
  current: string
  progress_percent: number
}

export interface FaultEvent {
  id: string
  label: string
  time: string
}

export interface ManualControlCommand {
  gear: 'D' | 'N' | 'R'
  drive_mode: 'Manual' | 'Remote' | 'Auto'
  target_speed: number
  front_steer: number
  rear_steer: number
  brake_enable: boolean
  left_turn: boolean
  right_turn: boolean
  position_light: boolean
  low_beam: boolean
  control_mode: 'speed' | 'current'
  safety_context?: SafetyOverrideUse
}

export interface SafetyOverrideUse {
  override_id: string
  session_id: string
  vehicle_id: string
}

export type SafetyOverrideOperation = 'manual'
export type SafetyOverrideStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REVOKED' | 'EXPIRED'

export interface SafetyOverrideRequest {
  reason: string
  session_id: string
  operation: SafetyOverrideOperation
  vehicle_id: string
  authorized_user: string
  duration_seconds: number
}

export interface SafetyOverrideRecord {
  id: string
  alarm_id: string
  status: SafetyOverrideStatus
  requested_by: string
  request_reason: string
  requested_at: string
  session_id: string
  operation: SafetyOverrideOperation
  vehicle_id: string
  authorized_user: string
  duration_seconds: number
  approved_by?: string | null
  approved_at?: string | null
  approval_reason?: string | null
  expires_at?: string | null
  revoked_by?: string | null
  revoked_at?: string | null
  revoke_reason?: string | null
}

export interface ManualControlStatus {
  can_send_allowed: boolean
  control_message: string
  period_ms: number
  control_channel: string
  periodic_running: boolean
  last_tx_time: string
  tx_fail_count: number
  emergency_stop: boolean
  safe_stop_active: boolean
}

export interface ManualInterlockItem {
  key: string
  label: string
  status: 'pass' | 'warning' | 'fail'
  value: string
  rule?: string
  current?: unknown
  threshold?: unknown
  blocking?: boolean
}

export interface ManualInterlockStatus {
  overall: 'allow' | 'warning' | 'block'
  items: ManualInterlockItem[]
  reasons?: string[]
  evaluation?: {
    allowed: boolean
    operation: string
    profile: string
    degraded_mode: boolean
    feedback_groups: string[]
    rules: Array<{
      rule: string
      label: string
      status: 'PASS' | 'FAIL'
      current: unknown
      threshold: unknown
      blocking: boolean
    }>
    reasons: Array<{ rule: string; label: string; status: string; current: unknown; threshold: unknown; blocking: boolean }>
  }
}

export interface ManualPreview {
  can_id: string
  bytes_hex: string[]
  bytes_dec: number[]
  field_notes: string[]
  data_hex?: string
  data?: number[]
}

export interface ManualFeedback {
  gear: string
  vehicle_speed: number
  front_steer_feedback: number
  rear_steer_feedback: number
  wheel_speeds: string
  light_feedback: string
  brake_status: string
  alarm_status: string
  fields?: ManualFeedbackField[]
  overall?: 'valid' | 'invalid'
  mock?: boolean
  stale?: boolean
  updated_at?: string
}

export interface ManualFeedbackField {
  rule: string
  label: string
  status: 'valid' | 'invalid'
  present: boolean
  age_ms: number | null
  quality: string
  channel: string | null
  can_id: string | null
  value: unknown
  checks: {
    present?: boolean
    fresh?: boolean
    quality_valid?: boolean
    source_valid?: boolean
    value_valid?: boolean
  }
  threshold: Record<string, unknown>
  blocking: boolean
}

export interface ManualCurves {
  speed: {
    x_axis: string[]
    target_speed: number[]
    feedback_speed: number[]
  }
  steering: {
    x_axis: string[]
    front_cmd: number[]
    front_feedback: number[]
    rear_cmd: number[]
    rear_feedback: number[]
  }
}

export type AutoTestStepStatus = 'PASS' | 'FAIL' | 'RUNNING' | 'WAIT' | 'SKIPPED'

export interface AutoTestSession {
  session_id: string
  chassis_no: string
  vin: string
  serial_no: string
  operator: string
  station_id: string
  test_plan: string
  remark: string
  overall_status: 'RUNNING' | 'PASS' | 'FAIL' | 'WAIT' | 'PAUSED' | 'ABORTED'
  elapsed: string
  remaining: string
  completed: number
  passed: number
  failed: number
  waiting: number
  total: number
  current_step_index: number
  current_step_key: string
  current_step_name: string
}

export interface AutoTestStep {
  index: number
  name: string
  status: AutoTestStepStatus
}

export interface AutoTestCurrentStep {
  title: string
  description: string
  command: string
  period_ms: number
  timeout_ms: number
}

export interface AutoTestMeasurement {
  name: string
  value: number | string
  unit: string
}

export interface AutoTestAssertion {
  description: string
  signal?: string
  threshold: string
  value: string
  result: AutoTestStepStatus
  fail_reason?: string
}

export interface AutoTestStepLog {
  time: string
  step: string
  action: string
  can_command: string
  feedback: string
  status: AutoTestStepStatus
}

export interface AutoTestDashboard extends DataSourceMetadata {
  session: AutoTestSession
  steps: AutoTestStep[]
  current_step: AutoTestCurrentStep
  measurements: AutoTestMeasurement[]
  assertions: AutoTestAssertion[]
  step_logs: AutoTestStepLog[]
  charts: {
    realtime: {
      x_axis: string[]
      series: Array<{ name: string; data: number[] }>
    }
  }
  stats: {
    pass_rate: number
    passed: number
    failed: number
    waiting: number
    total_elapsed: string
    avg_step_duration: string
  }
}

export type AlarmLevelLabel = 'Normal' | 'Warning' | 'Fault' | 'Critical'

export interface AlarmMatrixItem {
  key: string
  label: string
  value: number
  status: AlarmLevelLabel
}

export interface BmsProtectItem {
  key: string
  label: string
  triggered?: boolean
  status?: string
}

export interface AlarmDiagnosisSuggestion {
  check_item: string
  suggestion: string
  allow_override: boolean
  priority: '高' | '中' | '低'
}

export interface AlarmHistoryItem {
  id?: string
  time: string
  channel: string
  can_id: string
  signal: string
  level: string
  status: string
  suggestion: string
  related_step: string
  released: boolean
}

export interface AlarmDiagnosisDashboard extends DataSourceMetadata {
  summary: {
    max_level: number
    max_label: AlarmLevelLabel
    current_count: number
    severe_locked: boolean
    recommendation: string
  }
  warning_matrix_0x77: AlarmMatrixItem[]
  bms_protect_0x102: {
    items: BmsProtectItem[]
    bitmap_bits: number[]
    bit_order: string
  }
  diagnosis_suggestions: AlarmDiagnosisSuggestion[]
  history: AlarmHistoryItem[]
  charts: {
    level_timeline: {
      x_axis: string[]
      series: Array<{ name: string; data: number[] }>
    }
    category_distribution: Array<{ name: AlarmLevelLabel; value: number; percent: number }>
  }
  updated_at?: string
  mock?: boolean
}

export interface ReportListItem {
  report_id: string
  session_id?: string
  chassis_no: string
  vin: string
  test_time: string
  result: string
  operator: string
  type: string
  size: string
  size_bytes?: number
  path: string
  generation_status: string
  file_hash?: string | null
}

export interface PrinterStatus {
  backend: string
  available: boolean
  default_printer: string | null
  printers: Array<{ name: string; is_default: boolean; status: string }>
  error: string | null
}

export interface PrintJob {
  id: string
  job_id: string
  report_id: string
  status: 'QUEUED' | 'PRINTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  printer_name: string
  backend: string
  spooler_job_id: string | null
  report_hash: string
  attempts: number
  status_detail: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface StorageLifecycleStats {
  data_root: string
  paths: Record<string, string>
  total_bytes: number
  used_bytes: number
  free_bytes: number
  used_percent: number
  category_bytes: Record<string, number>
  schema_version: number
  latest_schema_version: number
  database_writable: boolean
  health: Record<string, unknown>
  measured_at: string
}

export interface CleanupPreview {
  dry_run: boolean
  cutoff_utc: string
  session_ids: string[]
  session_count: number
  oldest_utc: string | null
  newest_utc: string | null
  row_counts: Record<string, number>
  file_count: number
  file_bytes: number
  estimated_database_bytes: number
  total_bytes: number
  protected: Record<string, number | string>
}

export interface BackupListItem {
  backup_id: string
  valid: boolean
  created_at: string | null
  schema_version: number | null
  size_bytes: number
  errors: string[]
}

export interface ReportPreviewData extends DataSourceMetadata {
  report_id: string
  filename: string
  file_type?: string
  file_sha256?: string
  file_size_bytes?: number
  preview: {
    title: string
    chassis_no: string
    vin: string
    test_time: string
    result: string
    operator: string
    page: number
    total_pages: number
    zoom: number
  }
  json_summary?: Record<string, unknown>
  csv_rows?: Array<Record<string, string | number>>
  document_text?: string[]
  preview_image_data_url?: string | null
}

export interface ReportRelatedSession {
  session_id: string
  started_at: string
  ended_at: string
  result: string
  report_count: number
}

export interface ReportManagementDashboard extends DataSourceMetadata {
  directory: {
    path: string
    total_gb: number
    used_gb: number
    free_gb: number
    used_percent: number
    last_scan_time: string
    scan_status: string
    file_type_stats: Array<{ type: string; count: number; percent: number }>
  }
  reports: ReportListItem[]
  selected_report: ReportPreviewData | null
  related_data: { sessions: ReportRelatedSession[] }
  charts: {
    storage_trend: Array<{ date: string; used: number; free: number }>
    result_distribution: Array<{ name: 'PASS' | 'FAIL'; value: number; percent: number }>
  }
  mock?: boolean
  updated_at?: string
}

export type HistorySessionResult = 'PASS' | 'FAIL' | 'ABORTED' | 'RUNNING'

export interface HistorySessionItem {
  session_id: string
  chassis_no: string
  vin: string
  serial_no?: string
  started_at: string
  ended_at: string
  result: HistorySessionResult
  failed_step: string
  operator: string
  station_id?: string
  report_id: string | null
}

export interface HistoryTimelineItem {
  time: string
  title: string
  description: string
  status: 'PASS' | 'FAIL' | 'INFO' | 'RUNNING'
  icon: string
}

export interface HistoryOperatorLog {
  time: string
  user: string
  action: string
  target: string
  params: string
  result: string
}

export interface HistoryDownloadItem {
  key: 'raw_can' | 'decoded_signals' | 'report_bundle' | 'audit_log' | 'curve_replay'
  name: string
  extension: string
  size: string
  available: boolean
}

export interface HistorySelectedSession {
  session_id: string
  duration: string
  result: HistorySessionResult
  timeline: HistoryTimelineItem[]
  operator_logs: HistoryOperatorLog[]
  downloads: HistoryDownloadItem[]
}

export interface HistoryDashboard extends DataSourceMetadata {
  filters: {
    start_time: string
    end_time: string
    page: number
    page_size: number
  }
  summary: {
    total_tests: number
    pass_rate: number
    fail_count: number
    alarm_count: number
    filtered_count: number
  }
  sessions: HistorySessionItem[]
  selected_session: HistorySelectedSession | null
  charts: {
    vehicle_result_trend: {
      vin: string
      x_axis: string[]
      pass: number[]
      fail: number[]
    }
    failure_pareto: {
      categories: string[]
      counts: number[]
      cumulative_percent: number[]
    }
  }
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
  mock?: boolean
  updated_at?: string
}

export interface SystemThresholdSetting {
  key: string
  label: string
  value: number | boolean
  min: number | null
  max: number | null
  unit: string
  scope: string
  description: string
  dangerous: boolean
  status?: 'normal' | 'invalid' | 'modified'
}

export interface SystemRoleSetting {
  role: string
  view: string
  test: string
  manual_control: string
  config: string
  maintenance: string
  delete_report: boolean
  admin_confirmation: boolean
}

export interface SystemMaintenanceSettings {
  maintenance_mode: boolean
  mock_can_gateway: boolean
  enable_0x123: boolean
  enable_0x126: boolean
  allow_canopen_nmt: boolean
  enable_pid_debug: boolean
  dual_control_channel_allowed: boolean
  requires_admin: boolean
}

export interface SystemSettingsDashboard extends DataSourceMetadata {
  save_state: {
    dirty: boolean
    last_saved_at: string
    status: string
  }
  auth: {
    current_user: string
    current_role: string
  }
  basic: {
    station_id: string
    host_ip: string
    control_channel: 'CAN1' | 'CAN2'
    report_directory: string
    database_path: string
    log_directory: string
    timezone: string
    language: string
    auto_save: boolean
  }
  dbc: {
    filename: string
    version: string
    hash: string
    status: 'loaded' | 'raw-only' | 'failed'
    error?: string
    message_count: number
    signal_count: number
    loaded_at: string
    overrides: Array<{ key: string; label: string; value: string; status: string }>
  }
  storage: {
    data_root: string
    report_directory: string
    raw_can_directory: string
    decoded_signal_directory: string
    database_path: string
    retention_days: number
    max_log_gb: number
    auto_cleanup: boolean
    word_enabled: boolean
    pdf_enabled: boolean
    csv_enabled: boolean
    parquet_enabled: boolean
    disk_total_gb: number
    disk_used_gb: number
    disk_free_gb: number
    disk_used_percent: number
    measurement_error?: string | null
  }
  thresholds: SystemThresholdSetting[]
  roles: SystemRoleSetting[]
  maintenance: SystemMaintenanceSettings
  safe_defaults: Array<{ label: string; enabled: boolean }>
  version: {
    software: string
    config: string
    test_plan: string
    python: string
    node: string
    electron: string
    platform: string
    build_time: string
  }
  storage_trend: Array<{ date: string; used_gb: number; source?: string }>
  storage_summary: {
    current_log_gb: number
    database_gb: number
    reports_gb: number
    raw_can_gb: number
    last_cleanup: string
    next_cleanup: string
    cleanup_status: string
    disk_alarm: string
  }
  config_history: Array<{
    time: string
    user: string
    key: string
    old_value: string
    new_value: string
    reason: string
    result: string
  }>
  mock?: boolean
  updated_at?: string
}
