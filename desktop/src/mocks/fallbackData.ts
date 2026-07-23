import type { AlarmDiagnosisDashboard, AutoTestDashboard, CanDecodedFrame, CanDecodedSignal, CanFrameRow, CanLatestFrame, CanMonitorStatistics, ChannelStatus, CurveConfig, CurveTimeseries, FaultEvent, HistoryDashboard, ManualControlCommand, ManualControlStatus, ManualCurves, ManualFeedback, ManualInterlockStatus, ManualPreview, NetworkConfigSummary, NetworkSelfTestResult, OverviewSummary, ReplayMetadata, ReportManagementDashboard, SignalDashboardSummary, SignalValue, StatusSnapshot } from '../api/types'

export const fallbackStatus: StatusSnapshot = {
  station_id: 'EOL-STATION-01',
  operator: 'op01',
  software_version: 'v1.0.2',
  control_channel: 'CAN2',
  emergency_stop: false,
  mock_enabled: true,
  max_alarm_level: 0,
  database: { type: 'SQLite', writable: true },
  dbc: { loaded: false, raw_only: true, version: 'Yunle_CAN_Integrated_CANdb' },
  channels: [],
}

export const fallbackChannels: ChannelStatus[] = [
  { channel: 'CAN1', online: false, fps: 0, error_count: 0 },
  { channel: 'CAN2', online: false, fps: 0, error_count: 0 },
]

export const fallbackSignals: Record<string, SignalValue> = {}
export const fallbackFrames: CanFrameRow[] = []

