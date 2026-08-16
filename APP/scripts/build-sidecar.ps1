$ErrorActionPreference="Stop"

$app=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repo=(Resolve-Path (Join-Path $app "..")).Path

$envDir=Join-Path $repo "AMBIENTES\desktop-sidecar"
$python=Join-Path $envDir "Scripts\python.exe"

$requirements=Join-Path $app "sidecar\requirements.txt"
$spec=Join-Path $app "sidecar\rachel_backend.spec"

$dist=Join-Path $app "sidecar\dist"
$work=Join-Path $app "sidecar\build"
$binaries=Join-Path $app "src-tauri\binaries"

function Check-Step([string]$name){
    if($LASTEXITCODE -ne 0){
        throw "$name falhou. Codigo: $LASTEXITCODE"
    }
}

if(-not (Test-Path -LiteralPath $python)){

    uv venv `
        --python 3.12 `
        "$envDir"

    Check-Step "uv venv sidecar"
}

uv pip install `
    --python "$python" `
    --requirement "$requirements"

Check-Step "sidecar requirements"

uv pip install `
    --python "$python" `
    --editable "$repo\RACHEL_CORE"

Check-Step "rachel-core sidecar"

if(Test-Path -LiteralPath $dist){
    [IO.Directory]::Delete(
        $dist,
        $true
    )
}

if(Test-Path -LiteralPath $work){
    [IO.Directory]::Delete(
        $work,
        $true
    )
}

$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

& $python `
    -X utf8 `
    -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath "$dist" `
    --workpath "$work" `
    "$spec"

Check-Step "PyInstaller"

$source=Join-Path $dist "rachel-backend.exe"

if(-not (Test-Path -LiteralPath $source)){
    throw "PyInstaller nao gerou rachel-backend.exe"
}

$triple=(rustc --print host-tuple).Trim()
Check-Step "rustc host tuple"

if([string]::IsNullOrWhiteSpace($triple)){
    throw "Target triple vazio."
}

New-Item `
    -ItemType Directory `
    -Path $binaries `
    -Force |
    Out-Null

$target=Join-Path `
    $binaries `
    "rachel-backend-$triple.exe"

Copy-Item `
    -LiteralPath $source `
    -Destination $target `
    -Force

Write-Host ""
Write-Host "SIDECAR_BUILD_OK"
Write-Host "TRIPLE=$triple"
Write-Host "SIDECAR=$target"
Write-Host "SIZE_MB=$([math]::Round((Get-Item -LiteralPath $target).Length / 1MB,2))"
