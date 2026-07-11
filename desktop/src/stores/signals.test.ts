import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fallbackCurveTimeseries, fallbackSignalDashboard } from '../mocks/fallbackData'

const websocketCallbacks = vi.hoisted(() => new Map<string, (payload: unknown) => void>())
const apiGet = vi.hoisted(() => vi.fn())
const isNetworkError = vi.hoisted(() => vi.fn(() => true))

vi.mock('../api/http', () => ({
  apiGet,
  isNetworkError,
  formatApiError: () => 'offline',
}))
vi.mock('../api/websocket', () => ({
  wsClient: {
    on: vi.fn((topic: string, callback: (payload: unknown) => void) => {
      websocketCallbacks.set(topic, callback)
      return vi.fn()
    }),
  },
}))

describe('signals store', () => {
  beforeEach(() => {
    websocketCallbacks.clear()
    apiGet.mockReset()
    isNetworkError.mockReturnValue(true)
    setActivePinia(createPinia())
  })

  it('applies timeseries batches directly and honors pause before flushing', async () => {
    const { useSignalsStore } = await import('./signals')
    const store = useSignalsStore()
    store.bindWebSocket()
    const batch = structuredClone(fallbackCurveTimeseries)
    batch.updated_at = '2030-01-01T00:00:00Z'

    store.setCurvePaused(true)
    websocketCallbacks.get('signals.timeseries.batch')?.(batch)
    expect(store.curveTimeseries.updated_at).not.toBe(batch.updated_at)
    store.setCurvePaused(false)
    expect(store.curveTimeseries.updated_at).toBe(batch.updated_at)
  })

  it('uses an explicit mock dashboard only on a network failure', async () => {
    const { useSignalsStore } = await import('./signals')
    const store = useSignalsStore()
    apiGet.mockRejectedValueOnce(new Error('offline'))

    await store.loadDashboard()

    expect(store.offline).toBe(true)
    expect(store.backendOnline).toBe(false)
    expect(store.dashboard.mock).toBe(true)
    expect(store.dashboard.data_source).toBe('frontend-explicit-fallback')
    expect(store.dashboard.status.overall).toBe(fallbackSignalDashboard.status.overall)
  })
})
