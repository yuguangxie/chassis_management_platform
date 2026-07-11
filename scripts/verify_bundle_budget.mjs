import { gzipSync } from 'node:zlib'
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const assets = resolve(root, 'desktop/dist/assets')
const output = process.argv[2] || resolve(root, 'docs/verification/phase-05/bundle-report.json')
if (!existsSync(assets)) throw new Error(`build assets not found: ${assets}`)

const chunks = readdirSync(assets)
  .filter((name) => name.endsWith('.js'))
  .map((name) => {
    const bytes = readFileSync(resolve(assets, name))
    return { name, bytes: bytes.length, gzip_bytes: gzipSync(bytes).length }
  })
  .sort((left, right) => right.gzip_bytes - left.gzip_bytes)

const main = chunks.find((item) => item.name.startsWith('index-'))
const echarts = chunks.find((item) => item.name.startsWith('echarts-vendor-'))
const totalGzipBytes = chunks.reduce((total, item) => total + item.gzip_bytes, 0)
const budgets = { main_gzip_bytes: 100_000, echarts_vendor_gzip_bytes: 380_000, total_js_gzip_bytes: 800_000 }
const assertions = {
  main_within_budget: Boolean(main) && main.gzip_bytes <= budgets.main_gzip_bytes,
  echarts_vendor_within_budget: Boolean(echarts) && echarts.gzip_bytes <= budgets.echarts_vendor_gzip_bytes,
  total_within_budget: totalGzipBytes <= budgets.total_js_gzip_bytes,
}
const result = { budgets, main, echarts_vendor: echarts, total_gzip_bytes: totalGzipBytes, chunks, assertions, passed: Object.values(assertions).every(Boolean) }
mkdirSync(dirname(output), { recursive: true })
writeFileSync(output, JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
if (!result.passed) process.exitCode = 1
