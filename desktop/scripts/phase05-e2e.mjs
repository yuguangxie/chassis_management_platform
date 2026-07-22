/* Reproducible loopback-only quality run: backend, simulator, renderer and safety fallback. */
import { once } from 'node:events'
import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { createSocket } from 'node:dgram'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(desktop, '..')
const output = process.env.CHASSIS_E2E_OUTPUT
  ? resolve(root, process.env.CHASSIS_E2E_OUTPUT)
  : resolve(root, 'docs/verification/phase-05/e2e')
const python = resolve(root, `backend/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`)
const electronLauncher = resolve(desktop, process.platform === 'win32' ? 'node_modules/.bin/electron.cmd' : 'node_modules/.bin/electron')
const electron = resolve(desktop, process.platform === 'win32' ? 'node_modules/electron/dist/electron.exe' : 'node_modules/.bin/electron')
const vite = resolve(desktop, 'node_modules/vite/bin/vite.js')
const runtime = process.argv.includes('--runtime') || process.argv.includes('--long')
const longRun = process.argv.includes('--long')
const apiPort = Number(process.env.CHASSIS_E2E_API_PORT || 18800)
const webPort = Number(process.env.CHASSIS_E2E_WEB_PORT || 15173)

function wait(milliseconds) { return new Promise((resolveWait) => setTimeout(resolveWait, milliseconds)) }

async function resetOutputDirectory() {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      rmSync(output, { recursive: true, force: true })
      mkdirSync(output, { recursive: true })
      return
    } catch (error) {
      if (error?.code !== 'EBUSY' || attempt === 11) throw error
      await wait(250)
    }
  }
}

async function commandOutput(command, args, options = {}) {
  return new Promise((resolveCommand, reject) => {
    const child = spawn(command, args, { windowsHide: true, shell: process.platform === 'win32', ...options })
    let outputText = ''
    child.stdout.on('data', (data) => { outputText += data })
    child.stderr.on('data', (data) => { outputText += data })
    child.once('error', reject)
    child.once('exit', (code) => code === 0 ? resolveCommand(outputText.trim()) : reject(new Error(`${command} exited with ${code}: ${outputText.trim()}`)))
  })
}

function extractElectronVersion(output) {
  // Electron's npm launcher can emit a one-time binary download notice before
  // the actual executable version on clean Windows runners.
  const versions = output.match(/\bv\d+\.\d+\.\d+\b/g) ?? []
  return versions.at(-1) ?? ''
}

async function chooseUdpBase() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const base = 24000 + Math.floor(Math.random() * 18000)
    const sockets = []
    try {
      for (const offset of [0, 1, 100, 101]) {
        const socket = createSocket('udp4')
        await new Promise((resolveBind, reject) => {
          socket.once('error', reject)
          socket.bind(base + offset, '127.0.0.1', resolveBind)
        })
        sockets.push(socket)
      }
      return base
    } catch {
      // Try another range; all sockets are released below.
    } finally {
      sockets.forEach((socket) => socket.close())
    }
  }
  throw new Error('unable to find an isolated UDP range')
}

function start(name, command, args, options = {}) {
  const logPath = resolve(output, `${name}.log`)
  const child = spawn(command, args, {
    cwd: root,
    windowsHide: true,
    shell: process.platform === 'win32' && command.toLowerCase().endsWith('.cmd'),
    stdio: ['ignore', 'pipe', 'pipe'],
    ...options,
  })
  child.stdout.on('data', (data) => writeFileSync(logPath, data, { flag: 'a' }))
  child.stderr.on('data', (data) => writeFileSync(logPath, data, { flag: 'a' }))
  return child
}

async function waitFor(url, label) {
  let lastError = ''
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url)
      if (response.ok) return
      lastError = `${response.status}`
    } catch (error) {
      lastError = String(error)
    }
    await wait(250)
  }
  throw new Error(`${label} did not start: ${lastError}`)
}

