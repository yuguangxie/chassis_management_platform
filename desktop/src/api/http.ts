export const AUTH_EXPIRED_EVENT = 'chassis:auth-expired'

export interface DesktopRuntimeConnection {
  apiBase: string
  wsUrl: string
  sidecarCredential: string
  runtimeProfile: string
  ready: boolean
  packaged: boolean
  releaseChannel: string
}

export function getRuntimeConnection(): DesktopRuntimeConnection {
  const desktop = window.chassisRuntime?.getConnection()
  if (desktop) return desktop
  if (import.meta.env.PROD) {
    return {
      apiBase: '',
      wsUrl: '',
      sidecarCredential: '',
      runtimeProfile: 'mock',
      ready: false,
      packaged: true,
      releaseChannel: 'runtime-bridge-unavailable',
    }
  }
  return {
    apiBase: import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8800/api/v1',
    wsUrl: import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8800/ws',
    sidecarCredential: '',
    runtimeProfile: import.meta.env.MODE === 'production' ? 'mock' : 'dev',
    ready: true,
    packaged: false,
    releaseChannel: 'development',
  }
}

export interface ApiErrorPayload {
  code: string
  message: string
  details: unknown
  trace_id: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly traceId: string
  readonly network: boolean

  constructor(payload: Partial<ApiErrorPayload> & { message: string }, status = 0, network = false) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code || (network ? 'NETWORK_ERROR' : 'HTTP_ERROR')
    this.details = payload.details ?? {}
    this.traceId = payload.trace_id || ''
    this.network = network
  }
}

export function getApiToken(): string {
  return window.sessionStorage.getItem('chassis_api_token') || ''
}

export function setApiToken(token: string): void {
  if (token) window.sessionStorage.setItem('chassis_api_token', token)
  else window.sessionStorage.removeItem('chassis_api_token')
}

function authHeaders(json = false): HeadersInit {
  const token = getApiToken()
  const sidecarCredential = getRuntimeConnection().sidecarCredential
  return {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(sidecarCredential ? { 'X-Chassis-Sidecar': sidecarCredential } : {}),
  }
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const runtime = getRuntimeConnection()
  if (!runtime.ready || !runtime.apiBase) {
    throw new ApiError({ code: 'SIDECAR_NOT_READY', message: '本地安全服务未就绪', details: {} }, 0, true)
  }
  try {
    return await fetch(`${runtime.apiBase}${path}`, init)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new ApiError({ code: 'NETWORK_ERROR', message: `后端不可达：${message}`, details: {} }, 0, true)
  }
}

async function parseError(res: Response): Promise<ApiError> {
  const traceFromHeader = res.headers.get('X-Trace-Id') || ''
  let body: unknown
  try {
    body = await res.json()
  } catch {
    body = undefined
  }
  const record = body && typeof body === 'object' ? body as Record<string, unknown> : {}
  const legacy = record.detail && typeof record.detail === 'object'
    ? record.detail as Record<string, unknown>
    : {}
  const code = String(record.code || legacy.code || `HTTP_${res.status}`)
  const message = String(record.message || legacy.message || res.statusText || '请求失败')
  const details = record.details ?? legacy.details ?? {}
  const traceId = String(record.trace_id || legacy.trace_id || traceFromHeader)
  return new ApiError({ code, message, details, trace_id: traceId }, res.status)
}

async function jsonRequest<T>(path: string, init: RequestInit): Promise<T> {
  const attemptedAuthorization = new Headers(init.headers).get('Authorization') || ''
  const attemptedToken = attemptedAuthorization.startsWith('Bearer ') ? attemptedAuthorization.slice(7) : ''
  const res = await request(path, init)
  if (!res.ok) {
    const error = await parseError(res)
    if (
      res.status === 401
      && attemptedToken
      && getApiToken() === attemptedToken
      && !['/auth/login', '/auth/unlock', '/auth/bootstrap'].includes(path)
    ) {
      setApiToken('')
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: { code: error.code } }))
    }
    throw error
  }
  if (res.status === 204) return undefined as T
  return await res.json() as T
}

export function isNetworkError(error: unknown): boolean {
  return error instanceof ApiError && error.network
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.traceId ? `${error.message}（追踪编号：${error.traceId}）` : error.message
  }
  return error instanceof Error ? error.message : String(error)
}

export async function apiGet<T>(path: string): Promise<T> {
  return jsonRequest<T>(path, { headers: authHeaders() })
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  return jsonRequest<T>(path, { method: 'POST', headers: authHeaders(true), body: JSON.stringify(body) })
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return jsonRequest<T>(path, { method: 'PUT', headers: authHeaders(true), body: JSON.stringify(body) })
}

export async function apiDelete<T>(path: string): Promise<T> {
  return jsonRequest<T>(path, { method: 'DELETE', headers: authHeaders() })
}

function contentDispositionFilename(value: string | null): string | undefined {
  if (!value) return undefined
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (utf8) return decodeURIComponent(utf8)
  return value.match(/filename="?([^";]+)"?/i)?.[1]
}

export async function apiDownload(path: string, suggestedFilename?: string): Promise<{ filename: string; size: number }> {
  const res = await request(path, { headers: authHeaders() })
  if (!res.ok) throw await parseError(res)
  const blob = await res.blob()
  const filename = contentDispositionFilename(res.headers.get('Content-Disposition')) || suggestedFilename || 'download.bin'
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
  return { filename, size: blob.size }
}
