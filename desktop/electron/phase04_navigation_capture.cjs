const { app, BrowserWindow } = require("electron")
const fs = require("node:fs")
const path = require("node:path")

const baseUrl = process.env.PHASE04_TARGET_URL || "http://127.0.0.1:5173"
const output = process.env.PHASE04_ELECTRON_OUTPUT
if (!output) throw new Error("PHASE04_ELECTRON_OUTPUT is required")

const pages = [
  "/overview", "/network-config", "/can-monitor", "/signal-dashboard", "/realtime-curve",
  "/manual-control", "/auto-test", "/alarm-diagnosis", "/report-management", "/history", "/system-settings",
]
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function inspect(window) {
  return window.webContents.executeJavaScript(`
    (() => {
      const root = document.scrollingElement
      return {
        hash: location.hash,
        title: document.querySelector('.page-title, h1, h2')?.textContent?.trim() || '',
        failedToFetch: /Failed to fetch/i.test(document.body?.innerText || ''),
        pageScrollable: Boolean(root && root.scrollHeight > root.clientHeight + 1),
        canvases: document.querySelectorAll('canvas').length,
      }
    })()
  `)
}

async function main() {
  await app.whenReady()
  fs.mkdirSync(output, { recursive: true })
  const window = new BrowserWindow({
    width: 1920,
    height: 1080,
    show: false,
    frame: false,
    backgroundColor: "#07111F",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  const inspections = []
  await window.loadURL(`${baseUrl}/#${pages[0]}`)
  for (const route of pages) {
    await window.webContents.executeJavaScript(`location.hash = ${JSON.stringify(`#${route}`)}`)
    await sleep(900)
    inspections.push({ route, ...(await inspect(window)) })
  }
  fs.writeFileSync(path.join(output, "single_window_navigation.json"), JSON.stringify({ inspections }, null, 2))
  await window.close()
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
