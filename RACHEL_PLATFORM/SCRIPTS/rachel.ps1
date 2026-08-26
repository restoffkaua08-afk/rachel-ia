$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $root "AMBIENTES\runtime\Scripts\python.exe"
$memberControl = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\member_control.py"
$teamRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\team_runtime.py"
$knowledgeRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\knowledge_runtime.py"
$cognitiveRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\cognitive_runtime.py"
$danyCli = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\dany_cli.py"
$aryaRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\arya_runtime.py"
$stellaRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\stella_runtime.py"
$toolsRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\tools_runtime.py"
$branCognitive = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\bran_cognitive.py"
$documentRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\document_runtime.py"
$webRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\web_runtime.py"
$searchRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\search_runtime.py"
$researchRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\research_runtime.py"
$taskRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\task_runtime.py"
$projectWorkspace = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\project_workspace.py"
$projectQuality = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\project_quality.py"
$securityRuntime = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\security_runtime.py"
$securityPanel = Join-Path $root "RACHEL_PLATFORM\RUNTIME\SRC\security_panel.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Runtime Python ausente." }
if ($args.Count -eq 0) { throw "Informe um comando." }
$securityDomains = @("security", "cyber")
$approvalDomains = @("approval")
$webDomains = @("web")
$searchDomains = @("search")
$qualityDomains = @("project-quality")
$projectDomains = @("project")
$taskDomains = @("task")
$researchDomains = @("research")
$documentDomains = @("document")
$branDomains = @("bran")
$toolsDomains = @("tools")
$stellaDomains = @("stella")
$aryaDomains = @("arya")
$cognitiveDomains = @("cognitive")
$evaluateDomains = @("evaluate")
$knowledgeDomains = @("memory", "vision")
$runtimeDomains = @("runtime", "event", "policy", "organ-health", "route")
if ($securityDomains -contains [string]$args[0]) {
    & $python $securityPanel @($args | Select-Object -Skip 1)
}
elseif ($approvalDomains -contains [string]$args[0]) {
    & $python $securityRuntime @($args | Select-Object -Skip 1)
}
elseif ($qualityDomains -contains [string]$args[0]) {
    & $python $projectQuality @($args | Select-Object -Skip 1)
}
elseif ($projectDomains -contains [string]$args[0]) {
    & $python $projectWorkspace @($args | Select-Object -Skip 1)
}
elseif ($taskDomains -contains [string]$args[0]) {
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
elseif ($evaluateDomains -contains [string]$args[0]) {
    & $python $danyCli @($args | Select-Object -Skip 1)
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
