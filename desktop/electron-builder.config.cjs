const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const sidecar = process.env.CHASSIS_SIDECAR_STAGE
  || path.join(os.tmpdir(), 'chassis-eol-sidecar-build', 'dist', 'chassis-eol-backend')
const releaseBuild = path.join(__dirname, 'release-build.json')
if (!fs.existsSync(releaseBuild)) throw new Error(`release build descriptor is missing: ${releaseBuild}`)
const descriptor = JSON.parse(fs.readFileSync(releaseBuild, 'utf8'))
const signed = descriptor.signed === true
const requireSigning = process.env.CHASSIS_REQUIRE_SIGNING === '1'

if (requireSigning && !signed) throw new Error('CHASSIS_REQUIRE_SIGNING=1 but CSC_LINK is not configured')
if (!fs.existsSync(sidecar)) throw new Error(`offline sidecar is missing: ${sidecar}`)

const releaseLabel = descriptor.release_label || (signed ? 'signed-nonreleasable' : 'unsigned-internal')

module.exports = {
  appId: 'com.yunle.chassis-eol-management',
  productName: '低速无人车线控底盘下线管理平台',
  copyright: 'Copyright © 2026 Yunle',
  asar: true,
  npmRebuild: false,
  directories: {
    output: 'release/windows',
    buildResources: 'build',
  },
  files: [
    '!node_modules/**/*',
    'dist/**/*',
    'electron/main.cjs',
    'electron/preload.cjs',
    'electron/sidecar.cjs',
    'electron/diagnostics.html',
    'package.json',
  ],
  extraResources: [
    { from: sidecar, to: 'backend-sidecar' },
    { from: path.join(root, 'configs'), to: 'configs', filter: ['**/*', '!**/*.secret', '!**/*.key'] },
    { from: path.join(root, 'assets'), to: 'assets' },
    { from: path.join(root, 'docs', 'production-configuration.schema.json'), to: 'schemas/production-configuration.schema.json' },
    { from: path.join(root, 'LICENSE.txt'), to: 'LICENSE.txt' },
    { from: releaseBuild, to: 'release-build.json' },
  ],
  win: {
    target: [{ target: 'nsis', arch: ['x64'] }],
    artifactName: `Chassis-EOL-Setup-\${version}-${releaseLabel}-\${arch}.\${ext}`,
    requestedExecutionLevel: 'asInvoker',
    verifyUpdateCodeSignature: signed,
  },
  nsis: {
    oneClick: false,
    perMachine: false,
    allowElevation: true,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
    shortcutName: '底盘下线管理平台',
    uninstallDisplayName: '低速无人车线控底盘下线管理平台',
    deleteAppDataOnUninstall: false,
    license: path.join(root, 'LICENSE.txt'),
    warningsAsErrors: true,
  },
  publish: null,
}
