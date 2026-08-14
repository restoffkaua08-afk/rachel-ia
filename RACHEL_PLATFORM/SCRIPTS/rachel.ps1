$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
$memberControl = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\member_control.py"
$teamRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\team_runtime.py"
$knowledgeRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\knowledge_runtime.py"
$cognitiveRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\cognitive_runtime.py"
$aryaRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\arya_runtime.py"
$stellaRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\stella_runtime.py"
$toolsRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\tools_runtime.py"
$branCognitive = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\bran_cognitive.py"
$documentRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\document_runtime.py"
$webRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\web_runtime.py"
$searchRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\search_runtime.py"
$researchRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\research_runtime.py"
$taskRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\task_runtime.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Runtime Python ausente." }
if ($args.Count -eq 0) { throw "Informe um comando." }
$webDomains = @("web")
$searchDomains = @("search")
$taskDomains = @("task")
$researchDomains = @("research")
$documentDomains = @("document")
$branDomains = @("bran")
$toolsDomains = @("tools")
$stellaDomains = @("stella")
$aryaDomains = @("arya")
$cognitiveDomains = @("cognitive", "evaluate")
$knowledgeDomains = @("memory", "vision")
$runtimeDomains = @("runtime", "event", "policy", "organ-health", "route")
if ($taskDomains -contains [string]$args[0]) {
    & $python $taskRuntime @($args | Select-Object -Skip 1)
}
elseif ($webDomains -contains [string]$args[0]) {
    & $python $webRuntime @($args | Select-Object -Skip 1)
}
elseif ($searchDomains -contains [string]$args[0]) {
    & $python $searchRuntime @($args | Select-Object -Skip 1)
}
elseif ($researchDomains -contains [string]$args[0]) {
    & $python $researchRuntime @($args | Select-Object -Skip 1)
}
elseif ($documentDomains -contains [string]$args[0]) {
    & $python $documentRuntime @($args | Select-Object -Skip 1)
}
elseif ($branDomains -contains [string]$args[0]) {
    & $python $branCognitive @($args | Select-Object -Skip 1)
}
elseif ($toolsDomains -contains [string]$args[0]) {
    & $python $toolsRuntime @($args | Select-Object -Skip 1)
}
elseif ($stellaDomains -contains [string]$args[0]) {
    & $python $stellaRuntime @($args | Select-Object -Skip 1)
}
elseif ($aryaDomains -contains [string]$args[0]) {
    & $python $aryaRuntime @($args | Select-Object -Skip 1)
}
elseif ($cognitiveDomains -contains [string]$args[0]) {
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
