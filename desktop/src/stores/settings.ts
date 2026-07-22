import { defineStore } from 'pinia'
import { apiGet, apiPost, apiPut, formatApiError } from '../api/http'
import { wsClient } from '../api/websocket'
import type {
  ConfigurationExportResult,
  ConfigurationPreviewResult,
  SignedConfigurationPackage,
  SystemMaintenanceSettings,
  SystemSettingsDashboard,
  CleanupPreview,
  StorageLifecycleStats,
  BackupListItem,
} from '../api/types'
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
    operationLoading: false,
    offline: false,
    error: '',
    dirty: false,
    externalUpdated: false,
    wsBound: false,
    storageStats: null as StorageLifecycleStats | null,
    cleanupPreview: null as CleanupPreview | null,
    backups: [] as BackupListItem[],
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
        this.error = ''
        this.dirty = false
        this.externalUpdated = false
      } catch (error) {
        if (!preserveEdits || !this.dirty) {
          this.dashboard = clone(fallbackSystemSettings)
          this.original = clone(fallbackSystemSettings)
          this.dirty = false
        }
        this.offline = true
        this.error = formatApiError(error)
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
      return await this.runOperation(async () => {
        const result = await apiPut<OperationResult>('/config', {
          basic: this.dashboard.basic,
          storage: this.dashboard.storage,
          thresholds: this.dashboard.thresholds,
          role: this.dashboard.auth.current_role,
          reason,
        })
        this.original = clone(this.dashboard)
        this.dirty = false
        this.dashboard.save_state = { dirty:false, status:'saved', last_saved_at:new Date().toISOString() }
        return result
      })
    },
    async previewConfig(configPackage: SignedConfigurationPackage) {
      return await apiPost<ConfigurationPreviewResult>('/config/import', { package:configPackage, dry_run:true })
    },
    async exportConfig() {
      const result = await apiGet<ConfigurationExportResult>('/config/export')
      const blob = new Blob([JSON.stringify(result.package, null, 2)], { type:'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = result.filename
      anchor.click()
      URL.revokeObjectURL(url)
      return result
    },
    async applyConfig(configPackage: SignedConfigurationPackage, reason: string) {
      const result = await apiPost<OperationResult>('/config/apply', { package:configPackage, confirmation:'APPLY', reason })
      await this.loadDashboard()
      return result
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
    async loadStorageStats() {
      this.storageStats = await apiGet<StorageLifecycleStats>('/storage/stats')
      return this.storageStats
    },
    async createBackup() {
      return await apiPost<Record<string, unknown>>('/storage/backups', {})
    },
    async listBackups() {
      const result = await apiGet<{items:BackupListItem[]}>('/storage/backups')
      this.backups = result.items
      return result.items
    },
    async restoreBackup(backupId:string, confirmation:string) {
      return await apiPost<Record<string, unknown>>(`/storage/backups/${encodeURIComponent(backupId)}/restore`, { confirmation })
    },
    async previewRetention(cutoffUtc: string) {
      this.cleanupPreview = await apiPost<CleanupPreview>('/storage/cleanup/preview', { cutoff_utc:cutoffUtc })
      return this.cleanupPreview
    },
    async startRetention(cutoffUtc: string) {
      return await apiPost<Record<string, unknown>>('/storage/cleanup', { cutoff_utc:cutoffUtc, confirmation:'CLEANUP', batch_size:50 })
    },
    async recheckStorage() {
      const result = await apiPost<Record<string, unknown>>('/storage/health/recheck', {})
      await this.loadStorageStats()
      return result
    },
    async runOperation<T>(operation: () => Promise<T>): Promise<T> {
      this.operationLoading = true
      try {
        const result = await operation()
        this.error = ''
        return result
      } catch (error) {
        this.error = formatApiError(error)
        throw error
      } finally {
        this.operationLoading = false
      }
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