export const fallbackOverviewSummary: OverviewSummary = {
  station: {
    station_id: 'EOL-STATION-01',
    operator: 'op01',
    software_version: 'v1.0.2',
    dbc_version: 'Yunle_CAN_Integrated_CANdb',
    database: { name: 'SQLite', status: 'normal' },
    control_channel: 'CAN2',
    mock_enabled: false,
    current_time: '2026-04-01 10:26:35',
  },
  kpi: {
    today_total: 18,
    pass_rate: 94.4,
    fail_count: 1,
    avg_duration: '08:42',
    software_version: 'v1.0.2',
  },
  channels: {
    CAN1: {
      online: true,
      local: '127.0.0.1:8234',
      device: '127.0.0.1:12341',
      protocol: 'UDP',
      fps: 820,
      error_frames: 0,
      last_frame_ms: 12,
      last_data_hex: '00 00 14 14 14 14 00 00',
    },
    CAN2: {
      online: true,
      local: '127.0.0.1:8235',
      device: '127.0.0.1:12342',
      protocol: 'UDP',
      fps: 610,
      error_frames: 0,
      last_frame_ms: 10,
      last_data_hex: '21 22 21 22 21 22 00 00',
    },
  },
  current_vehicle: {
    chassis_no: 'YL-JD-001',
    vin: 'L0000000000000001',
    serial_no: 'SN-20260401-001',
    test_plan: '标准下线方案 V1',
    operator: 'op01',
    current_step: 'BMS检测',
    session_id: 'EOL-20260401-0001',
  },
  alarm_summary: {
    max_alarm_level: 0,
    max_alarm_label: 'Normal',
    bms_protect_status: '全部未触发',
    emergency_stop: false,
    protection_items: [
      { name: '过压保护', status: '正常' },
      { name: '欠压保护', status: '正常' },
      { name: '过流保护', status: '正常' },
      { name: '过温保护', status: '正常' },
      { name: '绝缘故障', status: '正常' },
      { name: '预充超时', status: '正常' },
      { name: '继电器粘连', status: '正常' },
      { name: 'SOC过低', status: '正常' },
    ],
  },
  charts: {
    today_result: {
      total: 18,
      items: [
        { name: 'PASS', value: 17, percent: 94.4 },
        { name: 'FAIL', value: 1, percent: 5.6 },
        { name: 'RUNNING', value: 0, percent: 0.0 },
        { name: '中止', value: 0, percent: 0.0 },
      ],
    },
    hourly_output: [
      { hour: '00', value: 0 },
      { hour: '02', value: 1 },
      { hour: '04', value: 2 },
      { hour: '06', value: 3 },
      { hour: '08', value: 5 },
      { hour: '10', value: 7 },
      { hour: '12', value: 3 },
      { hour: '14', value: 2 },
      { hour: '16', value: 2 },
      { hour: '18', value: 1 },
      { hour: '20', value: 0 },
      { hour: '22', value: 0 },
    ],
    fps_trend: [
      { time: '09:56', can1: 900, can2: 610 },
      { time: '10:01', can1: 920, can2: 620 },
      { time: '10:06', can1: 890, can2: 600 },
      { time: '10:11', can1: 930, can2: 615 },
      { time: '10:16', can1: 910, can2: 605 },
      { time: '10:21', can1: 940, can2: 620 },
      { time: '10:26', can1: 920, can2: 610 },
    ],
  },
  recent_sessions: [
    { session_id: 'EOL-20260401-0001', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', started_at: '2026-04-01 10:15:22', ended_at: '—', result: 'RUNNING', operator: 'op01', report: null },
    { session_id: 'EOL-20260401-0000', chassis_no: 'YL-JD-000', vin: 'L0000000000000000', started_at: '2026-04-01 09:58:13', ended_at: '2026-04-01 10:12:47', result: 'PASS', operator: 'op01', report: 'RPT-20260401-0000' },
    { session_id: 'EOL-20260401-000-1', chassis_no: 'YL-JD-099', vin: 'L0000000000000099', started_at: '2026-04-01 09:12:20', ended_at: '2026-04-01 09:28:03', result: 'PASS', operator: 'op01', report: 'RPT-20260401-000-1' },
    { session_id: 'EOL-20260401-000-2', chassis_no: 'YL-JD-098', vin: 'L0000000000000098', started_at: '2026-04-01 08:41:09', ended_at: '2026-04-01 08:57:50', result: 'FAIL', operator: 'op02', report: 'RPT-20260401-000-2' },
  ],
}

export const fallbackNetworkConfig: NetworkConfigSummary = {
  local_network: {
    host_ip: '127.0.0.1',
    dev_ip: '127.0.0.1',
    nic_name: '回环占位（Mock）',
    adapter_index: null,
    mac_address: null,
    bind_address: '127.0.0.1',
    adapter_identity_status: 'not_applicable',
    adapter_identity_rule: null,
    subnet_mask: 'not-measured',
    link_speed: 'not-measured',
    ports: [
      { port: 8234, protocol: 'UDP', status: 'free' },
      { port: 8235, protocol: 'UDP', status: 'free' },
    ],
  },
  channels: [
    {
      name: 'CAN1',
      protocol: 'UDP',
      local_ip: '127.0.0.1',
      local_port: 8234,
      device_ip: '127.0.0.1',
      device_port: 12341,
      enabled: true,
      rx_status: 'unconfirmed',
      period_ms: 20,
      control_enabled: false,
      status: 'disabled',
      bind_status: 'not_diagnosed',
      last_frame_age_ms: null,
      tcp_state: 'not_applicable',
      source_allowlist_enforced: true,
      approved_sources: ['127.0.0.1:12341'],
    },
    {
      name: 'CAN2',
      protocol: 'UDP',
      local_ip: '127.0.0.1',
      local_port: 8235,
      device_ip: '127.0.0.1',
      device_port: 12342,
      enabled: true,
      rx_status: 'unconfirmed',
      period_ms: 20,
      control_enabled: true,
      status: 'disabled',
      bind_status: 'not_diagnosed',
      last_frame_age_ms: null,
      tcp_state: 'not_applicable',
      source_allowlist_enforced: true,
      approved_sources: ['127.0.0.1:12342'],
    },
  ],
}

export const fallbackNetworkSelfTest: NetworkSelfTestResult = {
  ping_latency_ms: null,
  udp_loopback: 'unavailable',
  protocol_valid_rate: 0,
  dlc_check: 'pass',
  reserved_bits_check: 'pass',
  sticky_half_packets: { sticky: 0, half: 0 },
  last_error: '尚未执行真实诊断',
  stub: true,
  message: '离线占位数据，不代表设备可达',
}

export const fallbackCanLatestFrames: CanLatestFrame[] = [
  { timestamp: '10:26:35.123.456', channel: 'CAN1', direction: 'RX', can_id: 0x121, can_id_hex: '0x121', frame_type: '标准帧', dlc: 8, data_hex: '20 03 FF 00 01 01 00 7F', message_name: 'SCU_Control_Command', period_ms: 50, status: '正常', source_session: '-', frame_count: 4872, last_seen_ms: 12 },
  { timestamp: '10:26:35.120.112', channel: 'CAN2', direction: 'RX', can_id: 0x51, can_id_hex: '0x51', frame_type: '标准帧', dlc: 8, data_hex: '01 2C 00 64 00 00 00 00', message_name: 'VCU_CCU_Status', period_ms: 20, status: '正常', source_session: '-', frame_count: 3812, last_seen_ms: 18 },
  { timestamp: '10:26:35.118.987', channel: 'CAN1', direction: 'RX', can_id: 0x77, can_id_hex: '0x77', frame_type: '标准帧', dlc: 8, data_hex: '00 00 00 00 00 00 00 00', message_name: 'VCU_Warning_Level', period_ms: 100, status: '正常', source_session: '-', frame_count: 2988, last_seen_ms: 24 },
  { timestamp: '10:26:35.117.654', channel: 'CAN2', direction: 'RX', can_id: 0x100, can_id_hex: '0x100', frame_type: '标准帧', dlc: 8, data_hex: '64 32 0A 08 00 00 00 00', message_name: 'BMS_Status', period_ms: 50, status: '正常', source_session: '-', frame_count: 4210, last_seen_ms: 20 },
  { timestamp: '10:26:35.115.432', channel: 'CAN2', direction: 'RX', can_id: 0x101, can_id_hex: '0x101', frame_type: '标准帧', dlc: 8, data_hex: 'B8 0E 00 64 00 00 00 00', message_name: 'BMS_Capacity_Status', period_ms: 100, status: '正常', source_session: '-', frame_count: 3966, last_seen_ms: 28 },
  { timestamp: '10:26:35.113.291', channel: 'CAN2', direction: 'RX', can_id: 0x102, can_id_hex: '0x102', frame_type: '标准帧', dlc: 8, data_hex: '00 00 00 00 00 00 00 00', message_name: 'BMS_Protect_Status', period_ms: 100, status: '正常', source_session: '-', frame_count: 2432, last_seen_ms: 31 },
  { timestamp: '10:26:35.111.146', channel: 'CAN2', direction: 'RX', can_id: 0x103, can_id_hex: '0x103', frame_type: '标准帧', dlc: 8, data_hex: '1E 1F 20 21 22 23 24 25', message_name: 'BMS_NTC_Temperature', period_ms: 500, status: '正常', source_session: '-', frame_count: 2011, last_seen_ms: 36 },
  { timestamp: '10:26:35.109.275', channel: 'CAN1', direction: 'RX', can_id: 0x168, can_id_hex: '0x168', frame_type: '标准帧', dlc: 8, data_hex: '00 00 19 00 00 00 1A 00', message_name: 'Wheel_Speed_Status', period_ms: 20, status: '正常', source_session: '-', frame_count: 3201, last_seen_ms: 22 },
  { timestamp: '10:26:35.107.304', channel: 'CAN1', direction: 'RX', can_id: 0xE1, can_id_hex: '0xE1', frame_type: '标准帧', dlc: 8, data_hex: 'F3 01 00 00 00 00 00 00', message_name: 'Steering_Angle_Status', period_ms: 20, status: '正常', source_session: '-', frame_count: 1756, last_seen_ms: 26 },
  { timestamp: '10:26:35.105.812', channel: 'CAN2', direction: 'RX', can_id: 0x703, can_id_hex: '0x703', frame_type: '标准帧', dlc: 1, data_hex: '7E', message_name: 'Motor_Heartbeat', period_ms: 100, status: '正常', source_session: '-', frame_count: 1283, last_seen_ms: 42 },
  { timestamp: '10:26:35.103.812', channel: 'CAN2', direction: 'RX', can_id: 0x704, can_id_hex: '0x704', frame_type: '标准帧', dlc: 1, data_hex: '7E', message_name: 'Motor_Heartbeat', period_ms: 100, status: '正常', source_session: '-', frame_count: 1260, last_seen_ms: 45 },
]

const signal121: CanDecodedSignal[] = [
  { name: 'SCU_Target_Speed', start_bit: 0, length: 16, type: 'uint16', raw: '0x0320', raw_value: 800, physical_value: 80.0, unit: 'km/h', enum: '-', remark: '0.1 km/h' },
  { name: 'SCU_Steering_Angle_Front', start_bit: 16, length: 8, type: 'int8', raw: '0xFF', raw_value: -1, physical_value: -1.0, unit: 'deg', enum: '-', remark: 'int8 有符号' },
  { name: 'SCU_Steering_Angle_Rear', start_bit: 24, length: 8, type: 'int8', raw: '0x00', raw_value: 0, physical_value: 0.0, unit: 'deg', enum: '-', remark: 'int8 有符号' },
  { name: 'Gear_Request', start_bit: 32, length: 4, type: 'uint4', raw: '0x1', raw_value: 1, physical_value: 1, unit: '-', enum: 'P:R:N:D', remark: '挡位请求' },
  { name: 'Drive_Mode', start_bit: 36, length: 4, type: 'uint4', raw: '0x0', raw_value: 0, physical_value: 0, unit: '-', enum: '0:Eco 1:Std 2:Sport', remark: '驱动模式' },
  { name: 'Brake_Enable', start_bit: 40, length: 1, type: 'bool', raw: '0x1', raw_value: 1, physical_value: true, unit: '-', enum: '0:False 1:True', remark: '制动使能' },
]

const warningNames = ['BMS_SOC_Warning', 'MCU_Disconnect_Warning', 'MCU_Motor_Warning', 'MCU_Speed_Warning', 'Steering_Disconnect_Warning', 'Steering_Lock_Warning', 'Steering_Uncontrollable_Warning', 'Steering_Error_Warning', 'Brake_Error_Warning']
const signal77: CanDecodedSignal[] = warningNames.map((name, index) => ({ name, start_bit: index * 2, length: 2, type: 'uint2', raw: '0x0', raw_value: 0, physical_value: 0, unit: '-', enum: '0 Normal / 1 Warning / 2 Derating / 3 Fault', remark: 'Normal' }))
const protectNames = ['BMS_OverVoltage', 'BMS_UnderVoltage', 'BMS_OverCurrent', 'BMS_OverTemperature', 'BMS_InsulationFault', 'BMS_PrechargeTimeout', 'BMS_RelayAdhesion', 'BMS_SOCTooLow']
const signal102: CanDecodedSignal[] = protectNames.map((name, index) => ({ name, start_bit: index, length: 1, type: 'unsigned bool', raw: '0x0', raw_value: 0, physical_value: '未触发', unit: '-', enum: '0 未触发 / 1 触发', remark: '保护位' }))

export const fallbackCanDecoded: Record<string, CanDecodedFrame> = {
  '0x121': { frame: fallbackCanLatestFrames[0], signals: signal121, dbc_status: 'decoded' },
  '0x77': { frame: fallbackCanLatestFrames[2], signals: signal77, dbc_status: 'decoded' },
  '0x100': { frame: fallbackCanLatestFrames[3], signals: [
    { name: 'BMS_Voltage', start_bit: 0, length: 16, type: 'uint16', raw: '0x6432', raw_value: 25650, physical_value: 2565.0, unit: 'V', enum: '-', remark: 'raw x 0.1' },
    { name: 'BMS_Current', start_bit: 16, length: 16, type: 'int16', raw: '0x0A08', raw_value: 2568, physical_value: 256.8, unit: 'A', enum: '-', remark: 'raw x 0.1' },
    { name: 'BMS_SOC', start_bit: 32, length: 8, type: 'uint8', raw: '0x00', raw_value: 0, physical_value: 86, unit: '%', enum: '-', remark: 'SOC' },
    { name: 'CRC', start_bit: 56, length: 8, type: 'uint8', raw: '0x00', raw_value: 0, physical_value: 0, unit: '-', enum: '-', remark: '校验' },
  ], dbc_status: 'decoded' },
  '0x102': { frame: fallbackCanLatestFrames[5], signals: signal102, dbc_status: 'decoded' },
  '0x168': { frame: fallbackCanLatestFrames[7], signals: [
    { name: 'Wheel_Speed_FL', start_bit: 0, length: 16, type: 'uint16', raw: '0x0000', raw_value: 0, physical_value: 0.0, unit: 'km/h', enum: '-', remark: '左前轮速' },
    { name: 'Wheel_Speed_FR', start_bit: 16, length: 16, type: 'uint16', raw: '0x1900', raw_value: 6400, physical_value: 25.0, unit: 'km/h', enum: '-', remark: '右前轮速' },
    { name: 'Wheel_Speed_RL', start_bit: 32, length: 16, type: 'uint16', raw: '0x0000', raw_value: 0, physical_value: 0.0, unit: 'km/h', enum: '-', remark: '左后轮速' },
    { name: 'Wheel_Speed_RR', start_bit: 48, length: 16, type: 'uint16', raw: '0x1A00', raw_value: 6656, physical_value: 26.0, unit: 'km/h', enum: '-', remark: '右后轮速' },
  ], dbc_status: 'decoded' },
  '0xE1': { frame: fallbackCanLatestFrames[8], signals: [
    { name: 'Steering_Angle_Front', start_bit: 0, length: 16, type: 'int16', raw: '0xF301', raw_value: -3327, physical_value: -332.7, unit: 'deg', enum: '-', remark: '前转角反馈' },
    { name: 'Steering_Angle_Rear', start_bit: 16, length: 16, type: 'int16', raw: '0x0000', raw_value: 0, physical_value: 0.0, unit: 'deg', enum: '-', remark: '后转角反馈' },
  ], dbc_status: 'decoded' },
}

export const fallbackCanMonitorStatistics: CanMonitorStatistics = {
  can_id_distribution: [
    { can_id_hex: '0x121', count: 4872, percent: 14.2 },
    { can_id_hex: '0x100', count: 4210, percent: 12.3 },
    { can_id_hex: '0x101', count: 3966, percent: 11.6 },
    { can_id_hex: '0x51', count: 3812, percent: 11.1 },
    { can_id_hex: '0x168', count: 3201, percent: 9.4 },
    { can_id_hex: '0x77', count: 2988, percent: 8.7 },
    { can_id_hex: '0x102', count: 2432, percent: 7.1 },
    { can_id_hex: '0x103', count: 2011, percent: 5.9 },
    { can_id_hex: '0xE1', count: 1756, percent: 5.1 },
    { can_id_hex: '0x703', count: 1283, percent: 3.7 },
  ],
  fps_trend: [
    { time: '10:21:35', can1: 720, can2: 560 },
    { time: '10:22:35', can1: 780, can2: 590 },
    { time: '10:23:35', can1: 735, can2: 575 },
    { time: '10:24:35', can1: 770, can2: 600 },
    { time: '10:25:35', can1: 745, can2: 582 },
    { time: '10:26:35', can1: 790, can2: 610 },
  ],
  period_jitter: [
    { time: '10:21:35', id_121: 4.2, id_51: 1.2, id_100: -3.5 },
    { time: '10:22:35', id_121: 5.1, id_51: 0.8, id_100: -4.2 },
    { time: '10:23:35', id_121: 3.8, id_51: 1.6, id_100: -2.8 },
    { time: '10:24:35', id_121: 4.9, id_51: 1.1, id_100: -3.9 },
    { time: '10:25:35', id_121: 3.6, id_51: 1.4, id_100: -4.6 },
    { time: '10:26:35', id_121: 5.4, id_51: 0.9, id_100: -3.2 },
  ],
  error_summary: { timeout_count: 23, error_frame_count: 4, protocol_error_count: 1 },
  history_files: [
    { file_id: 'raw_can_20260401_102015', file_name: 'raw_can_20260401_102015.bin', session_id: 'S20260401-001', started_at: '10:20:15', size: '122 MB' },
    { file_id: 'raw_can_20260401_095430', file_name: 'raw_can_20260401_095430.bin', session_id: 'S20260401-002', started_at: '09:54:30', size: '118 MB' },
    { file_id: 'raw_can_20260401_083012', file_name: 'raw_can_20260401_083012.bin', session_id: 'S20260401-003', started_at: '08:30:12', size: '97 MB' },
    { file_id: 'raw_can_20260331_171512', file_name: 'raw_can_20260331_171512.bin', session_id: 'S20260331-001', started_at: '17:15:12', size: '104 MB' },
    { file_id: 'raw_can_20260331_153045', file_name: 'raw_can_20260331_153045.bin', session_id: 'S20260331-002', started_at: '15:30:45', size: '91 MB' },
  ],
  footer_status: { recording: true, uptime: '02:15:48', buffer_usage: 26, rx_fps: 1284, tx_fps: 162 },
}

export const fallbackSignalDashboard: SignalDashboardSummary = {
  status: {
    overall: 'normal',
    updated_at: '2026-04-01 10:26:35.123',
    mock: true,
  },
  bms: {
    status: '正常',
    total_voltage: 76.8,
    current: -12.5,
    soc: 86,
    ntc_temperature: 31,
    cell_max_voltage: 3.228,
    cell_min_voltage: 3.210,
    cell_delta_mv: 18,
    charge_discharge_state: '放电',
    trend: {
      voltage: [76.2, 76.5, 76.3, 76.8, 76.6, 76.9, 76.7, 76.8],
      current: [-10.2, -11.5, -12.1, -12.5, -11.8, -12.4, -12.0, -12.5],
      soc: [85, 85, 85.5, 86, 86, 86.1, 86, 86],
      ntc: [30, 31, 31, 31, 30.8, 31.2, 31, 31],
    },
  },
  vehicle: {
    status: '正常',
    gear: 'D',
    drive_mode: 'Remote',
    ignition: 'ON',
    parking: 'RELEASED',
    speed: 2.4,
  },
  wheel_speed: {
    status: '正常',
    unit: 'km/h',
    front_left: 2.5,
    front_right: 2.4,
    rear_left: 2.5,
    rear_right: 2.4,
  },
  steering: {
    status: '正常',
    front_cmd: 17.0,
    front_feedback: 16.8,
    rear_cmd: 0.0,
    rear_feedback: 0.0,
    front_trend: [15.8, 16.2, 16.8, 16.7, 16.9, 16.5, 16.8, 16.8],
    rear_trend: [0.0, 0.1, 0.0, 0.0, -0.1, 0.0, 0.0, 0.0],
  },
  motor: {
    status: '正常',
    speed_rpm: 620,
    phase_current_a: 14.2,
    heartbeat: '0x703 / 0x704',
    heartbeat_status: '正常',
    speed_trend: [580, 600, 615, 620, 612, 618, 622, 620],
    current_trend: [13.8, 14.0, 14.1, 14.2, 13.9, 14.3, 14.0, 14.2],
  },
  lights_brake: {
    left_turn: 'OFF',
    right_turn: 'OFF',
    position_light: 'ON',
    low_beam: 'OFF',
    brake_request: 'OFF',
  },
  alarm: {
    status: '正常',
    level: 0,
    label: 'Normal',
    thresholds: [
      { name: '总压阈值', status: '正常' },
      { name: '电流阈值', status: '正常' },
      { name: '温度阈值', status: '正常' },
      { name: '压差阈值', status: '正常' },
      { name: '转角阈值', status: '正常' },
    ],
  },
  watchlist: [
    { signal_name: 'BMS_总压', can_id: '0x180', channel: 'CAN1', value: 76.8, unit: 'V', threshold: '[60.0 ~ 84.0]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [76.2, 76.3, 76.5, 76.8] },
    { signal_name: 'BMS_电流', can_id: '0x180', channel: 'CAN1', value: -12.5, unit: 'A', threshold: '[-120.0 ~ 120.0]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [-10.2, -11.5, -12.1, -12.5] },
    { signal_name: 'BMS_SOC', can_id: '0x181', channel: 'CAN1', value: 86, unit: '%', threshold: '[10 ~ 100]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [85, 85, 86, 86] },
    { signal_name: 'VCU_车速', can_id: '0x200', channel: 'CAN2', value: 2.4, unit: 'km/h', threshold: '[0 ~ 40]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [2.0, 2.2, 2.3, 2.4] },
    { signal_name: 'WHL_FL_轮速', can_id: '0x280', channel: 'CAN2', value: 2.5, unit: 'km/h', threshold: '[0 ~ 80]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [2.2, 2.5, 2.4, 2.5] },
    { signal_name: 'STEER_前转角反馈', can_id: '0x300', channel: 'CAN1', value: 16.8, unit: '°', threshold: '[-45.0 ~ 45.0]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [15.8, 16.2, 16.8, 16.7] },
    { signal_name: 'MCU_相电流', can_id: '0x400', channel: 'CAN2', value: 14.2, unit: 'A', threshold: '[0 ~ 200]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [13.8, 14.0, 14.1, 14.2] },
    { signal_name: 'BMS_单体压差', can_id: '0x182', channel: 'CAN1', value: 18, unit: 'mV', threshold: '[0 ~ 50]', quality: '100%', updated_at: '2026-04-01 10:26:35.123', trend: [14, 16, 18, 18] },
  ],
}

const curveTimes = ['10:21:35', '10:22:00', '10:22:35', '10:23:00', '10:23:35', '10:24:00', '10:24:35', '10:25:00', '10:25:35', '10:26:00', '10:26:35']

export const fallbackCurveConfig: CurveConfig = {
  groups: [
    { key: 'speed', label: '速度', count: 6 },
    { key: 'wheel', label: '轮速', count: 4 },
    { key: 'steering', label: '转向', count: 8 },
    { key: 'bms', label: 'BMS', count: 12 },
    { key: 'motor', label: '电机', count: 10 },
    { key: 'alarm', label: '告警', count: 7 },
    { key: 'custom', label: '自定义', count: 0 },
  ],
  signals: [
    { name: 'SCU_Target_Speed', can_id: '0x121', unit: 'km/h', color: '#21C55D', current_value: 30.0, selected: true },
    { name: 'Vehicle_Speed', can_id: '0x051', unit: 'km/h', color: '#2F80FF', current_value: 29.7, selected: true },
    { name: 'FL_Wheel_Speed', can_id: '0x168', unit: 'km/h', color: '#F97316', current_value: 29.6, selected: true },
    { name: 'FR_Wheel_Speed', can_id: '0x169', unit: 'km/h', color: '#D946EF', current_value: 29.8, selected: true },
    { name: 'RL_Wheel_Speed', can_id: '0x16A', unit: 'km/h', color: '#06B6D4', current_value: 29.5, selected: true },
    { name: 'RR_Wheel_Speed', can_id: '0x16B', unit: 'km/h', color: '#FACC15', current_value: 29.4, selected: true },
    { name: 'Front_Steer_Cmd', can_id: '0x121', unit: 'deg', color: '#EC4899', current_value: -2.3, selected: true },
    { name: 'Front_Steer_Fdbk', can_id: '0xE1', unit: 'deg', color: '#2F80FF', current_value: -2.1, selected: true },
    { name: 'Rear_Steer_Cmd', can_id: '0x121', unit: 'deg', color: '#F97316', current_value: -0.6, selected: true },
    { name: 'Rear_Steer_Fdbk', can_id: '0xE1', unit: 'deg', color: '#21C55D', current_value: -0.5, selected: true },
    { name: 'BMS_Total_Voltage', can_id: '0x100', unit: 'V', color: '#FACC15', current_value: 605.2, selected: true },
    { name: 'BMS_Current', can_id: '0x100', unit: 'A', color: '#C084FC', current_value: -15.6, selected: true },
    { name: 'SOC', can_id: '0x100', unit: '%', color: '#22D3EE', current_value: 78.6, selected: true },
    { name: 'Motor_Speed', can_id: '0x181', unit: 'rpm', color: '#F97316', current_value: 1450, selected: true },
    { name: 'Motor_Current_A', can_id: '0x181', unit: 'A', color: '#2F80FF', current_value: 28.4, selected: true },
  ],
  default_window: '5分钟',
  default_sample_rate: '100 Hz',
  default_downsample: '平均值',
  default_playback_speed: '1.0x',
}

export const fallbackCurveTimeseries: CurveTimeseries = {
  mode: 'live',
  updated_at: '2026-04-01 10:26:35.123',
  charts: {
    speed_vs_vehicle: {
      x_axis: curveTimes,
      series: [
        { name: 'SCU_Target_Speed', unit: 'km/h', color: '#21C55D', data: [0, 6, 22, 30, 30, 30, 30, 30, 30, 12, 6] },
        { name: 'Vehicle_Speed', unit: 'km/h', color: '#2F80FF', data: [0, 4, 18, 27, 28.5, 29.1, 29.3, 29.4, 29.1, 16, 8] },
      ],
    },
    speed_vs_wheels: {
      x_axis: curveTimes,
      series: [
        { name: 'SCU_Target_Speed', unit: 'km/h', color: '#21C55D', data: [0, 6, 22, 30, 30, 30, 30, 30, 30, 12, 6] },
        { name: 'FL_Wheel_Speed', unit: 'km/h', color: '#F97316', data: [0, 5, 20, 28, 28.9, 29.6, 29.7, 29.5, 29.4, 14, 7] },
        { name: 'FR_Wheel_Speed', unit: 'km/h', color: '#D946EF', data: [0, 4, 19, 27, 29.0, 29.8, 29.4, 29.2, 29.5, 13, 6] },
        { name: 'RL_Wheel_Speed', unit: 'km/h', color: '#06B6D4', data: [0, 5, 21, 28, 28.7, 29.5, 29.3, 29.0, 29.2, 13, 7] },
        { name: 'RR_Wheel_Speed', unit: 'km/h', color: '#FACC15', data: [0, 4, 20, 28, 28.6, 29.4, 29.2, 29.0, 29.1, 12, 6] },
      ],
    },
    steering: {
      x_axis: curveTimes,
      series: [
        { name: 'Front_Steer_Cmd', unit: 'deg', color: '#EC4899', data: [0, 2, 13, 16, 3, -5, -2, -1, -2, -2.3, -2.3] },
        { name: 'Front_Steer_Fdbk', unit: 'deg', color: '#2F80FF', data: [0, 1, 10, 14, 2, -4, -1, -1, -1.8, -2.1, -2.1] },
        { name: 'Rear_Steer_Cmd', unit: 'deg', color: '#F97316', data: [0, 1, 6, 8, 4, -6, -2, -1, -0.8, -0.6, -0.6] },
        { name: 'Rear_Steer_Fdbk', unit: 'deg', color: '#21C55D', data: [0, 0.5, 5, 7, 3, -5, -1.5, -1, -0.6, -0.5, -0.5] },
      ],
    },
    bms: {
      x_axis: curveTimes,
      series: [
        { name: 'BMS_Total_Voltage', unit: 'V', color: '#FACC15', data: [606, 605.8, 605.4, 605.3, 605.2, 605.5, 605.2, 604.9, 605.1, 605.0, 605.2], y_axis: 0 },
        { name: 'BMS_Current', unit: 'A', color: '#C084FC', data: [-8, -12, -18, -16, -15, -14, -17, -16, -15, -30, -15.6], y_axis: 0 },
        { name: 'SOC', unit: '%', color: '#22D3EE', data: [78.9, 78.8, 78.7, 78.7, 78.6, 78.6, 78.6, 78.6, 78.6, 78.6, 78.6], y_axis: 1 },
      ],
    },
    motor: {
      x_axis: curveTimes,
      series: [
        { name: 'Motor_Speed', unit: 'rpm', color: '#F97316', data: [0, 120, 950, 1600, 1900, 2100, 2050, 1980, 1900, 900, 120], y_axis: 0 },
        { name: 'Motor_Current_A', unit: 'A', color: '#2F80FF', data: [0, 18, 80, 42, 36, 30, 29, 28, 27, 18, 28.4], y_axis: 1 },
      ],
    },
    alarm_timeline: {
      x_axis: curveTimes,
      series: [
        { name: '正常', unit: 'level', color: '#21C55D', data: [0, 0, 0, 0, NaN, NaN, NaN, NaN, NaN, 0, 0] },
        { name: '提示', unit: 'level', color: '#2F80FF', data: [NaN, NaN, 1, 1, 1, NaN, NaN, NaN, NaN, NaN, NaN] },
        { name: '次要', unit: 'level', color: '#FACC15', data: [NaN, NaN, NaN, NaN, 2, 2, 2, NaN, NaN, NaN, NaN] },
        { name: '主要', unit: 'level', color: '#F97316', data: [NaN, NaN, NaN, NaN, NaN, NaN, NaN, 3, 3, 3, NaN] },
        { name: '严重', unit: 'level', color: '#EF4444', data: [NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN, NaN] },
      ],
    },
  },
}

export const fallbackReplayMetadata: ReplayMetadata = {
  session_id: 'EOL-20260401-0001',
  data_source: '本地存储',
  timezone: 'UTC+08:00',
  start_time: '2026-04-01 09:56:13.000',
  end_time: '2026-04-01 10:26:13.000',
  duration: '00:30:00',
  current: '00:16:42',
  progress_percent: 56,
}

export const fallbackFaultEvents: FaultEvent[] = [
  { id: 'fault-001', label: 'FAIL 前 5s', time: '2026-04-01 10:23:10.000' },
]

export const fallbackManualCommand: ManualControlCommand = {
  gear: 'D',
  drive_mode: 'Remote',
  target_speed: 2.0,
  front_steer: 12,
  rear_steer: 0,
  brake_enable: true,
  left_turn: false,
  right_turn: false,
  position_light: true,
  low_beam: true,
  control_mode: 'speed',
}

export const fallbackManualStatus: ManualControlStatus = {
  can_send_allowed: false,
  control_message: '0x121',
  period_ms: 20,
  control_channel: 'CAN2',
  periodic_running: false,
  last_tx_time: '',
  tx_fail_count: 0,
  emergency_stop: false,
  safe_stop_active: false,
}

export const fallbackManualInterlock: ManualInterlockStatus = {
  overall: 'block',
  items: [
    { key: 'key_frames_online', label: '关键报文在线', status: 'fail', value: '后端离线 / Mock，不允许发送' },
    { key: 'no_severe_alarm', label: '无严重告警', status: 'pass', value: '正常' },
    { key: 'speed_limit', label: '速度上限', status: 'pass', value: '≤ 8.0 km/h' },
    { key: 'steering_limit', label: '转角限幅', status: 'pass', value: '≤ ±120°' },
    { key: 'emergency_stop', label: '急停', status: 'pass', value: '未触发' },
    { key: 'watchdog', label: '看门狗', status: 'pass', value: 'OK (120 ms)' },
    { key: 'control_channel', label: '控制通道', status: 'warning', value: 'CAN2 延时 18ms' },
  ],
  reasons: ['后端离线或身份未认证，控制保守禁止'],
}

export const fallbackManualPreview: ManualPreview = {
  can_id: '0x121',
  bytes_hex: ['81', '0C', '00', '14', '02', '40', '01', '04'],
  bytes_dec: [129, 12, 0, 20, 2, 64, 1, 4],
  field_notes: [
    'Byte0: gear=D, drive_mode=Remote',
    'Byte1: front steering +12 -> 0x0C (int8 two\'s complement)',
    'Byte2: rear steering 0 -> 0x00 (int8 two\'s complement)',
    'Byte3~4: target speed raw=20, 20 x 0.1 = 2.0 km/h; brake=1',
  ],
  data_hex: '81 0C 00 14 02 40 01 04',
  data: [129, 12, 0, 20, 2, 64, 1, 4],
}

export const fallbackManualFeedback: ManualFeedback = {
  gear: 'D',
  vehicle_speed: 2.0,
  front_steer_feedback: 11,
  rear_steer_feedback: 0,
  wheel_speeds: '2.1 / 2.0 / 2.0 / 2.1 km/h',
  light_feedback: '位置灯, 近光灯',
  brake_status: '未制动',
  alarm_status: '无告警',
}

export const fallbackManualCurves: ManualCurves = {
  speed: {
    x_axis: ['10:20:35', '10:20:55', '10:21:15', '10:21:35', '10:21:55', '10:22:15', '10:22:35'],
    target_speed: [2.0, 1.8, 2.0, 2.1, 1.9, 2.0, 2.0],
    feedback_speed: [1.6, 1.5, 1.8, 1.9, 1.7, 1.9, 2.0],
  },
  steering: {
    x_axis: ['10:20:35', '10:20:55', '10:21:15', '10:21:35', '10:21:55', '10:22:15', '10:22:35'],
    front_cmd: [0, 0, 12, 12, 12, 0, 0],
    front_feedback: [0, 0, 8, 11, 11, 3, 0],
    rear_cmd: [0, 0, 0, 0, 0, 0, 0],
    rear_feedback: [0, 0, -1, 0, 0, 0, 0],
  },
}

export const fallbackAutoTestDashboard: AutoTestDashboard = {
  session: {
    session_id: '',
    chassis_no: '-',
    vin: '',
    serial_no: '',
    operator: '-',
    station_id: '-',
    vehicle_series: '',
    work_order_id: '',
    test_plan: '未加载',
    remark: '',
    overall_status: 'WAIT',
    elapsed: '00:00:00',
    remaining: '00:00:00',
    completed: 0,
    passed: 0,
    failed: 0,
    waiting: 12,
    total: 12,
    current_step_index: 0,
    current_step_key: '',
    current_step_name: '等待开始',
  },
  runtime_profile: 'mock',
  mock_session_allowed: true,
  steps: [
    { index: 1, name: '上电自检', status: 'PASS' },
    { index: 2, name: 'CAN通信检测', status: 'PASS' },
    { index: 3, name: 'BMS检测', status: 'RUNNING' },
    { index: 4, name: 'VCU状态检测', status: 'WAIT' },
    { index: 5, name: '电机心跳检测', status: 'WAIT' },
    { index: 6, name: '档位检测', status: 'WAIT' },
    { index: 7, name: '低速驱动检测', status: 'WAIT' },
    { index: 8, name: '转向检测', status: 'WAIT' },
    { index: 9, name: '灯光检测', status: 'WAIT' },
    { index: 10, name: '制动停止检测', status: 'WAIT' },
    { index: 11, name: '告警复查', status: 'WAIT' },
    { index: 12, name: '报告生成', status: 'WAIT' },
  ],
  current_step: {
    title: 'BMS检测',
    description: '读取BMS关键状态，校验电池总压、SOC、温度等参数，并确认无保护告警。',
    command: '0x7DF → 0x102：22 01 00',
    period_ms: 500,
    timeout_ms: 2000,
  },
  measurements: [
    { name: 'BMS总压', value: 329.6, unit: 'V' },
    { name: 'SOC', value: 56.8, unit: '%' },
    { name: '电池温度(均值)', value: 28.6, unit: '°C' },
    { name: '电池电流', value: -1.2, unit: 'A' },
    { name: '单体最高温', value: 31.2, unit: '°C' },
    { name: '单体最低温', value: 26.1, unit: '°C' },
    { name: '保护状态(0x102)', value: '未触发', unit: '' },
  ],
  assertions: [
    { description: 'BMS总压 在范围内', signal: 'BMS_TotVolt', threshold: '280 ~ 360 V', value: '329.6 V', result: 'PASS', fail_reason: '-' },
    { description: 'SOC >= 30%', signal: 'BMS_SOC', threshold: '>= 30%', value: '56.8%', result: 'PASS', fail_reason: '-' },
    { description: '电池温度 在范围内', signal: 'BMS_Temp_Avg', threshold: '-10 ~ 60°C', value: '28.6°C', result: 'PASS', fail_reason: '-' },
    { description: '0x102 保护未触发', signal: 'BMS_ProtState', threshold: '未触发', value: '未触发', result: 'PASS', fail_reason: '-' },
  ],
  step_logs: [
    { time: '10:20:58', step: '1 上电自检', action: '发送上电检测请求', can_command: '0x7DF 22 01 00', feedback: '0x7E8 62 01 00', status: 'PASS' },
    { time: '10:21:15', step: '1 上电自检', action: '读取VCU版本', can_command: '0x7DF 22 F1 90', feedback: '0x7E8 62 F1 90', status: 'PASS' },
    { time: '10:21:33', step: '1 上电自检', action: '读取BMS版本', can_command: '0x7DF 22 F1 91', feedback: '0x7E8 62 F1 91', status: 'PASS' },
    { time: '10:22:05', step: '2 CAN通信检测', action: '周期连通性检测', can_command: '0x7DF 3E 00', feedback: '0x7E8 7E 00', status: 'PASS' },
    { time: '10:22:47', step: '2 CAN通信检测', action: '多节点心跳检测', can_command: '---', feedback: '---', status: 'PASS' },
    { time: '10:23:03', step: '3 BMS检测', action: '读取BMS关键状态', can_command: '0x7DF 22 01 00', feedback: '0x7E8 62 01 00', status: 'RUNNING' },
  ],
  charts: {
    realtime: {
      x_axis: ['09:56', '10:01', '10:06', '10:11', '10:16', '10:21', '10:26'],
      series: [
        { name: '车速(km/h)', data: [0, 0.5, 1.2, 1.8, 2.0, 2.1, 2.0] },
        { name: '转向角(°)', data: [0, 5, 12, 16, 14, 10, 8] },
        { name: 'BMS总压(V)', data: [329, 329.2, 329.4, 329.6, 329.5, 329.6, 329.6] },
        { name: '告警级别', data: [0, 0, 0, 0, 0, 0, 0] },
      ],
    },
  },
  stats: {
    pass_rate: 100,
    passed: 2,
    failed: 0,
    waiting: 10,
    total_elapsed: '00:05:32',
    avg_step_duration: '00:02:46',
  },
}

export const fallbackAlarmDiagnosisDashboard: AlarmDiagnosisDashboard = {
  summary: {
    max_level: 0,
    max_label: 'Normal',
    current_count: 0,
    severe_locked: false,
    recommendation: '无处理中告警',
  },
  warning_matrix_0x77: [
    { key: 'BMS_SOC', label: 'BMS_SOC', value: 0, status: 'Normal' },
    { key: 'MCU_Disconnect', label: 'MCU掉线', value: 0, status: 'Normal' },
    { key: 'MCU_Motor', label: '电机告警', value: 0, status: 'Normal' },
    { key: 'MCU_Speed', label: '超速', value: 0, status: 'Normal' },
    { key: 'Steering_Disconnect', label: '转向掉线', value: 0, status: 'Normal' },
    { key: 'Steering_Lock', label: '转向卡死', value: 0, status: 'Normal' },
    { key: 'Steering_Uncontrollable', label: '转向失控', value: 0, status: 'Normal' },
    { key: 'Steering_Error', label: '角度故障', value: 0, status: 'Normal' },
    { key: 'Brake_Error', label: '刹车故障', value: 0, status: 'Normal' },
  ],
  bms_protect_0x102: {
    items: [
      { key: 'short_circuit', label: '短路', triggered: false },
      { key: 'over_current', label: '过流', triggered: false },
      { key: 'over_temp', label: '过温', triggered: false },
      { key: 'under_temp', label: '欠温', triggered: false },
      { key: 'over_voltage', label: '过压', triggered: false },
      { key: 'under_voltage', label: '欠压', triggered: false },
      { key: 'mos_status', label: 'MOS状态', status: '正常' },
      { key: 'precharge_status', label: '预充状态', status: '正常' },
    ],
    bitmap_bits: Array.from({ length: 16 }, () => 0),
    bit_order: 'High -> Low',
  },
  diagnosis_suggestions: [
    { check_item: 'BMS 与通信链路', suggestion: '检查 CAN1 连接与供电', allow_override: false, priority: '高' },
    { check_item: 'BMS 保护状态', suggestion: '确认 0x102 所有保护未触发', allow_override: false, priority: '高' },
    { check_item: 'MCU 掉线', suggestion: '检查 MCU 心跳与供电', allow_override: false, priority: '高' },
    { check_item: '电机系统', suggestion: '检查电机与逆变器状态', allow_override: false, priority: '中' },
    { check_item: '转向系统', suggestion: '检查转向通信与角度信号', allow_override: false, priority: '中' },
    { check_item: '刹车系统', suggestion: '检查制动执行与反馈信号', allow_override: false, priority: '中' },
    { check_item: '超速（速度源）', suggestion: '校验速度传感器与标定', allow_override: false, priority: '低' },
  ],
  history: [
    { id: 'ALM-001', time: '2026-04-01 10:15:22.123', channel: 'CAN1', can_id: '0x77', signal: 'MCU掉线', level: '1 (Warning)', status: '恢复 (10:15:25.187)', suggestion: '检查 CAN1 与 MCU 供电/心跳', related_step: '步骤: 02-CAN通信自检', released: false },
    { id: 'ALM-002', time: '2026-04-01 10:12:47.663', channel: 'CAN1', can_id: '0x77', signal: 'BMS_SOC', level: '1 (Warning)', status: '恢复 (10:12:55.021)', suggestion: '确认 SOC 来源与有效区间', related_step: '步骤: 03-BMS检查', released: false },
    { id: 'ALM-003', time: '2026-04-01 10:08:31.558', channel: 'CAN1', can_id: '0x77', signal: '超速', level: '2 (Fault)', status: '恢复 (10:08:33.914)', suggestion: '校验速度传感器与限速参数', related_step: '步骤: 04-速度校验', released: false },
    { id: 'ALM-004', time: '2026-04-01 09:58:13.447', channel: 'CAN1', can_id: '0x102', signal: '过温', level: '1 (Warning)', status: '恢复 (09:58:20.301)', suggestion: '检查电池温度传感器与散热', related_step: '步骤: 05-BMS保护', released: false },
    { id: 'ALM-005', time: '2026-04-01 09:36:58.912', channel: 'CAN1', can_id: '0x102', signal: '欠压', level: '2 (Fault)', status: '恢复 (09:37:05.772)', suggestion: '检查电池电压与预充状态', related_step: '步骤: 05-BMS保护', released: false },
  ],
  charts: {
    level_timeline: {
      x_axis: ['09:56', '10:01', '10:06', '10:11', '10:16', '10:21', '10:26'],
      series: [
        { name: '0 Normal', data: [0, 0, 0, 0, 0, 0, 0] },
        { name: '1 Warning', data: [0, 0, 1, 0, 0, 1, 0] },
        { name: '2 Fault', data: [0, 0, 0, 2, 0, 0, 0] },
        { name: '3 Critical', data: [0, 0, 0, 0, 0, 0, 0] },
      ],
    },
    category_distribution: [
      { name: 'Normal', value: 156, percent: 83.9 },
      { name: 'Warning', value: 22, percent: 11.8 },
      { name: 'Fault', value: 8, percent: 4.3 },
      { name: 'Critical', value: 0, percent: 0.0 },
    ],
  },
  updated_at: '2026-04-01 10:26:35.123',
  mock: true,
}

export const fallbackReportManagementDashboard: ReportManagementDashboard = {
  directory: {
    path: '<data_root>\\reports',
    total_gb: 931.5,
    used_gb: 286.7,
    free_gb: 644.8,
    used_percent: 30.8,
    last_scan_time: '2026-04-01 10:25:12',
    scan_status: '扫描完成',
    file_type_stats: [
      { type: '.docx', count: 1256, percent: 28.6 },
      { type: '.pdf', count: 1842, percent: 41.9 },
      { type: '.json', count: 684, percent: 15.6 },
      { type: '.csv', count: 327, percent: 7.4 },
      { type: '.log / .bin', count: 289, percent: 6.5 },
    ],
  },
  reports: [
    { report_id: 'RPT-20260401-0001', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', test_time: '2026-04-01 10:15:22', result: 'PASS', operator: 'op01', type: '.docx', size: '1.24 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0001.docx', generation_status: '完成' },
    { report_id: 'RPT-20260401-0002', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', test_time: '2026-04-01 10:15:22', result: 'PASS', operator: 'op01', type: '.pdf', size: '2.87 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0002.pdf', generation_status: '完成' },
    { report_id: 'RPT-20260401-0003', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', test_time: '2026-04-01 10:15:22', result: 'PASS', operator: 'op01', type: '.json', size: '512.46 KB', path: '<data_root>\\reports\\202604\\RPT-20260401-0003.json', generation_status: '完成' },
    { report_id: 'RPT-20260401-0004', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', test_time: '2026-04-01 10:15:22', result: 'PASS', operator: 'op01', type: '.csv', size: '1.07 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0004.csv', generation_status: '完成' },
    { report_id: 'RPT-20260401-0005', chassis_no: 'YL-JD-002', vin: 'L0000000000000002', test_time: '2026-04-01 09:58:13', result: 'PASS', operator: 'op01', type: '.docx', size: '1.19 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0005.docx', generation_status: '完成' },
    { report_id: 'RPT-20260401-0006', chassis_no: 'YL-JD-002', vin: 'L0000000000000002', test_time: '2026-04-01 09:58:13', result: 'FAIL', operator: 'op01', type: '.pdf', size: '2.91 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0006.pdf', generation_status: '完成' },
    { report_id: 'RPT-20260401-0007', chassis_no: 'YL-JD-002', vin: 'L0000000000000002', test_time: '2026-04-01 09:58:13', result: 'FAIL', operator: 'op01', type: '.json', size: '520.14 KB', path: '<data_root>\\reports\\202604\\RPT-20260401-0007.json', generation_status: '完成' },
    { report_id: 'RPT-20260401-0008', chassis_no: 'YL-JD-003', vin: 'L0000000000000003', test_time: '2026-04-01 09:36:58', result: 'PASS', operator: 'op01', type: 'raw.log', size: '45.32 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0008.log', generation_status: '完成' },
    { report_id: 'RPT-20260401-0009', chassis_no: 'YL-JD-003', vin: 'L0000000000000003', test_time: '2026-04-01 09:36:58', result: 'PASS', operator: 'op01', type: 'decoded.csv', size: '3.21 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0009.csv', generation_status: '完成' },
    { report_id: 'RPT-20260401-0010', chassis_no: 'YL-JD-004', vin: 'L0000000000000004', test_time: '2026-04-01 09:22:11', result: 'FAIL', operator: 'op01', type: '.pdf', size: '2.65 MB', path: '<data_root>\\reports\\202604\\RPT-20260401-0010.pdf', generation_status: '完成' },
  ],
  selected_report: {
    report_id: 'RPT-20260401-0002',
    filename: 'RPT-20260401-0002.pdf',
    preview: { title: '低速无人车线控底盘检测报告', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', test_time: '2026-04-01 10:15:22', result: 'PASS', operator: 'op01', page: 1, total_pages: 12, zoom: 100 },
    json_summary: { report_id: 'RPT-20260401-0002', software_version: 'v1.0.2', dbc_version: 'Yunle_CAN_Integrated_CANdb', result: 'PASS' },
    csv_rows: [
      { signal: 'BMS_Total_Voltage', value: 329.6, unit: 'V', result: 'PASS' },
      { signal: 'BMS_SOC', value: 56.8, unit: '%', result: 'PASS' },
      { signal: 'Vehicle_Speed', value: 2.0, unit: 'km/h', result: 'PASS' },
    ],
  },
  related_data: {
    sessions: [
      { session_id: 'EOL-20260401-0001', started_at: '2026-04-01 10:12:47', ended_at: '2026-04-01 10:15:22', result: 'PASS', report_count: 4 },
      { session_id: 'EOL-20260401-0002', started_at: '2026-04-01 09:55:03', ended_at: '2026-04-01 09:58:13', result: 'FAIL', report_count: 4 },
      { session_id: 'EOL-20260401-0003', started_at: '2026-04-01 09:34:58', ended_at: '2026-04-01 09:36:58', result: 'PASS', report_count: 3 },
      { session_id: 'EOL-20260401-0004', started_at: '2026-04-01 09:20:11', ended_at: '2026-04-01 09:22:11', result: 'FAIL', report_count: 3 },
      { session_id: 'EOL-20260401-0005', started_at: '2026-04-01 09:05:30', ended_at: '2026-04-01 09:07:35', result: 'PASS', report_count: 3 },
    ],
  },
  charts: {
    storage_trend: [
      { date: '03-26', used: 260, free: 110 }, { date: '03-27', used: 258, free: 112 }, { date: '03-28', used: 270, free: 118 },
      { date: '03-29', used: 275, free: 120 }, { date: '03-30', used: 282, free: 126 }, { date: '03-31', used: 295, free: 132 }, { date: '04-01', used: 315, free: 140 },
    ],
    result_distribution: [
      { name: 'PASS', value: 3478, percent: 79.1 },
      { name: 'FAIL', value: 920, percent: 20.9 },
    ],
  },
  mock: true,
  updated_at: '2026-04-01 10:25:12',
}

export const fallbackHistoryDashboard: HistoryDashboard = {
  filters: { start_time: '2026-03-25 00:00', end_time: '2026-04-01 23:59', page: 1, page_size: 20 },
  summary: { total_tests: 1248, pass_rate: 94.4, fail_count: 68, alarm_count: 23, filtered_count: 128 },
  sessions: [
    { session_id: 'EOL-20260401-0001', chassis_no: 'YL-JD-001', vin: 'L0000000000000001', serial_no: 'SN-20260401-001', started_at: '2026-04-01 10:15:22', ended_at: '2026-04-01 10:26:47', result: 'PASS', failed_step: '-', operator: 'op01', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0001' },
    { session_id: 'EOL-20260401-0000', chassis_no: 'YL-JD-000', vin: 'L0000000000000000', serial_no: 'SN-20260401-000', started_at: '2026-04-01 09:58:13', ended_at: '2026-04-01 10:12:47', result: 'PASS', failed_step: '-', operator: 'op01', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0000' },
    { session_id: 'EOL-20260401-000-1', chassis_no: 'YL-JD-099', vin: 'L0000000000000099', serial_no: 'SN-20260401-099', started_at: '2026-04-01 09:40:35', ended_at: '2026-04-01 09:55:03', result: 'PASS', failed_step: '-', operator: 'op01', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0099' },
    { session_id: 'EOL-20260401-000-2', chassis_no: 'YL-JD-098', vin: 'L0000000000000098', serial_no: 'SN-20260401-098', started_at: '2026-04-01 09:22:11', ended_at: '2026-04-01 09:36:58', result: 'FAIL', failed_step: '低速驱动检测', operator: 'op01', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0098' },
    { session_id: 'EOL-20260401-000-3', chassis_no: 'YL-JD-097', vin: 'L0000000000000097', serial_no: 'SN-20260401-097', started_at: '2026-04-01 09:04:03', ended_at: '2026-04-01 09:18:20', result: 'PASS', failed_step: '-', operator: 'op02', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0097' },
    { session_id: 'EOL-20260401-000-4', chassis_no: 'YL-JD-096', vin: 'L0000000000000096', serial_no: 'SN-20260401-096', started_at: '2026-04-01 08:44:51', ended_at: '2026-04-01 08:59:27', result: 'PASS', failed_step: '-', operator: 'op02', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0096' },
    { session_id: 'EOL-20260401-000-5', chassis_no: 'YL-JD-095', vin: 'L0000000000000095', serial_no: 'SN-20260401-095', started_at: '2026-04-01 08:24:12', ended_at: '2026-04-01 08:38:49', result: 'PASS', failed_step: '-', operator: 'op01', station_id: 'EOL-STATION-01', report_id: 'RPT-20260401-0095' },
  ],
  selected_session: {
    session_id: 'EOL-20260401-0001', duration: '11分25秒', result: 'PASS',
    timeline: [
      { time: '10:15:22.123', title: '创建会话', description: '系统上电、电源、电压、温度自检', status: 'PASS', icon: 'power' },
      { time: '10:15:45.367', title: 'CAN通信检测', description: 'CAN1 / CAN2 连接与心跳检测', status: 'PASS', icon: 'network' },
      { time: '10:16:10.882', title: 'BMS检测', description: '电池状态、SOC、绝缘、继电器', status: 'PASS', icon: 'battery' },
      { time: '10:17:02.394', title: '档位检测', description: '档位状态与切换一致性', status: 'PASS', icon: 'settings' },
      { time: '10:18:15.561', title: '低速驱动检测', description: '电机响应、转速、相电流、限流', status: 'PASS', icon: 'gauge' },
      { time: '10:20:34.729', title: '转向检测', description: '转向角、角速度、助力状态', status: 'PASS', icon: 'steering' },
      { time: '10:22:18.441', title: '人工操作 - 制动踏板踩下（保持3s）', description: '操作员 op01', status: 'PASS', icon: 'user' },
      { time: '10:23:05.672', title: '告警记录', description: '记录 0 条告警，无活动告警', status: 'INFO', icon: 'alarm' },
      { time: '10:24:51.203', title: '报告生成', description: '生成检测报告与数据包', status: 'PASS', icon: 'report' },
    ],
    operator_logs: [
      { time: '10:15:20.983', user: 'op01', action: '开始检测会话', target: 'EOL-20260401-0001', params: '工位：EOL-STATION-01', result: '成功' },
      { time: '10:16:05.114', user: 'op01', action: '配置加载', target: 'DBC / 测试配置', params: 'Yunle_CAN_Integrated_CANdb', result: '成功' },
      { time: '10:18:12.447', user: 'op01', action: '手动操作', target: '制动踏板', params: '动作：踩下，保持：3s', result: '成功' },
      { time: '10:22:00.331', user: 'op01', action: '阈值调整', target: '低速驱动检测', params: '相电流上限：120 → 130 A', result: '成功' },
      { time: '10:24:51.210', user: 'op01', action: '报告保存', target: '检测报告', params: '路径：reports/EOL-20260401-0001', result: '成功' },
    ],
    downloads: [
      { key: 'raw_can', name: '原始 CAN 数据', extension: '.asc / .blf', size: '256.3 MB', available: true },
      { key: 'decoded_signals', name: '解析后信号数据', extension: '.csv', size: '48.7 MB', available: true },
      { key: 'report_bundle', name: '报告与数据包', extension: '.zip', size: '12.4 MB', available: true },
      { key: 'audit_log', name: '审计日志', extension: '.json', size: '1.2 MB', available: true },
      { key: 'curve_replay', name: '曲线回放包', extension: '.zip', size: '31.8 MB', available: true },
    ],
  },
  charts: {
    vehicle_result_trend: { vin: 'L0000000000000001', x_axis: ['03-25','03-26','03-27','03-28','03-29','03-30','03-31','04-01'], pass: [12,14,13,16,15,17,13,18], fail: [0,0,0,0,1,0,0,0] },
    failure_pareto: { categories: ['低速驱动检测','转向检测','档位检测','BMS检测','其他'], counts: [9,5,3,2,1], cumulative_percent: [45,70,85,95,100] },
  },
  pagination: { page: 1, page_size: 20, total: 128, total_pages: 7 },
  mock: true,
  updated_at: '2026-04-01 10:26:35',
}

export const fallbackPageData = {
  overview: {
    sessions: [
      { id: 'EOL-20260709-0031', chassis: 'YL-LSV-2026-0719', vin: 'L0000000000000719', start: '2026-07-09 09:18:00', result: 'RUNNING', operator: 'op01' },
      { id: 'EOL-20260709-0030', chassis: 'YL-LSV-2026-0718', vin: 'L0000000000000718', start: '2026-07-09 08:02:13', result: 'FAIL', operator: 'op02' },
      { id: 'EOL-20260708-0029', chassis: 'YL-LSV-2026-0717', vin: 'L0000000000000717', start: '2026-07-08 17:01:45', result: 'PASS', operator: 'op01' },
    ],
  },
  network: {
    channels: [
      { channel: 'CAN1', protocol: 'UDP', local: '127.0.0.1:8234', device: '127.0.0.1:12341', tx: '禁用', period: '-', status: 'online / monitor' },
      { channel: 'CAN2', protocol: 'UDP', local: '127.0.0.1:8235', device: '127.0.0.1:12342', tx: '0x121', period: '20 ms', status: 'online / control' },
    ],
  },
  canMonitor: {
    frames: [
      { time: '10:26:35.123', channel: 'CAN1', direction: 'RX', canId: '0x121', type: '标准帧', dlc: 8, data: '20 03 FF 00 01 01 00 7F', name: 'SCU_Control_Command', period: 50, status: '正常' },
      { time: '10:26:35.120', channel: 'CAN2', direction: 'RX', canId: '0x100', type: '标准帧', dlc: 8, data: '64 32 0A 08 00 00 00 00', name: 'BMS_Status', period: 100, status: '正常' },
      { time: '10:26:35.118', channel: 'CAN1', direction: 'RX', canId: '0x77', type: '标准帧', dlc: 8, data: '00 00 00 00 00 00 00 00', name: 'Alarm_Status', period: 100, status: '正常' },
    ],
    decodeRows: [
      { signal: 'SCU_Target_Speed', start: 0, type: 'uint16', raw: '0x0320', value: '80.0', unit: 'km/h', note: '0.1 km/h' },
      { signal: 'SCU_Steering_Angle_Front', start: 16, type: 'int8', raw: '0xFF', value: '-1.0', unit: 'deg', note: 'int8 有符号' },
      { signal: 'SCU_Steering_Angle_Rear', start: 24, type: 'int8', raw: '0x00', value: '0.0', unit: 'deg', note: 'int8 有符号' },
      { signal: 'Brake_Enable', start: 40, type: 'bool', raw: '0x1', value: 'True', unit: '-', note: '制动使能' },
    ],
  },
  signalDashboard: {
    lights: ['左转灯', '右转灯', '位置灯', '近光灯', '制动灯', '驻车灯'],
    signalRows: [
      { key: 'BMS_SOC', value: 86, unit: '%', quality: 'good', can_id: '0x100' },
      { key: 'Vehicle_Speed', value: 1.8, unit: 'km/h', quality: 'good', can_id: '0x168' },
      { key: 'SAS_Front_Angle', value: 11, unit: 'cmd', quality: 'good', can_id: '0xE1' },
    ],
  },
  realtimeCurve: {
    groups: [
      { name: '速度', count: 6, active: true },
      { name: '轮速', count: 4, active: false },
      { name: '转向', count: 8, active: true },
      { name: 'BMS', count: 12, active: false },
      { name: '电机', count: 10, active: false },
      { name: '告警', count: 7, active: true },
    ],
    signals: [
      { signal: 'Vehicle_Target_Speed', canId: '0x121', unit: 'km/h', current: '3.0', min: '0.0', max: '3.2', avg: '2.5', rate: '50Hz' },
      { signal: 'Vehicle_Speed', canId: '0x131', unit: 'km/h', current: '2.9', min: '0.0', max: '3.1', avg: '2.4', rate: '50Hz' },
      { signal: 'Front_Steer_Cmd', canId: '0x121', unit: 'raw', current: '20', min: '-18', max: '24', avg: '7', rate: '50Hz' },
      { signal: 'Front_Steer_Feed', canId: '0x132', unit: 'deg', current: '27.6', min: '-24.4', max: '32.1', avg: '9.6', rate: '50Hz' },
    ],
  },
  manualControl: {
    interlocks: [
      { name: '关键反馈在线', value: '0x131/0x132 正常', status: 'pass' },
      { name: '无严重告警', value: '存在通信 warning', status: 'fail' },
      { name: '急停释放', value: '释放', status: 'pass' },
      { name: '速度上限', value: '<= 5 km/h', status: 'pass' },
      { name: '控制通道', value: 'CAN2 独占', status: 'pass' },
      { name: '数据库可写', value: 'OK', status: 'pass' },
    ],
    rules: [
      { rule: '最高告警等级', current: 'warning', threshold: '< fault', status: 'PASS', action: '禁止周期发送' },
      { rule: '目标速度限制', current: '3.0 km/h', threshold: '<= 5 km/h', status: 'PASS', action: '裁剪命令' },
      { rule: '前转角限制', current: '20 raw', threshold: '-120..120', status: 'PASS', action: '裁剪命令' },
      { rule: '控制报文白名单', current: '0x121', threshold: '仅 0x121', status: 'PASS', action: '拒绝 0x123/0x126' },
    ],
  },
  autoTest: {
    assertions: [
      { id: 'A-071', desc: '前转角跟随', signal: 'Front_Steer_Angle', threshold: '<= 3 deg', value: '1.4 deg', result: 'PASS' },
      { id: 'A-072', desc: '响应时间', signal: 'Steer_Response_Time', threshold: '<= 500 ms', value: '280 ms', result: 'PASS' },
      { id: 'A-073', desc: '无严重告警', signal: 'Alarm_Level', threshold: '< 2', value: '0', result: 'PASS' },
    ],
    logs: [
      { time: '09:34:12.020', step: '转向响应', action: 'preview 0x121', feedback: 'bytes=40 03 14 F6 02 00 00 00', status: 'OK' },
      { time: '09:34:12.044', step: '转向响应', action: 'send once', feedback: 'tx_seq=3821', status: 'OK' },
      { time: '09:34:12.324', step: '转向响应', action: 'assert feedback', feedback: '27.6 deg', status: 'PASS' },
    ],
  },
  alarms: {
    matrix: [
      { name: 'BMS_SOC', label: '正常', level: 'ok' },
      { name: 'MCU 掉线', label: '正常', level: 'ok' },
      { name: '电机过流', label: 'WARNING', level: 'warn' },
      { name: '超速', label: '正常', level: 'ok' },
      { name: '转向掉线', label: '正常', level: 'ok' },
      { name: '角故障', label: 'WARNING', level: 'warn' },
      { name: '制动故障', label: '正常', level: 'ok' },
      { name: '通信超时', label: 'WARNING', level: 'warn' },
    ],
    bmsBits: [
      { name: 'MOS', active: false },
      { name: '短路', active: false },
      { name: '过流', active: true },
      { name: '过温', active: false },
      { name: '欠温', active: false },
      { name: '过压', active: false },
      { name: '欠压', active: false },
      { name: '均衡', active: true },
    ],
    rows: [
      { time: '09:41:12.110', channel: 'CAN2', canId: '0x77', signal: 'MCU_Motor_Warning', level: 'WARNING', state: 'active', advice: '检查电机相电流', override: '需工程师' },
      { time: '09:41:13.008', channel: 'CAN1', canId: '0x102', signal: 'BMS_OverCurrent', level: 'WARNING', state: 'latched', advice: '确认 BMS 负载', override: '不可放行' },
      { time: '09:41:14.320', channel: 'CAN2', canId: 'timeout', signal: 'Steer_Feedback', level: 'WARNING', state: 'recovered', advice: '复查网关延迟', override: '可申请' },
    ],
    suggestions: [
      { title: '电机相电流偏高', body: '检查驱动轮空载状态，复核 Torque_feed raw x 0.1 A。', status: 'warning', label: '需复核' },
      { title: 'BMS 过流保护', body: '不允许人工放行；若持续存在，检测结论应 FAIL。', status: 'fail', label: '禁止放行' },
      { title: '转向反馈短时超时', body: '可在恢复后重新执行转向响应步骤并保留审计记录。', status: 'normal', label: '可重测' },
    ],
  },
  reports: {
    rows: [
      { id: 'RPT-20260709-0031', chassis: 'YL-LSV-2026-0719', vin: 'L0000000000000719', time: '2026-07-09 09:42', result: 'PASS', operator: 'op01', types: 'docx/pdf/json/csv', size: '18.2 MB', status: '完成' },
      { id: 'RPT-20260709-0030', chassis: 'YL-LSV-2026-0718', vin: 'L0000000000000718', time: '2026-07-09 08:15', result: 'FAIL', operator: 'op02', types: 'docx/pdf/json/raw', size: '26.4 MB', status: '完成' },
      { id: 'RPT-20260708-0029', chassis: 'YL-LSV-2026-0717', vin: 'L0000000000000717', time: '2026-07-08 17:30', result: 'PASS', operator: 'op01', types: 'docx/pdf/json/csv', size: '17.8 MB', status: '归档' },
    ],
  },
  history: {
    sessions: [
      { id: 'EOL-20260709-0031', chassis: 'YL-LSV-2026-0719', vin: 'L0000000000000719', start: '09:18', end: '09:42', result: 'PASS', failStep: '-', operator: 'op01', report: 'RPT-0031' },
      { id: 'EOL-20260709-0030', chassis: 'YL-LSV-2026-0718', vin: 'L0000000000000718', start: '08:02', end: '08:31', result: 'FAIL', failStep: 'BMS_CHECK', operator: 'op02', report: 'RPT-0030' },
      { id: 'EOL-20260708-0029', chassis: 'YL-LSV-2026-0717', vin: 'L0000000000000717', start: '17:01', end: '17:30', result: 'PASS', failStep: '-', operator: 'op01', report: 'RPT-0029' },
    ],
    audits: [
      { time: '09:34:12.044', user: 'op01', action: 'send_once', target: '0x121', params: 'speed=3.0, steer=20', result: 'OK' },
      { time: '09:41:18.205', user: 'op01', action: 'ack_alarm', target: 'ALM-1024', params: 'warning', result: 'OK' },
      { time: '09:42:03.120', user: 'op01', action: 'generate_report', target: 'RPT-0031', params: 'pdf/docx/json', result: 'OK' },
    ],
  },
  settings: {
    thresholds: [
      { item: '0x121 周期', value: '20 ms', range: '10..100 ms', scope: 'control', note: '默认周期' },
      { item: '目标速度上限', value: '5 km/h', range: '0..8 km/h', scope: 'safety', note: '联锁阈值' },
      { item: '转角控制值', value: '-120..120', range: 'int8', scope: 'safety', note: '超限裁剪' },
      { item: '反馈超时', value: '500 ms', range: '100..2000 ms', scope: 'diagnosis', note: '关键反馈离线判定' },
    ],
    roles: [
      { role: 'viewer', pages: '查看', control: '无', maintenance: '无' },
      { role: 'operator', pages: '检测/报告', control: '一键检测', maintenance: '无' },
      { role: 'engineer', pages: '全部业务页', control: '手动 0x121', maintenance: '非危险配置' },
      { role: 'admin', pages: '全部', control: '审批', maintenance: '危险项确认' },
    ],
    history: [
      { time: '2026-07-09 09:10', user: 'admin', key: 'report.path', oldValue: '<旧 data_root>\\reports', newValue: '<data_root>\\reports', reason: '产线目录迁移' },
      { time: '2026-07-09 09:05', user: 'engineer', key: 'control.period_ms', oldValue: '50', newValue: '20', reason: '方案版本 v1.0.2' },
      { time: '2026-07-08 17:22', user: 'admin', key: 'mock.enabled', oldValue: 'false', newValue: 'true', reason: '桌面端演示' },
    ],
  },
} satisfies Record<string, Record<string, unknown>>
