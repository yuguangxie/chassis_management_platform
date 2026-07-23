import { defineStore } from 'pinia'
import { apiGet, apiPost } from '../api/http'
import type { AutoTestDashboard } from '../api/types'
import { fallbackAutoTestDashboard } from '../mocks/fallbackData'

type ActionResponse = { ok?: boolean; stub?: boolean; message?: string; session_id?: string; report_id?: string }

export interface EolIdentityDraft {
  chassis_no: string
  vin: string
  serial_no: string
  vehicle_series: string
  work_order_id: string
  plan_id: string
  remarks: string
  duplicate_policy: 'reject' | 'retest'
}

function cloneDashboard(): AutoTestDashboard {
  return structuredClone(fallbackAutoTestDashboard)
}

let dashboardRequest: Promise<void> | undefined

export const useEolStore = defineStore('eol', {
  state: () => ({
    dashboard: cloneDashboard(),
    offline: false,
    initialLoading: false,
    refreshing: false,
    actionPending: false,
    initialized: false,
    error: '',
    identityDraft: {
      chassis_no: '',
      vin: '',
      serial_no: '',
      vehicle_series: '',
      work_order_id: '',
      plan_id: 'default_chassis_eol_v1',
      remarks: '',
      duplicate_policy: 'reject',
    } as EolIdentityDraft,
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
          const dashboard = await apiGet<AutoTestDashboard>('/eol/dashboard')
          this.dashboard = dashboard
          if (dashboard.session.session_id) {
            this.identityDraft = {
              chassis_no: dashboard.session.chassis_no || '',
              vin: dashboard.session.vin || '',
              serial_no: dashboard.session.serial_no || '',
              vehicle_series: dashboard.session.vehicle_series || '',
              work_order_id: dashboard.session.work_order_id || '',
              plan_id: this.identityDraft.plan_id || 'default_chassis_eol_v1',
              remarks: dashboard.session.remark || '',
              duplicate_policy: this.identityDraft.duplicate_policy,
            }
          }
          this.offline = false
          this.error = ''
          this.initialized = true
        } catch (error) {
          if (!this.initialized) this.dashboard = cloneDashboard()
          this.offline = true
          this.error = error instanceof Error ? error.message : String(error)
        } finally {
          this.initialLoading = false
          this.refreshing = false
          dashboardRequest = undefined
        }
      })()
      return dashboardRequest
    },
    async createSession() {
      const session = this.dashboard.session
      const draft = this.identityDraft
      const response = await apiPost<{ id?: string; session_id?: string }>('/eol/sessions', {
        ...draft,
        mock_session: this.dashboard.mock_session_allowed,
      })
      this.dashboard.session.session_id = response.session_id || response.id || session.session_id
      return this.dashboard.session.session_id
    },
    generateMockIdentity() {
      if (!this.dashboard.mock_session_allowed) throw new Error('生产环境禁止生成模拟会话身份')
      const stamp = `${Date.now()}`.slice(-12)
      this.identityDraft = {
        chassis_no: `MOCK-${stamp}`,
        vin: `LMC${stamp.padStart(14, '0').slice(-14)}`,
        serial_no: `MOCK-SN-${stamp}`,
        vehicle_series: this.dashboard.session.vehicle_series || 'JD',
        work_order_id: `MOCK-WO-${stamp}`,
        plan_id: 'default_chassis_eol_v1',
        remarks: '显式 Mock 会话',
        duplicate_policy: 'reject',
      }
    },
    async runSessionAction(action: 'start' | 'pause' | 'resume' | 'abort' | 'emergency-stop' | 'report') {
      if (this.actionPending) throw new Error('已有检测操作正在执行')
      this.actionPending = true
      try {
        const sid = action === 'start' ? await this.createSession() : this.dashboard.session.session_id || await this.createSession()
        const result = await apiPost<ActionResponse>(`/eol/sessions/${sid}/${action}`, {})
        await this.loadDashboard(true)
        return result
      } finally {
        this.actionPending = false
      }
    },
  },
})