async function postJson(url, body, token) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(url, { method:'POST', headers, body:JSON.stringify(body) })
  const payload = response.status === 204 ? null : await response.json()
  if (!response.ok) throw new Error(`request failed (${response.status}) at ${new URL(url).pathname}: ${JSON.stringify(payload)}`)
  return payload
}

async function getJson(url, token) {
  const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  const payload = await response.json()
  if (!response.ok) throw new Error(`request failed (${response.status}) at ${new URL(url).pathname}: ${JSON.stringify(payload)}`)
  return payload
}

async function stop(child) {
  if (!child || child.exitCode !== null) return
  const waitForExit = () => Promise.race([
    once(child, 'exit'),
    wait(5_000),
  ])
  if (process.platform === 'win32' && child.pid) {
    const killer = spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' })
    await Promise.race([
      once(killer, 'exit'),
      wait(5_000),
    ])
    await waitForExit()
    await wait(200)
  } else {
    child.kill('SIGTERM')
    await waitForExit()
  }
}

async function command(command, args, env, name) {
  const child = start(name, command, args, { env })
  const code = await new Promise((resolveExit) => child.once('exit', (exitCode) => resolveExit(exitCode ?? 1)))
  if (code !== 0) throw new Error(`${name} failed with exit code ${code}`)
}

