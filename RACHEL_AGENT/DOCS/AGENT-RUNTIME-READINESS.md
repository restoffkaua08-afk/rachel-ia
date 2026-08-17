# Agent Runtime — Read-only Readiness

## Estado 14/1B

A Etapa 14/1B introduz `AgentRuntime` apenas como camada de inspeção.

O runtime não é um executor.

## Estratégia read-only

Para evitar efeitos indiretos, o Agent Runtime não importa nem instancia:

- `TaskOrchestrator`;
- `NedTaskPlanner`;
- `TaskExecutor`;
- `ToolCoordinator`;
- `ApprovalStore`.

A inspeção dos componentes existentes é realizada por:

- leitura de JSON;
- leitura de código-fonte;
- parsing com AST;
- inspeção estática de classes e métodos.

## Dependencies

O runtime verifica estaticamente:

1. Task Runtime;
2. Task Planner;
3. Task Executor;
4. Tools Runtime;
5. Cyber Runtime.

A existência desses componentes não concede autorização para utilizá-los.

## Authority Map

O mapa de autoridade combina, sem executar código operacional:

- `tools.registry.json`;
- `approval.policy.json`;
- `task_planner.EFFECTS`;
- `agent-runtime-policy.json`.

Isso permite visualizar:

- ferramenta;
- membro responsável;
- efeito;
- risco;
- necessidade de autorização.

## Readiness

O readiness possui cinco dimensões:

1. contract integrity;
2. runtime dependencies;
3. authority boundaries;
4. autonomy budgets;
5. agent execution.

Na Etapa 14/1B, espera-se:

- contrato: ready;
- dependencies: ready;
- authority: ready;
- autonomy budgets: blocked;
- agent execution: blocked.

Isso é intencional.

Readiness não é execução.

## Bloqueios esperados

Enquanto a execução permanecer desativada:

- autonomy budgets not defined;
- Agent Runtime execution disabled;
- Agent loop execution disabled;
- goal decomposition disabled;
- task execution by Agent disabled;
- tool execution by Agent disabled.

## Segurança

O runtime não:

- cria task plan;
- executa task plan;
- invoca ferramenta;
- cria approval;
- consome approval;
- abre browser;
- usa credencial;
- publica externamente;
- inicia background loop;
- modifica a si mesmo;
- inicia treinamento.

## Próximo passo

A integração com Desktop Bridge deve ocorrer separadamente.

Essa integração deverá expor apenas os métodos de inspeção antes de
qualquer evolução para execução real.
