import { defineStore } from 'pinia'
import { ApiError, apiDelete, apiDownload, apiGet, apiPost, formatApiError, isNetworkError } from '../api/http'
import type { ReportListItem, ReportManagementDashboard, ReportPreviewData, ReportRelatedSession } from '../api/types'
import { fallbackReportManagementDashboard } from '../mocks/fallbackData'

type ReportAction = 'scan' | 'open-directory' | 'change-directory' | 'export-word' | 'export-pdf' | 'print' | 'regenerate'
type ActionResponse = {
  ok: boolean
  message: string
  trace_id: string
  details: Record<string, unknown>
}

function cloneDashboard(): ReportManagementDashboard {
  const dashboard = structuredClone(fallbackReportManagementDashboard)
  dashboard.data_source = 'frontend-explicit-fallback'
  dashboard.mock = true
  dashboard.quality = 'mock'
  dashboard.trace_id = ''
  return dashboard
}

export const useReportsStore = defineStore('reports', {
  state: () => ({
    dashboard: cloneDashboard(),
    offline: false,
    loading: false,
    error: '',
  }),
  actions: {
    async loadDashboard() {
      this.loading = true
      try {
        this.dashboard = await apiGet<ReportManagementDashboard>('/reports/dashboard')
        this.offline = false
        this.error = ''
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.dashboard = cloneDashboard()
          this.offline = true
        } else {
          this.offline = false
        }
      } finally {
        this.loading = false
      }
    },
    async selectReport(report: ReportListItem) {
      try {
        const [preview, related] = await Promise.all([
          apiGet<ReportPreviewData>(`/reports/${encodeURIComponent(report.report_id)}/preview`),
          apiGet<{ sessions: ReportRelatedSession[] }>(`/reports/${encodeURIComponent(report.report_id)}/related-data`),
        ])
        this.dashboard.selected_report = preview
        this.dashboard.related_data = related
        this.error = ''
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) this.offline = true
        throw error
      }
    },
    selectedReportId(): string {
      const id = this.dashboard.selected_report?.report_id
      if (!id) throw new ApiError({ code: 'REPORT_NOT_SELECTED', message: '请先选择报告', details: {} }, 422)
      return id
    },
    async runAction(action: ReportAction) {
      const id = action === 'scan' || action === 'open-directory' || action === 'change-directory'
        ? ''
        : this.selectedReportId()
      const routes: Record<ReportAction, string> = {
        scan: '/reports/scan',
        'open-directory': '/reports/open-directory',
        'change-directory': '/reports/change-directory',
        'export-word': `/reports/${encodeURIComponent(id)}/export-word`,
        'export-pdf': `/reports/${encodeURIComponent(id)}/export-pdf`,
        print: `/reports/${encodeURIComponent(id)}/print`,
        regenerate: `/reports/${encodeURIComponent(id)}/regenerate`,
      }
      const result = await apiPost<ActionResponse>(
        routes[action],
        action === 'change-directory' ? { path: this.dashboard.directory.path } : {},
      )
      const downloadUrl = typeof result.details.download_url === 'string' ? result.details.download_url : ''
      if (downloadUrl && (action === 'export-word' || action === 'export-pdf')) {
        await apiDownload(downloadUrl, typeof result.details.file_name === 'string' ? result.details.file_name : undefined)
      }
      if (action === 'open-directory') {
        const path = typeof result.details.path === 'string' ? result.details.path : ''
        if (!path || !window.desktopFiles) {
          throw new ApiError({ code: 'DESKTOP_FILE_API_UNAVAILABLE', message: '桌面目录接口不可用', details: { path } }, 503)
        }
        await window.desktopFiles.openPath(path)
      }
      if (action === 'scan' || action === 'regenerate' || action === 'change-directory') await this.loadDashboard()
      return result
    },
    async downloadSelected() {
      const report = this.dashboard.selected_report
      if (!report) throw new ApiError({ code: 'REPORT_NOT_SELECTED', message: '请先选择报告', details: {} }, 422)
      return apiDownload(`/reports/${encodeURIComponent(report.report_id)}/file`, report.filename)
    },
    async deleteSelected() {
      const result = await apiDelete<ActionResponse>(`/reports/${encodeURIComponent(this.selectedReportId())}`)
      await this.loadDashboard()
      return result
    },
    async relatedData() {
      return await apiGet<{ sessions: ReportRelatedSession[] }>(`/reports/${encodeURIComponent(this.selectedReportId())}/related-data`)
    },
  },
})
