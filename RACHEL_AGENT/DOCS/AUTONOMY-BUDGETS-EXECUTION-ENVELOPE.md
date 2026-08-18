# Autonomy Budgets + Execution Envelope

## Estado

Etapa `14/1E`.

Os contratos de budget e execution envelope estao definidos, mas a
execucao do Agent continua desativada.

## Budget strategy

A Rachel nao recebe um budget global implicito.

A estrategia e:

`explicit-per-goal-no-default`

Antes de uma futura execucao, o goal devera fornecer explicitamente:

- maximum iterations;
- maximum tool calls;
- wall-clock limit;
- maximum consecutive failures.

Nenhuma dessas dimensoes possui valor default.

Budget ausente ou incompleto deve resultar em deny.

O modelo nao pode escolher o proprio budget.

O Agent nao pode ampliar o proprio budget.

## Execution envelope

O envelope reutiliza o `TaskExecutor` existente.

Nao existe segundo executor.

O parametro existente `maximum_steps` sera a fronteira de slice.

O contrato determina:

`maximum_completed_steps_per_slice = 1`

Isso significa que uma futura execucao governada devera retornar ao
ciclo de observacao/checkpoint depois de no maximo uma etapa concluida.

## Continuation

Automatic continuation continua desativada.

Antes de qualquer futuro slice adicional, deverao ser revalidados:

- state;
- dependencies;
- authorization;
- budget.

## Failure behavior

Continuam obrigatorios:

- stop on failed step;
- stop on failed dependency;
- stop on unknown state.

Continuam desativados:

- automatic retry;
- automatic replan;
- automatic budget increase.

## Readiness

Antes do 14/1E:

- contract integrity: ready;
- runtime dependencies: ready;
- authority boundaries: ready;
- autonomy budgets: blocked;
- agent execution: blocked.

Depois do 14/1E:

- contract integrity: ready;
- runtime dependencies: ready;
- authority boundaries: ready;
- autonomy budgets: ready;
- agent execution: blocked.

A existencia do contrato de budget nao significa que um budget de goal
foi materializado.

`contract ready != execution admitted`

## Execution

Continuam desativados:

- goal execution;
- goal decomposition;
- task execution by Agent;
- tool execution by Agent;
- browser execution;
- background execution;
- unattended execution;
- external publish;
- credential use;
- self-modification;
- training.

## Frozen proof

O arquivo `stage-14-frozen-validation-1d.json` registra a prova historica
do frozen build do commit `9595d01c`.

Como o 14/1E altera source/config, esse frozen passa a ser historico.

Um novo frozen build sera necessario antes do fechamento final da
Etapa 14.
