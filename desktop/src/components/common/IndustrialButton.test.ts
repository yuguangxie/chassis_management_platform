import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IndustrialActionButton from './IndustrialActionButton.vue'
import IndustrialButton from './IndustrialButton.vue'

describe('工业按钮体系', () => {
  it('提供统一的紧凑、危险、焦点和禁用语义', async () => {
    const wrapper = mount(IndustrialButton, {
      props: { size: 'compact', variant: 'danger', disabled: true },
      slots: { default: '删除' },
    })
    const button = wrapper.get('button')
    expect(button.classes()).toEqual(expect.arrayContaining(['industrial-button', 'compact', 'danger']))
    expect(button.attributes('aria-disabled')).toBe('true')
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('主要操作保持 70px 结构和 loading 状态', () => {
    const wrapper = mount(IndustrialActionButton, {
      props: { title: '保存并应用', subtitle: '失败自动回滚', loading: true },
      slots: { icon: '<span data-testid="icon" />' },
    })
    expect(wrapper.get('button').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('button').attributes('title')).toBe('保存并应用：失败自动回滚')
    expect(wrapper.text()).toContain('保存并应用')
    expect(wrapper.text()).toContain('失败自动回滚')
  })
})
