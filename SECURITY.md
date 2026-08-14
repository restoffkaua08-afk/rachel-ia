# Política de segurança

## Princípios

- Nenhuma credencial deve ser versionada.
- Modelos não recebem acesso administrativo direto.
- Ferramentas devem operar com permissões mínimas.
- Ações destrutivas exigem confirmação.
- Dados pessoais devem permanecer locais por padrão.
- Toda ação sensível deve gerar registro de auditoria.

## Segredos

Utilize arquivos `.env` locais baseados em `.env.example`.

Nunca publique:

- chaves de API;
- tokens;
- senhas;
- cookies;
- sessões autenticadas;
- chaves privadas;
- bancos contendo conversas ou memórias pessoais.

## Vulnerabilidades

Não publique vulnerabilidades contendo credenciais ou dados pessoais em issues
públicas.
