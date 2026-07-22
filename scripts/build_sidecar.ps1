[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$Spec = Join-Path $Root 'backend\packaging\backend-sidecar.spec'
$BuildRoot = Join-Path ([IO.Path]::GetTempPath()) 'chassis-eol-sidecar-build'
$Dist = Join-Path $BuildRoot 'dist'
$Work = Join-Path $BuildRoot 'work'

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') { throw 'Windows sidecar builds must run on Windows' }
if (-not (Test-Path $Python)) { throw "Locked backend environment is missing: $Python" }

$ResolvedTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$ResolvedBuild = [IO.Path]::GetFullPath($BuildRoot)
if (-not $ResolvedBuild.StartsWith("$ResolvedTemp\", [StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to clean sidecar build path outside the system temp directory: $ResolvedBuild"
}
if (Test-Path -LiteralPath $ResolvedBuild) { Remove-Item -LiteralPath $ResolvedBuild -Recurse -Force }
New-Item -ItemType Directory -Force $Dist, $Work | Out-Null
$env:CHASSIS_SIDECAR_STAGE = Join-Path $Dist 'chassis-eol-backend'

& $Python -m PyInstaller --noconfirm --clean --distpath $Dist --workpath $Work $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Executable = Join-Path $env:CHASSIS_SIDECAR_STAGE 'chassis-eol-backend.exe'
if (-not (Test-Path $Executable)) { throw "Sidecar executable was not produced: $Executable" }

& $Executable --self-test
if ($LASTEXITCODE -ne 0) { throw "Packaged sidecar failed its executable smoke check: $LASTEXITCODE" }
Write-Host "Offline sidecar ready: $Executable"
