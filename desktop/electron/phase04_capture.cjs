const { app, BrowserWindow } = require("electron")
const fs = require("node:fs")
const path = require("node:path")

const baseUrl = process.env.PHASE04_TARGET_URL || "http://127.0.0.1:5173"
const output = process.env.PHASE04_ELECTRON_OUTPUT
if (!output) throw new Error("PHASE04_ELECTRON_OUTPUT is required")
const captureDelayMs = Number(process.env.PHASE04_CAPTURE_DELAY_MS || 1800)

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

async function capturePage(name, route, width, height) {
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
  await window.loadURL(`${baseUrl}/#${route}`)
  await sleep(captureDelayMs)
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
        layout_rects: { shell: rect('.shell'), sidebar: rect('.sidebar'), topbar: rect('.topbar'), content: rect('.content') },
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
  await window.close()
  return { page: name, route, width, height, filename, renderer_console_errors: rendererConsoleErrors, renderer_page_errors: rendererPageErrors, ...inspection }
}

async function main() {
  await app.whenReady()
  fs.mkdirSync(output, { recursive: true })
  const inspections = []
  for (const [name, route] of pages.filter(([name]) => !requestedPages.size || requestedPages.has(name))) {
    for (const [width, height] of viewports) {
      inspections.push(await capturePage(name, route, width, height))
    }
  }
  fs.writeFileSync(
    path.join(output, "page_capture_metrics.json"),
    JSON.stringify({ baseUrl, inspections }, null, 2),
  )
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
