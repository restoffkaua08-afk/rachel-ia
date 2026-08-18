# Etapa 14 — Agent Runtime / Governed Autonomy

## Decisão arquitetural

Não existe um roadmap textual anterior que nomeie explicitamente a
Etapa 14.

O repositório, entretanto, já reserva `RACHEL_AGENT`, enquanto o
planejamento e a execução de tarefas já possuem implementação em
`RACHEL_PLATFORM/RUNTIME/SRC`.

Portanto, a Etapa 14 formaliza `RACHEL_AGENT` como uma camada de
coordenação governada, e não como um novo executor.

## Componentes existentes reutilizados

### Ned

O runtime atual já possui:

- Task Orchestrator;
- Task Planner;
- Task Executor;
- persistent plans;
- resumable execution.

### Arya

O Tool Coordinator continua sendo o caminho para ferramentas.

### Cyber

Cyber continua sendo a autoridade de segurança.

O Agent não poderá aprovar a si mesmo nem transformar planejamento em
autorização.

## Princípio

`Agent Runtime != Task Executor`

O Agent coordena intenção e ciclo.

O executor realiza passos já validados.

Cyber continua autorizando efeitos conforme risco e contrato.

## Contrato inicial

O `14/1A` é contract-only.

Não há:

- loop executável;
- unattended execution;
- background loop;
- browser automation;
- self-modification;
- self-update;
- automatic permission expansion;
- external publish;
- credential use;
- treinamento.

## Budgets

Os budgets de autonomia ainda não são definidos.

Não serão inventados valores para:

- número máximo de iterações;
- número máximo de tool calls;
- duração máxima;
- número máximo de falhas consecutivas.

A calibração será uma etapa futura e explícita.

## Próxima evolução

O `14/1B` deverá fornecer apenas uma camada read-only para expor:

- Agent status;
- authority map;
- readiness;
- blockers;
- capabilities.

Nenhum objetivo será executado nessa subetapa.