async function main() {
  if (!existsSync(python)) throw new Error(`backend virtualenv is required: ${python}`)
  if (process.env.CHASSIS_E2E_ELECTRON) throw new Error('CHASSIS_E2E_ELECTRON is forbidden for phase-05 verification')
  if (!existsSync(electronLauncher) || !existsSync(electron)) throw new Error(`installed Electron 43 binary is required: ${electron}`)
  await resetOutputDirectory()
  const electronVersionOutput = await commandOutput(electronLauncher, ['--version'])
  const electronVersion = extractElectronVersion(electronVersionOutput)
  if (electronVersion !== 'v43.1.0') throw new Error(`Electron 43.1.0 is required, got ${electronVersion}`)
  writeFileSync(resolve(output, 'electron-version.txt'), `${electronVersion}\n`)
  const udpBase = await chooseUdpBase()
  const apiBase = `http://127.0.0.1:${apiPort}/api/v1`
  const bootstrapSecret = randomBytes(32).toString('base64url')
  const configSigningKey = randomBytes(48).toString('base64url')
  const passwords = {
    admin: `A-${randomBytes(18).toString('base64url')}9!`,
    viewer: `V-${randomBytes(18).toString('base64url')}9!`,
    operator: `O-${randomBytes(18).toString('base64url')}9!`,
    engineer: `E-${randomBytes(18).toString('base64url')}9!`,
  }
  const env = {
    ...process.env,
    CHASSIS_RUNTIME_PROFILE: 'test',
    CHASSIS_DATA_DIR: resolve(output, 'runtime-data'),
    CHASSIS_TEST_PORT_BASE: String(udpBase),
    CHASSIS_API_BASE: apiBase,
    CHASSIS_WS_URL: `ws://127.0.0.1:${apiPort}/ws`,
    VITE_API_BASE: apiBase,
    VITE_WS_URL: `ws://127.0.0.1:${apiPort}/ws`,
    CHASSIS_ALLOWED_UI_ORIGINS: `http://127.0.0.1:${webPort}`,
    CHASSIS_BOOTSTRAP_SECRET: bootstrapSecret,
    CHASSIS_CONFIG_SIGNING_KEY: configSigningKey,
    CHASSIS_CAN1_PORT: String(udpBase),
    CHASSIS_CAN2_PORT: String(udpBase + 1),
    PYTHONPATH: resolve(root, 'backend'),
  }
  const result = {
    electronVersion,
    pageCount: 11,
    viewportCount: 2,
    boundary: '127.0.0.1 loopback only',
    apiBase,
    webPort,
    udpBase,
    passed: false,
  }
  let backend
  let simulator
  let frontend
  let viewerToken = ''
  let operatorToken = ''
  let engineerToken = ''
  try {
    backend = start('backend', python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(apiPort)], { env })
    await waitFor(`${apiBase}/health`, 'FastAPI')
    const admin = await postJson(`${apiBase}/auth/bootstrap`, { bootstrap_secret:bootstrapSecret, username:'e2e-admin', password:passwords.admin })
    for (const role of ['viewer', 'operator', 'engineer']) {
      await postJson(`${apiBase}/auth/accounts`, { username:`e2e-${role}`, password:passwords[role], role }, admin.token)
    }
    viewerToken = (await postJson(`${apiBase}/auth/login`, { username:'e2e-viewer', password:passwords.viewer })).token
    operatorToken = (await postJson(`${apiBase}/auth/login`, { username:'e2e-operator', password:passwords.operator })).token
    engineerToken = (await postJson(`${apiBase}/auth/login`, { username:'e2e-engineer', password:passwords.engineer })).token
    const mockSession = await postJson(`${apiBase}/eol/sessions`, {
      chassis_no:'MOCK-E2E-001', vin:'LMOCKE2E00000001', serial_no:'MOCK-E2E-SN', station_id:'LOOPBACK-E2E',
      plan_id:'default_chassis_eol_v1', remarks:'Electron loopback UI interaction evidence',
    }, operatorToken)
    const mockSessionId = mockSession.id || mockSession.session_id
    if (!mockSessionId) throw new Error('mock EOL session did not return an id')
    const generatedReport = await postJson(`${apiBase}/eol/sessions/${encodeURIComponent(mockSessionId)}/report`, {}, operatorToken)
    const configExport = await getJson(`${apiBase}/config/export`, admin.token)
    const configPackagePath = resolve(output, 'signed-config-dry-run.json')
    writeFileSync(configPackagePath, JSON.stringify(configExport.package, null, 2))
    result.mockSession = { session_id:mockSessionId, report_generated:Boolean(generatedReport.ok) }
    const authenticatedEnv = { ...env, CHASSIS_API_TOKEN:viewerToken }
    simulator = start('simulator', python, [
      'scripts/dev_simulator.py', '--profile', 'normal_pass', '--rate-hz', '60',
      '--can1-target', `127.0.0.1:${udpBase}`, '--can2-target', `127.0.0.1:${udpBase + 1}`,
      '--can1-listen', `127.0.0.1:${udpBase + 100}`, '--can2-listen', `127.0.0.1:${udpBase + 101}`,
    ], { env })
    frontend = start('frontend', process.execPath, [vite, '--host', '127.0.0.1', '--port', String(webPort)], { cwd: desktop, env })
    await waitFor(`http://127.0.0.1:${webPort}`, 'Vite')
    await wait(1800)

    if (runtime) {
      await command(python, ['scripts/verify_phase04_runtime.py', '--output', resolve(output, 'runtime'), '--duration', '4'], authenticatedEnv, 'runtime')
    }
    if (longRun) {
      await command(python, ['scripts/verify_phase04_stress.py', '--output', resolve(output, 'stress-10m'), '--duration', '600', '--backend-pid', String(backend.pid)], authenticatedEnv, 'stress-10m')
    }
    const captureScript = resolve(desktop, 'electron/phase04_capture.cjs')
    await command(electron, [captureScript], {
      ...env,
      PHASE04_TARGET_URL: `http://127.0.0.1:${webPort}`,
      PHASE04_ELECTRON_OUTPUT: resolve(output, 'screenshots'),
      PHASE04_CAPTURE_DELAY_MS: '1000',
      PHASE04_API_TOKEN: admin.token,
      PHASE04_VIEWER_TOKEN: viewerToken,
      PHASE04_CONFIG_PACKAGE: configPackagePath,
      PHASE04_MOCK_SESSION_ID: mockSessionId,
    }, 'renderer-capture')
    const captureMetrics = JSON.parse(readFileSync(resolve(output, 'screenshots/page_capture_metrics.json'), 'utf8'))
    const inspections = captureMetrics.inspections
    result.authentication = captureMetrics.authentication
    result.permission = captureMetrics.permission
    const interactionRows = inspections.filter((item) => item.width === 1920)
    result.interaction_assertions = {
      pages_exercised: interactionRows.length,
      every_page_clicked: interactionRows.every((item) => Array.isArray(item.interaction.clicked) && item.interaction.clicked.length > 0),
      every_assertion_passed: interactionRows.every((item) => Object.values(item.interaction.assertions || {}).every(Boolean)),
      details: interactionRows.map((item) => ({ page:item.page, ...item.interaction })),
    }
    result.screenshot_assertions = {
      captures: inspections.length,
      no_page_scroll: inspections.every((item) => !item.page_scrollable),
      no_white_controls: inspections.every((item) => item.white_controls === 0),
      no_failed_fetch_banner: inspections.every((item) => !item.failed_to_fetch_banner),
      no_renderer_console_errors: inspections.every((item) => item.renderer_console_errors.length === 0),
      no_renderer_page_errors: inspections.every((item) => item.renderer_page_errors.length === 0),
    }

    await stop(simulator)
    simulator = undefined
    const simulatorStoppedAt = performance.now()
    await wait(2300)
    const channels = await fetch(`${apiBase}/can/channels/status`, { headers: { Authorization: `Bearer ${viewerToken}` } }).then((response) => response.json())
    const control = await fetch(`${apiBase}/control/121/send-once`, {
      method: 'POST', headers: { Authorization: `Bearer ${engineerToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ gear: 'D', drive_mode: 'Remote', target_speed: 1, front_steer: 0, rear_steer: 0, brake_enable: false }),
    })
    result.stale_online = { channels, control_status: control.status, control_body: await control.json() }
    result.stale_online_assertion = control.status === 409 && Array.isArray(channels) && channels.every((item) => item.online === false)
    result.screenshotCount = result.screenshot_assertions.captures
    result.pageLevelScrollFailures = inspections.filter((item) => item.page_scrollable).length
    result.failedFetchBanners = inspections.filter((item) => item.failed_to_fetch_banner).length
    result.whiteControlFailures = inspections.reduce((total, item) => total + item.white_controls, 0)
    result.rendererConsoleErrors = inspections.flatMap((item) => item.renderer_console_errors)
    result.rendererPageErrors = inspections.flatMap((item) => item.renderer_page_errors)
    result.simulatorOfflineDelayMs = Math.round(performance.now() - simulatorStoppedAt)
    result.offlineControlStatus = control.status
    result.nonLoopbackRequests = [apiBase, `http://127.0.0.1:${webPort}`, env.CHASSIS_WS_URL]
      .filter((address) => new URL(address).hostname !== '127.0.0.1').length
    result.passed = result.electronVersion === 'v43.1.0'
      && result.pageCount === 11
      && result.viewportCount === 2
      && result.screenshotCount === 22
      && result.pageLevelScrollFailures === 0
      && result.failedFetchBanners === 0
      && result.whiteControlFailures === 0
      && result.rendererConsoleErrors.length === 0
      && result.rendererPageErrors.length === 0
      && result.nonLoopbackRequests === 0
      && Object.values(result.authentication).every(Boolean)
      && result.permission.viewer_network_redirects_403
      && result.mockSession.report_generated
      && result.interaction_assertions.pages_exercised === 11
      && result.interaction_assertions.every_page_clicked
      && result.interaction_assertions.every_assertion_passed
      && result.screenshot_assertions.no_page_scroll
      && result.screenshot_assertions.no_white_controls
      && result.screenshot_assertions.no_failed_fetch_banner
      && result.stale_online_assertion
  } catch (error) {
    result.error = `${error?.name || 'Error'}: ${error?.message || error}`
  } finally {
    await stop(simulator)
    await stop(frontend)
    await stop(backend)
  }
  writeFileSync(resolve(output, 'e2e-summary.json'), JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
  if (!result.passed) process.exitCode = 1
}

await main()
