
# RACHEL — Roadmap Completo: De Protótipo a Agente de IA Profissional

**Versão:** 1.0
**Data:** 2026-08-19
**Branch de execução:** `evolution/rachel-professional-agent`
**main:** intocada até gates finais
**Estado atual:** Architecture Closed 15/15 (legado). Novo critério: **Professional Agent Ready**.

---

## Como ler este documento

Cada etapa tem **dois blocos**:

1. **📋 Descrição simples** — parágrafo curto em português, para humanos (Kauã) entenderem o que vai mudar e por quê, sem precisar ler código.
2. **🔧 Especificação técnica** — instruções detalhadas, com paths de arquivos, contratos, critérios de pronto e testes. Feita para outra IA (Claude, Codex, etc.) executar.

**Regra:** nenhuma etapa deve ser pulada. As dependências estão documentadas em "Pré-requisitos".

**Regra:** cada etapa termina com um **GATE** — uma lista de testes que devem passar antes de avançar.

---

## Visão geral das 15 etapas

| # | Nome | Tipo | Por quê nesta ordem |
|---|---|---|---|
| 1 | CI mínimo (rede de segurança) | P0 | Sem CI, qualquer mudança pode quebrar a RACHEL silenciosamente. Esta etapa é **pré-requisito de todas as outras**. |
| 2 | Cérebro único + intent router | P0 | Hoje há dois cérebros divergentes e o prompt mente sobre ferramentas. Sem corrigir, o resto falha. |
| 3 | Runtime persistente + streaming | P0 | Sidecar-per-call mata a UX. 15-40s por mensagem é inaceitável. |
| 4 | Tool runtime profissional (filesystem tipado) | P0 | "Crie uma pasta na Área de Trabalho" deve funcionar sem o usuário saber que existe "Arya". |
| 5 | Agent Loop real (ligar Ned+Executor+Cyber) | P0 | Peças existem mas estão desligadas por policy. Ativar gradualmente. |
| 6 | Model Router | P0/P1 | `qwen3:1.7b` não aguenta raciocínio pesado. Local-first + cloud opcional. |
| 7 | Project Intelligence (repo map, symbols) | P1 | Para trabalhar em projetos grandes sem despejar tudo no contexto. |
| 8 | Dany profissional (grounding, factualidade) | P1 | A Dany do chat dá "100" pra qualquer texto não vazio. Falsidade. |
| 9 | Knowledge Port real | P1 | `NullKnowledgeAdapter` é o padrão. Toda evidência do chat é vazia. |
| 10 | Pesquisa web profissional | P1 | Bing RSS + Wikipedia com ranking fraco. Resultado "Narcóticos Anônimos pra Python" é prova. |
| 11 | Browser governado (Playwright) | P1 | Reservado, não integrado. Cyber governa ações sensíveis. |
| 12 | MCP runtime | P1/P2 | Submódulo MCP SDK existe, mas sem registry real. Habilita extensibilidade. |
| 13 | Voz integrada ao Agent Loop | P1/P2 | Hoje voz é runtime isolado. Precisa rodar **a mesma Rachel Session** do chat. |
| 14 | Desktop UX profissional | P1/P2 | Chat streaming, tool cards, diff viewer, plan view, cancelar/continuar. |
| 15 | Hardening + Rachel Model + release | P2 | Security tests, performance gates, dataset, modelo próprio (só se HW permitir). |

---

# ETAPA 1 — CI mínimo (rede de segurança)

## 📋 Descrição simples

Hoje a RACHEL não tem CI no GitHub. Se eu (ou qualquer IA) mudar um arquivo do cérebro e quebrar o chat, **ninguém descobre automaticamente**. Os 74 testes existentes só rodam local, na máquina de quem lembrar de rodar.

Esta etapa cria uma esteira automática: toda vez que você fizer push ou abrir um PR, o GitHub roda os testes do Core e do Runtime em Windows. Se algo quebrar, o PR fica vermelho e não dá pra mergear sem consertar.

É literalmente uma rede de segurança antes da gente entrar na sala de cirurgia das próximas etapas.

## 🔧 Especificação técnica

### Pré-requisitos

- Nenhum (esta é a primeira etapa).

### Objetivo

Criar um workflow GitHub Actions mínimo que rode em `windows-latest` e execute os testes de:

1. `RACHEL_CORE/tests/`
2. `RACHEL_PLATFORM/RUNTIME/TESTS/`
3. Testes de bridge (`APP/bridge/`)

### Arquivos a criar/modificar

1. **`.github/workflows/test.yml`** (novo)
2. **`pyproject.toml`** (novo, raiz do repo) — declara dependências de teste
3. **`requirements-dev.txt`** (novo, raiz) — pin de pytest, hypothesis, etc.
4. **`.github/workflows/lint.yml`** (novo, opcional) — ruff/flake8

### Especificação `.github/workflows/test.yml`

