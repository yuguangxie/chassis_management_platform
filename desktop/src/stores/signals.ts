import { defineStore } from 'pinia'
import { apiGet, formatApiError, isNetworkError } from '../api/http'
import { wsClient } from '../api/websocket'
import type { CurveConfig, CurveTimeseries, FaultEvent, ReplayMetadata, SignalDashboardSummary } from '../api/types'
import { fallbackCurveConfig, fallbackCurveTimeseries, fallbackFaultEvents, fallbackReplayMetadata, fallbackSignalDashboard } from '../mocks/fallbackData'

type DashboardQuality = NonNullable<SignalDashboardSummary['quality']>

function dashboardQuality(value: unknown, fallback: DashboardQuality): DashboardQuality {
  return ['good', 'degraded', 'stale', 'invalid', 'unavailable', 'mock'].includes(String(value))
    ? value as DashboardQuality
    : fallback
}

export function normalizeDashboardPayload(
  payload: Partial<SignalDashboardSummary>,
  previous: SignalDashboardSummary,
): SignalDashboardSummary {
  const status = payload.status as (SignalDashboardSummary['status'] & { quality?: DashboardQuality }) | undefined
  const quality = dashboardQuality(payload.quality ?? status?.quality, previous.quality ?? 'unavailable')
  const updatedAt = payload.updated_at || status?.updated_at || previous.updated_at || previous.status.updated_at
  return {
    ...previous,
    ...payload,
    status: {
      ...previous.status,
      ...(status || {}),
      quality,
      updated_at: updatedAt,
      mock: payload.mock ?? status?.mock ?? previous.status.mock,
    },
    quality,
    updated_at: updatedAt,
    mock: payload.mock ?? previous.mock,
    data_source: payload.data_source || previous.data_source || 'websocket-runtime',
    trace_id: payload.trace_id ?? previous.trace_id ?? '',
  }
}

function explicitFallback<T>(value: T): T {
  const result = structuredClone(value) as T & {
    data_source?: string
    mock?: boolean
    quality?: DashboardQuality
    trace_id?: string
  }
  result.data_source = 'frontend-explicit-fallback'
  result.mock = true
  result.quality = 'mock'
  result.trace_id = ''
  return result as T
}

export const useSignalsStore = defineStore('signals', {
  state: () => ({
    dashboard: explicitFallback(fallbackSignalDashboard) as SignalDashboardSummary,
    curveConfig: explicitFallback(fallbackCurveConfig) as CurveConfig,
    curveTimeseries: explicitFallback(fallbackCurveTimeseries) as CurveTimeseries,
    replay: fallbackReplayMetadata as ReplayMetadata,
    faultEvents: fallbackFaultEvents as FaultEvent[],
    replayError: '',
    backendOnline: true,
    offline: false,
    error: '',
    wsBound: false,
    curvePaused: false,
    pendingCurveTimeseries: undefined as CurveTimeseries | undefined,
    pendingRequests: 0,
  }),
  getters: {
    loading: (state) => state.pendingRequests > 0,
  },
  actions: {
    async loadDashboard() {
      this.pendingRequests += 1
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
      } finally { this.pendingRequests = Math.max(0, this.pendingRequests - 1) }
    },
    async loadCurveConfig() {
      this.pendingRequests += 1
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
      } finally { this.pendingRequests = Math.max(0, this.pendingRequests - 1) }
    },
    async loadCurveTimeseries(query = '') {
      this.pendingRequests += 1
      try {
        this.curveTimeseries = await apiGet<CurveTimeseries>(`/signals/timeseries${query}`)
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.curveTimeseries = explicitFallback(fallbackCurveTimeseries)
          this.offline = true
        }
      } finally { this.pendingRequests = Math.max(0, this.pendingRequests - 1) }
    },
    async loadReplay(sessionId: string) {
      if (!sessionId.trim()) {
        this.replayError = '历史模式缺少检测会话编号'
        return false
      }
      this.pendingRequests += 1
      try {
        this.replay = await apiGet<ReplayMetadata>(`/test-sessions/${encodeURIComponent(sessionId)}/replay`)
        this.replayError = ''
        return true
      } catch (error) {
        this.replayError = formatApiError(error)
        if (isNetworkError(error)) {
          this.replay = structuredClone(fallbackReplayMetadata)
          this.offline = true
        }
        return false
      } finally { this.pendingRequests = Math.max(0, this.pendingRequests - 1) }
    },
    async loadFaultEvents(sessionId: string) {
      if (!sessionId.trim()) {
        this.replayError = '历史模式缺少检测会话编号'
        return false
      }
      this.pendingRequests += 1
      try {
        this.faultEvents = await apiGet<FaultEvent[]>(`/test-sessions/${encodeURIComponent(sessionId)}/fault-events`)
        return true
      } catch (error) {
        this.replayError = formatApiError(error)
        if (isNetworkError(error)) {
          this.faultEvents = structuredClone(fallbackFaultEvents)
          this.offline = true
        }
        return false
      } finally { this.pendingRequests = Math.max(0, this.pendingRequests - 1) }
    },
    bindWebSocket() {
      if (this.wsBound) return
      this.wsBound = true
      wsClient.on('signals.dashboard', (payload) => {
        this.dashboard = normalizeDashboardPayload(payload as Partial<SignalDashboardSummary>, this.dashboard)
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
    resetHistoryState() {
      this.replay = structuredClone(fallbackReplayMetadata)
      this.replay.session_id = ''
      this.faultEvents = []
      this.replayError = ''
    },
  },
})
