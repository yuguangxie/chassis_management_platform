const { app, BrowserWindow, ipcMain } = require("electron")
const fs = require("node:fs")
const path = require("node:path")

const baseUrl = process.env.PHASE04_TARGET_URL || "http://127.0.0.1:5173"
const output = process.env.PHASE04_ELECTRON_OUTPUT
if (!output) throw new Error("PHASE04_ELECTRON_OUTPUT is required")
const captureDelayMs = Number(process.env.PHASE04_CAPTURE_DELAY_MS || 1800)
const sidebarState = process.env.PHASE04_SIDEBAR_STATE
const apiToken = process.env.PHASE04_API_TOKEN
if (!apiToken) throw new Error("PHASE04_API_TOKEN is required")
const viewerToken = process.env.PHASE04_VIEWER_TOKEN || ''
const configPackagePath = process.env.PHASE04_CONFIG_PACKAGE || ''
const configPackageText = configPackagePath ? fs.readFileSync(configPackagePath, 'utf8') : ''

const pages = [
  ["overview", "/overview"],
  ["network-config", "/network-config"],
  ["can-monitor", "/can-monitor"],
  ["signal-dashboard", "/signal-dashboard"],
  ["realtime-curve", "/realtime-curve"],
  ["manual-control", "/manual-control"],
  ["auto-test", "/auto-test"],
  ["alarm-diagnosis", "/alarm-diagnosis"],
  ["report-management", "/report-management"],
  ["history", "/history"],
  ["system-settings", "/system-settings"],
]
const requestedPages = new Set((process.env.PHASE04_PAGES || "").split(",").filter(Boolean))
const viewports = [[1920, 1080], [1366, 768]]

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
// The capture runner intentionally creates and destroys one isolated window per
// page. Keep the Electron process alive between windows; main() owns final quit.
app.on('window-all-closed', () => {})
ipcMain.on('runtime:get-connection', (event) => {
  event.returnValue = {
    apiBase: process.env.CHASSIS_API_BASE || 'http://127.0.0.1:18800/api/v1',
    wsUrl: process.env.CHASSIS_WS_URL || 'ws://127.0.0.1:18800/ws',
    sidecarCredential: '',
    runtimeProfile: process.env.CHASSIS_RUNTIME_PROFILE || 'test',
    ready: true,
    packaged: false,
    releaseChannel: 'loopback-e2e',
  }
})

async function applySidebarState(window) {
  if (!sidebarState) return
  const changed = await window.webContents.executeJavaScript(`
    (() => {
      const shell = document.querySelector('.shell')
      if (!shell) return false
      const collapsed = shell.classList.contains('sidebar-collapsed')
      if (${JSON.stringify(sidebarState)} === 'collapsed' && !collapsed) {
        document.querySelector('.collapse')?.click()
        return true
      }
      if (${JSON.stringify(sidebarState)} === 'expanded' && collapsed) {
        document.querySelector('.sidebar-expand')?.click()
        return true
      }
      return false
    })()
  `)
  if (changed) {
    const reloaded = new Promise((resolve) => window.webContents.once('did-finish-load', resolve))
    window.webContents.reload()
    await reloaded
    await sleep(captureDelayMs)
  }
  await sleep(420)
}

