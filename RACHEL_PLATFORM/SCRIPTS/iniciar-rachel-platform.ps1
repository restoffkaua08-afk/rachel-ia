$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Runtime Python ausente." }
& $python (Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\supervisor.py") doctor
& $python (Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\supervisor.py") audit
