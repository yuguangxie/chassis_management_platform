import { describe, expect, it } from 'vitest'
import router from './index'

describe('application routes', () => {
  it('keeps all eleven operational pages lazy-loaded', () => {
    const routes = router.getRoutes().filter((route) => route.path !== '/')
    expect(routes).toHaveLength(11)
    expect(routes.every((route) => typeof route.components?.default === 'function')).toBe(true)
  })
})
