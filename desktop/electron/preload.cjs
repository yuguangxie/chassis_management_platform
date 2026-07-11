const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("windowControls", {
  minimize: () => ipcRenderer.send("window:minimize"),
  maximize: () => ipcRenderer.send("window:maximize"),
  close: () => ipcRenderer.send("window:close"),
})

contextBridge.exposeInMainWorld("desktopFiles", {
  openPath: (targetPath) => ipcRenderer.invoke("files:open-path", targetPath),
})
