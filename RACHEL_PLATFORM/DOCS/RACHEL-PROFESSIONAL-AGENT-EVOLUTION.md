# RACHEL Professional Agent Evolution

Status atual: **Lotes 0 e 1 concluídos e validados no CI; Lote 2 em implementação**

Base do ciclo: `main@69efdc5ce239b03098f02eb613e00cc02cd8c88d`

Branch de evolução: `evolution/rachel-professional-agent`

Este ciclo começa depois do fechamento arquitetural das 15 etapas. Ele **não é uma Etapa 16**. O objetivo agora é transformar a arquitetura existente em um produto profissional, rápido, verificável e utilizável no dia a dia.

## Definição do produto-alvo

A RACHEL deve funcionar como uma única agente de IA para o usuário. O usuário descreve o objetivo em linguagem natural; a RACHEL decide internamente quais capacidades, membros e ferramentas utilizar.

O usuário **não deve precisar** escrever instruções como `use Arya`, `chame Cyber`, `use Bran`, `king.recent` ou nomes equivalentes da arquitetura interna.

Exemplos do comportamento-alvo:

- "Crie uma pasta chamada faculdade na minha Área de Trabalho e coloque estas anotações em um TXT."
- "Abra meu projeto, descubra por que o login não funciona, corrija e teste."
- "Pesquise a versão mais recente do Python no site oficial e explique o que mudou."
- "Continue o trabalho de ontem nesse projeto."

A RACHEL deverá entender a intenção, escolher ferramentas, pedir autorização quando necessária, executar, observar, verificar e só então afirmar que concluiu.

## Princípios obrigatórios

1. **Uma RACHEL, um fluxo cognitivo canônico.**
2. **Membros internos invisíveis para o uso normal.**
3. **Planejar não significa executar.**
4. **Aprovação não significa sucesso.**
5. **Nenhuma ação é considerada concluída sem evidência verificável.**
6. **Cyber continua deny-by-default para efeitos sensíveis.**
7. **Autonomia existe apenas dentro de escopo, orçamento e autorização.**
8. **`arya.run` será fallback; ações comuns devem possuir ferramentas tipadas.**
9. **Local-first permanece padrão. Providers externos serão opt-in.**
10. **Treinamento de pesos não será usado para esconder problemas de arquitetura.**
11. **Toda grande refatoração deverá ter regressão automatizada.**
12. **A `main` só recebe mudanças após validação do lote.**

## Achados que motivam o ciclo

### P0 — confiabilidade e experiência

- Backend desktop abre um novo sidecar PyInstaller por request.
- Não existe streaming de resposta ou eventos de execução.
- Fluxos cognitivos coexistem e precisam convergir para uma entrada canônica.
- Após autorização Cyber, uma ação pode voltar a ser planejada em vez de retomar exatamente o plano aprovado.
- A resposta precisa ser rigidamente vinculada ao resultado real das ferramentas.
- O usuário ainda precisa de instruções técnicas demais para provocar determinadas capacidades.

### P0 — agente

- Agent Runtime atual é essencialmente de inspeção/contrato.
- Goal decomposition e Agent Loop estão deliberadamente desativados.
- Planner, PlanStore, TaskExecutor, checkpoints e Cyber já existem, mas ainda não formam o loop operacional profissional.

### P0 — ferramentas e segurança

- `arya.run` é genérico demais para ser a interface principal de ações.
- O sandbox atual limita o filesystem ao workspace interno e não possui escopos temporários autorizáveis.
- A classificação read-only baseada em executável/argumentos é insuficiente para expansão segura.
- Faltam ferramentas tipadas de filesystem, código, Git, build, test, lint, processos e inspeção.

### P1 — inteligência e contexto

- O `qwen3:1.7b` é provider temporário e não é o Rachel Model.
- Falta model routing por perfil de tarefa.
- Grandes projetos precisam de repo map, symbol index, working set e compactação de contexto.

### P1 — memória e conhecimento

- Existem múltiplos mecanismos paralelos de memória.
- O Core ainda possui caminho com `NullKnowledgeAdapter`.
- Recuperação cognitiva atual é majoritariamente lexical.
- Falta distinção explícita entre memória de conversa, sessão, usuário, projeto e conhecimento documental.

### P1 — pesquisa, browser e avaliação

- Search atual depende de fontes limitadas e ranking simples.
- Browser ainda está reservado/desativado.
- Dany do chat faz validação estrutural básica, não verificação factual/grounded completa.

### P0/P1 — engenharia de produto

