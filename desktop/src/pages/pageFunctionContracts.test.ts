import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { routes } from '../router'

type PageContract = {
  file: string
  route: string
  read: string
  write: string
  error: string
  emptyOrStale: string
}

const contracts: PageContract[] = [
  { file:'OverviewPage.vue', route:'/overview', read:"'/overview/summary'", write:"'/reports/scan'", error:'formatApiError', emptyOrStale:'—（stale）' },
  { file:'NetworkConfigPage.vue', route:'/network-config', read:"'/config/channels'", write:"apiPut<NetworkConfigSummary", error:'界面已回滚', emptyOrStale:'offline.value ? []' },
  { file:'CanMonitorPage.vue', route:'/can-monitor', read:'store.loadLatest()', write:"'/can/frames/clear-display'", error:'formatApiError', emptyOrStale:'—（stale）' },
  { file:'SignalDashboardPage.vue', route:'/signal-dashboard', read:'signals.loadDashboard()', write:"'/signals/watchlist'", error:'formatApiError', emptyOrStale:'—（stale）' },
  { file:'RealtimeCurvePage.vue', route:'/realtime-curve', read:'signals.loadCurveTimeseries', write:"'/signals/snapshot'", error:'formatApiError', emptyOrStale:'—（stale）' },
  { file:'ManualControlPage.vue', route:'/manual-control', read:'control.loadAll()', write:"'/control/121/send-once'", error:'formatActionError', emptyOrStale:'control.stale' },
  { file:'AutoTestPage.vue', route:'/auto-test', read:'eol.loadDashboard()', write:"'start'", error:'formatActionError', emptyOrStale:':stale="eol.offline"' },
  { file:'AlarmDiagnosisPage.vue', route:'/alarm-diagnosis', read:'alarms.loadDashboard()', write:'alarms.runAction', error:'formatApiError', emptyOrStale:'alarms.offline ? []' },
  { file:'ReportManagementPage.vue', route:'/report-management', read:'reportsStore.loadDashboard()', write:'reportsStore.submitPrint', error:'formatApiError', emptyOrStale:':empty="!dashboard.reports.length"' },
  { file:'HistoryPage.vue', route:'/history', read:'historyStore.loadDashboard', write:'historyStore.exportHistory', error:'查询失败', emptyOrStale:'historyStore.offline ? []' },
  { file:'SystemSettingsPage.vue', route:'/system-settings', read:'settingsStore.loadDashboard()', write:'settingsStore.previewConfig', error:'formatError', emptyOrStale:':stale="settingsStore.offline"' },
]

function source(file: string) {
  return readFileSync(new URL(file, import.meta.url), 'utf8')
}

describe('11-page control-to-service contracts', () => {
  it.each(contracts)('$file has successful read, major write, failure, and empty/stale assertions', (contract) => {
    const text = source(contract.file)
    expect(text, `${contract.file}: unified state`).toContain('PageDataState')
    expect(text, `${contract.file}: successful read chain`).toContain(contract.read)
    expect(text, `${contract.file}: primary write chain`).toContain(contract.write)
    expect(text, `${contract.file}: backend failure/timeout chain`).toContain(contract.error)
    expect(text, `${contract.file}: empty or stale chain`).toContain(contract.emptyOrStale)
  })

  it.each(contracts)('$route has authenticated role metadata enforced by the router', (contract) => {
    const route = routes.find((item) => item.path === contract.route)
    expect(route).toBeDefined()
    expect(route?.meta?.requiresAuth).toBe(true)
    expect(route?.meta?.roles?.length).toBeGreaterThan(0)
  })

  it('requires every unresolved visible button to be disabled and labelled', () => {
    for (const contract of contracts) {
      const text = source(contract.file)
      for (const match of text.matchAll(/<button[^>]*>[^<]*(?:尚未实现)[\s\S]*?<\/button>/g)) {
        expect(match[0], `${contract.file}: unresolved control must be disabled`).toContain('disabled')
        expect(match[0], `${contract.file}: unresolved control must explain why`).toContain('title=')
      }
    }
  })

  it('masks offline FPS and live metrics instead of presenting fallback values as fresh', () => {
    expect(source('OverviewPage.vue')).toContain("return '—（stale）'")
    expect(source('NetworkConfigPage.vue')).toContain('offline.value ? []')
    expect(source('CanMonitorPage.vue')).toContain("store.offline ? '—（stale）'")
    expect(source('SignalDashboardPage.vue')).toContain("signals.offline ? '—（stale）'")
    expect(source('RealtimeCurvePage.vue')).toContain('if (signals.offline')
  })
})
