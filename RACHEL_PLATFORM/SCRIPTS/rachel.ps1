$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
$controller = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\member_control.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Runtime Python ausente." }
& $python $controller @args
exit $LASTEXITCODE
