import { defineStore } from 'pinia'
import { apiGet, apiPost, apiPut } from '../api/http'
import { wsClient } from '../api/websocket'
import type { SystemMaintenanceSettings, SystemSettingsDashboard } from '../api/types'
import { fallbackSystemSettings } from '../mocks/systemSettings'

interface OperationResult {
  ok?: boolean
  stub?: boolean
  message?: string
  changed_items?: Array<Record<string, unknown>>
  maintenance_mode?: boolean
  features?: Partial<SystemMaintenanceSettings>
  [key: string]: unknown
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    dashboard: clone(fallbackSystemSettings),
    original: clone(fallbackSystemSettings),
    loading: false,
    offline: false,
    dirty: false,
    externalUpdated: false,
    wsBound: false,
  }),
  actions: {
    async loadDashboard(preserveEdits = false) {
      if (preserveEdits && this.dirty) return
      this.loading = true
      try {
        const data = await apiGet<SystemSettingsDashboard>('/config/system-dashboard')
        this.dashboard = clone(data)
        this.original = clone(data)
        this.offline = false
        this.dirty = false
        this.externalUpdated = false
      } catch {
        if (!preserveEdits || !this.dirty) {
          this.dashboard = clone(fallbackSystemSettings)
          this.original = clone(fallbackSystemSettings)
          this.dirty = false
        }
        this.offline = true
      } finally {
        this.loading = false
      }
    },
    markDirty() {
      this.dirty = true
      this.dashboard.save_state.dirty = true
      this.dashboard.save_state.status = 'dirty'
    },
    async save(reason: string) {
      const result = await apiPut<OperationResult>('/config', {
        basic: this.dashboard.basic,
        storage: this.dashboard.storage,
        thresholds: this.dashboard.thresholds,
        role: this.dashboard.auth.current_role,
        reason,
      })
      this.original = clone(this.dashboard)
      this.dirty = false
      this.dashboard.save_state = { dirty:false, status:'saved', last_saved_at:new Date().toLocaleString('zh-CN',{hour12:false}) }
      return result
    },
    async importConfig() {
      return await apiPost<OperationResult>('/config/import', { source:'electron-file-picker', role:this.dashboard.auth.current_role })
    },
    async exportConfig() {
      return await apiGet<OperationResult>('/config/export?format=yaml')
    },
    async reloadDbc() {
      const result = await apiPost<OperationResult>('/dbc/reload')
      this.dashboard.dbc = { ...this.dashboard.dbc, ...(result as Partial<SystemSettingsDashboard['dbc']>) }
      return result
    },
    async enterMaintenance(confirmation: string, reason: string) {
      const result = await apiPost<OperationResult>('/maintenance/enter', { confirmation, reason, role:this.dashboard.auth.current_role })
      this.dashboard.maintenance.maintenance_mode = Boolean(result.maintenance_mode)
      return result
    },
    async exitMaintenance() {
      const result = await apiPost<OperationResult>('/maintenance/exit', { role:this.dashboard.auth.current_role, reason:'系统设置页退出维护模式' })
      this.dashboard.maintenance.maintenance_mode = false
      Object.assign(this.dashboard.maintenance, result.features || {})
      return result
    },
    async updateFeatures(features: SystemMaintenanceSettings, confirmation: string, reason: string) {
      const result = await apiPut<OperationResult>('/maintenance/features', { ...features, confirmation, reason, role:this.dashboard.auth.current_role })
      Object.assign(this.dashboard.maintenance, result.features || {})
      this.dashboard.maintenance.maintenance_mode = Boolean(result.maintenance_mode)
      return result
    },
    async restoreSafeDefaults(confirmation: string, reason: string) {
      const result = await apiPost<OperationResult>('/config/restore-safe-defaults', { confirmation, reason, role:this.dashboard.auth.current_role })
      await this.loadDashboard()
      return result
    },
    bindWebSocket() {
      if (this.wsBound) return
      this.wsBound = true
      wsClient.on('system.config_changed', () => {
        if (this.dirty) this.externalUpdated = true
        else void this.loadDashboard()
      })
      wsClient.on('system.maintenance_changed', (payload) => Object.assign(this.dashboard.maintenance, payload as Partial<SystemMaintenanceSettings>))
      wsClient.on('dbc.status_changed', (payload) => Object.assign(this.dashboard.dbc, payload as Partial<SystemSettingsDashboard['dbc']>))
      if (!wsClient.ws) wsClient.connect()
    },
  },
})
