import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('windowControls', {
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
})

contextBridge.exposeInMainWorld('desktopFiles', {
  openPath: (targetPath: string) => ipcRenderer.invoke('files:open-path', targetPath),
})

contextBridge.exposeInMainWorld('chassisRuntime', {
  getConnection: () => ipcRenderer.sendSync('runtime:get-connection'),
})
