export type UiTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'
export type SignalBinaryState = 'on' | 'off' | 'unknown'

const STATUS_LABELS: Readonly<Record<string, string>> = Object.freeze({
  online: '在线',
  offline: '离线',
  unavailable: '不可用',
  stale: '数据陈旧',
  invalid: '无效',
  degraded: '降级',
  good: '正常',
  mock: '模拟数据',
  normal: '正常',
  warning: '警告',
  fault: '故障',
  critical: '严重',
  pass: '通过',
  fail: '失败',
  running: '运行中',
  aborted: '已中止',
  wait: '等待',
  paused: '已暂停',
  skipped: '已跳过',
  admin: '管理员',
  operator: '操作员',
  engineer: '工程师',
  viewer: '查看者',
  manual: '手动',
  remote: '远程',
  auto: '自动',
  on: '开启',
  off: '关闭',
  released: '已释放',
  engaged: '已接合',
  enabled: '已启用',
  disabled: '已禁用',
  active: '活动',
  inactive: '未活动',
  queued: '已排队',
  printing: '打印中',
  completed: '已完成',
  cancelled: '已取消',
  pending_review: '待审批',
  approved: '已批准',
  revoked: '已撤销',
  expired: '已过期',
  receive_confirmed: '收帧已确认',
  unconfirmed: '未确认',
  connected: '已连接',
  disconnected: '未连接',
  connectable: '可连接',
  not_applicable: '不适用',
  owned_by_runtime: '当前进程使用',
  available: '可绑定',
  occupied_or_unbindable: '占用或不可绑定',
  not_diagnosed: '未检测',
  'not-diagnosed': '未检测',
  'not-measured': '未测量',
})

export function localizeStatus(value: unknown, fallback = '未知'): string {
  if (value === null || value === undefined || value === '') return fallback
  const text = String(value).trim()
  if (!text || text === '-') return text || fallback
  return STATUS_LABELS[text.toLowerCase()] ?? text
}

export function qualityLabel(value: unknown): string {
  return localizeStatus(value, '不可用')
}

export function qualityIsUsable(value: unknown): boolean {
  const quality = String(value ?? '').trim().toLowerCase()
  return quality === 'good' || quality === 'mock'
}

export function statusTone(value: unknown): UiTone {
  const key = String(value ?? '').trim().toLowerCase()
  if (['good', 'normal', 'pass', 'online', 'completed', 'enabled', 'approved'].includes(key)) return 'success'
  if (['warning', 'degraded', 'stale', 'wait', 'paused', 'queued', 'mock', 'pending_review'].includes(key)) return 'warning'
  if (['fault', 'critical', 'fail', 'invalid', 'offline', 'unavailable', 'aborted', 'cancelled', 'revoked', 'expired'].includes(key)) return 'danger'
  return 'neutral'
}

export function normalizeBinaryState(value: unknown, quality: unknown = 'good'): SignalBinaryState {
  const qualityKey = String(quality ?? '').trim().toLowerCase()
  if (['stale', 'invalid', 'unavailable', 'degraded'].includes(qualityKey)) return 'unknown'
  if (typeof value === 'boolean') return value ? 'on' : 'off'
  if (typeof value === 'number') return value === 1 ? 'on' : value === 0 ? 'off' : 'unknown'
  const key = String(value ?? '').trim().toLowerCase()
  if (['on', '1', 'true', 'enabled'].includes(key)) return 'on'
  if (['off', '0', 'false', 'disabled'].includes(key)) return 'off'
  return 'unknown'
}

export function binaryStateLabel(state: SignalBinaryState, quality: unknown = 'good'): string {
  if (state === 'unknown') {
    const qualityKey = String(quality ?? '').trim().toLowerCase()
    return qualityKey === 'stale' ? '数据陈旧' : qualityKey === 'invalid' ? '无效' : '未知'
  }
  return state === 'on' ? '开启' : '关闭'
}

export const uiStatusLabels = STATUS_LABELS
