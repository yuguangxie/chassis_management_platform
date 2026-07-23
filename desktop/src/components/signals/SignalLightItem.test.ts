import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import SignalLightItem from './SignalLightItem.vue'

describe('灯光与制动信号灯效', () => {
  it('状态切换时灯色立即归一化，避免旧的点亮色残留', () => {
    const source = readFileSync('src/components/signals/SignalLightItem.vue', 'utf8')
    expect(source).not.toContain('transition:color')
  })

  const signals = [
    ['左转灯', 'yellow'], ['右转灯', 'yellow'], ['位置灯', 'red'],
    ['近光灯', 'white'], ['制动请求', 'red'],
  ] as const

  it.each(signals)('%s 开启时使用 %s 灯效', (label, tone) => {
    const wrapper = mount(SignalLightItem, { props: { label, value: 'ON', quality: 'good', tone } })
    expect(wrapper.attributes('data-state')).toBe('on')
    expect(wrapper.classes()).toContain(`tone-${tone}`)
    expect(wrapper.text()).toContain('开启')
  })

  for (const [signalLabel, tone] of signals) {
    it.each([
      ['OFF', 'good', 'off', '关闭'],
      ['ON', 'stale', 'unknown', '数据陈旧'],
      [true, 'invalid', 'unknown', '无效'],
      [1, 'unavailable', 'unknown', '未知'],
    ] as const)(`${signalLabel} 值/质量 %s/%s 不保留错误灯效`, (value, quality, state, stateLabel) => {
      const wrapper = mount(SignalLightItem, { props: { label: signalLabel, value, quality, tone } })
      expect(wrapper.attributes('data-state')).toBe(state)
      expect(wrapper.classes()).not.toContain('on')
      expect(wrapper.text()).toContain(stateLabel)
    })
  }
})
