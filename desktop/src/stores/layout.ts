import { defineStore } from 'pinia'

const sidebarStorageKey = 'chassis.sidebarCollapsed'

function readSidebarCollapsed() {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(sidebarStorageKey) === 'true'
  } catch {
    return false
  }
}

function persistSidebarCollapsed(value: boolean) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(sidebarStorageKey, String(value))
  } catch {
    // Storage can be disabled in hardened Electron profiles. Keep the UI usable.
  }
}

export const useLayoutStore = defineStore('layout', {
  state: () => ({ sidebarCollapsed: readSidebarCollapsed() }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      persistSidebarCollapsed(this.sidebarCollapsed)
    },
    collapseSidebar() {
      this.sidebarCollapsed = true
      persistSidebarCollapsed(true)
    },
    expandSidebar() {
      this.sidebarCollapsed = false
      persistSidebarCollapsed(false)
    },
  },
})
