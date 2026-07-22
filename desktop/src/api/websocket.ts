import { AUTH_EXPIRED_EVENT, getApiToken, getRuntimeConnection, setApiToken } from './http'

type Handler = (payload: unknown) => void
type ConnectionState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'auth-required' | 'closed'
type StatusHandler = (state: ConnectionState) => void

export class WsClient {
  ws?: WebSocket
  private readonly handlers = new Map<string, Set<Handler>>()
  private readonly statusHandlers = new Set<StatusHandler>()
  private reconnectTimer?: number
  private retryAttempt = 0
  private shouldReconnect = true
  private state: ConnectionState = 'idle'

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = undefined
    const token = getApiToken()
    if (!token) {
      this.shouldReconnect = false
      this.setState('auth-required')
      return
    }
    this.shouldReconnect = true
    this.setState(this.retryAttempt ? 'reconnecting' : 'connecting')
    const runtime = getRuntimeConnection()
    if (!runtime.ready || !runtime.wsUrl) {
      this.shouldReconnect = false
      this.setState('closed')
      return
    }
    const protocols = ['chassis-session', `chassis-token.${token}`]
    if (runtime.sidecarCredential) protocols.push(`chassis-sidecar.${runtime.sidecarCredential}`)
    const socket = new WebSocket(runtime.wsUrl, protocols)
    this.ws = socket
    socket.onopen = () => {
      if (this.ws !== socket) return
      this.retryAttempt = 0
      this.setState('open')
      this.syncSubscriptions()
    }
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { topic?: string; payload?: unknown }
        if (!msg.topic) return
        for (const handler of this.handlers.get(msg.topic) || []) handler(msg.payload)
      } catch {
        // Invalid messages are ignored; a malformed frame must not tear down the renderer.
      }
    }
    socket.onerror = () => {
      // onclose schedules the retry. Keeping this handler side-effect free prevents duplicate retries.
    }
    socket.onclose = (event) => {
      if (this.ws === socket) this.ws = undefined
      if (event.code === 4401) {
        this.shouldReconnect = false
        setApiToken('')
        this.setState('auth-required')
        window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: { code: 'SESSION_EXPIRED' } }))
        return
      }
      if (!this.shouldReconnect) {
        this.setState('closed')
        return
      }
      this.scheduleReconnect()
    }
  }

  close() {
    this.shouldReconnect = false
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = undefined
    const socket = this.ws
    this.ws = undefined
    socket?.close(1000, 'application shutdown')
    this.setState('closed')
  }

  suspendForAuth() {
    this.close()
    this.setState('auth-required')
  }

  resumeAfterAuth() {
    this.shouldReconnect = true
    this.retryAttempt = 0
    this.connect()
  }

  send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(data))
  }

  on(topic: string, handler: Handler): () => void {
    const handlers = this.handlers.get(topic) || new Set<Handler>()
    const first = handlers.size === 0
    handlers.add(handler)
    this.handlers.set(topic, handlers)
    if (first) this.send({ action: 'subscribe', topics: [topic] })
    this.connect()
    return () => this.off(topic, handler)
  }

  off(topic: string, handler?: Handler) {
    const handlers = this.handlers.get(topic)
    if (!handlers) return
    if (handler) handlers.delete(handler)
    else handlers.clear()
    if (handlers.size) return
    this.handlers.delete(topic)
    this.send({ action: 'unsubscribe', topics: [topic] })
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler)
    handler(this.state)
    return () => this.statusHandlers.delete(handler)
  }

  get connectionState(): ConnectionState {
    return this.state
  }

  private syncSubscriptions() {
    const topics = [...this.handlers.keys()]
    if (topics.length) this.send({ action: 'subscribe', topics })
  }

  private scheduleReconnect() {
    if (this.reconnectTimer || !this.shouldReconnect) return
    this.retryAttempt += 1
    const delay = Math.min(15_000, 500 * 2 ** Math.min(this.retryAttempt - 1, 5))
    this.setState('reconnecting')
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = undefined
      this.connect()
    }, delay)
  }

  private setState(state: ConnectionState) {
    this.state = state
    for (const handler of this.statusHandlers) handler(state)
  }
}

export const wsClient = new WsClient()
