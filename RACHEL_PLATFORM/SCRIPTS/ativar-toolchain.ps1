$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$toolchain = Join-Path $root "AMBIENTES\toolchain\Scripts"
$tools = Join-Path $root "RACHEL_PLATFORM\TOOLS"
$cargo = Join-Path $env:USERPROFILE ".cargo\bin"

$env:Path = "$toolchain;$tools;$cargo;$env:Path"

Write-Host "Toolchain Rachel ativada." -ForegroundColor Green

python --version
cmake --version
ninja --version
rustc --version
cargo --version
ffmpeg -version | Select-Object -First 1
