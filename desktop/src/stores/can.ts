import { defineStore } from 'pinia'
import { apiGet, formatApiError, isNetworkError } from '../api/http'
import type { CanDecodedFrame, CanLatestFrame, CanMonitorStatistics } from '../api/types'
import { wsClient } from '../api/websocket'
import { fallbackCanDecoded, fallbackCanLatestFrames, fallbackCanMonitorStatistics } from '../mocks/fallbackData'

type SortMode = 'last_seen_desc' | 'can_id_asc' | 'can_id_desc'
type ChannelFilter = 'ALL' | 'CAN1' | 'CAN2'
type DirectionFilter = 'ALL' | 'RX' | 'TX'
type RadixMode = 'Hex' | 'Dec'

interface RawFramePayload {
  timestamp_ns?: number
  timestamp?: string
  channel?: string
  direction?: string
  can_id?: number
  can_id_hex?: string
  frame_type?: string
  dlc?: number
  data_hex?: string
  message_name?: string
  parse_status?: string
  status?: string
  period_ms?: number | string
  source_session?: string
  frame_count?: number
  last_seen_ms?: number
}

function normalizeCanIdHex(value: string | number | undefined): string {
  if (typeof value === 'number' && Number.isFinite(value)) return `0x${value.toString(16).toUpperCase()}`
  const text = String(value || '').trim()
  if (!text) return '0x0'
  if (text.toLowerCase().startsWith('0x')) return `0x${text.slice(2).toUpperCase()}`
  const parsed = Number.parseInt(text, 10)
  return Number.isFinite(parsed) ? `0x${parsed.toString(16).toUpperCase()}` : text.toUpperCase()
}

function parseCanId(value: string | number | undefined): number {
  if (typeof value === 'number') return value
  const text = String(value || '').trim()
  if (!text) return 0
  return Number.parseInt(text.toLowerCase().startsWith('0x') ? text.slice(2) : text, text.toLowerCase().startsWith('0x') ? 16 : 10) || 0
}

function formatTimestamp(timestampNs?: number, fallback?: string): string {
  if (!timestampNs) return fallback || new Date().toTimeString().slice(0, 12)
  const ms = Math.floor(timestampNs / 1_000_000)
  const micros = Math.floor((timestampNs % 1_000_000) / 1_000)
  const date = new Date(ms)
  const h = String(date.getHours()).padStart(2, '0')
  const m = String(date.getMinutes()).padStart(2, '0')
  const s = String(date.getSeconds()).padStart(2, '0')
  const milli = String(date.getMilliseconds()).padStart(3, '0')
  return `${h}:${m}:${s}.${milli}.${String(micros).padStart(3, '0')}`
}

function statusToUi(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized.includes('timeout') || normalized.includes('超时')) return '超时'
  if (normalized.includes('error') || normalized.includes('错误') || normalized.includes('fail')) return '错误'
  if (normalized.includes('正常') || normalized.includes('ok') || normalized.includes('normal') || normalized === 'decoded') return '正常'
  return status || '正常'
}

function frameKey(frame: Pick<CanLatestFrame, 'can_id_hex'>): string {
  return normalizeCanIdHex(frame.can_id_hex)
}

function fallbackStatistics(): CanMonitorStatistics {
  const result = structuredClone(fallbackCanMonitorStatistics)
  result.data_source = 'frontend-explicit-fallback'
  result.mock = true
  result.quality = 'mock'
  result.trace_id = ''
  result.fps_trend = []
  result.period_jitter = []
  result.can_id_distribution = []
  result.error_summary = { timeout_count: 0, error_frame_count: 0, protocol_error_count: 0 }
  result.footer_status = { ...result.footer_status, recording: false, uptime: '-', buffer_usage: 0, rx_fps: 0, tx_fps: 0 }
  return result
}

