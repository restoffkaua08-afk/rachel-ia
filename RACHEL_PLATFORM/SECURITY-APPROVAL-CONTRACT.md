# RACHEL - Contrato de Autorizacao Operacional

Acoes sensiveis nao podem ser liberadas por booleanos, flags genericas
ou confianca implicita no modelo.

O unico mecanismo de liberacao operacional e um `approval_id` emitido
pelo Cyber e persistido pelo `ApprovalStore`.

## Fluxo

1. Ned solicita uma ferramenta.
2. Cyber avalia efeito e risco.
3. Se necessario, Cyber cria uma autorizacao persistente.
4. A interface apresenta risco, motivo, escopo e validade.
5. O usuario aprova ou nega.
6. Ned retoma a etapa usando o `approval_id`.
7. Cyber valida ferramenta, efeito, hash dos argumentos, prazo e status.
8. O token e consumido atomicamente e apenas uma vez.
9. A operacao e executada.
10. King e Jhon mantem auditoria e observabilidade.

## Invariantes

- Nao existe `approved=True` como bypass de ToolCoordinator.
- Nao existe `--approved`.
- Nao existe `--approved-step`.
- Nao existe `--approve-all`.
- Alterar argumentos invalida a autorizacao.
- Trocar ferramenta invalida a autorizacao.
- Token expirado nao executa.
- Token consumido nao pode ser reutilizado.
- Token invalido pode gerar uma nova solicitacao sem destruir o plano.
- O payload publico de aprovacao nao expoe argumentos crus.
- O front apresenta decisoes; ele nao concede privilegios.

O modelo pode raciocinar e planejar com autonomia crescente, enquanto
a autoridade para efeitos sensiveis permanece separada no Cyber.