```yaml
name: tests

on:
  push:
    branches:
      - evolution/**
      - main
  pull_request:
    branches:
      - main
      - evolution/**

jobs:
  test:
    runs-on: windows-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: false  # submódulos NÃO são necessários para testes do Core/Runtime

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-timeout
          # Não instalamos dependências pesadas do backend aqui — só test harness

      - name: Discover tests
        run: |
          python -m pytest --collect-only RACHEL_CORE/tests RACHEL_PLATFORM/RUNTIME/TESTS 2>&1 | tee collection.log

      - name: Run Core tests
        run: |
          python -m pytest RACHEL_CORE/tests -v --timeout=60

      - name: Run Runtime tests
        run: |
          $env:PYTHONUTF8 = "1"
          $env:PYTHONDONTWRITEBYTECODE = "1"
          python -m pytest RACHEL_PLATFORM/RUNTIME/TESTS -v --timeout=60

      - name: Run bridge tests
        run: |
          $env:PYTHONUTF8 = "1"
          $env:RACHEL_RUNTIME_ROOT = "$env:GITHUB_WORKSPACE"
          $env:RACHEL_STATE_ROOT = "$env:RUNNER_TEMP/rachel-state"
          New-Item -ItemType Directory -Force -Path $env:RACHEL_STATE_ROOT
          python -m pytest RACHEL_PLATFORM/RUNTIME/TESTS -v -k "bridge" --timeout=120
```

### Especificação `pyproject.toml` (raiz)

```toml
[project]
name = "rachel-ia"
version = "0.1.0"
description = "RACHEL IA - agente local-first"
requires-python = ">=3.11"

[project.optional-dependencies]
test = [
    "pytest>=7.4",
    "pytest-timeout>=2.1",
]

[tool.pytest.ini_options]
testpaths = ["RACHEL_CORE/tests", "RACHEL_PLATFORM/RUNTIME/TESTS"]
python_files = ["test_*.py"]
python_classes = ["*Tests", "Test*"]
python_functions = ["test_*"]
addopts = "-ra -q --strict-markers"
markers = [
    "slow: testes que levam mais de 30s",
    "integration: testes que abrem processos",
]
```

### Especificação `requirements-dev.txt`

```
pytest>=7.4.0
pytest-timeout>=2.1.0
```

### Branch protection (manual, no GitHub UI)

Após merge:
- Settings → Branches → Branch protection rules
- Adicionar regra para `evolution/rachel-professional-agent`:
  - ✅ Require status checks to pass before merging
  - ✅ Require branches to be up to date before merging
  - Selecionar: `tests / test`

### GATE — Critério de pronto

- [ ] Arquivo `.github/workflows/test.yml` existe e é válido
- [ ] `pyproject.toml` e `requirements-dev.txt` existem
- [ ] Push na branch dispara o workflow
- [ ] Workflow passa (todos os testes verdes)
- [ ] Pelo menos **1 teste propositalmente quebrado** foi simulado e o workflow **falhou** (provando que o CI detecta regressão)
- [ ] Após a simulação, o teste foi corrigido de volta
- [ ] Branch protection configurada (ou documentada para Kauã fazer manualmente)

### Riscos

- Tests podem falhar em Windows por motivos de path encoding. Mitigação: usar `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`.
- Tests que dependem de Ollama rodando vão falhar no CI. Mitigação: marcar com `@pytest.mark.integration` ou `@pytest.mark.skipif(not has_ollama())`.

### Commit message

```
ci: adicionar GitHub Actions para tests de Core e Runtime

- Cria .github/workflows/test.yml em windows-latest
- Adiciona pyproject.toml e requirements-dev.txt
- Roda testes do Core, Runtime e bridge
- Não instala dependências pesadas (Ollama, modelos)
- Garante que regressões em agent loop, segurança ou memória
  sejam detectadas antes de chegar à main
```

---

# ETAPA 2 — Cérebro único + intent router natural

## 📋 Descrição simples

Hoje a RACHEL tem dois "cérebros" (um no Core, outro no Runtime) que discordam sobre o que é capaz. O prompt principal diz "ferramentas desativadas" mesmo quando elas estão habilitadas. O Ned (planejador) gasta uma chamada inteira ao modelo só para decidir se precisa de ferramenta — até em "oi, tudo bem?".

Esta etapa unifica o caminho cognitivo num único entry point, reescreve o prompt sem mentira, e adiciona um roteador de intenção natural. Você vai poder dizer:

- "Crie uma pasta faculdade na Área de Trabalho" → RACHEL roteia para filesystem (mesmo que depois peça escopo).
- "Pesquise sobre Next.js" → roteia para web research.
- "Lembre que prefiro VSCode" → roteia para Bran.
- "O que é Python?" → fica em chat puro.

Sem precisar dizer "use X".

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 1 (CI verde).

### Objetivo

1. Unificar `ChatService` (Core) e `NedCognitiveBridge` (Runtime) num único caminho.
2. Reescrever `DEFAULT_SYSTEM_PROMPT` removendo "ferramentas desativadas".
3. Adicionar `IntentRouter` que decide intenção **sem chamar modelo grande** em conversa normal.
4. Remover a chamada extra ao LLM no `NedToolPlanner.plan()` quando a heurística já bateu.

