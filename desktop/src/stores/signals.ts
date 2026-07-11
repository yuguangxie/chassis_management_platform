import { defineStore } from 'pinia'
import { apiGet, formatApiError, isNetworkError } from '../api/http'
import { wsClient } from '../api/websocket'
import type { CurveConfig, CurveTimeseries, FaultEvent, ReplayMetadata, SignalDashboardSummary } from '../api/types'
import { fallbackCurveConfig, fallbackCurveTimeseries, fallbackFaultEvents, fallbackReplayMetadata, fallbackSignalDashboard } from '../mocks/fallbackData'

function explicitFallback<T extends { data_source?: string; mock?: boolean; quality?: 'good' | 'degraded' | 'unavailable' | 'mock'; trace_id?: string }>(value: T): T {
  const result = structuredClone(value)
  result.data_source = 'frontend-explicit-fallback'
  result.mock = true
  result.quality = 'mock'
  result.trace_id = ''
  return result
}

export const useSignalsStore = defineStore('signals', {
  state: () => ({
    dashboard: explicitFallback(fallbackSignalDashboard) as SignalDashboardSummary,
    curveConfig: explicitFallback(fallbackCurveConfig) as CurveConfig,
    curveTimeseries: explicitFallback(fallbackCurveTimeseries) as CurveTimeseries,
    replay: fallbackReplayMetadata as ReplayMetadata,
    faultEvents: fallbackFaultEvents as FaultEvent[],
    backendOnline: true,
    offline: false,
    error: '',
    wsBound: false,
    curvePaused: false,
    pendingCurveTimeseries: undefined as CurveTimeseries | undefined,
  }),
  actions: {
    async loadDashboard() {
      try {
        this.dashboard = await apiGet<SignalDashboardSummary>('/signals/dashboard')
        this.backendOnline = true
        this.offline = false
        this.error = ''
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.dashboard = explicitFallback(fallbackSignalDashboard)
          this.backendOnline = false
          this.offline = true
        } else {
          this.backendOnline = true
          this.offline = false
        }
      }
    },
    async loadCurveConfig() {
      try {
        this.curveConfig = await apiGet<CurveConfig>('/signals/curve-config')
        this.backendOnline = true
        this.offline = false
        this.error = ''
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.curveConfig = explicitFallback(fallbackCurveConfig)
          this.backendOnline = false
          this.offline = true
        } else {
          this.backendOnline = true
          this.offline = false
        }
      }
    },
    async loadCurveTimeseries(query = '') {
      try {
        this.curveTimeseries = await apiGet<CurveTimeseries>(`/signals/timeseries${query}`)
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.curveTimeseries = explicitFallback(fallbackCurveTimeseries)
          this.offline = true
        }
      }
    },
    async loadReplay(sessionId = fallbackReplayMetadata.session_id) {
      try {
        this.replay = await apiGet<ReplayMetadata>(`/test-sessions/${encodeURIComponent(sessionId)}/replay`)
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.replay = structuredClone(fallbackReplayMetadata)
          this.offline = true
        }
      }
    },
    async loadFaultEvents(sessionId = fallbackReplayMetadata.session_id) {
      try {
        this.faultEvents = await apiGet<FaultEvent[]>(`/test-sessions/${encodeURIComponent(sessionId)}/fault-events`)
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.faultEvents = structuredClone(fallbackFaultEvents)
          this.offline = true
        }
      }
    },
    bindWebSocket() {
      if (this.wsBound) return
      this.wsBound = true
      wsClient.on('signals.dashboard', (payload) => {
        this.dashboard = {
          ...(payload as SignalDashboardSummary),
          data_source: (payload as SignalDashboardSummary).data_source || 'websocket-runtime',
          mock: Boolean((payload as SignalDashboardSummary).mock),
        }
        this.backendOnline = true
        this.offline = false
      })
      wsClient.on('signals.current', (payload) => {
        // A current snapshot is useful to callers that only need signal freshness. The
        // dashboard itself is updated by its dedicated 10 Hz topic, without an HTTP echo.
        const snapshot = payload as { quality?: string }
        if (snapshot.quality === 'unavailable') this.offline = false
      })
      wsClient.on('signals.timeseries.batch', (payload) => {
        const next = payload as CurveTimeseries
        if (this.curvePaused) this.pendingCurveTimeseries = next
        else this.curveTimeseries = next
      })
      wsClient.on('test.replay.cursor', (payload) => {
        this.replay = { ...this.replay, ...(payload as Partial<ReplayMetadata>) }
      })
    },
    setCurvePaused(paused: boolean) {
      this.curvePaused = paused
      if (!paused && this.pendingCurveTimeseries) {
        this.curveTimeseries = this.pendingCurveTimeseries
        this.pendingCurveTimeseries = undefined
      }
    },
  },
})
