import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('global industrial form theme', () => {
  it('defines a dark color scheme and shared non-white form controls', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')
    expect(css).toContain('color-scheme:dark')
    expect(css).toMatch(/input[^{]*\{[^}]*background:\s*#07172A/s)
    expect(css).not.toMatch(/input[^{]*\{[^}]*background:\s*(?:#fff|white)/is)
  })
})
