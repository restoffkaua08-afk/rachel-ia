$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
$memberControl = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\member_control.py"
$teamRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\team_runtime.py"
$knowledgeRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\knowledge_runtime.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Runtime Python ausente." }
if ($args.Count -eq 0) { throw "Informe um comando." }
$knowledgeDomains = @("memory", "vision")
$runtimeDomains = @("runtime", "event", "policy", "organ-health", "route")
if ($knowledgeDomains -contains [string]$args[0]) {
    & $python $knowledgeRuntime @args
}
elseif ($runtimeDomains -contains [string]$args[0]) {
    & $python $teamRuntime @args
}
else {
    & $python $memberControl @args
}
exit $LASTEXITCODE
