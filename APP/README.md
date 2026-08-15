# RACHEL IA Desktop

Aplicativo desktop local da RACHEL IA construido com Tauri 2, React e TypeScript.

## Integracoes atuais

- Ned: cognicao, roteamento e assist
- Cyber: painel de riscos e autorizacoes explicitas
- Bran: memoria governada e pesquisa
- Stella: diagnostico de voz
- Tyrion: saude dos orgaos
- Bridge Rust -> Python controlado
- CSP ativa
- Sem shell arbitrario exposto ao frontend

## Desenvolvimento

pnpm install
pnpm tauri dev

## Build

pnpm tauri build

O instalador Windows e produzido pelo bundle NSIS configurado no projeto.

## Estado de empacotamento

Esta versao usa o runtime local da RACHEL nesta estacao de desenvolvimento.
O empacotamento standalone do backend Python, modelos e orgaos sera tratado separadamente.