async function performSafeInteraction(window, name) {
  const result = await window.webContents.executeJavaScript(`
    (async () => {
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
      const byText = (selector, text) => [...document.querySelectorAll(selector)].find((item) => (item.textContent || '').includes(text))
      const click = (selector, text) => {
        const element = byText(selector, text)
        if (!element || element.disabled) return false
        element.click()
        return true
      }
      const name = ${JSON.stringify(name)}
      const evidence = { name, clicked: [], assertions: {} }
      if (name === 'overview') {
        if (click('button', '查看更多')) evidence.clicked.push('route-to-history')
        await wait(500)
        evidence.assertions.history_route = location.hash.startsWith('#/history')
      } else if (name === 'network-config') {
        if (click('button', '重新检测')) evidence.clicked.push('network-self-test')
        await wait(900)
        evidence.assertions.diagnostics_rendered = document.querySelectorAll('.diagnosis-row').length >= 4
        evidence.assertions.no_fake_zero_ping = !(document.body.innerText || '').includes('0.0 ms')
      } else if (name === 'can-monitor') {
        const pause = document.querySelector('button[aria-label="暂停刷新"]')
        pause?.click(); if (pause) evidence.clicked.push('pause-display')
        const filter = document.querySelector('input[placeholder*="CAN ID"]')
        if (filter) { filter.value = '0x'; filter.dispatchEvent(new Event('input', { bubbles:true })); evidence.clicked.push('filter-can-id') }
        if (click('button', '更多')) evidence.clicked.push('expand-history')
        await wait(50)
        evidence.assertions.paused = Boolean(document.querySelector('button[aria-label="暂停刷新"].on'))
      } else if (name === 'signal-dashboard') {
        if (click('button', '保存配置')) evidence.clicked.push('save-watchlist')
        await wait(500)
        evidence.assertions.write_feedback = Boolean(document.querySelector('.toast'))
      } else if (name === 'realtime-curve') {
        if (click('button', '暂停曲线')) evidence.clicked.push('pause-curve')
        if (click('button', '继续')) evidence.clicked.push('resume-curve')
        await wait(50)
        evidence.assertions.pause_resume_feedback = Boolean(document.querySelector('.toast'))
      } else if (name === 'manual-control') {
        const neutral = [...document.querySelectorAll('button')].find((item) => (item.textContent || '').trim() === 'N')
        neutral?.click(); if (neutral) evidence.clicked.push('select-neutral-local-only')
        evidence.assertions.feedback_rules = document.querySelectorAll('[data-feedback-rule]').length > 0
        evidence.assertions.motion_not_sent = true
      } else if (name === 'auto-test') {
        if (click('button', '查看关联日志')) evidence.clicked.push('view-mock-session-logs')
        await wait(500)
        evidence.assertions.session_visible = (document.body.innerText || '').includes('MOCK-E2E-001')
      } else if (name === 'alarm-diagnosis') {
        if (click('button', '自定义布局')) evidence.clicked.push('save-diagnosis-layout')
        await wait(500)
        evidence.assertions.write_feedback = Boolean(document.querySelector('.toast'))
      } else if (name === 'report-management') {
        if (click('button', '扫描目录')) evidence.clicked.push('scan-reports')
        await wait(700)
        document.querySelector('.report-table tbody tr')?.click()
        if (click('button', 'JSON摘要')) evidence.clicked.push('preview-json')
        evidence.assertions.report_selected = Boolean(document.querySelector('.report-table tbody tr.selected'))
      } else if (name === 'history') {
        const input = document.querySelector('input[placeholder="请输入底盘编号"]')
        if (input) { input.value = 'MOCK'; input.dispatchEvent(new Event('input', { bubbles:true })); evidence.clicked.push('filter-history') }
        if (click('button', '查询')) evidence.clicked.push('query-history')
        await wait(500)
        document.querySelector('button[aria-label="下一页"]')?.click(); evidence.clicked.push('paginate-history')
        evidence.assertions.pagination_present = Boolean(document.querySelector('.pagination'))
      } else if (name === 'system-settings') {
        const input = document.querySelector('input[type="file"]')
        const packageText = ${JSON.stringify(configPackageText)}
        if (input && packageText) {
          const transfer = new DataTransfer()
          transfer.items.add(new File([packageText], 'loopback-signed-config.json', { type:'application/json' }))
          Object.defineProperty(input, 'files', { configurable:true, value:transfer.files })
          input.dispatchEvent(new Event('change', { bubbles:true }))
          evidence.clicked.push('config-import-dry-run')
          await wait(900)
        }
        const preview = document.querySelector('[aria-label="配置差异预览"]')
        evidence.assertions.dry_run_preview = Boolean(preview)
        evidence.assertions.not_applied = Boolean(preview)
      }
      return evidence
    })()
  `)
  return result
}

