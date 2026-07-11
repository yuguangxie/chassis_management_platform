import { defineStore } from 'pinia'
import { ApiError, apiDownload, apiGet, apiPost, formatApiError, isNetworkError } from '../api/http'
import type { HistoryDashboard, HistoryDownloadItem, HistoryOperatorLog, HistorySessionItem, HistoryTimelineItem } from '../api/types'
import { fallbackHistoryDashboard } from '../mocks/fallbackData'

export interface HistoryQuery {
  chassis_no?: string
  vin?: string
  serial_no?: string
  start_time?: string
  end_time?: string
  result?: string
  operator?: string
  station?: string
  page?: number
  page_size?: number
}

type ActionResponse = {
  ok: boolean
  message: string
  trace_id: string
  details: Record<string, unknown>
}

function cloneDashboard(): HistoryDashboard {
  const dashboard = structuredClone(fallbackHistoryDashboard)
  dashboard.data_source = 'frontend-explicit-fallback'
  dashboard.mock = true
  dashboard.quality = 'mock'
  dashboard.trace_id = ''
  return dashboard
}

function queryString(query: HistoryQuery) {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== '全部') params.set(key, String(value))
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

function fileType(key: HistoryDownloadItem['key']): string {
  return {
    raw_can: 'raw-can',
    decoded_signals: 'decoded-signals',
    report_bundle: 'report-bundle',
    audit_log: 'audit-log',
    curve_replay: 'curve-replay',
  }[key]
}

export const useHistoryStore = defineStore('history', {
  state: () => ({
    dashboard: cloneDashboard(),
    offline: false,
    loading: false,
    error: '',
    selectedSessionId: fallbackHistoryDashboard.selected_session?.session_id || '',
  }),
  actions: {
    async loadDashboard(query: HistoryQuery = {}, preserveSelection = false) {
      const previous = preserveSelection ? this.selectedSessionId : ''
      this.loading = true
      try {
        this.dashboard = await apiGet<HistoryDashboard>(`/history/dashboard${queryString(query)}`)
        this.offline = false
        this.error = ''
        const target = previous && this.dashboard.sessions.some((item) => item.session_id === previous)
          ? previous
          : this.dashboard.sessions[0]?.session_id || ''
        this.selectedSessionId = target
        if (target && this.dashboard.selected_session?.session_id !== target) await this.selectSession(target)
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.dashboard = cloneDashboard()
          this.offline = true
          this.selectedSessionId = previous || this.dashboard.selected_session?.session_id || ''
        } else {
          this.offline = false
        }
      } finally {
        this.loading = false
      }
    },
    async selectSession(sessionId: string) {
      this.selectedSessionId = sessionId
      const row = this.dashboard.sessions.find((item) => item.session_id === sessionId)
      try {
        const [detail, timeline, logs, downloads] = await Promise.all([
          apiGet<HistorySessionItem & { duration?: string }>(`/test-sessions/${encodeURIComponent(sessionId)}`),
          apiGet<HistoryTimelineItem[]>(`/test-sessions/${encodeURIComponent(sessionId)}/timeline`),
          apiGet<HistoryOperatorLog[]>(`/test-sessions/${encodeURIComponent(sessionId)}/operator-actions`),
          apiGet<HistoryDownloadItem[]>(`/test-sessions/${encodeURIComponent(sessionId)}/downloads`),
        ])
        this.dashboard.selected_session = {
          session_id: sessionId,
          duration: detail.duration || '-',
          result: detail.result || row?.result || 'RUNNING',
          timeline,
          operator_logs: logs,
          downloads,
        }
        this.error = ''
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) this.offline = true
        throw error
      }
    },
    requireSession(): string {
      if (!this.selectedSessionId) throw new ApiError({ code: 'SESSION_NOT_SELECTED', message: '请先选择检测会话', details: {} }, 422)
      return this.selectedSessionId
    },
    async exportHistory(query: HistoryQuery) {
      const result = await apiPost<ActionResponse>('/history/export', query)
      const url = typeof result.details.download_url === 'string' ? result.details.download_url : ''
      if (!url) throw new ApiError({ code: 'EXPORT_FILE_MISSING', message: '导出结果未返回文件地址', details: result.details }, 500)
      await apiDownload(url, typeof result.details.file_name === 'string' ? result.details.file_name : undefined)
      return result
    },
    async downloadFile(item: HistoryDownloadItem) {
      const sessionId = this.requireSession()
      return apiDownload(
        `/test-sessions/${encodeURIComponent(sessionId)}/download/${fileType(item.key)}`,
        `${sessionId}-${fileType(item.key)}${item.extension.split(' ')[0]}`,
      )
    },
    async openDetail() {
      return await apiPost<ActionResponse>(`/test-sessions/${encodeURIComponent(this.requireSession())}/open-detail`, {})
    },
    async downloadBundle() {
      const item = this.dashboard.selected_session?.downloads.find((entry) => entry.key === 'report_bundle')
      if (!item) throw new ApiError({ code: 'DOWNLOAD_NOT_AVAILABLE', message: '当前会话没有报告数据包', details: {} }, 404)
      return this.downloadFile(item)
    },
  },
})
