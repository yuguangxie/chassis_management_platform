const { app, BrowserWindow } = require("electron")
const fs = require("node:fs")
const path = require("node:path")

const targetUrl = process.env.PHASE03_TARGET_URL || "http://127.0.0.1:5173/report-management"
const output = process.env.PHASE03_ELECTRON_OUTPUT

if (!output) throw new Error("PHASE03_ELECTRON_OUTPUT is required")

async function main() {
  await app.whenReady()
  const window = new BrowserWindow({
    width: 1920,
    height: 1080,
    show: false,
    backgroundColor: "#07111F",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  await window.loadURL(targetUrl)
  await new Promise((resolve) => setTimeout(resolve, 1500))
  const renderer = await window.webContents.executeJavaScript(`
    (async () => {
      const scan = document.querySelector('.scan-actions button')
      const result = {
        desktopFilesExposed: Boolean(window.desktopFiles && window.desktopFiles.openPath),
        scanButtonPresent: Boolean(scan),
        reportRowsBefore: document.querySelectorAll('.report-table tbody tr').length,
      }
      if (scan) scan.click()
      await new Promise((resolve) => setTimeout(resolve, 900))
      return {
        ...result,
        reportRowsAfter: document.querySelectorAll('.report-table tbody tr').length,
        toast: document.querySelector('.toast')?.textContent?.trim() || '',
      }
    })()
  `)
  const image = await window.webContents.capturePage()
  fs.mkdirSync(output, { recursive: true })
  fs.writeFileSync(path.join(output, "report-management.png"), image.toPNG())
  fs.writeFileSync(
    path.join(output, "electron-smoke.json"),
    JSON.stringify({ targetUrl, renderer }, null, 2),
  )
  await window.close()
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
