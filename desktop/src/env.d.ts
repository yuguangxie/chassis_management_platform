/// <reference types="vite/client" />

interface Window {
  windowControls?: {
    minimize: () => void
    maximize: () => void
    close: () => void
  }
  desktopFiles?: {
    openPath: (targetPath: string) => Promise<{ ok: boolean }>
  }
  chassisRuntime?: {
    getConnection: () => {
      apiBase: string
      wsUrl: string
      sidecarCredential: string
      runtimeProfile: 'dev' | 'mock' | 'production'
      ready: boolean
      packaged: boolean
      releaseChannel: string
    }
  }
}
