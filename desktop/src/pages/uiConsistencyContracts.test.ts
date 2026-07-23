import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const pageFiles = [
  'OverviewPage.vue', 'NetworkConfigPage.vue', 'CanMonitorPage.vue', 'SignalDashboardPage.vue',
  'RealtimeCurvePage.vue', 'ManualControlPage.vue', 'AutoTestPage.vue', 'AlarmDiagnosisPage.vue',
  'ReportManagementPage.vue', 'HistoryPage.vue', 'SystemSettingsPage.vue',
]
const source = (file: string) => readFileSync(new URL(file, import.meta.url), 'utf8')

describe('11 页 UI 收口静态契约', () => {
  it.each(pageFiles)('%s 具有统一状态槽和受限页面根布局', (file) => {
    const text = source(file)
    expect(text).toContain('PageDataState')
    expect(text).toMatch(/height:\s*100%/)
    expect(text).toMatch(/min-height:\s*0/)
  })

  it('实时曲线不包含虚构默认会话且实时模式不加载回放', () => {
    const text = source('RealtimeCurvePage.vue')
    expect(text).not.toContain('EOL-20260401-0001')
    expect(text).toContain("route.query.mode === 'history'")
    expect(text).toContain('resetHistoryState')
  })

  it('Network 以真实草稿开关表达通道启用和发送安全策略', () => {
    const text = source('NetworkConfigPage.vue')
    expect(text).toContain('v-model="selectedChannel.enabled"')
    expect(text).not.toContain('v-model="selectedChannel.tx_enabled"')
    expect(text).toContain('未应用变更')
    expect(text).toContain('安全策略锁定：CAN1 禁止主动发送')
    expect(text).toContain('仅批准 CAN2 的 0x121')
  })

  it('1366 下不再隐藏手动控制曲线和安全提示', () => {
    const text = source('ManualControlPage.vue')
    expect(text).not.toMatch(/\.chart-row,\s*\n\s*\.safety-tip\s*\{\s*display:\s*none/)
  })

  it('全局分段控件不再强制固定最小宽度或越过父容器高度', () => {
    const text = readFileSync('src/styles/industrial-theme.css', 'utf8')
    expect(text).not.toMatch(/\.segmented button\s*\{[^}]*min-width:\s*70px/s)
    expect(text).toMatch(/\.segmented button\s*\{[^}]*height:\s*100%/s)
    expect(text).toMatch(/\.segmented button\s*\{[^}]*min-width:\s*0/s)
  })

  it('批准词典中的原始英文状态不直接作为模板选项文字', () => {
    for (const file of pageFiles) {
      const template = source(file).split('<script setup')[0]
      expect(template, file).not.toMatch(/>(PASS|FAIL|RUNNING|ABORTED|WAIT|PAUSED|online|offline|unavailable|stale|invalid|Manual|Remote|Auto|ON|OFF|RELEASED)(?=<)/)
    }
  })
})
