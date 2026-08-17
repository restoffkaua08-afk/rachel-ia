# Ambientes gerenciados pelo Samwell

## Development Runtime

Raiz:

`AMBIENTES/runtime`

Usado para desenvolvimento, testes e runtime tecnico local.

## Packaging Runtime

Raiz:

`AMBIENTES/desktop-sidecar`

Usado para gerar o backend empacotado.

Pode possuir Torch ou outras bibliotecas devido aos componentes do aplicativo.

Essas bibliotecas nao tornam o Training Runtime disponivel.

## Portable Runtime

Artefato:

`APP/src-tauri/binaries/rachel-backend-*.exe`

O Python fica empacotado no executavel.

O usuario final nao precisa possuir Python externo apenas para executar o backend desktop.

## Inference Runtime

Runtime atual:

Ollama

Modelo temporario atual:

`qwen3:1.7b`

## Training Runtime

Raiz reservada:

`AMBIENTES/training`

Ambiente independente e futuro para especializacao do Rachel Model.

Pode exigir:

- Python;
- LitGPT;
- PyTorch;
- Lightning;
- bitsandbytes;
- GPU NVIDIA;
- CUDA;
- checkpoint LitGPT;
- dataset compilado.

O PC atual continua bloqueado para treinamento de pesos.

## Seguranca

Samwell nao instala ou repara automaticamente.

Mutacoes passam pelo Cyber.