- Não havia GitHub Actions no início deste ciclo.
- Build/test/release precisam de gates reproduzíveis.
- Falta telemetria técnica local de TTFT, tempo total, tool latency e falhas por componente.

## Roadmap de implementação

### Lote 0 — Fundação de engenharia

Objetivo: criar proteção antes das grandes mudanças.

- [x] Criar branch dedicada de evolução.
- [x] Adicionar CI inicial.
- [x] Validar Python/JSON automaticamente.
- [x] Executar Core completo no CI.
- [x] Executar regressão crítica do Runtime no CI.
- [x] Build do frontend no CI.
- [x] `cargo check` do Tauri no CI.
- [x] Registrar este roadmap no repositório.
- [x] Confirmar primeira execução verde do workflow.

Validação do Lote 0:

- Python Core + Runtime contracts: PASS
- Desktop frontend build: PASS
- Tauri Rust check: PASS
- sidecar real não foi versionado; o CI usa placeholder efêmero somente para satisfazer o `externalBin` durante `cargo check`

### Lote 1 — Cérebro único e confiabilidade

- [x] Definir uma entrada cognitiva canônica.
- [x] Remover/absorver fluxos de chat duplicados sem quebrar contratos públicos.
- [x] Intent routing natural sem exigir nomes internos.
- [x] Fast path para conversa normal sem planner LLM desnecessário.
- [x] Retomada exata do plano vinculado ao approval Cyber.
- [x] Grounding obrigatório de claims de execução.
- [x] Resposta de ferramenta baseada somente em evidência real.
- [x] Dany declarar claramente escopo estrutural vs. semântico.
- [x] Testes E2E de linguagem natural para pesquisa, memória e ações.

Validação do Lote 1:

- entrada canônica: `NedCognitiveBridge.handle`; `assist` preservado como alias compatível
- fast path de conversa normal: PASS, sem chamada extra ao planner de ferramentas
- retomada Cyber: plano exato, sem replanning, aprovação de uso único preservada
- transporte desktop da retomada: memória de processo; argumentos não persistidos no arquivo IPC temporário
- execução grounded: somente `state=completed` pode produzir `executed=true`
- Dany do chat: escopo declarado como estrutural, sem falsa alegação de verificação factual
- testes de confiabilidade: 14/14 PASS
- E2E natural governado: pesquisa, projeto e memória 3/3 PASS
- regressão cognitiva legada: 10/10 PASS
- Python Core + Runtime contracts: PASS
- Desktop frontend build: PASS
- Tauri Rust check: PASS

### Lote 2 — Runtime persistente e streaming

- [ ] Backend residente durante toda a sessão desktop.
- [ ] IPC persistente entre Tauri e backend.
- [ ] Streaming de tokens.
- [ ] Streaming de eventos de ferramentas/planos.
- [ ] Cancelamento de geração/tarefa.
- [ ] Reutilização de container, bancos e provider.
- [ ] Métricas TTFT, total latency e tool latency.

### Lote 3 — Tool Runtime profissional

- [ ] Filesystem tipado: list/stat/read/search/mkdir/write/patch/copy/move/delete.
- [ ] Escopos autorizáveis por pasta/sessão.
- [ ] Diff e preview para mutações.
- [ ] Git tipado: status/diff/log/branch/commit.
- [ ] Build/test/lint/typecheck como operações distintas.
- [ ] Process management governado.
- [ ] `arya.run` rebaixado a fallback controlado.
- [ ] Política de segurança baseada em efeitos/capacidades, não blocklist de strings.

### Lote 4 — Agent Loop real

- [ ] Integrar Agent Runtime ao TaskOrchestrator/TaskExecutor existentes.
- [ ] Objetivos naturais -> planos persistentes.
- [ ] Ciclo PLAN -> ACT -> OBSERVE -> VERIFY -> REPAIR/CONTINUE.
- [ ] Budgets de turns/tool calls/tempo/falhas.
- [ ] Pause/resume/cancel.
- [ ] Checkpoints entre efeitos.
- [ ] Replanejamento controlado após evidência de falha.
- [ ] Nunca ampliar autorização silenciosamente.

### Lote 5 — Project Intelligence

- [ ] Descoberta de projeto/repositório.
- [ ] Repo map.
- [ ] Dependency map.
- [ ] Symbol index.
- [ ] Code search.
- [ ] Working set por tarefa.
- [ ] Ignore rules.
- [ ] Instruções persistentes do projeto.
- [ ] Memória de decisões arquiteturais.

