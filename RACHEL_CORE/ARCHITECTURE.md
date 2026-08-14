# Arquitetura do Rachel Core

## Princípio central

O núcleo contém regras e casos de uso, enquanto integrações externas são adaptadores substituíveis. Nenhuma interface, modelo ou ferramenta deve se tornar uma dependência estrutural do domínio.

## Camadas

- `domain`: modelos imutáveis, estados e erros estáveis;
- `ports.py`: contratos de modelo, memória, política, conhecimento e auditoria;
- `application.py`: fluxo de conversa e persistência;
- `adapters`: SQLite, JSONL, modelo simulado e API compatível;
- `bootstrap.py`: composição explícita das dependências;
- `cli.py`: entrada de terminal;
- `api.py`: servidor HTTP local sem dependências externas.

## Fluxo

1. entrada é validada;
2. conversa é criada ou recuperada;
3. mensagem do usuário é persistida;
4. auditoria registra somente metadados redigidos;
5. contexto recente e evidências autorizadas são reunidos;
6. o adaptador de modelo produz a resposta;
7. resposta é persistida;
8. resultado inclui IDs, provedor, modelo, estado e duração.

## Extensões previstas

RAG, voz, ferramentas, memória semântica e modelos locais devem implementar as portas existentes ou novas portas pequenas. Ferramentas nunca são chamadas diretamente pelo modelo: passam por registro, validação de argumentos, classificação de risco, política e confirmação.

## Decisões de segurança

- API limitada a loopback;
- token opcional para o aplicativo local;
- limite de 1 MB por corpo HTTP e 50 mil caracteres por mensagem;
- erros internos não expostos pela API;
- política de ferramentas nega tudo por padrão;
- logs mascaram padrões comuns de segredo;
- dados locais e `.env` ignorados pelo Git.

