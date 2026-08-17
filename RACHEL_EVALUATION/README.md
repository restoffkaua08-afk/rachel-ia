# Rachel Evaluation

## Responsavel

Dany (`ST-Dany`).

## Objetivo

A camada `RACHEL_EVALUATION` concentra avaliacao, regressao, comparacao e promocao controlada dos modelos e runtimes da Rachel.

## Estado atual

Etapa 13 iniciada em modo de contrato.

Nenhuma avaliacao de modelo e executada nesta fase.

## Escopo futuro

A camada sera responsavel por:

- contrato de suites;
- baseline de qualidade;
- avaliacao de candidatos;
- regressao;
- seguranca;
- uso correto de ferramentas;
- memoria e privacidade;
- relatorios;
- gate de promocao.

## Baseline atual

`qwen3:1.7b` via Ollama pode futuramente atuar como baseline temporario.

Ele nao e o Rachel Model e nunca pode ser promovido como se fosse `rachel-model-v0.1`.

## Rachel Model

`rachel-model-v0.1` permanece como candidato futuro.

Ainda nao existe checkpoint treinado.

## Promptfoo

Orgão associado a Dany para avaliacao e regressao.

Invocacao ainda desativada.

## DSPy

Orgão associado a Dany para analise e futura otimizacao controlada.

Otimizacao ainda desativada.

## Promocao

Promocao automatica e proibida.

Antes de qualquer promocao futura ser elegivel:

1. precisa existir checkpoint candidato;
2. precisa existir baseline;
3. suites precisam ser executadas;
4. regressao precisa ser analisada;
5. falhas criticas precisam ser zero;
6. nao pode haver regressao de seguranca;
7. Dany precisa aprovar;
8. publicacao externa continua sujeita ao Cyber.

Os thresholds numericos ainda nao foram calibrados e nao devem ser inventados nesta etapa.

## Estado de seguranca

- model execution: desativado;
- Promptfoo: desativado;
- DSPy optimization: desativado;
- report write: desativado;
- promotion execution: desativado;
- external publish: desativado;
- training: desativado;
- weights modified: nao.