### Arquivos a modificar/criar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/intent_router.py`** (novo) — classificador determinístico + LLM leve opcional.
2. **`RACHEL_CORE/src/rachel_core/application.py`** — reescrever `DEFAULT_SYSTEM_PROMPT`.
3. **`RACHEL_PLATFORM/RUNTIME/SRC/cognitive_runtime.py`** — refatorar `NedCognitiveBridge` para usar `IntentRouter` e eliminar a chamada LLM extra em casos claros.
4. **`RACHEL_CORE/src/rachel_core/bootstrap.py`** — corrigir `capabilities.knowledge/tools` para refletir verdade.
5. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_intent_router.py`** (novo) — testes unitários.

### Especificação `intent_router.py`

```python
class IntentRouter:
    """
    Classificador de intenção em 3 camadas:
    1. Heurística rápida (palavras-chave + estrutura).
    2. LLM leve opcional (apenas se 1 for incerto).
    3. Fallback para 'conversation'.
    """

    INTENTS = [
        "conversation",            # chat normal
        "research",                # web.research / web.search
        "action_filesystem",       # criar/ler/mover/apagar arquivo
        "action_code",             # rodar comando, ler código
        "memory_save",             # lembrar algo
        "memory_recall",           # buscar memória
        "task_plan",               # plano multi-etapa
        "task_resume",             # retomar tarefa (carrega approval_id)
        "system_status",           # saúde da RACHEL
    ]

    def route(self, content: str, conversation_history: list | None = None) -> Intent:
        # 1. Heurística rápida (regex + keywords) — SEM chamada LLM
        # 2. Se ambíguo, LLM leve com prompt pequeno — apenas para classificar
        # 3. Default: conversation
        ...
```

### Especificação novo `DEFAULT_SYSTEM_PROMPT`

Substituir em `RACHEL_CORE/src/rachel_core/application.py:13`:

**Antes:**
```
Você é Rachel, uma assistente técnica cuidadosa e objetiva.
Responda em português claro. Não invente fatos. Diferencie fatos, inferências e recomendações.
Não alegue ter executado ações que não foram realmente executadas.
Ferramentas estão desativadas nesta versão; quando uma ação externa for necessária,
explique o próximo passo ao usuário.
```

**Depois:**
```
Você é Rachel, uma agente de IA técnica local-first.
Identidade: cuidadosa, objetiva, em português claro.
Grounding: nunca invente fatos, valores, comandos ou resultados.
Quando uma ferramenta foi realmente executada, cite o resultado retornado.
Quando uma ferramenta falhou, não esconda o erro.
Quando precisa de autorização, explique exatamente o que vai fazer e por quê.
Quando não sabe, diga que não sabe.
Não alegue ter feito algo que não fez.
Responda em português.
```

### Refator em `cognitive_runtime.py`

- Substituir `NedToolPlanner.plan()` por chamada a `IntentRouter.route()`.
- Quando intent é claro pela heurística, **zero** chamadas extras ao modelo.
- Quando ambíguo, **uma** chamada pequena (modelo leve, prompt curto).
- `NedCognitiveBridge.assist()` recebe o intent, executa a capability correspondente, retorna resposta grounded.

### Correção em `bootstrap.py`

`Container` expõe um único método público: `respond(content, conversation_id, approval_id=None)`. Não expõe `chat` diretamente. `status()` retorna a verdade absoluta (única fonte).

### GATE — Critério de pronto

- [ ] `DEFAULT_SYSTEM_PROMPT` não contém "ferramentas estão desativadas"
- [ ] `IntentRouter.route()` retorna intent sem chamar modelo em casos óbvios
- [ ] "olá" → intent=conversation, **0 chamadas extras de modelo**
- [ ] "pesquise sobre X" → intent=research, **0 chamadas extras**
- [ ] "crie uma pasta X" → intent=action_filesystem
- [ ] "lembre que Y" → intent=memory_save
- [ ] Capabilities reportadas batem entre Core e Runtime
- [ ] Testes de regressão do chat passam (resposta a "oi" ainda é conversacional)
- [ ] CI verde

### Riscos

- Heurística pode classificar errado. Mitigação: threshold de confiança, fallback para conversation.
- LLM leve pode alucinar intent. Mitigação: whitelist de intents.

---

# ETAPA 3 — Runtime persistente + streaming

## 📋 Descrição simples

Hoje cada clique no chat da RACHEL abre um processo Python gigante (PyInstaller com 400MB), espera ele abrir tudo, fazer o trabalho, e mata. Isso demora 15 a 40 segundos por mensagem — você viu isso acontecer.

Esta etapa transforma o backend em um processo que **fica vivo** durante toda a execução do app. O Tauri abre uma vez, conversa por socket local, recebe tokens em tempo real (você vê as palavras aparecendo), pode cancelar tarefas sem matar tudo.

Resultado: chat curto responde em < 1.5s. Ferramentas pesadas têm progresso visível. Cancelar funciona.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 1 (CI verde).

### Objetivo

1. Substituir o `sidecar(...).output().await` por spawn persistente + IPC.
2. Adicionar modo `serve` no bridge Python (`rachel-bridge --serve --port 0`).
3. Streaming de tokens via JSON-lines no stdout ou SSE em HTTP local.
4. Cancelamento via signal/message.
5. Métricas TTFT (time-to-first-token).

### Arquivos a modificar/criar

1. **`APP/src-tauri/src/lib.rs`** — novo `backend_manager.rs`, IPC persistente.
2. **`APP/bridge/rachel_bridge.py`** — adicionar modo servidor.
3. **`APP/src-tauri/src-tauri/capabilities/default.json`** — permitir shell persistente.
4. **`RACHEL_CORE/src/rachel_core/adapters/model_openai_compatible.py`** — habilitar streaming.
5. **`RACHEL_PLATFORM/RUNTIME/SRC/cognitive_runtime.py`** — gerar em chunks.
6. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_streaming.py`** (novo).
7. **`APP/src/App.tsx`** — consumir stream, render incremental.

