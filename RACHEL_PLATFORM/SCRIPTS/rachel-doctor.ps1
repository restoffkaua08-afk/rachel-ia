$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Runtime Python ausente. Execute INSTALAR-RUNTIME-RACHEL.ps1." }
& $python (Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\supervisor.py") doctor
if ($LASTEXITCODE -ne 0) { throw "Rachel Doctor encontrou falhas." }
& $python (Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\supervisor.py") audit
if ($LASTEXITCODE -ne 0) { throw "Auditoria dos orgaos encontrou falhas." }
