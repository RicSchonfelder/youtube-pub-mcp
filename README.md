# youtube-pub-mcp

Servidor MCP para publicação de vídeos no YouTube, com suporte a múltiplos canais e fila de agendamento em JSON.

> Estado atual: **alpha**. Publicações reais exigem OAuth do Google e devem ser testadas primeiro com vídeos privados ou não listados.

## O que existe hoje

- autenticação OAuth 2.0 para contas/canais do YouTube;
- upload e publicação por meio da YouTube Data API v3;
- suporte a múltiplos canais autorizados;
- scheduler/queue com estados, janela de quota e retry;
- schema documentado em `docs/scheduler-schema.md`;
- testes em `tests/`.

## Requisitos

- Python 3.11 ou superior;
- `uv`;
- projeto Google Cloud com YouTube Data API v3 ativada;
- credencial OAuth 2.0 do tipo Desktop app.

## Instalação

```bash
uv sync
```

## Credenciais

Guarde o JSON OAuth fora do repositório, por exemplo em:

```text
~/.config/youtube-pub-mcp/credentials.json
```

Tokens gerados também devem permanecer fora do Git. Consulte `docs/setup.md` para o fluxo de autorização.

## Comandos

O entry point declarado no `pyproject.toml` é:

```bash
youtube-pub-mcp --help
```

Também é possível usar:

```bash
uv run youtube-pub-mcp --help
```

Os subcomandos e opções disponíveis devem ser conferidos com `--help`, pois o projeto ainda está em evolução.

## Agendamento JSON

A estrutura da fila está documentada em:

- `docs/scheduler-schema.md`
- `docs/setup.md`

Os estados incluem `pending`, `ready`, `executing`, `succeeded`, `failed` e estados de limitação de quota. Datas devem usar ISO-8601 em UTC quando o schema exigir.

## Testes e qualidade

```bash
PYTHONPATH=src uv run python -m pytest
uv run ruff check .
uv run mypy src
```

O `PYTHONPATH=src` é necessário no estado atual porque o pacote usa layout `src/` e os testes ainda não registram esse caminho automaticamente.

## Segurança operacional

Nunca versione `credentials.json`, `token.json`, refresh tokens ou chaves. Não publique automaticamente sem confirmar canal, vídeo, visibilidade e horário. A quota e as políticas do YouTube podem limitar uploads.
