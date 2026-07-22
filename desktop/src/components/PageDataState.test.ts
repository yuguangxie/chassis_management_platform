import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PageDataState from './PageDataState.vue'

describe('PageDataState', () => {
  it.each([
    [{ loading: true }, 'loading', '正在加载'],
    [{ empty: true }, 'empty', '暂无数据'],
    [{ stale: true }, 'stale', '数据已陈旧'],
    [{ error: 'backend timeout' }, 'error', '加载失败'],
    [{ error: '403 权限不足' }, 'permission-denied', '权限不足'],
  ] as const)('renders the unified %s state', (props, state, label) => {
    const wrapper = mount(PageDataState, { props: props as { loading?:boolean; empty?:boolean; stale?:boolean; error?:string } })
    expect(wrapper.get('[role="status"]').attributes('data-state')).toBe(state)
    expect(wrapper.text()).toContain(label)
  })

  it('keeps fail-closed error precedence over stale fallback data', () => {
    const wrapper = mount(PageDataState, { props: { error: 'request timed out', stale: true, empty: true } })
    expect(wrapper.get('[role="status"]').attributes('data-state')).toBe('error')
  })
})
