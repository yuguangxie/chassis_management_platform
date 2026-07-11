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
}
