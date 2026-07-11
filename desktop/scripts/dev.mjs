import { spawn } from "node:child_process"

const shell = process.platform === "win32"
const vite = spawn("npm", ["run", "dev:web"], { shell, stdio: "inherit" })

let electron
const timer = setTimeout(() => {
  electron = spawn("npx", ["electron", "."], {
    shell,
    stdio: "inherit",
    env: { ...process.env, VITE_DEV_SERVER_URL: "http://127.0.0.1:5173" },
  })
  electron.on("exit", (code) => {
    vite.kill()
    process.exit(code ?? 0)
  })
}, 2500)

process.on("SIGINT", () => {
  clearTimeout(timer)
  electron?.kill()
  vite.kill()
  process.exit(0)
})
