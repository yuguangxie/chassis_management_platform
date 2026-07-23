import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const electronMain = readFileSync('electron/main.cjs', 'utf8')
const rendererCapture = readFileSync('electron/phase04_capture.cjs', 'utf8')
const installerVerification = readFileSync('../scripts/verify_windows_installer.ps1', 'utf8')

describe('packaged Electron E2E evidence contract', () => {
  it('waits for the Vue route and captures the current renderer frame', () => {
    expect(electronMain).toContain('createPackagedCaptureWindow(route, token, width, height)')
    expect(electronMain).toContain("waitForPackagedRoute(window, '/overview')")
    expect(electronMain).toContain('waitForPackagedRoute(window, route)')
    expect(electronMain).toContain("document.documentElement.dataset.currentRoute")
    expect(electronMain).toContain('captureWindow.webContents.capturePage()')
    expect(electronMain).not.toContain('const image = await mainWindow.capturePage()')
  })

  it('fails when the viewport, route, or page captures are not genuine', () => {
    for (const rule of ['route_capture_matches', 'viewport_matches_request', 'unique_page_captures']) {
      expect(electronMain).toContain(rule)
      expect(installerVerification).toContain(rule)
    }
  })

  it('waits for principal-backed routes instead of using a fixed refresh delay', () => {
    expect(rendererCapture).toContain("waitForRendererRoute(firstWindow, '/overview')")
    expect(rendererCapture).toContain("waitForRendererRoute(restartedWindow, '/login')")
    expect(rendererCapture).toContain("preload:path.join(__dirname,'preload.cjs')")
    expect(rendererCapture).not.toContain("const refreshedRoute = await firstWindow.webContents.executeJavaScript('location.hash')")
  })
})
