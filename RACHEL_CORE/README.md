# Rachel Core 0.1.1

Núcleo local e independente da Rachel IA. Fornece conversas, memória SQLite, auditoria segura, política de ferramentas, provedor simulado, adaptador para APIs compatíveis e uma API HTTP restrita a `127.0.0.1`.

## Requisitos

- Windows 11, Linux ou macOS;
- Python 3.11 ou 3.12;
- `uv` recomendado, ou `pip`.

## Instalação com uv

```powershell
Set-Location -LiteralPath "C:\Users\Kauã\Desktop\Rachel IA\RACHEL_CORE"
uv python install 3.11
uv venv --python 3.11
uv pip install -e .
uv run python -m unittest discover -s tests -v
```

## Primeira execução

```powershell
uv run rachel doctor
uv run rachel chat
```

O provedor padrão é `mock`, portanto o sistema funciona sem rede e sem chave. Para conectar uma API compatível com o formato OpenAI, copie `.env.example` para `.env` e configure `RACHEL_MODEL_PROVIDER=openai-compatible`, URL, modelo e chave. O arquivo `.env` nunca deve ser versionado.

## API local

```powershell
uv run rachel serve --port 8765
```

Abra `http://127.0.0.1:8765` no navegador para usar a interface provisória.

Rotas:

- `GET /health`
- `POST /v1/chat`
- `GET /v1/conversations`
- `GET /v1/conversations/{id}/export`
- `DELETE /v1/conversations/{id}`

Se `RACHEL_API_TOKEN` estiver definido, use `Authorization: Bearer <token>`. O servidor recusa hosts que não sejam loopback.

## Dados

Por padrão, tudo fica em `.rachel/`: banco `rachel.db` e auditoria `audit.jsonl`. Conversas podem ser exportadas e apagadas. O log de auditoria mascara padrões comuns de segredo.

## Limites deliberados da versão 0.1

- ferramentas de computador são negadas por padrão;
- não há execução de terminal, navegador ou alteração de arquivos;
- não existe aprendizado automático a partir das conversas;
- a API compatível usa resposta JSON não contínua; o núcleo oferece streaming lógico ao CLI;
- voz, RAG e aplicativo desktop entram por adaptadores posteriores.
