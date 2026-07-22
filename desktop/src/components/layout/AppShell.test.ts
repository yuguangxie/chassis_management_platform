import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLayoutStore } from '../../stores/layout'

const refresh = vi.fn()
const connectWs = vi.fn()

vi.mock('../../stores/appStatus', () => ({
  useAppStatusStore: () => ({ refresh, connectWs }),
}))

import AppShell from './AppShell.vue'

describe('AppShell sidebar layout', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('shows the edge expansion control and restores the grid after a collapse', async () => {
    const layout = useLayoutStore()
    layout.collapseSidebar()
    const wrapper = mount(AppShell, {
      global: {
        stubs: {
          SidebarNav: { template: '<aside class="sidebar"></aside>' },
          TopStatusBar: { template: '<header class="topbar"></header>' },
          WindowChrome: { template: '<header class="window-chrome"></header>' },
          RouterView: { template: '<div></div>' },
        },
      },
    })

    expect(wrapper.classes()).toContain('sidebar-collapsed')
    const expand = wrapper.get('.sidebar-expand')
    expect(expand.attributes('title')).toBe('展开侧栏')
    await expand.trigger('click')

    expect(layout.sidebarCollapsed).toBe(false)
    expect(wrapper.classes()).not.toContain('sidebar-collapsed')
    expect(wrapper.find('.sidebar-expand').exists()).toBe(false)
    wrapper.unmount()
  })
})
