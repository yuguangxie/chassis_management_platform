const { app, BrowserWindow, Menu, ipcMain, session, shell } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const { SidecarSupervisor } = require('./sidecar.cjs')

Menu.setApplicationMenu(null)

const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) app.quit()

if (process.env.CHASSIS_PACKAGED_E2E === '1') {
  const isolatedUserData = process.env.CHASSIS_E2E_USER_DATA || ''
  if (!path.isAbsolute(isolatedUserData) || !path.basename(isolatedUserData).startsWith('chassis-eol-package-e2e-')) {
    throw new Error('packaged E2E requires a dedicated chassis-eol-package-e2e-* userData directory')
  }
  app.setPath('userData', isolatedUserData)
}

let mainWindow
let supervisor
let quitting = false
let applicationExitCode = 0
let awaitingSidecarRecovery = false

function resourceRoot() {
  return app.isPackaged ? process.resourcesPath : path.resolve(__dirname, '..', '..')
}

function dataRoot() {
  return path.join(app.getPath('userData'), 'data')
}

function readReleaseChannel(root) {
  try {
    const value = JSON.parse(fs.readFileSync(path.join(root, 'release-build.json'), 'utf8'))
    return value.release_label || (value.signed === true ? 'signed-nonreleasable' : 'unsigned-internal')
  } catch {
    return app.isPackaged ? 'unsigned-internal' : 'development'
  }
}

function sidecarOptions() {
  const root = resourceRoot()
  const packagedExecutable = path.join(root, 'backend-sidecar', 'chassis-eol-backend.exe')
  const developmentPython = process.env.CHASSIS_PYTHON || path.join(root, 'backend', '.venv', 'Scripts', 'python.exe')
  const executable = app.isPackaged ? packagedExecutable : developmentPython
  const args = app.isPackaged ? [] : ['-m', 'app.sidecar']
  const profile = process.env.CHASSIS_DESKTOP_RUNTIME_PROFILE || 'mock'
  if (!['mock', 'production'].includes(profile)) throw new Error('packaged desktop profile must be mock or production')
  return {
    executable,
    args,
    cwd: app.isPackaged ? path.dirname(packagedExecutable) : path.join(root, 'backend'),
    configDir: path.join(root, 'configs'),
    assetsDir: path.join(root, 'assets'),
    reportFont: path.join(root, 'assets', 'fonts', 'NotoSansCJKsc-Regular.otf'),
    dataRoot: dataRoot(),
    logPath: path.join(dataRoot(), 'logs', 'sidecar', 'sidecar.log'),
    profile,
    packaged: app.isPackaged,
    releaseChannel: readReleaseChannel(root),
    releaseManifest: path.join(root, 'release-build.json'),
  }
}

function runtimeSnapshot() {
  if (supervisor) return supervisor.snapshot()
  const apiBase = process.env.VITE_API_BASE || 'http://127.0.0.1:8800/api/v1'
  return {
    apiBase,
    wsUrl: process.env.VITE_WS_URL || apiBase.replace(/^http/, 'ws').replace(/\/api\/v1$/, '/ws'),
    sidecarCredential: '',
    runtimeProfile: process.env.CHASSIS_RUNTIME_PROFILE || 'dev',
    ready: true,
    packaged: false,
    releaseChannel: 'development',
  }
}

function writeRuntimeState(detail = {}) {
  const target = path.join(dataRoot(), 'logs', 'sidecar', 'runtime-state.json')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, `${JSON.stringify({
    timestamp_utc: new Date().toISOString(),
    ready: Boolean(supervisor?.ready),
    profile: supervisor?.options.profile || 'dev',
    endpoint: '127.0.0.1:dynamic',
    control_transmission: 'stopped',
    ...detail,
  }, null, 2)}\n`, 'utf8')
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1366,
    minHeight: 768,
    show: false,
    frame: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    backgroundColor: '#07111F',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  })
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (event, url) => {
    if (url !== win.webContents.getURL()) event.preventDefault()
  })
  win.once('ready-to-show', () => win.show())
  mainWindow = win
  return win
}

async function showDiagnostics(message) {
  const win = mainWindow || createWindow()
  await win.loadFile(path.join(__dirname, 'diagnostics.html'))
  win.setTitle(`启动诊断 - ${String(message).slice(0, 120)}`)
  win.show()
}

