# Samwell

## Cargo

Gestor de dependencias, ambientes e portabilidade.

## Responsabilidade

Samwell administra a camada de pre-requisitos tecnicos da Rachel.

Responsabilidades:

- runtimes;
- package managers;
- ambientes Python;
- dependencias de sistema;
- dependencias de IA;
- compatibilidade;
- empacotamento;
- Portable Runtime;
- diagnostico;
- planos de provisionamento;
- planos de reparo.

## Samwell x Tyrion

Samwell responde se os requisitos necessarios para um componente funcionar existem e sao compativeis.

Tyrion supervisiona se os orgaos e servicos estao operacionais.

## Samwell x Cyber

Samwell pode auditar e planejar.

Instalar, atualizar, remover, reparar ou alterar configuracoes exige autorizacao do Cyber.

## Frozen x Portable Runtime

`frozen` permanece como termo tecnico interno do Python/PyInstaller.

Na arquitetura da Rachel o backend empacotado recebe o nome `Portable Runtime`.

O Portable Runtime fica sob responsabilidade do Samwell.

## Isolamento

Uma biblioteca presente em um ambiente nao habilita automaticamente outro ambiente.

Torch presente no Packaging Runtime nao significa que o Training Runtime esteja pronto.