### Lote 6 — Model Router

- [ ] Perfis fast/general/reasoning/coding/vision.
- [ ] Modo local-only obrigatório.
- [ ] Modo hybrid opcional.
- [ ] Provider externo somente por configuração explícita.
- [ ] Política de privacidade por provider.
- [ ] Fallback e health checks.
- [ ] Context budgeting e compactação.

### Lote 7 — Bran + Knowledge unificados

- [ ] Consolidar memórias duplicadas.
- [ ] Conversation/session/user/project memory.
- [ ] Knowledge base documental real.
- [ ] Recuperação híbrida lexical + semântica + recência + importância.
- [ ] Contradições e atualização de fatos.
- [ ] Visualizar/editar/esquecer memória.
- [ ] KnowledgePort real no Core.

### Lote 8 — Web Research

- [ ] Query rewriting.
- [ ] Preferência por fontes primárias.
- [ ] Filtros mínimos de relevância.
- [ ] Domain/site constraints.
- [ ] Freshness para perguntas temporais.
- [ ] Pesquisa multi-query.
- [ ] Cross-check entre fontes.
- [ ] Síntese grounded com citações.

### Lote 9 — Browser governado

- [ ] Navegação controlada via Playwright/MCP.
- [ ] Leitura de páginas.
- [ ] Screenshots/evidência.
- [ ] Forms/clicks sensíveis com Cyber.
- [ ] Downloads governados.
- [ ] Sessões autenticadas com política explícita.

### Lote 10 — Dany profissional

- [ ] Aderência ao pedido.
- [ ] Grounding em resultados de ferramentas.
- [ ] Verificação factual quando aplicável.
- [ ] Validação de citações.
- [ ] Código validado por build/test/lint/typecheck.
- [ ] Verificação pós-ação.
- [ ] Rejeitar sucesso não comprovado.

### Lote 11 — MCP e extensões

- [ ] Registro de servidores MCP.
- [ ] Descoberta de ferramentas.
- [ ] Normalização de schemas.
- [ ] Efeitos e riscos atribuídos pelo Cyber.
- [ ] Enable/disable por servidor/capacidade.

### Lote 12 — Desktop profissional

- [ ] Chat streaming.
- [ ] Cards de plano e progresso.
- [ ] Aprovações Cyber no fluxo da conversa.
- [ ] Diff viewer.
- [ ] Artifacts/arquivos.
- [ ] Sessões persistentes por projeto.
- [ ] Cancel/resume.
- [ ] Painel técnico opcional para membros internos.

### Lote 13 — Voz integrada

- [ ] Voz utiliza a mesma Agent Session do texto.
- [ ] STT/TTS.
- [ ] Wake word opcional.
- [ ] Barge-in/interrupção natural.
- [ ] Recuperação de erros e continuidade de conversa.

### Lote 14 — Hardening e release

- [ ] Testes de segurança e permissões.
- [ ] E2E Windows real.
- [ ] Performance gates.
- [ ] Migrações de banco.
- [ ] Backup/crash recovery.
- [ ] Installer reproduzível.
- [ ] Release/versionamento.
- [ ] Update seguro.

### Lote 15 — Rachel Model

Somente depois do sistema operacional produzir dados de alta qualidade.

- [ ] Dataset real e autorizado.
- [ ] Dany preflight.
- [ ] Hardware de treinamento apropriado.
- [ ] SFT/LoRA controlado.
- [ ] Avaliação baseline/candidate.
- [ ] Cyber antes de promoção.
- [ ] Nenhuma atualização automática de pesos.

## Critério final: Professional Agent Ready

A RACHEL só poderá receber este estado quando testes end-to-end demonstrarem, com evidência:

- conversa útil e coerente;
- roteamento autônomo de intenção;
- pesquisa grounded;
- memória funcional;
- trabalho em projetos grandes;
- leitura e edição de arquivos;
- execução de comandos governada;
- Git e testes;
- correção iterativa após falhas;
- tarefas multi-etapas persistentes;
- pausa/retomada;
- browser governado;
- segurança Cyber sem bypass;
- verificação de ações;
- baixa latência para uso diário;
- ausência de alegações falsas de execução.

## Estado legado preservado

O fechamento anterior continua registrado como:

- Architecture Closed: YES
- Production Ready: NO
- Frozen histórico preservado

Este novo ciclo não reescreve essa história. Ele mede uma coisa diferente: se a RACHEL passou de arquitetura fechada para **produto agêntico profissional comprovadamente funcional**.
