# Lote 3 — Tool Runtime profissional

## Estado

**CONCLUÍDO E VALIDADO NO CI**

Este lote substitui o uso de shell genérico nas operações comuns por capacidades tipadas, governadas por Cyber e verificáveis.

## Filesystem tipado

Capacidades:

- `filesystem.status`
- `filesystem.list`
- `filesystem.stat`
- `filesystem.read`
- `filesystem.search`
- `filesystem.mkdir`
- `filesystem.write`
- `filesystem.patch`
- `filesystem.copy`
- `filesystem.move`
- `filesystem.delete`

Garantias:

- escopos nomeados: `workspace`, `desktop`, `documents`, `downloads`;
- caminhos sempre relativos ao escopo;
- `..`, caminhos absolutos, NUL e escape de escopo são bloqueados;
- symlinks são bloqueados na superfície tipada;
- escrita textual é atômica;
- sobrescrita gera backup local;
- patch exige exatamente um match;
- mutações verificam o estado final;
- delete de diretório é não recursivo por padrão;
- leitura no workspace permanece low-risk;
- leitura/list/search/inspect em escopos pessoais é promovida para efeito `external` e exige autorização Cyber.

## Git tipado

Capacidades:

- `git.status`
- `git.diff`
- `git.log`
- `git.branches`
- `git.stage`
- `git.commit`
- `git.branch.create`
- `git.checkout`

Garantias:

- `shell=False`;
- paths relativos validados;
- branches validadas;
- stage e commit são autorizações separadas;
- branch create não troca de branch silenciosamente;
- commit só usa conteúdo já staged;
- `git.push` não existe nessa superfície e publicação remota permanece fora do escopo deste lote.

## Validação de projetos tipada

Capacidades:

- `dev.detect`
- `dev.test`
- `dev.build`
- `dev.lint`
- `dev.typecheck`

Garantias:

- o modelo não fornece linha de comando arbitrária;
- o runtime detecta Node/Rust/Python;
- Node usa scripts conhecidos do `package.json` e package manager detectado por lockfile;
- Rust usa comandos Cargo definidos pelo runtime;
- Python usa unittest/pytest, compileall e ferramentas de lint/typecheck somente quando disponíveis;
- execução é governada pelo Cyber;
- resultado inclui return code, sucesso e saída limitada.

## Processos governados

Capacidades:

- `process.start`
- `process.list`
- `process.status`
- `process.logs`
- `process.stop`

Garantias:

- somente perfis conhecidos podem ser iniciados;
- somente processos iniciados e registrados pela RACHEL podem ser consultados ou encerrados;
- não existe operação para matar PID arbitrário do sistema;
- stdout/stderr ficam em logs próprios;
- start e stop são efeitos governados e independentes;
- stop verifica o encerramento.

## `arya.run` como fallback

O fallback genérico foi endurecido:

- sempre exige autorização Cyber;
- aceita somente nomes de executáveis permitidos resolvidos pelo PATH;
- bloqueia caminhos absolutos/relativos de executável;
- bloqueia PowerShell, pwsh, cmd, bash, sh, zsh, WSL, cscript e wscript;
- não usa shell;
- limita quantidade e tamanho de argumentos;
- operações comuns devem preferir ferramentas tipadas.

## Métricas e observabilidade

O `ToolCoordinator` mede `duration_ms` exclusivamente em torno do executor real da ferramenta e declara `duration_scope=tool-execution-only`.

Eventos King e logs Jhon recebem duração e estados de falha/conclusão.

## Validação automática

O gate crítico inclui testes específicos para:

- filesystem e escape de escopo;
- Cyber em Desktop;
- escrita atômica/backup/patch/delete;
- Git real em repositórios descartáveis;
- stage/commit/branches;
- build e testes Python reais;
- processos RACHEL-owned;
- bloqueio de shells no fallback;
- single-use approvals e regressões anteriores.

Rodada final de validação do lote:

- Python Core + Runtime contracts: **PASS**
- Desktop frontend build: **PASS**
- Tauri Rust check: **PASS**

## Linguagem natural

O usuário não deve citar nomes de ferramentas. O roteador cognitivo envia intenções de ação em linguagem natural ao planner com o catálogo tipado disponível.

A seleção do modelo real para frases como “crie uma pasta teste na Área de Trabalho” será novamente comprovada no E2E final com o provider local; os testes deste lote comprovam a capacidade e a segurança da ferramenta em si.

## Fora do escopo deste lote

- Agent Loop multi-etapas;
- push/publicação remota;
- browser;
- model routing;
- memória semântica unificada;
- avaliação factual avançada;
- UI final de diffs/progresso.
