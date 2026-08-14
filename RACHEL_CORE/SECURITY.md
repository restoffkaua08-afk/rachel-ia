# Segurança

Não publique chaves, `.env`, bancos, auditorias ou conversas. Em caso de suspeita de exposição, revogue a credencial no provedor e remova o dado do ambiente antes de qualquer commit.

O Rachel Core 0.1 não executa terminal, navegador, instalações ou operações administrativas. Integrações futuras devem aplicar menor privilégio, confirmação por ação, escopo exato, auditoria redigida e possibilidade de cancelamento.

A API deve continuar restrita a `127.0.0.1`, `localhost` ou `::1`. Não exponha a porta diretamente à rede local ou à internet.

