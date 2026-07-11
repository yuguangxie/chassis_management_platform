import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const candidates = process.platform === 'win32'
  ? [resolve(root, 'backend/.venv/Scripts/python.exe'), 'python3', 'python']
  : [resolve(root, 'backend/.venv/bin/python'), 'python3', 'python']

let executed = false
for (const candidate of candidates) {
  if (candidate.includes('/') && !existsSync(candidate)) continue
  const result = spawnSync(candidate, ['scripts/run_quality.py', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' })
  if (result.error?.code === 'ENOENT') continue
  executed = true
  process.exitCode = result.status ?? 1
  break
}
if (!executed) {
  console.error('No Python interpreter found. Create backend/.venv or install python3.')
  process.exitCode = 1
}
