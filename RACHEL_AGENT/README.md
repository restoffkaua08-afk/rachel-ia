# RACHEL_AGENT

## Estado

`contract-defined-execution-disabled`

A pasta `RACHEL_AGENT` representa a futura camada de Agent Runtime da
Rachel.

Ela não substitui os runtimes já existentes.

## Responsabilidades

O Agent Runtime deverá coordenar um objetivo de nível mais alto por meio
de componentes já existentes:

- Rachel — coordenação;
- Ned — planejamento e execução de task plans;
- Arya — coordenação de ferramentas;
- Cyber — autorização e enforcement.

## Não duplicar

A Etapa 14 não deve criar:

- um segundo Task Executor;
- um segundo Task Planner;
- um segundo mecanismo de autorização;
- um segundo Tool Coordinator.

A camada Agent deve reutilizar:

- `task_runtime.py`;
- `task_planner.py`;
- `task_executor.py`;
- `tools_runtime.py`;
- `security_runtime.py`.

## Governed Autonomy

A autonomia é governada.

Um objetivo futuro deverá seguir conceitualmente:

goal
→ plan
→ deterministic validation
→ risk resolution
→ authorization
→ eligible step
→ observation
→ checkpoint
→ continue or stop

A existência de um plano não autoriza seus efeitos.

## Estado 14/1A

Nesta subetapa:

- nenhum Agent Runtime executável foi criado;
- nenhum loop autônomo foi ativado;
- nenhum goal decomposition foi executado;
- nenhuma ferramenta foi executada pelo Agent;
- nenhum browser foi controlado;
- nenhum efeito externo ocorreu;
- nenhuma autorização foi criada ou consumida;
- nenhuma credencial foi utilizada;
- nenhum treinamento foi iniciado;
- nenhum peso de modelo foi alterado.

## Autonomia proibida por padrão

Continuam desativados:

- execução unattended;
- execução em background;
- self-spawn;
- self-replication;
- self-modification;
- self-update;
- instalação automática de ferramentas;
- ampliação automática de permissões;
- publicação externa automática;
- uso automático de credenciais.

## Próximo passo

`14/1B`

Criar uma implementação read-only capaz de inspecionar:

- readiness;
- authority boundaries;
- blockers;
- dependencies;
- execution capabilities.

Sem executar goals ou ferramentas.