export const useCanStore = defineStore('can', {
  state: () => ({
    latestFramesById: {} as Record<string, CanLatestFrame>,
    pendingFramesById: {} as Record<string, CanLatestFrame>,
    decodedById: {} as Record<string, CanDecodedFrame>,
    statistics: fallbackStatistics(),
    selectedCanId: '0x121',
    paused: false,
    backendOnline: true,
    offline: false,
    loading: false,
    error: '',
    dataSource: 'initial',
    quality: 'unavailable' as 'good' | 'degraded' | 'unavailable' | 'mock',
    sortMode: 'last_seen_desc' as SortMode,
    filters: {
      channel: 'ALL' as ChannelFilter,
      canId: '',
      messageName: '',
      direction: 'ALL' as DirectionFilter,
      status: 'all',
      timeRange: 'realtime',
      radix: 'Hex' as RadixMode,
    },
    wsBound: false,
  }),
  getters: {
    latestFrames(state): CanLatestFrame[] {
      const canIdFilter = state.filters.canId.trim().toLowerCase()
      const messageFilter = state.filters.messageName.trim().toLowerCase()
      const frames = Object.values(state.latestFramesById).filter((frame) => {
        if (state.filters.channel !== 'ALL' && frame.channel !== state.filters.channel) return false
        if (state.filters.direction !== 'ALL' && frame.direction.toUpperCase() !== state.filters.direction) return false
        if (state.filters.status !== 'all' && frame.status !== ({ normal: '正常', timeout: '超时', error: '错误' } as Record<string, string>)[state.filters.status]) return false
        if (canIdFilter) {
          const dec = String(frame.can_id)
          const hex = frame.can_id_hex.toLowerCase()
          if (!hex.includes(canIdFilter) && !dec.includes(canIdFilter.replace(/^0x/, ''))) return false
        }
        if (messageFilter && !frame.message_name.toLowerCase().includes(messageFilter)) return false
        return true
      })
      return frames.sort((a, b) => {
        if (state.sortMode === 'can_id_asc') return a.can_id - b.can_id
        if (state.sortMode === 'can_id_desc') return b.can_id - a.can_id
        return a.last_seen_ms - b.last_seen_ms
      })
    },
    selectedFrame(state): CanLatestFrame | undefined {
      return state.latestFramesById[state.selectedCanId] || Object.values(state.latestFramesById)[0]
    },
    selectedDecoded(state): CanDecodedFrame | undefined {
      return state.decodedById[state.selectedCanId]
    },
  },
  actions: {
    initFallback() {
      this.latestFramesById = Object.fromEntries(fallbackCanLatestFrames.map((frame) => [frameKey(frame), frame]))
      this.decodedById = { ...fallbackCanDecoded }
      this.statistics = fallbackStatistics()
      this.dataSource = 'frontend-explicit-fallback'
      this.quality = 'mock'
      if (!this.latestFramesById[this.selectedCanId]) this.selectedCanId = '0x121'
    },
    bindWebSocket() {
      if (this.wsBound) return
      this.wsBound = true
      wsClient.on('can.latest_frames.batch', (payload) => {
        const items = (payload as { items?: RawFramePayload[] }).items || []
        for (const item of items) this.upsertLatestFrame(item)
      })
      wsClient.on('can.raw_frames.batch', (payload) => {
        const items = (payload as { items?: RawFramePayload[] }).items || []
        for (const item of items) this.upsertLatestFrame(item)
      })
      wsClient.on('can.monitor_statistics', (payload) => {
        this.statistics = payload as CanMonitorStatistics
      })
    },
    async loadLatest() {
      this.loading = true
      const params = new URLSearchParams()
      params.set('channel', this.filters.channel)
      if (this.filters.canId) params.set('can_id', this.filters.canId)
      if (this.filters.messageName) params.set('message_name', this.filters.messageName)
      params.set('direction', this.filters.direction)
      params.set('status', this.filters.status)
      params.set('sort', this.sortMode)
      try {
        const data = await apiGet<{ items: CanLatestFrame[]; data_source?: string; quality?: 'good' | 'degraded' | 'unavailable' | 'mock' }>(`/can/frames/latest?${params.toString()}`)
        this.latestFramesById = Object.fromEntries(data.items.map((frame) => [frameKey(frame), frame]))
        this.backendOnline = true
        this.offline = false
        this.error = ''
        this.dataSource = data.data_source || 'runtime'
        this.quality = data.quality || (data.items.length ? 'good' : 'unavailable')
        if (!this.selectedCanId && data.items[0]) this.selectedCanId = frameKey(data.items[0])
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.backendOnline = false
          this.offline = true
          this.initFallback()
        } else {
          this.backendOnline = true
          this.offline = false
        }
      } finally {
        this.loading = false
      }
    },
    async loadDecoded(canId?: string, channel?: string) {
      const key = normalizeCanIdHex(canId || this.selectedCanId)
      this.selectedCanId = key
      const query = channel ? `?channel=${encodeURIComponent(channel)}` : ''
      try {
        const decoded = await apiGet<CanDecodedFrame>(`/can/frames/latest/${encodeURIComponent(key)}/decoded${query}`)
        this.decodedById[key] = decoded
        this.backendOnline = true
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error) && fallbackCanDecoded[key]) {
          this.decodedById[key] = fallbackCanDecoded[key]
          this.offline = true
          this.quality = 'mock'
        } else {
          delete this.decodedById[key]
        }
      }
    },
    async loadStatistics() {
      try {
        this.statistics = await apiGet<CanMonitorStatistics>('/can/statistics/monitor')
      } catch (error) {
        this.error = formatApiError(error)
        if (isNetworkError(error)) {
          this.statistics = fallbackStatistics()
          this.offline = true
        }
      }
    },
    selectFrame(frame: CanLatestFrame) {
      this.selectedCanId = frameKey(frame)
      void this.loadDecoded(this.selectedCanId, frame.channel)
    },
    upsertLatestFrame(payload: RawFramePayload) {
      const canIdHex = normalizeCanIdHex(payload.can_id_hex || payload.can_id)
      const previous = this.latestFramesById[canIdHex]
      const frame: CanLatestFrame = {
        timestamp: formatTimestamp(payload.timestamp_ns, payload.timestamp),
        channel: payload.channel || previous?.channel || 'CAN1',
        direction: String(payload.direction || previous?.direction || 'RX').toUpperCase(),
        can_id: parseCanId(payload.can_id ?? canIdHex),
        can_id_hex: canIdHex,
        frame_type: payload.frame_type || previous?.frame_type || '标准帧',
        dlc: Number(payload.dlc ?? previous?.dlc ?? 8),
        data_hex: payload.data_hex || previous?.data_hex || '',
        message_name: payload.message_name || previous?.message_name || '-',
        period_ms: payload.period_ms ?? previous?.period_ms ?? '-',
        status: statusToUi(payload.status || payload.parse_status),
        source_session: payload.source_session || previous?.source_session || '-',
        frame_count: Number(payload.frame_count ?? (previous?.frame_count || 0) + 1),
        last_seen_ms: Number(payload.last_seen_ms ?? 0),
      }
      if (this.paused) {
        this.pendingFramesById[canIdHex] = frame
        return
      }
      this.latestFramesById[canIdHex] = frame
      if (this.selectedCanId === canIdHex && this.decodedById[canIdHex]) {
        this.decodedById[canIdHex] = { ...this.decodedById[canIdHex], frame }
      }
    },
    setPaused(value: boolean) {
      this.paused = value
      if (!value) this.flushPending()
    },
    flushPending() {
      for (const frame of Object.values(this.pendingFramesById)) this.latestFramesById[frameKey(frame)] = frame
      this.pendingFramesById = {}
    },
    cycleSortByCanId() {
      if (this.sortMode === 'last_seen_desc') this.sortMode = 'can_id_asc'
      else if (this.sortMode === 'can_id_asc') this.sortMode = 'can_id_desc'
      else this.sortMode = 'last_seen_desc'
    },
    clearDisplay() {
      this.latestFramesById = {}
      this.pendingFramesById = {}
    },
  },
})