### Especificação do protocolo IPC

JSON-lines sobre stdin/stdout (compatível com subprocess simples):

```
# Request:
{"id": "req-1", "action": "respond", "content": "...", "conversation_id": null, "approval_id": null}

# Streaming events:
{"id": "req-1", "event": "start"}
{"id": "req-1", "event": "token", "data": "Olá"}
{"id": "req-1", "event": "token", "data": ", tudo"}
{"id": "req-1", "event": "tool_start", "tool": "web.research"}
{"id": "req-1", "event": "tool_progress", "tool": "web.research", "stage": "fetching", "pct": 0.5}
{"id": "req-1", "event": "tool_end", "tool": "web.research", "result": {...}}
{"id": "req-1", "event": "token", "data": "Encontrei 3 fontes..."}
{"id": "req-1", "event": "done", "result": {...}}
{"id": "req-1", "event": "error", "error": "..."}

# Cancel:
{"id": "req-1", "action": "cancel"}
```

### Especificação `backend_manager.rs` (Rust)

```rust
pub struct BackendManager {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    pending: HashMap<String, oneshot::Sender<Response>>,
}

impl BackendManager {
    pub async fn start(&mut self, app: &AppHandle) -> Result<(), Error> { ... }
    pub async fn send(&mut self, request: Request) -> Result<Receiver<Event>, Error> { ... }
    pub async fn cancel(&mut self, request_id: &str) -> Result<(), Error> { ... }
    pub async fn stop(&mut self) -> Result<(), Error> { ... }
}
```

### Especificação `rachel_bridge.py --serve`

Adicionar CLI argparse para modo servidor:

```python
def main_serve():
    bridge = RachelBridge()
    bridge.serve_unix_socket()  # ou TCP em 127.0.0.1:port dinâmico
```

Modo `serve`:
- Mantém `Container` em memória (SQLite aberto, adapters instanciados).
- Lê JSON-lines de stdin.
- Escreve eventos de streaming em stdout.
- Trata SIGTERM/SIGINT limpamente.

### GATE — Critério de pronto

- [ ] Backend inicia uma vez no startup do app Tauri
- [ ] Primeira resposta < 1.5s para chat curto (< 100 tokens)
- [ ] Tokens fluem incrementalmente no frontend
- [ ] Cancelamento funciona: usuário pode abortar resposta em curso
- [ ] Estado (DBs, adapters) persiste entre chamadas
- [ ] Latência primeira palavra (TTFT) < 800ms após inicialização
- [ ] Métricas expostas via `runtime.metrics()`
- [ ] Testes de streaming passam
- [ ] CI verde

### Riscos

- IPC stateful é mais complexo que one-shot. Mitigação: começar com request_id único + timeout.
- Ollama pode não suportar streaming bem em algumas versões. Mitigação: testar localmente antes.

---

# ETAPA 4 — Tool runtime profissional (filesystem tipado)

## 📋 Descrição simples

Hoje a Arya só tem `arya.run` (escape hatch genérico) e fica presa ao `WORKSPACE` da RACHEL. Se você pede "crie uma pasta na Área de Trabalho", ela rejeita porque o caminho não está dentro do workspace permitido.

Esta etapa adiciona **ferramentas tipadas** de filesystem: `fs.read`, `fs.write`, `fs.mkdir`, `fs.patch`, `fs.move`, `fs.copy`, `fs.delete`, `fs.list`. Cada uma declara o que faz, o efeito, e pede autorização Cyber por escopo (`Desktop`, `Documents`, projeto X).

Você autoriza "Desktop" uma vez para uma operação. RACHEL cria a pasta faculdade. Sem liberar PowerShell.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 2 (cérebro com intent router detectando `action_filesystem`).
- Etapa 3 (runtime persistente, mas pode ser parcial).

### Objetivo

1. Substituir `safe_cwd()` (rejeita tudo fora do WORKSPACE) por modelo de **escopo autorizável**.
2. Adicionar tools tipadas em `RACHEL_PLATFORM/RUNTIME/SRC/scoped_filesystem.py`.
3. Cyber ganha campo `scope` em aprovações.
4. Desktop UI mostra "RACHEL quer acessar Desktop. Aprovar?"

### Arquivos a criar/modificar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/scoped_filesystem.py`** (novo)
2. **`RACHEL_PLATFORM/CONFIG/approval.policy.json`** — adicionar `effect: filesystem` com `scope`
3. **`RACHEL_PERMISSIONS/scope.schema.json`** (novo) — schema de escopo
4. **`RACHEL_PLATFORM/RUNTIME/SRC/security_runtime.py`** — `consume()` valida scope
5. **`RACHEL_PLATFORM/RUNTIME/SRC/arya_runtime.py`** — expor as novas tools
6. **`RACHEL_PLATFORM/CONFIG/tools.registry.json`** — adicionar fs.read/write/mkdir/patch/move/copy/delete
7. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_scoped_filesystem.py`** (novo)

### Especificação `scoped_filesystem.py`

```python
class ScopeType(str, Enum):
    WORKSPACE = "workspace"          # WORKSPACE da RACHEL
    DESKTOP = "desktop"              # %USERPROFILE%/Desktop
    DOCUMENTS = "documents"          # %USERPROFILE%/Documents
    PROJECT = "project"              # projeto específico (path)
    USER_GRANTED = "user_granted"    # usuário digitou path absoluto + aprovou

