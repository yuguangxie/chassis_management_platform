const test = require('node:test')
const assert = require('node:assert/strict')
const dgram = require('node:dgram')
const fs = require('node:fs')
const net = require('node:net')
const os = require('node:os')
const path = require('node:path')
const { SidecarSupervisor, chooseUdpPortBase, redact, reserveTcpPort } = require('./sidecar.cjs')

test('selects a bindable localhost TCP port without a fixed default', async () => {
  const port = await reserveTcpPort()
  assert.ok(port > 0 && port <= 65535)
  await new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(port, '127.0.0.1', () => server.close(resolve))
  })
})

test('selects four available loopback UDP endpoints for two mock channels', async () => {
  const base = await chooseUdpPortBase()
  const sockets = []
  try {
    for (const offset of [0, 1, 100, 101]) {
      const socket = dgram.createSocket('udp4')
      sockets.push(socket)
      await new Promise((resolve, reject) => {
        socket.once('error', reject)
        socket.bind(base + offset, '127.0.0.1', resolve)
      })
    }
  } finally {
    sockets.forEach((socket) => socket.close())
  }
})

test('redacts transient credentials before sidecar output reaches disk', () => {
  assert.equal(redact('token=super-secret-value', ['super-secret-value']), 'token=[REDACTED]')
})

test('bounds restart attempts when the packaged executable cannot start', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sidecar-restart-test-'))
  const supervisor = new SidecarSupervisor({
    executable: path.join(root, 'missing-sidecar.exe'), args: [], cwd: root,
    configDir: root, assetsDir: root, reportFont: path.join(root, 'font.otf'), dataRoot: root,
    logPath: path.join(root, 'sidecar.log'), profile: 'mock', maxRestarts: 2, startupTimeoutMs: 100,
  })
  const failed = new Promise((resolve) => supervisor.once('failed', resolve))
  await assert.rejects(supervisor.start())
  await Promise.race([failed, new Promise((_, reject) => setTimeout(() => reject(new Error('restart limit timeout')), 5000))])
  assert.equal(supervisor.restartCount, 2)
  await supervisor.stop()
})
