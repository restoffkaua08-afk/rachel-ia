# Etapa 12 - Rachel Model v0.1

## Estado

Etapa 12 tecnicamente concluida.

Esta etapa definiu a arquitetura inicial do modelo especializado da Rachel sem executar treinamento real.

## Rachel Model

- Model ID: `rachel-model-v0.1`
- Estrategia: specialized adapter
- Abordagem: adapter-first
- Fase inicial: SFT
- Metodo inicial: LoRA
- Base oficial de treinamento: `Qwen/Qwen3-1.7B-Base`
- Familia: Qwen3
- Variante: Base
- Parametros aproximados: 1.7B
- Licenca registrada no contrato: Apache-2.0

## Runtime temporario

O modelo `qwen3:1.7b` usado via Ollama continua sendo apenas o runtime temporario de inferencia.

Ele nao e o Rachel Model e nao substitui a base oficial de treinamento.

## Training Run Planner

A Etapa 12 definiu planejamento deterministico para execucoes futuras de LoRA + SFT.

Parametros iniciais do perfil minimo incluem:

- LoRA rank: 8
- LoRA alpha: 16
- sequencia maxima: 2048
- seed: 1337
- precision policy: bf16
- treinamento automatico: desativado

## Hardware

O computador atual permanece bloqueado para treinamento de pesos.

O treinamento real exige um host futuro compativel com a politica de hardware da Rachel.

O host GPU ainda nao foi selecionado.

Consequentemente, ainda nao existem versoes exatas bloqueadas de:

- CUDA;
- Torch;
- drivers NVIDIA;
- stack final do Training Runtime.

## Samwell

A Etapa 12 adicionou o membro `Samwell`.

Setor:

`Dependencias, Ambientes e Portabilidade`

Responsabilidades:

- Development Runtime;
- Packaging Runtime;
- Portable Runtime;
- Inference Runtime;
- Training Runtime;
- dependencias;
- compatibilidade;
- provisionamento;
- diagnostico;
- empacotamento.

O termo tecnico interno `frozen` permanece valido para Python/PyInstaller.

Na arquitetura da Rachel, o artefato distribuivel e chamado de `Portable Runtime`.

## Isolamento de ambientes

O Training Runtime possui ambiente dedicado:

`AMBIENTES/training`

Esse ambiente ainda nao foi criado.

O ambiente de empacotamento nao e reutilizado como ambiente de treinamento.

Em particular:

- Packaging Python != Training Python
- Packaging Torch != Training Torch
- Torch presente no sidecar nao habilita treinamento

## LitGPT

Backend de treinamento selecionado:

- repositorio: `Lightning-AI/litgpt`
- versao observada: `0.5.13`
- commit fixado: `7bf2960dfb26bae8e815c9a16a22732974824ac1`
- Python: `>=3.10`
- Torch: `>=2.7`
- Lightning: `>=2.6.1`

As versoes exatas do stack GPU somente devem ser resolvidas depois da selecao e auditoria do host NVIDIA real.

## Base weights

Repositorio oficial:

`Qwen/Qwen3-1.7B-Base`

Estado:

`not-downloaded`

Download automatico permanece desativado.

## Conversao para LitGPT

O fluxo planejado e:

1. selecionar host GPU;
2. validar hardware;
3. criar Training Runtime;
4. instalar dependencias autorizadas;
5. fixar versoes exatas;
6. baixar base oficial;
7. converter Hugging Face -> LitGPT;
8. verificar checkpoint;
9. validar dataset;
10. executar Dany preflight;
11. passar pelo Cyber;
12. somente entao permitir treinamento.

Checkpoint esperado futuramente:

- `model_config.yaml`
- `lit_model.pth`

Estado atual:

`not-created`

## Dany

Dany participa do controle de qualidade do treinamento.

Avaliacao preflight e obrigatoria antes da execucao.

Avaliacao posterior ao treinamento devera ocorrer antes de promocao ou exportacao.

## Cyber

Toda operacao mutante permanece protegida.

Cyber e obrigatorio para:

- criacao do ambiente;
- instalacao de dependencias;
- downloads;
- conversao de checkpoint;
- execucao de treinamento;
- operacoes externas futuras.

As aprovacoes continuam persistentes, escopadas, vinculadas aos argumentos e single-use.

## Training Execution Gate

A Etapa 12 implementou um gate seguro de dry-run.

O gate permite validar:

- Dany;
- Cyber;
- binding de argumentos;
- single-use;
- manifestos;
- integridade;
- invariantes de seguranca.

Nao existe acao de treinamento real exposta pelo gate atual.

## Portable Runtime

Artefato validado:

`APP/src-tauri/binaries/rachel-backend-x86_64-pc-windows-msvc.exe`

Tamanho da validacao final:

`405.39 MB`

SHA256:

`4398974A66147869C1A05364B716E8C3D4E56C5936B03B91B34C0472BF50B923`

O Portable Runtime confirmou:

- `portable_mode = true`
- Samwell ativo
- Rachel Model ativo
- Training Backend Contract ativo
- Dashboard integrado
- treinamento bloqueado

O repositorio fisico do LitGPT nao precisa ser empacotado dentro do Portable Runtime.

O codigo-fonte do LitGPT pertence ao contexto de provisionamento/treinamento.

## Estado de seguranca no fechamento

- Training Runtime criado: nao
- Host GPU selecionado: nao
- Dependency lock criado: nao
- Base weights baixados: nao
- Checkpoint LitGPT criado: nao
- Provision execution: desativada
- Command generation: desativada
- Automatic install: desativado
- Automatic download: desativado
- Automatic conversion: desativado
- Automatic training: desativado
- Training execution: desativada
- Weights modified: nao

## Commits principais da Etapa 12

- `78f0bde6dd2b44f70c13ccadf9023ff4078974b5` - contrato Rachel Model v0.1
- `192d8ec70d38079c3baddb7762220b4bc913f0ce` - Qwen3 1.7B Base
- `eb5f18c0dcdc815448a52fb2c8aa95ff70170084` - planner LoRA/SFT
- `959e6f0b8fb9fc5d96d64ef524353ff9bc1c3d9c` - Dany/Cyber dry-run gate
- `d50de5c0bf0b592c37f53ecc9268cc0e08ee252d` - Desktop Bridge
- `9b19a3b5d65748ce78e187ef3e00383783e9badb` - Samwell
- `90e38542515358f47e9c7a15a6b883b449c390c6` - Training Backend Provisioning Contract

## Resultado

A Rachel agora possui uma arquitetura formal para seu primeiro modelo especializado.

A Etapa 12 nao treinou pesos.

Ela preparou:

- identidade do modelo;
- base oficial;
- estrategia LoRA/SFT;
- planejamento;
- hardware policy;
- Dany gate;
- Cyber gate;
- Desktop Bridge;
- Samwell;
- Portable Runtime;
- Training Backend Provisioning Contract.

O treinamento real fica explicitamente adiado ate existir hardware NVIDIA adequado e autorizacao especifica.
