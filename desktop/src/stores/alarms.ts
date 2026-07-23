import { defineStore } from 'pinia'
import { ApiError, apiDownload, apiGet, apiPost, formatApiError, isNetworkError } from '../api/http'
import type { AlarmDiagnosisDashboard } from '../api/types'
import { fallbackAlarmDiagnosisDashboard } from '../mocks/fallbackData'

type AlarmActionResponse = { ok: boolean; message: string; trace_id: string; details: Record<string, unknown> }

function cloneDashboard(): AlarmDiagnosisDashboard {
  const result = structuredClone(fallbackAlarmDiagnosisDashboard)
  result.data_source = 'frontend-explicit-fallback'
  result.mock = true
  result.quality = 'mock'
  result.trace_id = ''
  return result
}

let dashboardRequest: Promise<void> | undefined

export const useAlarmsStore = defineStore('alarms', {
  state: () => ({
    dashboard: cloneDashboard(),
    offline: false,
    initialLoading: false,
    refreshing: false,
    actionPending: false,
    initialized: false,
    error: '',
  }),
  getters: {
    loading: (state) => state.initialLoading,
  },
  actions: {
    async loadDashboard(background = false) {
      if (dashboardRequest) return dashboardRequest
      if (background || this.initialized) this.refreshing = true
      else this.initialLoading = true
      dashboardRequest = (async () => {
        try {
          this.dashboard = await apiGet<AlarmDiagnosisDashboard>('/alarms/dashboard')
          this.offline = false
          this.error = ''
          this.initialized = true
        } catch (error) {
          this.error = formatApiError(error)
          if (isNetworkError(error)) {
            if (!this.initialized) this.dashboard = cloneDashboard()
            this.offline = true
          } else {
            this.offline = false
          }
        } finally {
          this.initialLoading = false
          this.refreshing = false
          dashboardRequest = undefined
        }
      })()
      return dashboardRequest
    },
    async runAction(action: 'ack' | 'override-request' | 'export-diagnosis' | 'jump-can-frame' | 'safe-stop') {
      if (this.actionPending) throw new ApiError({ code: 'ACTION_PENDING', message: '已有告警操作正在执行', details: {} }, 409)
      this.actionPending = true
      try {
      const currentId = this.dashboard.history[0]?.id
      if ((action === 'ack' || action === 'override-request') && !currentId) {
        throw new ApiError({ code: 'NO_ACTIVE_ALARM', message: '当前没有可操作的告警记录', details: {} }, 404)
      }
      const routes = {
        ack: `/alarms/${encodeURIComponent(currentId || '')}/ack`,
        'override-request': `/alarms/${encodeURIComponent(currentId || '')}/override-request`,
        'export-diagnosis': '/alarms/export-diagnosis',
        'jump-can-frame': '/alarms/jump-can-frame',
        'safe-stop': '/control/safe-stop',
      } as const
      const result = await apiPost<AlarmActionResponse>(routes[action], {
        alarm_id: currentId,
        can_id: this.dashboard.history[0]?.can_id || '0x77',
        reason: action === 'override-request' ? '产线人工放行复核申请' : undefined,
      })
      const downloadUrl = typeof result.details.download_url === 'string' ? result.details.download_url : ''
      if (action === 'export-diagnosis' && downloadUrl) {
        await apiDownload(downloadUrl, typeof result.details.file_name === 'string' ? result.details.file_name : undefined)
      }
      if (action === 'ack') await this.loadDashboard(true)
      return result
      } finally {
        this.actionPending = false
      }
    },
  },
})