@dataclass
class ScopedPath:
    scope: ScopeType
    relative: str
    absolute: Path

class ScopedFilesystem:
    def __init__(self, approved_scopes: list[ScopedPath]):
        self.approved_scopes = approved_scopes

    def resolve(self, scope: str, relative: str) -> ScopedPath:
        """Resolve para path absoluto se scope aprovado, senão AuthorizationRequired."""

    def read(self, path: ScopedPath) -> str: ...
    def write(self, path: ScopedPath, content: str, atomic: bool = True) -> None: ...
    def mkdir(self, path: ScopedPath, parents: bool = False) -> None: ...
    def patch(self, path: ScopedPath, old: str, new: str) -> PatchResult: ...
    def move(self, src: ScopedPath, dst: ScopedPath) -> None: ...
    def copy(self, src: ScopedPath, dst: ScopedPath) -> None: ...
    def delete(self, path: ScopedPath, recursive: bool = False) -> None: ...
    def list(self, path: ScopedPath, pattern: str | None = None) -> list[FileEntry]: ...
```

### GATE — Critério de pronto

- [ ] "Crie pasta faculdade no Desktop" → pede autorização de escopo
- [ ] Usuário aprova Desktop uma vez
- [ ] RACHEL cria a pasta via `fs.mkdir(scope=DESKTOP, relative=faculdade)`
- [ ] Pasta existe e foi criada pelo processo correto
- [ ] Fora do escopo aprovado, Cyber nega
- [ ] `safe_cwd()` substituído em todo runtime
- [ ] Testes cobrem: scope não autorizado, path traversal, atomicidade
- [ ] CI verde

### Riscos

- Path traversal (`../../`). Mitigação: validar `resolve()` e bloquear.
- Operações irreversíveis (delete). Mitigação: Cyber exige aprovação explícita + log.

---

# ETAPA 5 — Agent Loop real (ligar Ned+Executor+Cyber)

## 📋 Descrição simples

Hoje o Agent Loop existe como contrato mas está **desligado por policy**. As flags estão todas `false`. O `TaskOrchestrator`, `TaskPlanner`, `TaskExecutor` existem e são competentes — só ninguém chama eles.

Esta etapa liga tudo. Quando você disser "veja meu projeto da RT, descubra por que o login não funciona, corrija e teste", a RACHEL vira isso num plano persistente, executa etapa por etapa, observa resultado, detecta falha, corrige, continua. Com budgets (max turnos, max tool calls, tempo máximo), pause/resume/cancel, e Cyber sempre governando.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 4 (tools profissionais).
- Etapa 3 (runtime persistente).

### Objetivo

1. Ativar flags em `RACHEL_AGENT/CONFIG/agent-runtime-policy.json` gradualmente.
2. `NedCognitiveBridge.assist()` detecta objetivos complexos (multi-etapa) e delega ao Agent Loop.
3. Agent Loop usa `TaskOrchestrator` + `TaskExecutor` existentes.
4. Budgets: `max_iterations`, `max_tool_calls`, `wall_clock_limit_seconds`, `max_consecutive_failures`.
5. Pause/resume/cancel via IPC.

### Arquivos a modificar/criar

1. **`RACHEL_AGENT/CONFIG/agent-runtime-policy.json`** — mudar flags em sublotes (1A: plan only; 1B: execute readonly; 1C: execute with approval).
2. **`RACHEL_AGENT/CONFIG/autonomy-budget-policy.json`** — materializar defaults por tier.
3. **`RACHEL_PLATFORM/RUNTIME/SRC/cognitive_runtime.py`** — adicionar `NedCognitiveBridge.run_goal(goal)`.
4. **`RACHEL_PLATFORM/RUNTIME/SRC/agent_runtime.py`** — sair de read-only, wired ao `TaskOrchestrator`.
5. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_agent_loop.py`** (novo) — testes de integração do loop.

### Especificação do Agent Loop

```python
class AgentLoop:
    def __init__(self, budget: Budget, tools: ToolCoordinator, cyber: ApprovalStore):
        self.budget = budget
        self.tools = tools
        self.cyber = cyber

    async def run(self, goal: str, conversation_id: str | None = None) -> GoalResult:
        plan = await self.plan(goal)
        for iteration in range(self.budget.max_iterations):
            step = plan.next_pending_step()
            if step is None:
                break  # done
            result = await self.execute_step(step)
            self.observe(step, result)
            if self.should_replan(result):
                plan = await self.replan(plan, result)
            if self.budget.exhausted():
                return GoalResult(state="budget_exhausted", ...)
        return GoalResult(state="completed", ...)
```

### Sublotes (ativação gradual)

- **5A**: `goal_decomposition_enabled: true`. RACHEL cria planos mas não executa.
- **5B**: `task_execution_enabled_by_agent: true` apenas para tools readonly (list, read, search).
- **5C**: tools de write/edit com aprovação obrigatória.
- **5D**: tools de execute/publish com aprovação obrigatória + scope.
- **5E**: recovery de falha dentro do orçamento.

### GATE — Critério de pronto

