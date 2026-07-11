import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 3

  readonly sent: string[] = []
  readyState = FakeWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  send(payload: string) { this.sent.push(payload) }
  open() { this.readyState = FakeWebSocket.OPEN; this.onopen?.() }
  receive(payload: unknown) { this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>) }
  close() { this.readyState = FakeWebSocket.CLOSED; this.onclose?.() }
}

describe('WsClient', () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.resetModules()
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeWebSocket)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('uses one socket, synchronizes topics, and unsubscribes the final listener', async () => {
    const { WsClient } = await import('./websocket')
    const client = new WsClient()
    const one = vi.fn()
    const two = vi.fn()
    const stopOne = client.on('signals.current', one)
    const stopTwo = client.on('signals.current', two)

    expect(FakeWebSocket.instances).toHaveLength(1)
    const socket = FakeWebSocket.instances[0]
    socket.open()
    expect(socket.sent.map((entry) => JSON.parse(entry))).toContainEqual({ action: 'subscribe', topics: ['signals.current'] })

    socket.receive({ topic: 'signals.current', payload: { quality: 'good' } })
    expect(one).toHaveBeenCalledWith({ quality: 'good' })
    expect(two).toHaveBeenCalledWith({ quality: 'good' })

    stopOne()
    expect(socket.sent.map((entry) => JSON.parse(entry))).not.toContainEqual({ action: 'unsubscribe', topics: ['signals.current'] })
    stopTwo()
    expect(socket.sent.map((entry) => JSON.parse(entry))).toContainEqual({ action: 'unsubscribe', topics: ['signals.current'] })
  })

  it('reconnects once with bounded exponential backoff after an unexpected close', async () => {
    const { WsClient } = await import('./websocket')
    const client = new WsClient()
    client.on('can.statistics', vi.fn())
    const first = FakeWebSocket.instances[0]
    first.open()
    first.close()

    expect(client.connectionState).toBe('reconnecting')
    vi.advanceTimersByTime(499)
    expect(FakeWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
