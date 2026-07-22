const { EventEmitter } = require('node:events')
const { spawn } = require('node:child_process')
const { randomBytes } = require('node:crypto')
const dgram = require('node:dgram')
const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')

const LOOPBACK = '127.0.0.1'

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function reserveTcpPort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer()
    server.unref()
    server.once('error', reject)
    server.listen(0, LOOPBACK, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close((error) => error ? reject(error) : resolve(port))
    })
  })
}

async function udpPortAvailable(port) {
  return await new Promise((resolve) => {
    const socket = dgram.createSocket('udp4')
    socket.unref()
    socket.once('error', () => {
      socket.close()
      resolve(false)
    })
    socket.bind(port, LOOPBACK, () => socket.close(() => resolve(true)))
  })
}

async function chooseUdpPortBase() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const base = 20000 + Math.floor(Math.random() * 30000)
    const ports = [base, base + 1, base + 100, base + 101]
    if ((await Promise.all(ports.map(udpPortAvailable))).every(Boolean)) return base
  }
  throw new Error('unable to allocate a loopback-only CAN port range')
}

function redact(text, secrets) {
  let safe = String(text)
  for (const secret of secrets) {
    if (secret) safe = safe.split(secret).join('[REDACTED]')
  }
  return safe
}

class SidecarSupervisor extends EventEmitter {
  constructor(options) {
    super()
    this.options = {
      startupTimeoutMs: 30000,
      shutdownTimeoutMs: 8000,
      maxRestarts: 3,
      ...options,
    }
    this.child = undefined
    this.connection = undefined
    this.stopping = false
    this.ready = false
    this.restartCount = 0
    this.startPromise = undefined
    this.restartTimer = undefined
    fs.mkdirSync(path.dirname(this.options.logPath), { recursive: true })
  }

  snapshot() {
    return {
      apiBase: this.connection ? `http://${LOOPBACK}:${this.connection.port}/api/v1` : '',
      wsUrl: this.connection ? `ws://${LOOPBACK}:${this.connection.port}/ws` : '',
      sidecarCredential: this.connection?.credential || '',
      runtimeProfile: this.options.profile,
      ready: this.ready,
      packaged: Boolean(this.options.packaged),
      releaseChannel: this.options.releaseChannel || 'development',
    }
  }

  async start() {
    if (this.startPromise) return await this.startPromise
    this.stopping = false
    this.startPromise = this._startAttempt()
    try {
      return await this.startPromise
    } catch (error) {
      this._scheduleRestart()
      throw error
    } finally {
      this.startPromise = undefined
    }
  }