- [ ] Plano é gerado para objetivo multi-etapa
- [ ] Cada etapa executa, observa, verifica
- [ ] Plano persistido (sobrevive a restart)
- [ ] Pause/resume/cancel funcionam
- [ ] Budget respeitado (para no limite)
- [ ] Falha de tool → replaneja dentro do orçamento
- [ ] Cyber sempre consultado para efeitos não-readonly
- [ ] "Veja projeto, descubra erro, corrija, teste" funciona end-to-end
- [ ] CI verde

### Riscos

- Loop infinito. Mitigação: budget rígido.
- Planos ruins que executam coisas perigosas. Mitigação: Cyber + scope.

---

# ETAPA 6 — Model Router

## � Descrição simples

O `qwen3:1.7b` rodando localmente não dá conta de raciocínio pesado, coding agent sério, ou planejamento multi-etapa. É um modelo pequeno para um PC modesto.

Esta etapa adiciona um **roteador de modelos**: tarefas simples (chat curto) usam o modelo local rápido; tarefas pesadas (planejamento, coding, raciocínio) podem ir para um modelo maior **se você configurar e autorizar**.

Você controla. Modo `local-only` (nunca envia nada para fora), `hybrid` (local por padrão, cloud opcional por tarefa), ou `cloud-enabled` (cloud por padrão quando configurado). Privacy mode explícito.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 3 (runtime persistente para carregar múltiplos providers).

### Objetivo

1. Perfis: `fast`, `general`, `reasoning`, `coding`, `vision`.
2. Adapter registry: provider local (Ollama) + cloud opcional (OpenAI-compat).
3. Política: `local-only`, `hybrid`, `cloud-enabled`.
4. Privacy: dados sensíveis (PII detectado por Presidio) nunca vão para cloud sem consentimento explícito.

### Arquivos a criar/modificar

1. **`RACHEL_CORE/src/rachel_core/adapters/model_router.py`** (novo)
2. **`RACHEL_PLATFORM/CONFIG/model.profiles.json`** (novo)
3. **`RACHEL_PLATFORM/CONFIG/privacy.policy.json`** (novo)
4. **`RACHEL_CORE/src/rachel_core/application.py`** — usar router em vez de adapter fixo.
5. **`RACHEL_PLATFORM/RUNTIME/SRC/cognitive_runtime.py`** — escolher profile por intent (chat=fast, plan=reasoning).

### Especificação `model_router.py`

```python
@dataclass
class ModelProfile:
    name: str           # "fast", "reasoning", "coding", "vision"
    provider: str       # "ollama", "openai-compat"
    model_name: str     # "qwen3:1.7b", "claude-sonnet-4-5", etc.
    max_tokens: int
    context_window: int

class ModelRouter:
    def __init__(self, profiles: list[ModelProfile], policy: PrivacyPolicy):
        self.profiles = {p.name: p for p in profiles}
        self.policy = policy

    def select(self, intent: Intent, content: str) -> ModelProfile:
        # chat curto → fast
        # planning → reasoning
        # code → coding
        # ...

    def generate(self, profile: ModelProfile, messages, system_prompt) -> Response:
        # Se policy=local-only, força profile com provider=local
        # Se content tem PII e policy=hybrid, força profile local
        ...
```

### GATE — Critério de pronto

- [ ] 2 providers configuráveis (local + cloud opcional)
- [ ] Chat curto usa `fast` (local)
- [ ] Plano multi-etapa usa `reasoning` (configurável)
- [ ] Privacy mode `local-only` nunca chama cloud, mesmo configurado
- [ ] PII em conteúdo → roteado para local em modo `hybrid`
- [ ] Latência `fast` < 1s para prompts curtos
- [ ] CI verde

### Riscos

- Custos de API cloud. Mitigação: budgets + opt-in.
- Privacy. Mitigação: Presidio + política explícita.

---

# ETAPA 7 — Project Intelligence (repo map, symbols)

## 📋 Descrição simples

Para projetos grandes (centenas de arquivos), a RACHEL não pode despejar tudo no contexto do modelo. Precisa de um mapa do projeto: estrutura, símbolos, dependências, working set.

Esta etapa adiciona Project Intelligence: a RACHEL lê a estrutura do projeto, monta um índice de symbols (funções, classes, imports), sabe qual arquivo é relevante para a tarefa atual, e mantém um "working set" que cabe no contexto.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 5 (Agent Loop).
- Etapa 4 (filesystem tipado com escopo por projeto).

### Objetivo

1. Project discovery: detecta linguagem, estrutura, build system.
2. Repo map: estrutura de diretórios + arquivos chave.
3. Symbol index: funções/classes via tree-sitter ou regex simples.
4. Working set: arquivos relevantes para a tarefa atual.
5. Project memory: decisões arquiteturais anteriores.

### Arquivos a criar/modificar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/project_intelligence.py`** (novo)
2. **`RACHEL_PLATFORM/RUNTIME/SRC/symbol_index.py`** (novo)
3. **`RACHEL_PLATFORM/RUNTIME/SRC/repo_map.py`** (novo)
4. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_project_intelligence.py`** (novo)

### Especificação `project_intelligence.py`

```python
class ProjectIntelligence:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.repo_map = RepoMap(project_root)
        self.symbols = SymbolIndex(project_root)
        self.memory = ProjectMemory(project_root)

    def discover(self) -> ProjectInfo:
        """Detecta linguagem, build system, entry points."""

    def working_set(self, goal: str, max_files: int = 20) -> list[Path]:
        """Retorna arquivos relevantes para a tarefa atual."""

    def context_for(self, goal: str, max_tokens: int = 8000) -> str:
        """Gera contexto otimizado: working set + symbols + memory."""
