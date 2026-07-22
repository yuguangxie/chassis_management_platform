import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const echartsMock = vi.hoisted(() => {
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
  return { chart, init: vi.fn(() => chart) }
})
vi.mock('echarts', () => ({ init: echartsMock.init }))

import RealtimeLineChart from './RealtimeLineChart.vue'

function nextFrame() {
  return new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))
}

describe('RealtimeLineChart', () => {
  it('waits for a measurable container, updates options, and disposes on unmount', async () => {
    const wrapper = mount(RealtimeLineChart, { props: { option: { series: [] }, height: '180px' } })
    await wrapper.vm.$nextTick()
    await nextFrame()

    expect(echartsMock.init).toHaveBeenCalledTimes(1)
    expect(echartsMock.chart.setOption).toHaveBeenCalledWith({ series: [] }, true)
    await wrapper.setProps({ option: { series: [{ data: [1, 2] }] } })
    await nextFrame()
    expect(echartsMock.chart.setOption).toHaveBeenLastCalledWith({ series: [{ data: [1, 2] }] }, true)
    wrapper.unmount()
    expect(echartsMock.chart.dispose).toHaveBeenCalledTimes(1)
  })
})
