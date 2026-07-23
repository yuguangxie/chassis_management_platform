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
const mockSessionId = process.env.PHASE04_MOCK_SESSION_ID || ''
const stabilitySeconds = Number(process.env.PHASE04_STABILITY_SECONDS || 60)

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
      const clickWhenAvailable = async (selector, text, attempts = 20) => {
        for (let attempt = 0; attempt < attempts; attempt += 1) {
          if (click(selector, text)) return true
          await wait(100)
        }
        return false
      }
      const name = ${JSON.stringify(name)}
      const evidence = { name, clicked: [], assertions: {} }
      if (name === 'overview') {
        if (await clickWhenAvailable('button', '查看更多')) evidence.clicked.push('route-to-history')
        await wait(500)
        evidence.assertions.history_route = location.hash.startsWith('#/history')
      } else if (name === 'network-config') {
        const channelToggle = document.querySelector('.channel-form button[role="switch"]')
        if (channelToggle && !channelToggle.disabled) {
          channelToggle.click(); await wait(40)
          evidence.assertions.draft_toggle_marks_dirty = Boolean(document.querySelector('.draft-pill'))
          channelToggle.click(); await wait(40)
          evidence.clicked.push('toggle-channel-draft-twice')
        }
        if (click('button', '保存并应用')) evidence.clicked.push('save-validated-config')
        await wait(900)
        const portRows = [...document.querySelectorAll('.channel-form .compact-field')]
        const devicePortRow = portRows.find((row) => (row.textContent || '').includes('设备端口'))
        const portInput = devicePortRow?.querySelector('input')
        if (portInput) {
          portInput.value = '70000'
          portInput.dispatchEvent(new Event('input', { bubbles:true }))
          if (click('button', '保存并应用')) evidence.clicked.push('invalid-config-rollback')
          await wait(700)
          evidence.assertions.failed_apply_rolled_back = portInput.value !== '70000' || (document.body.innerText || '').includes('已回滚')
        }
        const can1Tab = byText('.channel-tabs button', 'CAN1')
        can1Tab?.click()
        await wait(80)
        evidence.assertions.can1_send_locked = (document.body.innerText || '').includes('CAN1 禁止主动发送')
        const can2Tab = byText('.channel-tabs button', 'CAN2')
        can2Tab?.click()
        await wait(80)
        evidence.assertions.only_121_approved = (document.body.innerText || '').includes('仅批准 CAN2 的 0x121')
        if (click('button', '重新检测')) evidence.clicked.push('network-self-test')
        await wait(900)
        evidence.assertions.diagnostics_rendered = document.querySelectorAll('.diagnosis-row').length >= 4
        evidence.assertions.no_fake_zero_ping = !(document.body.innerText || '').includes('0.0 ms')
        evidence.assertions.no_raw_diagnostic_enums = !/(not-measured|receive_confirmed|not_applicable|owned_by_runtime)/.test(document.body.innerText || '')
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
        const lights = [...document.querySelectorAll('.signal-light')]
        evidence.assertions.five_signal_lights = lights.length === 5
        evidence.assertions.light_states_explicit = lights.every((item) => ['on','off','unknown'].includes(item.dataset.state || ''))
        const compactColor = (value) => value.replace(/\\s/g, '')
        const activeColors = { 'tone-yellow':'rgb(246,195,67)', 'tone-red':'rgb(239,68,68)', 'tone-white':'rgb(248,250,252)' }
        evidence.assertions.light_colors_match_state = lights.every((item) => {
          const lamp = item.querySelector('.lamp')
          if (!lamp) return false
          const state = item.dataset.state
          const actual = compactColor(getComputedStyle(lamp).color)
          if (state === 'off') return actual === 'rgb(148,163,184)'
          if (state === 'unknown') return actual === 'rgb(120,138,159)'
          const tone = Object.keys(activeColors).find((name) => item.classList.contains(name))
          return tone ? actual === activeColors[tone] : false
        })
        evidence.light_samples = lights.map((item) => ({
          label: item.querySelector('.label')?.textContent?.trim(),
          state: item.dataset.state,
          quality: item.dataset.quality,
          tone: Object.keys(activeColors).find((name) => item.classList.contains(name)) || '',
          color: item.querySelector('.lamp') ? compactColor(getComputedStyle(item.querySelector('.lamp')).color) : '',
          text: item.querySelector('strong')?.textContent?.trim(),
        }))
        evidence.assertions.no_blink_animation = lights.every((item) => getComputedStyle(item).animationName === 'none' && getComputedStyle(item.querySelector('.lamp')).animationName === 'none')
      } else if (name === 'realtime-curve') {
        if (click('button', '暂停曲线')) evidence.clicked.push('pause-curve')
        if (click('button', '继续')) evidence.clicked.push('resume-curve')
        await wait(50)
        evidence.assertions.pause_resume_feedback = Boolean(document.querySelector('.toast'))
        const resources = performance.getEntriesByType('resource').map((entry) => entry.name)
        evidence.assertions.live_mode_zero_history_requests = resources.every((url) => !url.includes('/test-sessions/') && !url.includes('mode=history'))
      } else if (name === 'manual-control') {
        const neutral = [...document.querySelectorAll('button')].find((item) => (item.textContent || '').trim() === 'N')
        neutral?.click(); if (neutral) evidence.clicked.push('select-neutral-local-only')
        evidence.assertions.feedback_rules = document.querySelectorAll('[data-feedback-rule]').length > 0
        evidence.assertions.motion_not_sent = true
      } else if (name === 'auto-test') {
        const sessionWasVisible = (document.body.innerText || '').includes(${JSON.stringify(mockSessionId)})
        if (click('button', '查看关联日志')) evidence.clicked.push('view-mock-session-logs')
        await wait(500)
        evidence.assertions.session_visible = sessionWasVisible || (document.body.innerText || '').includes(${JSON.stringify(mockSessionId)})
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
    minWidth: width,
    minHeight: height,
    useContentSize: true,
    resizable: false,
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
  window.setContentSize(width, height, false)
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
      const content = document.querySelector('.content')
      const page = content?.firstElementChild
      const contentRect = content?.getBoundingClientRect()
      const pageRect = page?.getBoundingClientRect()
      const inside = (child, parent, tolerance = 1) => child && parent
        ? child.left >= parent.left - tolerance && child.right <= parent.right + tolerance
          && child.top >= parent.top - tolerance && child.bottom <= parent.bottom + tolerance
        : false
      const sections = page ? [...page.children].filter((item) => {
        const style = getComputedStyle(item)
        return style.display !== 'none' && style.position !== 'fixed' && !item.classList.contains('toast') && !item.classList.contains('dialog-overlay')
      }) : []
      const sectionBounds = sections.map((item) => {
        const value = item.getBoundingClientRect()
        return { className:item.className, inside:inside(value, contentRect), top:value.top, bottom:value.bottom }
      })
      const internalScroll = [...document.querySelectorAll('.table-scroll,.table-wrap,.session-table-wrap,.card-scroll,.timeline-scroll,.watch-table-wrap,.frame-table-wrap,.diagnosis-list')]
        .filter((item) => getComputedStyle(item).display !== 'none')
        .map((item) => {
          const original = item.scrollTop
          item.scrollTop = item.scrollHeight
          const endReached = item.scrollHeight <= item.clientHeight + 1 || item.scrollTop + item.clientHeight >= item.scrollHeight - 1
          item.scrollTop = 0
          const startReached = item.scrollTop === 0
          item.scrollTop = original
          return { className:item.className, startReached, endReached }
        })
      const segmentedBounds = [...document.querySelectorAll('.segmented')].map((group) => {
        const parent = group.getBoundingClientRect()
        return [...group.querySelectorAll('button')].map((button) => {
          const child = button.getBoundingClientRect()
          return { text:(button.textContent || '').trim(), inside:inside(child,parent), textFits:button.scrollWidth <= button.clientWidth + 1 }
        })
      }).flat()
      const chartBounds = [...document.querySelectorAll('canvas')].map((canvas) => {
        const child = canvas.getBoundingClientRect()
        const container = canvas.closest('.chart')?.getBoundingClientRect()
        return { inside:inside(child,container,2), width:child.width, height:child.height }
      })
      const actionTextBounds = [...document.querySelectorAll('.industrial-action .action-copy strong')].map((text) => ({
        text:(text.textContent || '').trim(), fits:text.scrollWidth <= text.clientWidth + 1,
      }))
      const compactColor = (value) => value.replace(/\\s/g, '')
      const signalLightSamples = [...document.querySelectorAll('.signal-light')].map((item) => ({
        label:item.querySelector('.label')?.textContent?.trim(), state:item.dataset.state,
        tone:['tone-yellow','tone-red','tone-white'].find((name) => item.classList.contains(name)) || '',
        color:item.querySelector('.lamp') ? compactColor(getComputedStyle(item.querySelector('.lamp')).color) : '',
        text:item.querySelector('strong')?.textContent?.trim(),
      }))
      const lightColors = { 'tone-yellow':'rgb(246,195,67)', 'tone-red':'rgb(239,68,68)', 'tone-white':'rgb(248,250,252)' }
      const screenshotLightColorsMatch = signalLightSamples.every((item) => item.state === 'off'
        ? item.color === 'rgb(148,163,184)'
        : item.state === 'unknown'
          ? item.color === 'rgb(120,138,159)'
          : item.color === lightColors[item.tone])
      return {
        location: location.hash,
        viewport: { width: innerWidth, height: innerHeight },
        page_scrollable: Boolean(root && root.scrollHeight > root.clientHeight + 1),
        root_scroll_height: root?.scrollHeight || 0,
        root_client_height: root?.clientHeight || 0,
        white_controls: whiteControls,
        chart_canvas_count: canvases,
        page_inside_content: inside(pageRect, contentRect),
        section_bounds: sectionBounds,
        sections_inside_content: sectionBounds.every((item) => item.inside),
        internal_scroll_reachable: internalScroll.every((item) => item.startReached && item.endReached),
        bottom_blank_px: pageRect && contentRect ? Math.max(0, Math.round(contentRect.bottom - pageRect.bottom)) : null,
        segmented_bounds: segmentedBounds,
        segmented_controls_fit: segmentedBounds.every((item) => item.inside && item.textFits),
        chart_bounds: chartBounds,
        charts_inside_containers: chartBounds.every((item) => item.inside && item.width > 0 && item.height > 0),
        action_text_bounds: actionTextBounds,
        action_texts_fit: actionTextBounds.every((item) => item.fits),
        signal_light_samples: signalLightSamples,
        screenshot_light_colors_match: screenshotLightColorsMatch,
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

async function openAuthenticatedWindow(route, readySelector) {
  const window = new BrowserWindow({ width:1366, height:768, show:false, frame:false, backgroundColor:'#07111F', webPreferences:{ preload:path.join(__dirname,'preload.cjs'), contextIsolation:true, nodeIntegration:false, backgroundThrottling:false } })
  await window.loadURL(`${baseUrl}/#/login`)
  await window.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(apiToken)})`)
  await window.loadURL(`${baseUrl}/?stability=${Date.now()}-${encodeURIComponent(route)}#${route}`)
  const deadline = Date.now() + 15000
  while (Date.now() < deadline) {
    const ready = await window.webContents.executeJavaScript(`Boolean(document.querySelector(${JSON.stringify(readySelector)}))`)
    if (ready) {
      await sleep(captureDelayMs)
      return window
    }
    await sleep(250)
  }
  const currentRoute = await window.webContents.executeJavaScript('location.hash')
  window.destroy()
  throw new Error(`Timed out waiting for ${readySelector} on ${route}; current route: ${currentRoute}`)
}

