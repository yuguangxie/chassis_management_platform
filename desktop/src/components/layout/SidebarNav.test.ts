import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useLayoutStore } from '../../stores/layout'
import SidebarNav from './SidebarNav.vue'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

describe('SidebarNav', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('collapses through the visible bottom control', async () => {
    const wrapper = mount(SidebarNav, {
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    expect(useLayoutStore().sidebarCollapsed).toBe(false)
    expect(wrapper.get('.collapse').attributes('title')).toBe('隐藏左侧导航栏')
    await wrapper.get('.collapse').trigger('click')
    expect(useLayoutStore().sidebarCollapsed).toBe(true)
  })
})
