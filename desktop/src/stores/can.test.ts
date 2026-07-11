import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/http', () => ({
  apiGet: vi.fn(),
  isNetworkError: () => true,
  formatApiError: () => 'offline',
}))
vi.mock('../api/websocket', () => ({ wsClient: { on: vi.fn() } }))

describe('CAN store aggregation', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('upserts a CAN ID and holds UI updates while paused', async () => {
    const { useCanStore } = await import('./can')
    const store = useCanStore()
    store.upsertLatestFrame({ can_id_hex: '0x77', channel: 'CAN1', data_hex: '00', frame_count: 1, last_seen_ms: 20 })
    expect(store.latestFramesById['0x77'].frame_count).toBe(1)

    store.setPaused(true)
    store.upsertLatestFrame({ can_id_hex: '0x77', channel: 'CAN2', data_hex: 'FF', frame_count: 2, last_seen_ms: 3 })
    expect(store.latestFramesById['0x77'].data_hex).toBe('00')
    store.setPaused(false)
    expect(store.latestFramesById['0x77'].data_hex).toBe('FF')
    expect(store.latestFramesById['0x77'].channel).toBe('CAN2')
  })

  it('cycles CAN-ID sorting through ascending, descending, and freshness order', async () => {
    const { useCanStore } = await import('./can')
    const store = useCanStore()
    store.upsertLatestFrame({ can_id_hex: '0x121', channel: 'CAN1', frame_count: 1, last_seen_ms: 30 })
    store.upsertLatestFrame({ can_id_hex: '0x51', channel: 'CAN1', frame_count: 1, last_seen_ms: 10 })

    store.cycleSortByCanId()
    expect(store.latestFrames.map((frame) => frame.can_id_hex)).toEqual(['0x51', '0x121'])
    store.cycleSortByCanId()
    expect(store.latestFrames.map((frame) => frame.can_id_hex)).toEqual(['0x121', '0x51'])
    store.cycleSortByCanId()
    expect(store.sortMode).toBe('last_seen_desc')
  })
})