async function verifyRuntimeStability() {
  const [signals, autoTest, alarms] = await Promise.all([
    openAuthenticatedWindow('/signal-dashboard', '.signal-dashboard-page .signal-light'),
    openAuthenticatedWindow('/auto-test', '.auto-test-page .action-row button'),
    openAuthenticatedWindow('/alarm-diagnosis', '.alarm-page .action-row button'),
  ])
  const initialize = async (window, selector) => window.webContents.executeJavaScript(`
    (() => {
      window.__phase04StableButton = document.querySelector(${JSON.stringify(selector)})
      if (!window.__phase04StableButton) return null
      return { disabled:window.__phase04StableButton.disabled, opacity:getComputedStyle(window.__phase04StableButton).opacity }
    })()
  `)
  const autoInitial = await initialize(autoTest, '.action-row button')
  const alarmInitial = await initialize(alarms, '.action-row button')
  const qualitySamples = []
  let signalStable = true
  let autoStable = Boolean(autoInitial)
  let alarmStable = Boolean(alarmInitial)
  for (let second = 0; second < stabilitySeconds; second += 1) {
    const [signalSample, autoSample, alarmSample] = await Promise.all([
      signals.webContents.executeJavaScript(`(() => { const light=document.querySelector('.signal-light'); return { quality:light?.dataset.quality || '', pageState:document.querySelector('[role="status"]')?.dataset.state || '' } })()`),
      autoTest.webContents.executeJavaScript(`(() => { const current=document.querySelector('.action-row button'); return { same:current===window.__phase04StableButton, disabled:current?.disabled, opacity:current?getComputedStyle(current).opacity:'' } })()`),
      alarms.webContents.executeJavaScript(`(() => { const current=document.querySelector('.action-row button'); return { same:current===window.__phase04StableButton, disabled:current?.disabled, opacity:current?getComputedStyle(current).opacity:'' } })()`),
    ])
    qualitySamples.push(signalSample)
    signalStable = signalStable && !['stale','invalid','unavailable'].includes(signalSample.quality)
    autoStable = autoStable && autoSample.same && autoSample.disabled === autoInitial.disabled && autoSample.opacity === autoInitial.opacity
    alarmStable = alarmStable && alarmSample.same && alarmSample.disabled === alarmInitial.disabled && alarmSample.opacity === alarmInitial.opacity
    await sleep(1000)
  }
  signals.destroy(); autoTest.destroy(); alarms.destroy()
  const qualities = [...new Set(qualitySamples.map((item) => item.quality))]
  return {
    duration_seconds: stabilitySeconds,
    sample_count: qualitySamples.length,
    signal_quality_values: qualities,
    signal_quality_stable: signalStable && qualities.length === 1,
    auto_test_button_stable: autoStable,
    alarm_button_stable: alarmStable,
  }
}

async function verifySessionLifecycle() {
  const firstWindow = new BrowserWindow({ show:false, webPreferences:{ contextIsolation:true, nodeIntegration:false } })
  await firstWindow.loadURL(`${baseUrl}/#/overview`)
  await sleep(captureDelayMs)
  const unauthenticatedRoute = await firstWindow.webContents.executeJavaScript('location.hash')
  await firstWindow.webContents.executeJavaScript(`sessionStorage.setItem('chassis_api_token', ${JSON.stringify(apiToken)})`)
  await firstWindow.loadURL(`${baseUrl}/#/overview`)
  await sleep(captureDelayMs)
  const reloaded = new Promise((resolve) => firstWindow.webContents.once('did-finish-load', resolve))
  firstWindow.webContents.reload()
  await reloaded
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
  const stability = await verifyRuntimeStability()
  const inspections = []
  for (const [name, route] of pages.filter(([name]) => !requestedPages.size || requestedPages.has(name))) {
    for (const [width, height] of viewports) {
      inspections.push(await capturePage(name, route, width, height))
    }
  }
  fs.writeFileSync(
    path.join(output, "page_capture_metrics.json"),
    JSON.stringify({ baseUrl, authentication, permission, stability, inspections }, null, 2),
  )
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
