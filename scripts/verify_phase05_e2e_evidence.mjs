import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const evidence = process.env.CHASSIS_E2E_OUTPUT
  ? resolve(root, process.env.CHASSIS_E2E_OUTPUT)
  : resolve(root, 'docs/verification/phase-05/e2e')
const summaryPath = resolve(evidence, 'e2e-summary.json')
const electronVersionPath = resolve(evidence, 'electron-version.txt')
const screenshotsPath = resolve(evidence, 'screenshots')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(existsSync(summaryPath), `missing E2E summary: ${summaryPath}`)
assert(existsSync(electronVersionPath), `missing Electron version evidence: ${electronVersionPath}`)
assert(existsSync(screenshotsPath), `missing screenshot evidence: ${screenshotsPath}`)

const summary = JSON.parse(readFileSync(summaryPath, 'utf8'))
const electronVersion = readFileSync(electronVersionPath, 'utf8').trim()
const screenshots = readdirSync(screenshotsPath).filter((file) => file.toLowerCase().endsWith('.png'))

assert(electronVersion === 'v43.1.0', `expected Electron evidence v43.1.0, received ${electronVersion}`)
assert(summary.electronVersion === 'v43.1.0', `expected summary Electron v43.1.0, received ${summary.electronVersion}`)
assert(summary.pageCount === 11, `expected 11 pages, received ${summary.pageCount}`)
assert(summary.viewportCount === 2, `expected 2 viewports, received ${summary.viewportCount}`)
assert(summary.screenshotCount === 22, `expected screenshotCount 22, received ${summary.screenshotCount}`)
assert(screenshots.length === 22, `expected exactly 22 PNG screenshots, received ${screenshots.length}`)
assert(summary.pageLevelScrollFailures === 0, `page scroll failures: ${summary.pageLevelScrollFailures}`)
assert(summary.failedFetchBanners === 0, `failed fetch banners: ${summary.failedFetchBanners}`)
assert(summary.whiteControlFailures === 0, `white control failures: ${summary.whiteControlFailures}`)
assert(Array.isArray(summary.rendererConsoleErrors) && summary.rendererConsoleErrors.length === 0, 'renderer console errors found')
assert(Array.isArray(summary.rendererPageErrors) && summary.rendererPageErrors.length === 0, 'renderer page errors found')
assert(typeof summary.simulatorOfflineDelayMs === 'number' && summary.simulatorOfflineDelayMs >= 1500 && summary.simulatorOfflineDelayMs <= 5000,
  `simulator offline transition outside expected range: ${summary.simulatorOfflineDelayMs}`)
assert(summary.offlineControlStatus === 409, `expected stale-online control status 409, received ${summary.offlineControlStatus}`)
assert(summary.nonLoopbackRequests === 0, `non-loopback requests: ${summary.nonLoopbackRequests}`)
assert(summary.permission?.viewer_network_redirects_403 === true, 'viewer did not redirect to the 403 page')
assert(summary.mockSession?.report_generated === true, 'Mock EOL session/report fixture was not generated')
assert(summary.interaction_assertions?.pages_exercised === 11, `expected 11 interacted pages, received ${summary.interaction_assertions?.pages_exercised}`)
assert(summary.interaction_assertions?.every_page_clicked === true, 'one or more pages had no safe UI interaction')
assert(summary.interaction_assertions?.every_assertion_passed === true, 'one or more page interaction assertions failed')
assert(summary.passed === true, 'E2E summary did not report passed=true')

console.log(JSON.stringify({
  electronVersion,
  screenshots: screenshots.length,
  simulatorOfflineDelayMs: summary.simulatorOfflineDelayMs,
  offlineControlStatus: summary.offlineControlStatus,
  interactedPages: summary.interaction_assertions.pages_exercised,
  verification: 'passed',
}, null, 2))
