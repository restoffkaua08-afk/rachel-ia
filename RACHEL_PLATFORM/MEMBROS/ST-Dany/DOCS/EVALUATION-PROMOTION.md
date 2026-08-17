# Evaluation & Model Promotion

## Dany

Dany e o setor responsavel por treinamento e qualidade.

Sua responsabilidade existente inclui:

- testes;
- avaliacoes;
- feedback;
- comparacao;
- melhoria controlada.

A Etapa 13 formaliza essas responsabilidades na camada `RACHEL_EVALUATION`.

## Orgãos

### Promptfoo

Responsavel futuramente por suites de avaliacao, comparacao e regressao.

### DSPy

Responsavel futuramente por analise e otimizacao controlada.

Nenhum dos dois e executado no contrato 13/1A.

## Relacao com a Etapa 12

A Etapa 12 criou:

- Rachel Model v0.1;
- Training Run Planner;
- Dany/Cyber Training Gate;
- Samwell;
- Training Backend Contract.

A Etapa 13 nao inicia treinamento.

Ela cria o sistema que futuramente dira se um candidato treinado merece ou nao ser promovido.

## Promocao

A promocao e uma decisao separada do treinamento.

Um treinamento concluido nao implica promocao.

Um checkpoint candidato deve passar por avaliacao e regressao antes de qualquer ativacao como runtime oficial da Rachel.

## Regras iniciais

- checkpoint obrigatorio;
- baseline obrigatorio;
- regressao obrigatoria;
- suite de seguranca obrigatoria;
- zero falhas criticas;
- nenhuma regressao de seguranca;
- Dany obrigatoria;
- publicacao externa protegida pelo Cyber;
- promocao automatica proibida.

## Thresholds

Nenhum threshold numerico sera inventado antes da calibracao real das suites.

O contrato começa com `thresholds_state = not-calibrated`.
