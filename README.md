# Rachel IA

Plataforma experimental de inteligência artificial local, modular e evolutiva.

A Rachel IA está sendo desenvolvida para reunir conversação, memória persistente,
pesquisa documental, raciocínio, programação, ferramentas controladas, navegação,
voz em tempo real e uma aplicação desktop.

## Estado

> Projeto em fase inicial de arquitetura e validação das fundações técnicas.

## Objetivos

- Conversação por texto e voz;
- execução local de modelos;
- memória persistente e editável;
- leitura de documentos e códigos;
- recuperação de conhecimento com evidências;
- ferramentas controladas por permissões;
- programação e automação em sandbox;
- avaliação contínua de qualidade;
- proteção de dados pessoais;
- aplicação desktop para Windows.

## Arquitetura prevista

- `APP`: aplicação desktop e interface;
- `RACHEL_CORE`: núcleo de orquestração;
- `RACHEL_MODEL`: inferência e treinamento;
- `RACHEL_MEMORY`: memória persistente;
- `RACHEL_KNOWLEDGE`: documentos e busca semântica;
- `RACHEL_AGENT`: planejamento e agentes;
- `RACHEL_TOOLS`: ferramentas e MCP;
- `RACHEL_PERMISSIONS`: políticas e aprovações;
- `RACHEL_PRIVACY`: proteção de dados;
- `RACHEL_BROWSER`: navegação controlada;
- `RACHEL_VOICE`: conversação por voz;
- `RACHEL_EVALUATION`: testes de inteligência e segurança;
- `FONTES`: referências técnicas e componentes externos.

## Segurança

A Rachel não deverá possuir acesso administrativo permanente.

Ações sensíveis deverão utilizar:

- permissões mínimas;
- sandbox;
- confirmação explícita;
- visualização prévia das mudanças;
- backup;
- registro de auditoria;
- possibilidade de reversão.

## Fontes externas

Os projetos em `FONTES/REPOSITORIOS` são registrados como submódulos Git.
Eles permanecem pertencendo aos respectivos autores e seguem suas próprias
licenças.

## Desenvolvimento

Cada alteração funcional será registrada em commits versionados. Segredos,
modelos, bancos, conversas, memórias pessoais e arquivos temporários não serão
publicados no GitHub.

## Autor

Kauã Restoff

- GitHub: https://github.com/restoffkaua08-afk
- LinkedIn: https://www.linkedin.com/in/kau%C3%A3-restoff-2821163a0

<!-- RACHEL_STAGE15_STATUS_START -->
## Status arquitetural

**Arquitetura: 15/15 etapas fechadas.**

A RACHEL atingiu **Architecture Closed**, mas **nao esta declarada
Production Ready**.

- Readiness: 12/20 READY
- Non-ready: 8
- Closure blockers: 0
- Production blockers: 8
- Agent execution: desativada
- Browser execution: desativada
- Training execution: desativada
- Model promotion: nao decidida
- Weights modified: nao
- Portable Runtime SHA256:
  `7CA02072E67E60871A2D6ED06BBEAEFE4637875B44A216362D44CFE97C6F7AA9`

O fechamento preserva explicitamente os dominios BLOCKED, RESERVED,
DEFERRED e UNAVAILABLE; nenhuma capacidade foi promovida artificialmente
para READY.
<!-- RACHEL_STAGE15_STATUS_END -->
