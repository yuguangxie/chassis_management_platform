import { afterEach, vi } from 'vitest'

class TestResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}
  observe(target: Element) {
    this.callback([{ target } as ResizeObserverEntry], this as unknown as ResizeObserver)
  }
  disconnect() {}
  unobserve() {}
}

Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 480 })
Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, get: () => 240 })
vi.stubGlobal('ResizeObserver', TestResizeObserver)

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})
