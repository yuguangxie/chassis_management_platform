[CmdletBinding()]
param(
  [switch]$RequireSigning,
  [switch]$SkipQuality
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Backend = Join-Path $Root 'backend'
$Desktop = Join-Path $Root 'desktop'
$Evidence = Join-Path $Root 'docs\verification\software-p0-p1-closure-2026-07-23\release'
$ReleaseDir = Join-Path $Desktop 'release\windows'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'

if ($RequireSigning) { $env:CHASSIS_REQUIRE_SIGNING = '1' }
New-Item -ItemType Directory -Force $Evidence | Out-Null
if ($RequireSigning -and (git -C $Root status --porcelain)) {
  throw 'formal signed release requires a clean source tree'
}

Push-Location $Backend
try {
  uv lock --check
  if ($LASTEXITCODE -ne 0) { throw 'backend/uv.lock is stale' }
  uv sync --locked --extra test --extra quality --extra production --extra packaging
  if ($LASTEXITCODE -ne 0) { throw 'locked Python release environment sync failed' }
} finally { Pop-Location }

if (-not $SkipQuality) {
  & $Python (Join-Path $Root 'scripts\check_report_dependencies.py') | Tee-Object (Join-Path $Evidence 'report-dependencies.json')
  if ($LASTEXITCODE -ne 0) { throw 'report dependency gate failed' }
  npm.cmd --prefix $Desktop run lint
  if ($LASTEXITCODE -ne 0) { throw 'desktop lint failed' }
  npm.cmd --prefix $Desktop run test:sidecar
  if ($LASTEXITCODE -ne 0) { throw 'sidecar unit tests failed' }
}

npm.cmd --prefix $Desktop run build
if ($LASTEXITCODE -ne 0) { throw 'renderer production build failed' }
& (Join-Path $Root 'scripts\build_sidecar.ps1')
node (Join-Path $Root 'scripts\generate_release_metadata.mjs') prepare
npm.cmd --prefix $Desktop run package:win
if ($LASTEXITCODE -ne 0) { throw 'Electron Builder failed' }

$NpmAudit = Join-Path $ReleaseDir 'npm-audit.json'
cmd /c "npm.cmd --prefix `"$Desktop`" audit --json > `"$NpmAudit`""
$NpmAuditExit = $LASTEXITCODE
$PipAudit = Join-Path $ReleaseDir 'pip-audit.json'
& $Python -m pip_audit --skip-editable --format json --output $PipAudit
$PipAuditExit = $LASTEXITCODE

Copy-Item -LiteralPath $NpmAudit, $PipAudit -Destination $Evidence -Force
$Installer = Get-ChildItem -LiteralPath $ReleaseDir -File -Filter 'Chassis-EOL-Setup-*.exe' | Select-Object -First 1
if (-not $Installer) { throw 'installer is missing before signing status collection' }
$Signature = Get-AuthenticodeSignature -LiteralPath $Installer.FullName
$SigningStatus = [ordered]@{
  timestamp_utc = [DateTime]::UtcNow.ToString('o')
  file = $Installer.Name
  status = [string]$Signature.Status
  signed = ($Signature.Status -eq 'Valid')
  formal_release = ($Signature.Status -eq 'Valid')
  note = if ($Signature.Status -eq 'Valid') { 'certificate signature validated by Windows' } else { 'unsigned internal package; not a formal production release' }
}
$SigningStatus | ConvertTo-Json | Set-Content (Join-Path $ReleaseDir 'signing-status.json') -Encoding utf8
$SigningStatus | ConvertTo-Json | Set-Content (Join-Path $Evidence 'signing-status.json') -Encoding utf8

node (Join-Path $Root 'scripts\generate_release_metadata.mjs') finalize
if ($NpmAuditExit -ne 0 -or $PipAuditExit -ne 0) {
  throw "dependency vulnerability gate failed (npm=$NpmAuditExit, pip=$PipAuditExit); reports were preserved"
}
Write-Host "Windows release complete. Signing: $(if ($env:CSC_LINK) { 'configured' } else { 'UNSIGNED INTERNAL' })"
