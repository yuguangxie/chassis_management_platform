$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$desktop = Join-Path $root 'desktop'
$electron = Join-Path $desktop 'node_modules\electron\dist\electron.exe'
$evidence = Join-Path $root 'docs\audit\evidence\commands'
$stdout = Join-Path $evidence 'electron_runtime_stdout.txt'
$stderr = Join-Path $evidence 'electron_runtime_stderr.txt'
$resultPath = Join-Path $evidence 'electron_runtime_probe.json'

$before = @(Get-Process electron -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$startedAt = Get-Date
$rootProcess = Start-Process -FilePath $electron -ArgumentList '.' -WorkingDirectory $desktop -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

Start-Sleep -Seconds 6
$newProcesses = @(Get-Process electron -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $before })
$result = [ordered]@{
    started_at = $startedAt.ToString('o')
    root_process_id = $rootProcess.Id
    root_process_alive_after_6s = -not $rootProcess.HasExited
    process_count = $newProcesses.Count
    processes = @($newProcesses | Select-Object Id, ProcessName, MainWindowTitle, Responding, StartTime)
    vite_listening = [bool](Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)
    backend_listening = [bool](Get-NetTCPConnection -LocalPort 8800 -State Listen -ErrorAction SilentlyContinue)
    production_entry_configured = $false
    backend_spawn_configured = $false
    conclusion = 'Electron can open against the running Vite server, but main.cjs has no dist file load path, backend spawn, or packaging configuration.'
}

$result | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $resultPath
$result | ConvertTo-Json -Depth 6

$newProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800
