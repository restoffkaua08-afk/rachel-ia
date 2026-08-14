$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
$memberControl = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\member_control.py"
$teamRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\team_runtime.py"
$knowledgeRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\knowledge_runtime.py"
$cognitiveRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\cognitive_runtime.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Runtime Python ausente." }
if ($args.Count -eq 0) { throw "Informe um comando." }
$cognitiveDomains = @("cognitive", "evaluate")
$knowledgeDomains = @("memory", "vision")
$runtimeDomains = @("runtime", "event", "policy", "organ-health", "route")
if ($cognitiveDomains -contains [string]$args[0]) {
    & $python $cognitiveRuntime @args
}
elseif ($knowledgeDomains -contains [string]$args[0]) {
    & $python $knowledgeRuntime @args
}
elseif ($runtimeDomains -contains [string]$args[0]) {
    & $python $teamRuntime @args
}
else {
    & $python $memberControl @args
}
exit $LASTEXITCODE