```

### GATE — Critério de pronto

- [ ] Projeto de 500 arquivos: working set < 20 arquivos
- [ ] Symbols extraídos corretamente para Python, JS/TS
- [ ] `context_for()` gera < 8000 tokens úteis
- [ ] Agent Loop usa `context_for()` em vez de despejar tudo
- [ ] CI verde

---

# ETAPA 8 — Dany profissional (grounding, factualidade)

## 📋 Descrição simples

A Dany que roda no chat hoje dá nota 100 para qualquer texto não vazio. Isso é falsidade de qualidade.

Esta etapa substitui por uma Dany que verifica:
- Cumprimento do pedido
- Consistência com tool_result (se houve tool)
- Citações presentes (se foi pesquisa)
- Grounding em evidências
- Detecção de alucinação óbvia (números, comandos, URLs)
- Admissão de "validei só estrutura, não factualidade" quando for o caso

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 2 (cérebro único).

### Objetivo

1. Substituir `DanyEvaluator` fraco por versão profissional.
2. Para tool results: se Arya retornou `returncode != 0`, RACHEL **não pode** dizer "executado com sucesso".
3. Para research: se 0 fontes primárias, RACHEL sinaliza baixa confiança.
4. Para código: build/test/lint rodaram?
5. Admitir limitação: "validei estrutura mas não factualidade" é resposta válida.

### Arquivos a criar/modificar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/dany_professional.py`** (novo)
2. **`RACHEL_PLATFORM/RUNTIME/SRC/cognitive_runtime.py`** — usar nova Dany.
3. **`RACHEL_PLATFORM/RUNTIME/TESTS/test_dany_professional.py`** (novo)

### Especificação `dany_professional.py`

```python
class DanyProfessional:
    def evaluate(self, response: str, context: EvalContext) -> QualityReport:
        checks = {
            "request_fulfilled": self._check_request_fulfilled(response, context.request),
            "tool_result_consistent": self._check_tool_result(response, context.tool_result),
            "citations_present": self._check_citations(response, context.citations),
            "grounded_in_evidence": self._check_grounding(response, context.evidence),
            "no_obvious_hallucination": self._check_hallucination(response),
            "admits_uncertainty": self._check_uncertainty_admission(response),
        }
        ...
```

### GATE — Critério de pronto

- [ ] Tool retornou `returncode != 0` → resposta diz "falhou"
- [ ] Research com 0 fontes primárias → resposta marca baixa confiança
- [ ] "Validei estrutura mas não factualidade" aparece em respostas ambíguas
- [ ] Score não é mais "100" por default
- [ ] CI verde

---

# ETAPA 9 — Knowledge Port real

## 📋 Descrição simples

Hoje `bootstrap.py` usa `NullKnowledgeAdapter`. Toda busca de evidência no chat retorna vazio.

Esta etapa conecta o `KnowledgeRuntime` real (que existe mas está desligado) ao Core.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 8 (Dany para verificar grounding).

### Arquivo a criar

1. **`RACHEL_CORE/src/rachel_core/adapters/knowledge_sqlite.py`** (novo) — delega ao `KnowledgeRuntime`.

### Modificação

- `RACHEL_CORE/src/rachel_core/bootstrap.py` — usar `SQLiteKnowledgeAdapter` em vez de `NullKnowledgeAdapter`.

### GATE

- [ ] Documentos indexados retornam como evidência no chat
- [ ] `capabilities.knowledge` reflete verdade
- [ ] CI verde

---

# ETAPA 10 — Pesquisa web profissional

## 📋 Descrição simples

Hoje a pesquisa usa Bing RSS + Wikipedia com ranking simples. O resultado "Narcóticos Anônimos para Python" mostrou que autoridade perde para match lexical.

Esta etapa adiciona query rewriting, preferência por fontes primárias, freshness, multi-query para pesquisas profundas, e síntese sempre baseada em evidências citadas.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 8 (Dany para verificar citações).

### Arquivos a modificar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/search_runtime.py`** — adicionar query expander, source authority scoring, freshness.
2. **`RACHEL_PLATFORM/RUNTIME/SRC/research_runtime.py`** — multi-query planner.

### GATE

- [ ] "Mudanças recentes no Next.js" → resultados dos últimos 30 dias
- [ ] Fontes primárias ranqueadas acima
- [ ] Citações obrigatórias em todas respostas de pesquisa
- [ ] Multi-query para "pesquisa profunda"
- [ ] CI verde

---

# ETAPA 11 — Browser governado (Playwright)

## � Descrição simples

Hoje o browser está reservado mas não integrado. Não dá pra abrir site, ler página, ou preencher formulário.

Esta etapa ativa Playwright-MCP governado pelo Cyber.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 4 (tool runtime).
- Etapa 5 (Agent Loop).

### Arquivos a criar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/browser_runtime.py`** (novo)
2. **`RACHEL_PLATFORM/MEMBROS/ST-Visao/SRC/`** — adapter Playwright real (substituir `.gitkeep`).

