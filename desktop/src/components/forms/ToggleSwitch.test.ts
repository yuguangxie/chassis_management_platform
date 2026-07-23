import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ToggleSwitch from './ToggleSwitch.vue'

describe('ToggleSwitch', () => {
  it('通过真实 button 暴露 switch 语义并更新草稿', async () => {
    const wrapper = mount(ToggleSwitch, { props: { modelValue: false, label: '通道启用' } })
    const button = wrapper.get('button')
    expect(button.attributes('role')).toBe('switch')
    expect(button.attributes('aria-checked')).toBe('false')
    await button.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
  })

  it('安全锁定时不可交互并给出原因', async () => {
    const wrapper = mount(ToggleSwitch, { props: { modelValue: false, disabled: true, label: '主动发送', disabledReason: '安全策略锁定' } })
    const button = wrapper.get('button')
    expect(button.attributes('aria-disabled')).toBe('true')
    expect(button.attributes('title')).toBe('安全策略锁定')
    await button.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
