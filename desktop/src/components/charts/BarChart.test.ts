import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const echartsMock = vi.hoisted(() => {
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
  return { chart, init: vi.fn(() => chart) }
})
vi.mock('echarts', () => ({ init: echartsMock.init }))

import BarChart from './BarChart.vue'

function nextFrame() {
  return new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()))
}

describe('BarChart', () => {
  it('resizes from the observed container and disposes its ECharts instance', async () => {
    const wrapper = mount(BarChart, { props: { option: { series: [] }, height: '180px' } })
    await nextFrame()
    expect(echartsMock.init).toHaveBeenCalledTimes(1)

    window.dispatchEvent(new Event('resize'))
    await nextFrame()
    expect(echartsMock.chart.resize).toHaveBeenCalled()

    wrapper.unmount()
    expect(echartsMock.chart.dispose).toHaveBeenCalledTimes(1)
  })
})
