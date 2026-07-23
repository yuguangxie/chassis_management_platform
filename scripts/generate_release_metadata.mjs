import { createHash, randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { basename, dirname, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const desktop = resolve(root, 'desktop')
const mode = process.argv[2]
const signed = Boolean(process.env.CSC_LINK)
const version = JSON.parse(readFileSync(resolve(desktop, 'package.json'), 'utf8')).version
const commit = (() => { try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim() } catch { return 'unavailable' } })()
const sourceStatus = (() => { try { return execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim() } catch { return 'unavailable' } })()
const sourceDirty = Boolean(sourceStatus)
const builtAt = new Date().toISOString()
const releaseLabel = signed ? (sourceDirty ? 'signed-nonreleasable' : 'signed-production-candidate') : 'unsigned-internal'

function sha256(file) {
  return createHash('sha256').update(readFileSync(file)).digest('hex')
}

function writeJson(file, value) {
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

if (mode === 'prepare') {
  writeJson(resolve(desktop, 'release-build.json'), {
    product: '低速无人车线控底盘生产下线管理平台',
    version,
    commit,
    built_at_utc: builtAt,
    signed,
    source_dirty: sourceDirty,
    release_label: releaseLabel,
    safety_default: 'mock-loopback-control-transmission-stopped',
  })
  process.exit(0)
}

if (mode !== 'finalize') throw new Error('usage: generate_release_metadata.mjs prepare|finalize')

const lock = JSON.parse(readFileSync(resolve(desktop, 'package-lock.json'), 'utf8'))
const npmComponents = Object.entries(lock.packages || {})
  .filter(([key, value]) => key.startsWith('node_modules/') && value.version)
  .map(([key, value]) => ({ type: 'library', name: basename(key), version: value.version, purl: `pkg:npm/${encodeURIComponent(basename(key))}@${value.version}` }))
const uvText = readFileSync(resolve(root, 'backend', 'uv.lock'), 'utf8')
const pythonComponents = [...uvText.matchAll(/\[\[package\]\]\s+name = "([^"]+)"\s+version = "([^"]+)"/g)]
  .map((match) => ({ type: 'library', name: match[1], version: match[2], purl: `pkg:pypi/${match[1]}@${match[2]}` }))
const sbom = {
  bomFormat: 'CycloneDX',
  specVersion: '1.5',
  serialNumber: `urn:uuid:${randomUUID()}`,
  version: 1,
  metadata: { timestamp: builtAt, component: { type: 'application', name: 'chassis-eol-desktop', version } },
  components: [...npmComponents, ...pythonComponents],
}
const releaseDir = resolve(desktop, 'release', 'windows')
writeJson(resolve(releaseDir, 'sbom.cdx.json'), sbom)

const ignored = new Set(['release-manifest.json'])
const artifacts = readdirSync(releaseDir)
  .map((name) => resolve(releaseDir, name))
  .filter((file) => statSync(file).isFile() && !ignored.has(basename(file)))
  .map((file) => ({ file: basename(file), bytes: statSync(file).size, sha256: sha256(file) }))
const dbcName = readdirSync(resolve(root, 'assets')).find((name) => name.toLowerCase().endsWith('.dbc'))
const dbcPath = dbcName ? resolve(root, 'assets', dbcName) : ''
const configSchema = resolve(root, 'docs', 'production-configuration.schema.json')
const manifest = {
  schema_version: 1,
  product: '低速无人车线控底盘生产下线管理平台',
  software_version: version,
  commit,
  built_at_utc: builtAt,
  source: { commit, dirty: sourceDirty, dirty_file_count: sourceStatus ? sourceStatus.split(/\r?\n/).length : 0 },
  release_label: releaseLabel,
  signing: { signed, provider: signed ? 'electron-builder CSC interface' : null, formal_release: signed && !sourceDirty },
  runtime: { electron: '43.1.0', python: 'embedded by PyInstaller', network_dependency_at_runtime: false },
  compatibility: { database_schema: 4, downgrade_open_newer_schema: 'blocked', migration_backup: 'required' },
  packaged_inputs: {
    dbc: dbcPath && existsSync(dbcPath) ? { file: dbcName, sha256: sha256(dbcPath) } : null,
    production_config_schema_sha256: sha256(configSchema),
  },
  safety_boundaries: [
    'default runtime profile is mock on 127.0.0.1',
    'first launch does not start a simulator or transmit CAN',
    'active transmit allowlist remains CAN2 0x121 only',
    '0x123, 0x126 and CANopen NMT remain disabled',
    'sidecar readiness is not vehicle readiness; missing feedback remains HTTP 409',
  ],
  artifacts,
}
writeJson(resolve(releaseDir, 'release-manifest.json'), manifest)
const evidence = resolve(root, 'docs', 'verification', 'software-p0-p1-closure-2026-07-23', 'release')
writeJson(resolve(evidence, 'release-manifest.json'), manifest)
writeJson(resolve(evidence, 'sbom.cdx.json'), sbom)
console.log(JSON.stringify({ releaseDir, artifactCount: artifacts.length, signed }, null, 2))
