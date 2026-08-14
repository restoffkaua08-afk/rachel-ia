param(
    [Parameter(Mandatory = $false)]
    [string]$Mensagem = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz

if ([string]::IsNullOrWhiteSpace($Mensagem)) {
    $Mensagem = "checkpoint: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}

$arquivosSensiveis = @(
    git status --porcelain |
    ForEach-Object {
        if ($_.Length -gt 3) {
            $_.Substring(3).Trim('"')
        }
    } |
    Where-Object {
        $_ -match '(^|/|\\)\.env($|\.)' -and $_ -notmatch '\.env\.example$' -or
        $_ -match '\.(pem|key|p12|pfx)$' -or
        $_ -match '(^|/|\\)(credentials|secrets?|tokens?)(/|\\|\.|$)'
    }
)

if ($arquivosSensiveis.Count -gt 0) {
    Write-Host "Arquivos sensíveis detectados:" -ForegroundColor Red
    $arquivosSensiveis | ForEach-Object {
        Write-Host "- $_" -ForegroundColor Red
    }

    throw "Commit bloqueado para proteger dados sensíveis."
}

git add -A

$alteracoes = @(git diff --cached --name-only)

if ($alteracoes.Count -eq 0) {
    Write-Host "Nenhuma alteração para registrar." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nArquivos preparados:" -ForegroundColor Cyan
$alteracoes | ForEach-Object {
    Write-Host "- $_"
}

git commit -m $Mensagem

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao criar commit."
}

git push

if ($LASTEXITCODE -ne 0) {
    throw "Falha ao enviar commit."
}

Write-Host "`nCheckpoint publicado com sucesso." -ForegroundColor Green
git log -1 --oneline
