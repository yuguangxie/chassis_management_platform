import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const echartsMock = vi.hoisted(() => {
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
  return { chart, init: vi.fn(() => chart) }
})
vi.mock('echarts', () => ({ init: echartsMock.init }))

import DonutChart from './DonutChart.vue'

function nextFrame() {
  return new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))
}

describe('DonutChart', () => {
  it('responds to layout resize events and cleans up on unmount', async () => {
    const wrapper = mount(DonutChart, { props: { option: { series: [] } } })
    await nextFrame()
    expect(echartsMock.init).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new Event('resize'))
    await nextFrame()
    expect(echartsMock.chart.resize).toHaveBeenCalled()

    wrapper.unmount()
    expect(echartsMock.chart.dispose).toHaveBeenCalledTimes(1)
  })
})
