# Lote 2 — Runtime persistente, streaming e desempenho

## Objetivo

Eliminar o custo de inicialização do backend a cada mensagem e criar uma base de execução desktop residente, observável e cancelável.

## Critérios de conclusão

O Lote 2 só pode ser considerado concluído quando os itens abaixo estiverem simultaneamente verdadeiros:

- o desktop mantém um único backend RACHEL residente durante a sessão;
- o mesmo `NedCognitiveBridge`, container, provider, memória e coordenador de ferramentas são reutilizados entre requests;
- o IPC entre Tauri e sidecar é persistente e baseado em NDJSON por stdin/stdout;
- o host Tauri reconstrói linhas NDJSON corretamente mesmo quando stdout chega fragmentado ou agrupado;
- o provider OpenAI-compatible usa streaming real (`stream=true`) e entrega chunks assim que chegam;
- o Core persiste a resposta do assistente somente quando o streaming termina com sucesso;
- cancelar uma geração não grava o texto parcial como resposta concluída;
- o servidor residente aceita pedido de cancelamento enquanto uma geração está em andamento;
- eventos de runtime podem carregar `chat.started`, `chat.delta`, `chat.completed`, `chat.cancelled` e fases de agente;
- TTFT é medido a partir do primeiro chunk real e não é preenchido artificialmente quando desconhecido;
- o tempo de execução da ferramenta é medido dentro do `ToolCoordinator`, separado do planejamento e da síntese posterior;
- Core completo, regressões críticas de Runtime, frontend e `cargo check` permanecem verdes.

## Garantias implementadas

### Backend residente

O `rachel-backend` é iniciado em modo `--server` e permanece ativo durante a sessão desktop. O Tauri mantém o processo filho e correlaciona requests por `request_id`.

### Streaming real

`OpenAICompatibleAdapter.generate_stream()` usa o protocolo de streaming do endpoint OpenAI-compatible e processa eventos `data:`/SSE, incluindo `[DONE]`.

O MockModel continua emitindo múltiplos chunks para testes determinísticos.

### Persistência segura

O conteúdo parcial recebido durante uma geração cancelada é transitório. Apenas uma resposta completa é adicionada à memória de conversa como mensagem do assistente.

### Cancelamento

O runtime residente mantém um evento de cancelamento por request ativo e aceita `cancel_all` sem esperar a geração atual terminar.

A garantia deste lote é especificamente **cancelamento de geração/runtime request**. Cancelamento, pausa e retomada de uma tarefa agêntica multi-etapas serão validados no Lote 4, junto do Agent Loop real.

### Métricas

- `total_ms`: latência total do request residente;
- `ttft_ms`: tempo até o primeiro chunk real quando existe streaming;
- `duration_ms` de `tool_result`: tempo exclusivamente dentro do executor da ferramenta;
- `duration_scope=tool-execution-only`: identifica explicitamente o escopo da métrica;
- métricas desconhecidas permanecem `null` em vez de receber valores estimados enganosos.

## Estado de validação

Antes deste documento, a rodada de CI que validou o novo transporte residente e streaming concluiu com:

- Python Core + Runtime contracts: PASS
- Desktop frontend build: PASS
- Tauri Rust check: PASS

O teste de métricas de ferramenta foi acrescentado em seguida e deve permanecer obrigatório no mesmo gate crítico.

## Limites deste lote

Este lote não declara concluídos:

- UI final de streaming/token a token;
- experiência visual completa de cancelamento e progresso;
- Agent Loop multi-etapas;
- filesystem externo;
- browser governado;
- model routing;
- avaliação semântica/factual avançada.

Essas capacidades pertencem aos lotes seguintes e não devem ser confundidas com a infraestrutura de runtime entregue aqui.
