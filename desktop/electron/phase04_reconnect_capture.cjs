const { app, BrowserWindow } = require("electron")
const fs = require("node:fs")
const path = require("node:path")

const baseUrl = process.env.PHASE04_TARGET_URL || "http://127.0.0.1:5173"
const output = process.env.PHASE04_ELECTRON_OUTPUT
if (!output) throw new Error("PHASE04_ELECTRON_OUTPUT is required")

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function inspect(window) {
  return window.webContents.executeJavaScript(`
    (() => {
      const root = document.scrollingElement
      return {
      hash: location.hash,
      failedToFetch: /Failed to fetch/i.test(document.body?.innerText || ''),
      offlinePills: [...document.querySelectorAll('*')]
        .filter((element) => /mock|offline|failed to fetch/i.test(element.textContent || ''))
        .slice(0, 8)
        .map((element) => element.textContent.trim()),
      topbar: document.querySelector('.topbar')?.innerText || '',
      pageScrollable: Boolean(root && root.scrollHeight > root.clientHeight + 1),
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
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })
  await window.loadURL(`${baseUrl}/#/overview`)
  await sleep(1800)
  const before = await inspect(window)
  fs.writeFileSync(path.join(output, "before-restart.png"), (await window.webContents.capturePage()).toPNG())

  // The caller restarts FastAPI while this existing renderer stays alive.
  await sleep(12000)
  const after = await inspect(window)
  fs.writeFileSync(path.join(output, "after-restart.png"), (await window.webContents.capturePage()).toPNG())
  fs.writeFileSync(path.join(output, "reconnect_renderer.json"), JSON.stringify({ before, after }, null, 2))
  await window.close()
  app.quit()
}

main().catch((error) => {
  console.error(error)
  app.exit(1)
})