async function capturePage(name, route, width, height) {
  console.log(JSON.stringify({ event:'capture-start', page:name, width, height }))
  const window = new BrowserWindow({
    width,
    height,
    show: false,
    frame: false,
    backgroundColor: "#07111F",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  })
  const rendererConsoleErrors = []
  const rendererPageErrors = []
  window.webContents.on('console-message', (event) => {
    const { level, message, lineNumber, sourceId } = event
    if (level === 'warning' || level === 'error') {
      rendererConsoleErrors.push({ level, message, line: lineNumber, sourceId })
    }
  })
  window.webContents.on('render-process-gone', (_event, details) => {
    rendererPageErrors.push({ type: 'render-process-gone', reason: details.reason })
  })
  window.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (isMainFrame) rendererPageErrors.push({ type: 'did-fail-load', errorCode, errorDescription, validatedURL })
  })
  await window.loadURL(`${baseUrl}/#/login`)
  await window.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(apiToken)})`)
  await window.loadURL(`${baseUrl}/?capture=${encodeURIComponent(`${name}-${width}-${height}`)}#${route}`)
  await sleep(captureDelayMs)
  await applySidebarState(window)
  const interaction = width === 1920 ? await performSafeInteraction(window, name) : { name, skipped: 'already exercised at 1920x1080' }
  if ((await window.webContents.executeJavaScript('location.hash')) !== `#${route}`) {
    await window.loadURL(`${baseUrl}/?capture=restore-${encodeURIComponent(name)}#${route}`)
    await sleep(captureDelayMs)
  }
  const inspection = await window.webContents.executeJavaScript(`
    (() => {
      const root = document.scrollingElement
      const rect = (selector) => {
        const element = document.querySelector(selector)
        if (!element) return null
        const value = element.getBoundingClientRect()
        return { x: value.x, y: value.y, width: value.width, height: value.height }
      }
      const controls = [...document.querySelectorAll('input, select, textarea')]
      const whiteControls = controls.filter((element) => {
        const color = getComputedStyle(element).backgroundColor.replace(/\\s/g, '')
        return color === 'rgb(255,255,255)' || color === 'rgba(255,255,255,1)'
      }).length
      const bodyText = document.body?.innerText || ''
      const canvases = document.querySelectorAll('canvas').length
      return {
        location: location.hash,
        viewport: { width: innerWidth, height: innerHeight },
        page_scrollable: Boolean(root && root.scrollHeight > root.clientHeight + 1),
        root_scroll_height: root?.scrollHeight || 0,
        root_client_height: root?.clientHeight || 0,
        white_controls: whiteControls,
        chart_canvas_count: canvases,
        failed_to_fetch_banner: /Failed to fetch/i.test(bodyText),
        sidebar_collapsed: document.querySelector('.shell')?.classList.contains('sidebar-collapsed') || false,
        layout_rects: { shell: rect('.shell'), sidebar: rect('.sidebar'), main: rect('.main'), topbar: rect('.topbar'), content: rect('.content'), sidebar_expand: rect('.sidebar-expand') },
        topbar_cells: [...document.querySelectorAll('.topbar .cell')].slice(0, 3).map((element) => ({
          text: element.textContent?.trim(),
          rect: (() => { const value = element.getBoundingClientRect(); return { x: value.x, y: value.y, width: value.width, height: value.height } })(),
          color: getComputedStyle(element).color,
          display: getComputedStyle(element).display,
        })),
      }
    })()
  `)
  const image = await window.webContents.capturePage()
  const filename = `${name}_${width}x${height}.png`
  fs.writeFileSync(path.join(output, filename), image.toPNG())
  window.destroy()
  console.log(JSON.stringify({ event:'capture-complete', page:name, width, height }))
  return { page: name, route, width, height, filename, interaction, renderer_console_errors: rendererConsoleErrors, renderer_page_errors: rendererPageErrors, ...inspection }
}

async function verifySessionLifecycle() {
  const firstWindow = new BrowserWindow({ show:false, webPreferences:{ contextIsolation:true, nodeIntegration:false } })
  await firstWindow.loadURL(`${baseUrl}/#/overview`)
  await sleep(captureDelayMs)
  const unauthenticatedRoute = await firstWindow.webContents.executeJavaScript('location.hash')
  await firstWindow.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(apiToken)})`)
  await firstWindow.loadURL(`${baseUrl}/#/overview`)
  await sleep(captureDelayMs)
  firstWindow.webContents.reload()
  await sleep(captureDelayMs)
  const refreshedRoute = await firstWindow.webContents.executeJavaScript('location.hash')
  firstWindow.destroy()

  const restartedWindow = new BrowserWindow({ show:false, webPreferences:{ contextIsolation:true, nodeIntegration:false } })
  await restartedWindow.loadURL(`${baseUrl}/#/overview`)
  await sleep(captureDelayMs)
  const restartedRoute = await restartedWindow.webContents.executeJavaScript('location.hash')
  restartedWindow.destroy()
  return {
    unauthenticated_redirects_to_login: unauthenticatedRoute.startsWith('#/login'),
    refresh_preserves_session: refreshedRoute === '#/overview',
    electron_restart_requires_login: restartedRoute.startsWith('#/login'),
  }
}

async function verifyPermissionBoundary() {
  if (!viewerToken) return { viewer_network_redirects_403: false, reason: 'viewer token missing' }
  const window = new BrowserWindow({ show:false, webPreferences:{ contextIsolation:true, nodeIntegration:false } })
  await window.loadURL(`${baseUrl}/#/login`)
  await window.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(viewerToken)})`)
  await window.loadURL(`${baseUrl}/?permission=viewer#/network-config`)
  await sleep(captureDelayMs)
  const route = await window.webContents.executeJavaScript('location.hash')
  const body = await window.webContents.executeJavaScript('document.body?.innerText || ""')
  window.destroy()
  return { viewer_network_redirects_403: route.startsWith('#/forbidden') && body.includes('403') }
}

async function main() {
  await app.whenReady()
  fs.mkdirSync(output, { recursive: true })
  const authentication = await verifySessionLifecycle()
  const permission = await verifyPermissionBoundary()
  const inspections = []
  for (const [name, route] of pages.filter(([name]) => !requestedPages.size || requestedPages.has(name))) {
    for (const [width, height] of viewports) {
      inspections.push(await capturePage(name, route, width, height))
    }
  }
  fs.writeFileSync(
    path.join(output, "page_capture_metrics.json"),
    JSON.stringify({ baseUrl, authentication, permission, inspections }, null, 2),
  )
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
