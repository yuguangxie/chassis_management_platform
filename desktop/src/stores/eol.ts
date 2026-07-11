import { defineStore } from 'pinia'
import { apiGet, apiPost } from '../api/http'
import type { AutoTestDashboard } from '../api/types'
import { fallbackAutoTestDashboard } from '../mocks/fallbackData'

type ActionResponse = { ok?: boolean; stub?: boolean; message?: string; session_id?: string; report_id?: string }

function cloneDashboard(): AutoTestDashboard {
  return structuredClone(fallbackAutoTestDashboard)
}

export const useEolStore = defineStore('eol', {
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
        this.dashboard = await apiGet<AutoTestDashboard>('/eol/dashboard')
        this.offline = false
        this.error = ''
      } catch (error) {
        this.dashboard = cloneDashboard()
        this.offline = true
        this.error = error instanceof Error ? error.message : String(error)
      } finally {
        this.loading = false
      }
    },
    async createSession() {
      const session = this.dashboard.session
      const response = await apiPost<{ id?: string; session_id?: string }>('/eol/sessions', {
        chassis_no: session.chassis_no,
        vin: session.vin,
        serial_no: session.serial_no,
        operator: session.operator,
        station_id: session.station_id,
        plan_id: 'default_chassis_eol_v1',
        remarks: session.remark,
      })
      this.dashboard.session.session_id = response.session_id || response.id || session.session_id
      return this.dashboard.session.session_id
    },
    async runSessionAction(action: 'start' | 'pause' | 'resume' | 'abort' | 'emergency-stop' | 'report') {
      const sid = action === 'start' ? await this.createSession() : this.dashboard.session.session_id || await this.createSession()
      const result = await apiPost<ActionResponse>(`/eol/sessions/${sid}/${action}`, {})
      await this.loadDashboard()
      return result
    },
  },
})
