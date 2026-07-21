# YouTube-Pub-MCP — Planejamento

## Visão
Ferramenta Python para envio e gerenciamento de canal YouTube, com suporte a múltiplos canais, agendamento e observabilidade via JSON.

## Requisitos funcionais (v1)
- Upload de vídeo longo e Shorts
- Agendamento via `publishAt`
- Suporte a múltiplos canais
- Limite diário configurável
- Scheduler local via `youtube-schedule.json`
- Skills Hermes + plugin OpenCode

## Requisitos não-funcionais
- Nenhum segredo commitado
- Local auth storage por canal
- Quota e retry explícitos

## Dependências principais
- Python 3.11+
- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`
- `python-dotenv`

## Estrutura
- `src/youtube_pub_mcp/`
- `docs/`
- `tests/`
- `.planning/`

## Status
- Pesquisas concluídas e salvas em `docs/`
- Estrutura pronta para implementação