  async _startAttempt() {
    const port = await reserveTcpPort()
    const canPortBase = await chooseUdpPortBase()
    const credential = randomBytes(32).toString('base64url')
    this.connection = { port, canPortBase, credential }
    this.ready = false
    const env = {
      ...process.env,
      CHASSIS_BACKEND_HOST: LOOPBACK,
      CHASSIS_BACKEND_PORT: String(port),
      CHASSIS_RUNTIME_PROFILE: this.options.profile,
      CHASSIS_CONFIG_DIR: this.options.configDir,
      CHASSIS_ASSETS_DIR: this.options.assetsDir,
      CHASSIS_DATA_DIR: this.options.dataRoot,
      CHASSIS_ALLOWED_FILE_ROOT: this.options.dataRoot,
      CHASSIS_LOOPBACK_CAN_PORT_BASE: String(canPortBase),
      CHASSIS_ALLOWED_UI_ORIGINS: 'http://127.0.0.1:5173,http://localhost:5173',
      CHASSIS_ALLOW_FILE_ORIGIN: '1',
      CHASSIS_SIDECAR_TOKEN: credential,
      CHASSIS_REPORT_FONT: this.options.reportFont,
      CHASSIS_PRINT_BACKEND: process.env.CHASSIS_PRINT_BACKEND || 'virtual',
      PYTHONUTF8: '1',
      PYTHONUNBUFFERED: '1',
    }
    const child = spawn(this.options.executable, this.options.args || [], {
      cwd: this.options.cwd,
      env,
      windowsHide: true,
      shell: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    this.child = child
    const append = (source, chunk) => {
      const line = `${new Date().toISOString()} ${source} ${redact(chunk, [credential])}`
      fs.appendFileSync(this.options.logPath, line, 'utf8')
    }
    child.stdout?.on('data', (chunk) => append('stdout', chunk))
    child.stderr?.on('data', (chunk) => append('stderr', chunk))
    child.once('error', (error) => this.emit('diagnostic', { code: 'SIDECAR_SPAWN_FAILED', message: error.message }))
    child.once('exit', (code, signal) => this._onExit(child, code, signal))
    try {
      await this._waitUntilReady(child)
      this.ready = true
      this.emit('ready', this.snapshot())
      return this.snapshot()
    } catch (error) {
      if (this.child === child && child.exitCode === null) child.kill()
      throw error
    }
  }

  async _waitUntilReady(child) {
    const deadline = Date.now() + this.options.startupTimeoutMs
    let lastError = 'no response'
    while (Date.now() < deadline) {
      if (child.exitCode !== null) throw new Error(`backend sidecar exited during startup (${child.exitCode})`)
      try {
        const health = await fetch(`http://${LOOPBACK}:${this.connection.port}/api/v1/health`, { signal: AbortSignal.timeout(1000) })
        if (health.ok) {
          const ready = await fetch(`http://${LOOPBACK}:${this.connection.port}/internal/sidecar/readiness`, {
            headers: { 'X-Chassis-Sidecar': this.connection.credential },
            signal: AbortSignal.timeout(1000),
          })
          if (ready.ok) return
          lastError = `readiness HTTP ${ready.status}`
        } else {
          lastError = `health HTTP ${health.status}`
        }
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error)
      }
      await delay(250)
    }
    throw new Error(`backend readiness timed out: ${lastError}`)
  }

  _onExit(child, code, signal) {
    if (this.child !== child) return
    this.child = undefined
    this.ready = false
    if (this.stopping) return
    this.emit('diagnostic', { code: 'SIDECAR_EXITED', message: `backend exited (${code ?? signal ?? 'unknown'})` })
    this._scheduleRestart()
  }

  _scheduleRestart() {
    if (this.stopping || this.restartTimer) return
    if (this.restartCount >= this.options.maxRestarts) {
      this.emit('failed', { code: 'SIDECAR_RESTART_LIMIT', message: 'backend restart limit reached' })
      return
    }
    this.restartCount += 1
    const delayMs = Math.min(4000, 500 * 2 ** (this.restartCount - 1))
    this.restartTimer = setTimeout(async () => {
      this.restartTimer = undefined
      try {
        await this.start()
      } catch (error) {
        this.emit('diagnostic', { code: 'SIDECAR_RESTART_FAILED', message: error instanceof Error ? error.message : String(error) })
        this._scheduleRestart()
      }
    }, delayMs)
  }

  async stop() {
    this.stopping = true
    this.ready = false
    if (this.restartTimer) clearTimeout(this.restartTimer)
    this.restartTimer = undefined
    const child = this.child
    if (!child || child.exitCode !== null) return { graceful: true }
    try {
      await fetch(`http://${LOOPBACK}:${this.connection.port}/internal/sidecar/shutdown`, {
        method: 'POST',
        headers: { 'X-Chassis-Sidecar': this.connection.credential },
        signal: AbortSignal.timeout(1500),
      })
    } catch {
      // The bounded wait below decides whether a forceful termination is required.
    }
    const exited = await Promise.race([
      new Promise((resolve) => child.once('exit', () => resolve(true))),
      delay(this.options.shutdownTimeoutMs).then(() => false),
    ])
    if (exited) return { graceful: true }
    child.kill()
    await Promise.race([new Promise((resolve) => child.once('exit', resolve)), delay(2000)])
    return { graceful: false }
  }
}

module.exports = { SidecarSupervisor, reserveTcpPort, chooseUdpPortBase, redact }
