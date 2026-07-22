import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useLayoutStore } from './layout'

describe('layout store sidebar state', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('defaults to an expanded sidebar', () => {
    expect(useLayoutStore().sidebarCollapsed).toBe(false)
  })

  it('persists collapse and expand actions for the next application instance', () => {
    const layout = useLayoutStore()
    layout.collapseSidebar()
    expect(layout.sidebarCollapsed).toBe(true)
    expect(window.localStorage.getItem('chassis.sidebarCollapsed')).toBe('true')

    setActivePinia(createPinia())
    expect(useLayoutStore().sidebarCollapsed).toBe(true)

    useLayoutStore().expandSidebar()
    expect(window.localStorage.getItem('chassis.sidebarCollapsed')).toBe('false')
    expect(useLayoutStore().sidebarCollapsed).toBe(false)
  })

  it('toggles the shared state without route-specific state', () => {
    const layout = useLayoutStore()
    layout.toggleSidebar()
    expect(layout.sidebarCollapsed).toBe(true)
    layout.toggleSidebar()
    expect(layout.sidebarCollapsed).toBe(false)
  })
})