async function loadRenderer() {
  const win = mainWindow || createWindow()
  if (app.isPackaged) {
    await win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), { hash: '/login' })
  } else {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5173')
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(`${new URL(url).pathname} returned ${response.status}: ${JSON.stringify(body)}`)
  return body
}

async function runPackagedVerification() {
  if (process.env.CHASSIS_PACKAGED_E2E !== '1') return
  const output = process.env.CHASSIS_PACKAGED_E2E_OUTPUT
  if (!output || !path.isAbsolute(output)) throw new Error('CHASSIS_PACKAGED_E2E_OUTPUT must be absolute')
  fs.mkdirSync(output, { recursive: true })
  let restarted = false
  if (process.env.CHASSIS_E2E_CRASH_ONCE === '1') {
    const oldCredential = supervisor.snapshot().sidecarCredential
    const restartedReady = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('sidecar did not recover from injected crash')), 30000)
      supervisor.once('ready', (snapshot) => { clearTimeout(timer); resolve(snapshot) })
    })
    supervisor.child.kill()
    const recovered = await restartedReady
    restarted = recovered.sidecarCredential !== oldCredential
  }
  const runtime = supervisor.snapshot()
  const sidecarHeaders = { 'X-Chassis-Sidecar': runtime.sidecarCredential }
  const status = await requestJson(`${runtime.apiBase}/auth/bootstrap/status`, { headers: sidecarHeaders })
  if (!status.required) throw new Error('packaged verification requires a clean isolated database')
  const bootstrapSecret = fs.readFileSync(path.join(dataRoot(), 'auth', 'bootstrap-admin.secret'), 'utf8').trim()
  const password = `E2e-${require('node:crypto').randomBytes(18).toString('base64url')}9!`
  const sessionResult = await requestJson(`${runtime.apiBase}/auth/bootstrap`, {
    method: 'POST',
    headers: { ...sidecarHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify({ bootstrap_secret: bootstrapSecret, username: 'packaged-e2e-admin', password }),
  })
  const token = sessionResult.token
  await mainWindow.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(token)})`)
  await new Promise((resolve) => {
    mainWindow.webContents.once('did-finish-load', resolve)
    mainWindow.webContents.reload()
  })
  await mainWindow.webContents.executeJavaScript(`location.hash = '#/overview'`)
  await new Promise((resolve) => setTimeout(resolve, 600))
  const pages = [
    ['overview', '/overview'], ['network-config', '/network-config'], ['can-monitor', '/can-monitor'],
    ['signal-dashboard', '/signal-dashboard'], ['realtime-curve', '/realtime-curve'], ['manual-control', '/manual-control'],
    ['auto-test', '/auto-test'], ['alarm-diagnosis', '/alarm-diagnosis'], ['report-management', '/report-management'],
    ['history', '/history'], ['system-settings', '/system-settings'],
  ]
  const inspections = []
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    mainWindow.setSize(width, height)
    for (const [name, route] of pages) {
      await mainWindow.webContents.executeJavaScript(`location.hash = ${JSON.stringify(`#${route}`)}`)
      await new Promise((resolve) => setTimeout(resolve, 450))
      const inspection = await mainWindow.webContents.executeJavaScript(`({
        route: location.hash,
        page_scrollable: document.documentElement.scrollHeight > document.documentElement.clientHeight + 2,
        failed_fetch: document.body.innerText.includes('Failed to fetch'),
        text_length: document.body.innerText.length
      })`)
      const image = await mainWindow.capturePage()
      fs.writeFileSync(path.join(output, `${name}_${width}x${height}.png`), image.toPNG())
      inspections.push({ name, width, height, ...inspection })
    }
  }
  const channels = await requestJson(`${runtime.apiBase}/can/channels/status`, {
    headers: { ...sidecarHeaders, Authorization: `Bearer ${token}` },
  })
  const controlResponse = await fetch(`${runtime.apiBase}/control/121/send-once`, {
    method: 'POST',
    headers: { ...sidecarHeaders, Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ gear: 'D', drive_mode: 'Remote', target_speed: 1, front_steer: 0, rear_steer: 0, brake_enable: false }),
  })
  const controlBody = await controlResponse.json().catch(() => ({}))
  const summary = {
    timestamp_utc: new Date().toISOString(),
    page_count: pages.length,
    viewport_count: 2,
    screenshot_count: inspections.length,
    loopback_only: runtime.apiBase.startsWith('http://127.0.0.1:'),
    simulator_running: false,
    channels_offline: Array.isArray(channels) && channels.every((channel) => channel.online === false),
    offline_control_status: controlResponse.status,
    offline_control: {
      code: controlBody?.code || '',
      blocking_rules: Array.isArray(controlBody?.details?.reasons)
        ? controlBody.details.reasons.map((item) => item.rule)
        : [],
    },
    crash_restart_credential_rotated: process.env.CHASSIS_E2E_CRASH_ONCE === '1' ? restarted : 'not-requested',
    inspections,
  }
  summary.passed = summary.screenshot_count === 22
    && summary.loopback_only
    && summary.channels_offline
    && summary.offline_control_status === 409
    && inspections.every((item) => !item.page_scrollable && !item.failed_fetch && item.text_length > 20)
    && summary.crash_restart_credential_rotated !== false
  fs.writeFileSync(path.join(output, 'installed-e2e-summary.json'), `${JSON.stringify(summary, null, 2)}\n`, 'utf8')
  writeRuntimeState({ installed_e2e_passed: summary.passed })
  if (!summary.passed) throw new Error('installed package E2E assertions failed')
  app.quit()
}

async function startApplication() {
  if (app.isPackaged || process.env.CHASSIS_START_DEV_SIDECAR === '1') {
    await showDiagnostics('正在启动')
    supervisor = new SidecarSupervisor(sidecarOptions())
    supervisor.on('ready', () => {
      writeRuntimeState()
      if (awaitingSidecarRecovery) {
        awaitingSidecarRecovery = false
        void loadRenderer()
      }
    })
    supervisor.on('failed', ({ message }) => void showDiagnostics(message))
    supervisor.on('diagnostic', (detail) => {
      if (process.env.CHASSIS_ELECTRON_DIAGNOSTICS === '1') console.error(detail.code, detail.message)
    })
    await supervisor.start()
  }
  await loadRenderer()
  if (process.env.CHASSIS_PACKAGED_SMOKE_EXIT === '1' && process.env.CHASSIS_PACKAGED_E2E === '1') {
    writeRuntimeState({ smoke_exit: true })
    app.quit()
    return
  }
  await runPackagedVerification()
}

ipcMain.on('window:minimize', (event) => BrowserWindow.fromWebContents(event.sender)?.minimize())
ipcMain.on('window:maximize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return
  if (win.isMaximized()) win.unmaximize()
  else win.maximize()
})
ipcMain.on('window:close', (event) => BrowserWindow.fromWebContents(event.sender)?.close())
ipcMain.on('runtime:get-connection', (event) => { event.returnValue = runtimeSnapshot() })
ipcMain.handle('files:open-path', async (_event, targetPath) => {
  if (typeof targetPath !== 'string' || !path.isAbsolute(targetPath)) {
    throw new Error('Only absolute paths returned by the backend are accepted')
  }
  const normalized = path.resolve(targetPath)
  const allowedRoot = path.resolve(dataRoot())
  const relative = path.relative(allowedRoot, normalized)
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Path is outside the application data root')
  const error = await shell.openPath(normalized)
  if (error) throw new Error(error)
  return { ok: true }
})

app.on('second-instance', () => {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
})

app.whenReady().then(async () => {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false))
  try {
    await startApplication()
  } catch (error) {
    if (process.env.CHASSIS_PACKAGED_E2E_OUTPUT) {
      fs.mkdirSync(process.env.CHASSIS_PACKAGED_E2E_OUTPUT, { recursive: true })
      fs.writeFileSync(path.join(process.env.CHASSIS_PACKAGED_E2E_OUTPUT, 'startup-failure.json'), `${JSON.stringify({ timestamp_utc: new Date().toISOString(), error: error instanceof Error ? error.message : String(error) }, null, 2)}\n`, 'utf8')
    }
    if (process.env.CHASSIS_PACKAGED_E2E === '1') {
      applicationExitCode = 2
      app.quit()
      return
    }
    awaitingSidecarRecovery = true
    await showDiagnostics(error instanceof Error ? error.message : String(error))
  }
})

app.on('before-quit', (event) => {
  if (quitting) return
  event.preventDefault()
  quitting = true
  void (async () => {
    if (supervisor) await supervisor.stop()
    for (const win of BrowserWindow.getAllWindows()) win.destroy()
    app.exit(applicationExitCode)
  })()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
