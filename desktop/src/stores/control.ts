import { defineStore } from 'pinia'
import { apiGet, apiPost } from '../api/http'
import type { ManualControlCommand, ManualControlStatus, ManualCurves, ManualFeedback, ManualInterlockStatus, ManualPreview } from '../api/types'
import { fallbackManualCommand, fallbackManualCurves, fallbackManualFeedback, fallbackManualInterlock, fallbackManualPreview, fallbackManualStatus } from '../mocks/fallbackData'

type InterlockItem = ManualInterlockStatus['items'][number]

function highestStatus(items: InterlockItem[]): InterlockItem['status'] {
  if (items.some((item) => item.status === 'fail')) return 'fail'
  if (items.some((item) => item.status === 'warning')) return 'warning'
  return 'pass'
}

function compactInterlock(status: ManualInterlockStatus): ManualInterlockStatus {
  const byKey = new Map(status.items.map((item) => [item.key, item]))
  const summary = (
    key: string,
    label: string,
    sourceKeys: string[],
    passValue: string,
  ): InterlockItem => {
    const sources = sourceKeys.map((sourceKey) => byKey.get(sourceKey)).filter((item): item is InterlockItem => Boolean(item))
    return {
      key,
      label,
      status: sources.length ? highestStatus(sources) : 'warning',
      value: sources.length && highestStatus(sources) === 'pass' ? passValue : sources.map((item) => item.value).join(' / ') || '待确认',
    }
  }

  return {
    overall: status.overall,
    reasons: status.reasons,
    items: [
      summary('key_frames_online', '关键报文在线', ['can2_online', 'critical_feedback_fresh'], '在线'),
      summary('no_severe_alarm', '无严重告警', ['no_severe_alarm'], '正常'),
      summary('control_channel', '控制通道', ['single_control_channel', 'can2_queue_healthy'], 'CAN2 正常'),
      summary('dbc_ready', 'DBC / 覆盖规则', ['dbc_ready'], '已加载'),
      summary('database_writable', '数据库可写', ['database_writable'], '正常'),
      summary('emergency_stop', '急停', ['emergency_released'], '未触发'),
      summary('safe_stop', '安全停车', ['safe_stop_released'], '未锁存'),
    ],
  }
}

export const useControlStore = defineStore('control', {
  state: () => ({
    command: { ...fallbackManualCommand } as ManualControlCommand,
    status: { ...fallbackManualStatus } as ManualControlStatus,
    interlock: { ...fallbackManualInterlock } as ManualInterlockStatus,
    preview: { ...fallbackManualPreview } as ManualPreview,
    feedback: { ...fallbackManualFeedback } as ManualFeedback,
    curves: { ...fallbackManualCurves } as ManualCurves,
    offline: false,
    error: '',
  }),
  actions: {
    async loadAll() {
      await Promise.all([
        this.loadStatus(),
        this.loadInterlock(),
        this.loadFeedback(),
        this.loadCurves(),
        this.refreshPreview(),
      ])
    },
    async loadStatus() {
      try {
        this.status = await apiGet<ManualControlStatus>('/control/status')
        this.offline = false
        this.error = ''
      } catch (error) {
        this.status = { ...fallbackManualStatus }
        this.offline = true
        this.error = error instanceof Error ? error.message : String(error)
      }
    },
    async loadInterlock() {
      try {
        this.interlock = compactInterlock(await apiGet<ManualInterlockStatus>('/control/interlock-status'))
      } catch {
        this.interlock = { ...fallbackManualInterlock }
      }
    },
    async loadFeedback() {
      try {
        this.feedback = await apiGet<ManualFeedback>('/control/manual-feedback')
      } catch {
        this.feedback = { ...fallbackManualFeedback }
      }
    },
    async loadCurves() {
      try {
        this.curves = await apiGet<ManualCurves>('/control/manual-curves')
      } catch {
        this.curves = { ...fallbackManualCurves }
      }
    },
    async refreshPreview() {
      try {
        this.preview = await apiPost<ManualPreview>('/control/121/preview', this.command)
      } catch {
        this.preview = { ...fallbackManualPreview }
      }
    },
    resetDefaults() {
      this.command = { ...fallbackManualCommand }
      this.preview = { ...fallbackManualPreview }
    },
  },
})
