## Lote 1 — Cérebro único e confiabilidade

### Critério de conclusão

O Lote 1 só pode ser considerado concluído quando todos os itens abaixo estiverem simultaneamente verdadeiros:

- toda retomada após aprovação Cyber executa exatamente o plano aprovado, sem novo planejamento de modelo;
- o plano de retomada não é persistido no JSON temporário de IPC do desktop;
- o Cyber continua validando ferramenta + argumentos e aprovação de uso único;
- estados diferentes de `completed` nunca são sintetizados como sucesso;
- respostas de execução expõem metadados explícitos `planned`, `executed`, `verified` e evidência mínima;
- pedidos naturais de conversa continuam funcionando sem ferramenta;
- intenções naturais cobertas por rotas determinísticas continuam funcionando sem exigir nomes internos de membros/ferramentas;
- testes cognitivos legados continuam verdes;
- testes específicos de confiabilidade do Lote 1 ficam verdes no CI;
- build do frontend e `cargo check` do Tauri permanecem verdes.

### Limite de garantia

Este lote garante confiabilidade do fluxo cognitivo e de autorização dentro do software e dos testes disponíveis. Ele não declara capacidades externas inexistentes, treinamento de pesos, navegador autônomo irrestrito ou hardware não disponível.