### GATE

- [ ] "Abra https://exemplo.com e me diga o título" funciona
- [ ] "Preencha formulário" pede autorização
- [ ] Cyber separa leitura de efeito (click, form, login, upload, download)
- [ ] CI verde

---

# ETAPA 12 — MCP runtime

## 📋 Descrição simples

O MCP Python SDK existe como submódulo, mas não há camada de registro MCP. Sem extensibilidade.

Esta etapa adiciona registry de servidores MCP, descoberta de tools, normalização, atribuição de efeito (Cyber).

## � Especificação técnica

### Arquivos a criar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/mcp_runtime.py`** (novo)
2. **`RACHEL_PLATFORM/CONFIG/mcp.servers.json`** (novo)

### GATE

- [ ] Cadastrar servidor MCP
- [ ] Tools do servidor aparecem no registry
- [ ] Cyber atribui efeitos
- [ ] Agent usa tools MCP
- [ ] CI verde

---

# ETAPA 13 — Voz integrada ao Agent Loop

## 📋 Descrição simples

Hoje voz é runtime isolado. Wake word, STT, TTS, barge-in existem mas não estão ligados ao agente.

Esta etapa faz a voz rodar **a mesma Rachel Session** do chat.

## 🔧 Especificação técnica

### Pré-requisitos

- Etapa 3 (runtime persistente).
- Etapa 5 (Agent Loop).

### Arquivos a modificar

1. **`RACHEL_PLATFORM/RUNTIME/SRC/voice_session.py`** — conectar ao `NedCognitiveBridge.assist()`.
2. **`RACHEL_PLATFORM/RUNTIME/SRC/realtime_voice.py`** — manter barge-in.

### Submódulos a wirear (quando HW permitir)

- WhisperCPP (STT)
- Piper (TTS)
- Silero-VAD
- OpenWakeWord

### GATE

- [ ] Wake word → escuta
- [ ] Pergunta por voz → processada pelo mesmo Agent Loop do chat
- [ ] Resposta falada
- [ ] Barge-in funciona (interrupção natural)

---

# ETAPA 14 — Desktop UX profissional

## 📋 Descrição simples

A RACHEL já tem Tauri rodando, mas a UX ainda é minimalista. Esta etapa profissionaliza:

- Chat streaming (palavras aparecendo)
- Tool cards (a RACHEL mostra o que está fazendo)
- Diff viewer (antes/depois de edição)
- Plan view (etapas, progresso)
- Cancelar/continuar tarefa
- Artifacts (arquivos gerados)
- Sessões/projetos persistentes
- Painel técnico opcional (para auditoria)

## 🔧 Especificação técnica

### Arquivos a modificar

1. **`APP/src/App.tsx`** — consumir stream, render incremental
2. **`APP/src/components/`** (novo) — ToolCard, DiffViewer, PlanView, ApprovalDialog, ArtifactList

### GATE

- [ ] Chat streaming renderiza token por token
- [ ] Tool cards aparecem em tempo real
- [ ] Approval dialog dentro do chat
- [ ] Diff viewer mostra antes/depois
- [ ] Plan view mostra etapas
- [ ] Cancel/continue funcional

---

# ETAPA 15 — Hardening + Rachel Model + release

## 📋 Descrição simples

Esta é a etapa final. Depois das 14 anteriores, a RACHEL já é um agente funcional. Aqui vem:

1. Security tests adversariais
2. Performance gates (TTFT < 800ms, p95 < 5s)
3. E2E tests
4. Installer reproduzível
5. Crash recovery
6. **Rachel Model** (treinamento próprio) — **SÓ** se hardware permitir (GPU + RAM ≥ 16GB)
7. Release final: tag, changelog, installer assinado

## � Especificação técnica

### Pré-requisitos

- Todas as etapas anteriores verdes.

### Sublotes

- **15A**: Security tests (permission escalation, prompt injection, path traversal).
- **15B**: Performance gates em CI.
- **15C**: E2E com Playwright desktop.
- **15D**: Crash recovery + migrations.
- **15E**: Installer NSIS reproduzível.
- **15F**: Rachel Model — APENAS se HW auditado permitir. Senão, fica como roadmap.

### GATE final — **Professional Agent Ready**

A RACHEL só recebe o selo quando comprova via E2E que:

- Conversa (chat streaming)
- Pesquisa (web com fontes citadas)
- Memoriza (consentimento, esquecimento)
- Trabalha em projeto (explora → plano → edita → testa)
- Edita arquivos (diff + rollback)
- Executa comandos (com aprovação)
- Usa Git (status, diff, commit)
- Roda testes, detecta falha, corrige, roda de novo
- Navega quando autorizado
- Retoma tarefas longas
- Executa planos multi-etapa
- Respeita Cyber
- Verifica suas próprias ações (não inventa execução)
- Responde rápido (TTFT < 800ms, p95 < 5s)
- Recupera-se de erro dentro do orçamento
- Fala (quando HW permitir)

---

## Resumo final

15 etapas. Cada uma termina com GATE. Cada GATE exige CI verde. A RACHEL só chega ao release quando a Etapa 15 passa.

A primeira etapa é **CI mínimo** — vou implementar agora.

---

**Ver também:** `ESTADO.md` (diagnóstico) e `MELHORIAS.md` (resumo executivo de melhorias).
