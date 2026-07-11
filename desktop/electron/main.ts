import { app, BrowserWindow, ipcMain, Menu, shell } from 'electron'
import path from 'node:path'

Menu.setApplicationMenu(null)

function createWindow() {
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1366,
    minHeight: 768,
    frame: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    backgroundColor: '#07111F',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  win.loadURL(process.env.VITE_DEV_SERVER_URL || 'http://127.0.0.1:5173')
}
app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })

ipcMain.on('window:minimize', (event) => BrowserWindow.fromWebContents(event.sender)?.minimize())
ipcMain.on('window:maximize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return
  if (win.isMaximized()) win.unmaximize()
  else win.maximize()
})
ipcMain.on('window:close', (event) => BrowserWindow.fromWebContents(event.sender)?.close())
ipcMain.handle('files:open-path', async (_event, targetPath: unknown) => {
  if (typeof targetPath !== 'string' || !path.isAbsolute(targetPath)) {
    throw new Error('Only absolute paths returned by the backend are accepted')
  }
  const normalized = path.resolve(targetPath)
  const allowedRoot = path.resolve(process.env.CHASSIS_ALLOWED_FILE_ROOT || path.join(__dirname, '..', '..', 'data'))
  const relative = path.relative(allowedRoot, normalized)
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('Path is outside the configured data root')
  }
  const result = await shell.openPath(normalized)
  if (result) throw new Error(result)
  return { ok: true }
})
