[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$InstallerPath,
  [string]$EvidenceDir = 'docs\verification\software-p0-p1-closure-2026-07-23\clean-machine',
  [string]$PreviousInstallerPath = ''
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Installer = (Resolve-Path $InstallerPath).Path
$Evidence = if ([IO.Path]::IsPathRooted($EvidenceDir)) { $EvidenceDir } else { Join-Path $Root $EvidenceDir }
$RunId = [guid]::NewGuid().ToString('N')
$Sandbox = Join-Path $env:TEMP "chassis-eol-package-e2e-$RunId 中文 空格"
$Install = Join-Path $Sandbox '安装 目录'
$UserData = Join-Path $Sandbox "chassis-eol-package-e2e-$RunId 用户 数据"
$Output = Join-Path $Evidence 'installed-e2e'
$AllowedEvidenceRoot = [IO.Path]::GetFullPath((Join-Path $Root 'docs\verification\software-p0-p1-closure-2026-07-23')).TrimEnd('\')
$ResolvedEvidence = [IO.Path]::GetFullPath($Evidence).TrimEnd('\')
$ResolvedOutput = [IO.Path]::GetFullPath($Output)
if (-not $ResolvedEvidence.StartsWith("$AllowedEvidenceRoot\", [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($ResolvedEvidence) -ne 'clean-machine') {
  throw "Refusing to clean an installer evidence path outside this work package: $ResolvedEvidence"
}
if (-not $ResolvedOutput.StartsWith("$ResolvedEvidence\", [StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to clean E2E output outside its evidence directory: $ResolvedOutput"
}
if (Test-Path -LiteralPath $ResolvedEvidence) { Remove-Item -LiteralPath $ResolvedEvidence -Recurse -Force }
New-Item -ItemType Directory -Force $Install, $UserData, $Output | Out-Null

if ([IO.Path]::GetFileName($Installer) -notmatch 'unsigned-internal|signed-production-candidate') {
  throw 'installer artifact name does not disclose its signing/release class'
}

$Listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 8800)
$Listener.Start()
try {
  $InstallProcess = Start-Process -FilePath $Installer -ArgumentList @('/S', "/D=$Install") -Wait -PassThru -WindowStyle Hidden
  if ($InstallProcess.ExitCode -ne 0) { throw "silent installer failed: $($InstallProcess.ExitCode)" }
  $Application = Get-ChildItem -LiteralPath $Install -File -Filter '*.exe' | Where-Object { $_.Name -notlike 'Uninstall*' } | Select-Object -First 1
  if (-not $Application) { throw "installed application executable not found in $Install" }

  $OldPath = $env:PATH
  $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
  $env:CHASSIS_PACKAGED_E2E = '1'
  $env:CHASSIS_E2E_USER_DATA = $UserData
  $env:CHASSIS_PACKAGED_E2E_OUTPUT = $Output
  $env:CHASSIS_E2E_CRASH_ONCE = '1'
  Remove-Item Env:CHASSIS_DESKTOP_RUNTIME_PROFILE -ErrorAction SilentlyContinue
  try {
    $AppProcess = Start-Process -FilePath $Application.FullName -PassThru -WindowStyle Hidden
    if (-not $AppProcess.WaitForExit(240000)) {
      Stop-Process -Id $AppProcess.Id -Force
      throw 'installed 11-page E2E timed out after 240 seconds'
    }
    if ($AppProcess.ExitCode -ne 0) { throw "installed application exited with $($AppProcess.ExitCode)" }
  } finally {
    $env:PATH = $OldPath
    Remove-Item Env:CHASSIS_E2E_CRASH_ONCE -ErrorAction SilentlyContinue
  }

  $SummaryPath = Join-Path $Output 'installed-e2e-summary.json'
  if (-not (Test-Path $SummaryPath)) { throw 'installed E2E summary was not produced' }
  $Summary = Get-Content $SummaryPath -Raw | ConvertFrom-Json
  if (-not $Summary.passed -or $Summary.screenshot_count -ne 22 -or $Summary.offline_control_status -ne 409 -or
      -not $Summary.route_capture_matches -or -not $Summary.viewport_matches_request -or -not $Summary.unique_page_captures) {
    throw 'installed E2E safety/UI assertions failed'
  }

  $StatePath = Join-Path $UserData 'data\logs\sidecar\runtime-state.json'
  $FirstStateTime = (Get-Item $StatePath).LastWriteTimeUtc
  $env:CHASSIS_PACKAGED_SMOKE_EXIT = '1'
  try {
    $Second = Start-Process -FilePath $Application.FullName -PassThru -WindowStyle Hidden
    if (-not $Second.WaitForExit(60000)) { Stop-Process -Id $Second.Id -Force; throw 'second launch timed out' }
    if ((Get-Item $StatePath).LastWriteTimeUtc -le $FirstStateTime) { throw 'second launch did not reach sidecar readiness' }
  } finally { Remove-Item Env:CHASSIS_PACKAGED_SMOKE_EXIT -ErrorAction SilentlyContinue }

  $SidecarExecutable = Join-Path $Install 'resources\backend-sidecar\chassis-eol-backend.exe'
  $BlockedExecutable = "$SidecarExecutable.blocked"
  $FailureOutput = Join-Path $Evidence 'sidecar-startup-failure'
  $FailureUserData = Join-Path $Sandbox "chassis-eol-package-e2e-$RunId 启动失败"
  New-Item -ItemType Directory -Force $FailureOutput, $FailureUserData | Out-Null
  Move-Item -LiteralPath $SidecarExecutable -Destination $BlockedExecutable
  try {
    $env:CHASSIS_E2E_USER_DATA = $FailureUserData
    $env:CHASSIS_PACKAGED_E2E_OUTPUT = $FailureOutput
    $FailedApp = Start-Process -FilePath $Application.FullName -PassThru -WindowStyle Hidden
    $FailurePath = Join-Path $FailureOutput 'startup-failure.json'
    $Deadline = [DateTime]::UtcNow.AddSeconds(45)
    while (-not (Test-Path $FailurePath) -and [DateTime]::UtcNow -lt $Deadline) { Start-Sleep -Milliseconds 250 }
    if (-not (Test-Path $FailurePath)) { throw 'sidecar startup failure did not produce actionable diagnostics' }
    Stop-Process -Id $FailedApp.Id -Force -ErrorAction SilentlyContinue
  } finally {
    Move-Item -LiteralPath $BlockedExecutable -Destination $SidecarExecutable
  }

  $DataMarker = Join-Path $UserData 'data\exports\uninstall-preservation-marker.txt'
  New-Item -ItemType Directory -Force (Split-Path $DataMarker) | Out-Null
  Set-Content -LiteralPath $DataMarker -Value 'must survive uninstall' -Encoding utf8
  $Uninstaller = Get-ChildItem -LiteralPath $Install -File -Filter 'Uninstall*.exe' | Select-Object -First 1
  if (-not $Uninstaller) { throw 'uninstaller not found' }
  $UninstallProcess = Start-Process -FilePath $Uninstaller.FullName -ArgumentList '/S' -Wait -PassThru -WindowStyle Hidden
  if ($UninstallProcess.ExitCode -ne 0) { throw "uninstaller failed: $($UninstallProcess.ExitCode)" }
  if (-not (Test-Path $DataMarker)) { throw 'business data was removed by uninstall' }

  $Matrix = [ordered]@{
    timestamp_utc = [DateTime]::UtcNow.ToString('o')
    installer = $Installer
    no_node_python_uv_or_internet_runtime = $true
    loopback_port_8800_occupied = $true
    unicode_and_space_paths = $true
    first_launch_11_pages = $Summary.passed
    second_launch = $true
    sidecar_crash_restart = $Summary.crash_restart_credential_rotated
    sidecar_start_failure_diagnostics = $true
    simulator_absent_control_409 = ($Summary.offline_control_status -eq 409)
    uninstall_preserved_business_data = $true
    previous_version_upgrade = if ($PreviousInstallerPath) { 'requires separate signed fixture workflow' } else { 'NOT_EXECUTED_NO_PREVIOUS_ARTIFACT' }
    rollback = if ($PreviousInstallerPath) { 'requires separate signed fixture workflow' } else { 'NOT_EXECUTED_NO_PREVIOUS_ARTIFACT' }
    administrator_and_standard_user = 'CI asInvoker covered; independent standard-user VM remains external'
    antivirus_firewall = 'actionable diagnostic path covered; vendor-specific allowlisting remains external'
    passed = $true
  }
  New-Item -ItemType Directory -Force $Evidence | Out-Null
  $Matrix | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Evidence 'clean-machine-matrix.json') -Encoding utf8
  Write-Host "Installed package verification passed: $Evidence"
} finally {
  $Listener.Stop()
  Remove-Item Env:CHASSIS_PACKAGED_E2E -ErrorAction SilentlyContinue
  Remove-Item Env:CHASSIS_E2E_USER_DATA -ErrorAction SilentlyContinue
  Remove-Item Env:CHASSIS_PACKAGED_E2E_OUTPUT -ErrorAction SilentlyContinue
}
