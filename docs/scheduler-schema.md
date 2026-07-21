# Scheduler / Queue de postagens YouTube

## Estrutura JSON proposta

### Arquivo singular `youtube-schedule.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/youtube-schedule.schema.json",
  "title": "youtube-schedule",
  "description": "Agendamento de uploads/publicações para o YouTube MCP.",
  "type": "object",
  "required": ["version", "generated_at", "quota", "jobs"],
  "properties": {
    "version": {
      "type": "string",
      "description": "Versão do formato do arquivo (ex.: 1.0.0). Facilita migrações futuras.",
      "examples": ["1.0.0"]
    },
    "generated_at": {
      "type": "string",
      "format": "date-time",
      "description": "UTC ISO-8601 do momento em que o arquivo foi gerado."
    },
    "quota": {
      "$ref": "#/$defs/quota"
    },
    "jobs": {
      "type": "array",
      "items": { "$ref": "#/$defs/job" },
      "description": "Fila/cronograma completa de jobs. Ordenação sugerida: scheduled_at asc."
    }
  },
  "$defs": {
    "quota": {
      "type": "object",
      "required": ["daily_limit", "window_start", "window_end", "timezone"],
      "properties": {
        "daily_limit": {
          "type": "integer",
          "minimum": 1,
          "description": "Máximo de jobs encerrantes por janela de 24h. Referência: ~15 envios/dia.",
          "examples": [15]
        },
        "window_start": {
          "type": "string",
          "pattern": "^\\d{2}:\\d{2}$",
          "description": "Horário local de início da janela (ex.: 00:00)."
        },
        "window_end": {
          "type": "string",
          "pattern": "^\\d{2}:\\d{2}$",
          "description": "Horário local de término da janela (ex.: 23:59)."
        },
        "timezone": {
          "type": "string",
          "examples": ["America/Sao_Paulo"]
        }
      }
    },
    "job": {
      "type": "object",
      "required": ["id", "type", "status", "scheduled_at", "visibility", "payload"],
      "properties": {
        "id": {
          "type": "string",
          "description": "Identificador único do job no armazenamento local/queue."
        },
        "type": {
          "type": "string",
          "enum": ["upload", "publish_draft"],
          "description": "upload = vídeo novo; publish_draft = materializar rascunho já existente."
        },
        "status": {
          "$ref": "#/$defs/job_status"
        },
        "scheduled_at": {
          "type": "string",
          "format": "date-time",
          "description": "Momento planejado para execução (UTC ISO-8601)."
        },
        "visibility": {
          "$ref": "#/$defs/visibility"
        },
        "payload": {
          "$ref": "#/$defs/payload"
        },
        "created_at": {
          "type": "string",
          "format": "date-time"
        },
        "updated_at": {
          "type": "string",
          "format": "date-time"
        },
        "retry": {
          "$ref": "#/$defs/retry"
        }
      }
    },
    "job_status": {
      "type": "string",
      "enum": [
        "pending",
        "ready",
        "executing",
        "succeeded",
        "failed",
        "cancelled",
        "skipped_rate_limited",
        "skipped_window_closed"
      ]
    },
    "visibility": {
      "type": "object",
      "required": ["mode"],
      "properties": {
        "mode": {
          "type": "string",
          "enum": ["public", "private", "unlisted", "scheduled"],
          "description": "Modo YouTube. 'scheduled' indica que scheduled_at define publicação pública futura."
        },
        "uses_youtube_schedule": {
          "type": "boolean",
          "default": true,
          "description": "Se modo=scheduled, repassar publishedAt à API do YouTube. Quando false, o MCP usar 'private' + própria lógica."
        }
      }
    },
    "retry": {
      "type": "object",
      "properties": {
        "attempts": {
          "type": "integer",
          "minimum": 0,
          "default": 0
        },
        "max_attempts": {
          "type": "integer",
          "minimum": 0,
          "default": 3
        },
        "next_at": {
          "type": "string",
          "format": "date-time",
          "description": "Próxima tentativa autorizada, respeitando janela de quota."
        },
        "reason": {
          "type": "string",
          "examples": ["quota_exceeded", "transient_api_error", "invalid_draft_id"]
        }
      }
    },
    "payload": {
      "type": "object",
      "description": "Payload específico por type.",
      "oneOf": [
        {
          "properties": {
            "type": { "const": "upload" },
            "video": {
              "type": "object",
              "required": ["file"],
              "properties": {
                "file": { "type": "string", "description": "Caminho local no repositório/shared." },
                "sha256": { "type": "string" },
                "title": { "type": "string" },
                "description": { "type": "string" },
                "tags": {
                  "type": "array",
                  "items": { "type": "string" },
                  "maxItems": 500
                },
                "category_id": { "type": "string" },
                "language": { "type": "string" },
                "thumbnail_local_path": { "type": "string" },
                "thumbnail_time_offset": { "type": "number" },
                "notify_subscribers": { "type": "boolean" }
              }
            },
            "draft_id": {
              "type": "string",
              "description": "Identificador inexistente para upload; mantido para unificação."
            }
          },
          "required": ["type", "video", "draft_id"]
        },
        {
          "properties": {
            "type": { "const": "publish_draft" },
            "video": {
              "type": "object",
              "properties": {
                "file": { "type": "string" },
                "sha256": { "type": "string" },
                "title": { "type": "string" },
                "description": { "type": "string" },
                "tags": {
                  "type": "array",
                  "items": { "type": "string" },
                  "maxItems": 500
                },
                "category_id": { "type": "string" },
                "language": { "type": "string" },
                "thumbnail_local_path": { "type": "string" },
                "thumbnail_time_offset": { "type": "number" },
                "notify_subscribers": { "type": "boolean" }
              }
            },
            "draft_id": {
              "type": "string",
              "description": "ID do rascunho existente retornado pelo MCP/YouTube."
            }
          },
          "required": ["type", "video", "draft_id"]
        }
      ]
    }
  }
}
```

---

## Variantes auxiliares

### 1) `youtube-schedule.pending.json`
Somente jobs prontos para processamento imediato/agendado.
Útil para workers que só precisam consumir jobs elegíveis.

```json
{
  "version": "1.0.0",
  "generated_at": "2026-07-21T20:00:00Z",
  "quota": {
    "daily_limit": 15,
    "window_start": "00:00",
    "window_end": "23:59",
    "timezone": "America/Sao_Paulo"
  },
  "jobs": [
    {
      "id": "job-0001",
      "type": "upload",
      "status": "ready",
      "scheduled_at": "2026-07-22T09:00:00Z",
      "visibility": { "mode": "scheduled", "uses_youtube_schedule": true },
      "payload": {
        "type": "upload",
        "video": {
          "file": "shared/videos/vid-123.mp4",
          "title": "Vídeo 1",
          "description": "Descrição",
          "tags": ["tag1", "tag2"]
        },
        "draft_id": null
      }
    },
    {
      "id": "job-0002",
      "type": "publish_draft",
      "status": "ready",
      "scheduled_at": "2026-07-22T10:00:00Z",
      "visibility": { "mode": "public", "uses_youtube_schedule": false },
      "payload": {
        "type": "publish_draft",
        "video": { "title": "Versão final" },
        "draft_id": "yt-draft-abc123"
      }
    }
  ]
}
```

### 2) `youtube-schedule.visibility.json`
Visão humana/script de auditoria com apenas campos necessários.

```json
{
  "version": "1.0.0",
  "generated_at": "2026-07-21T20:00:00Z",
  "jobs": [
    {
      "id": "job-0001",
      "status": "pending",
      "scheduled_at": "2026-07-23T08:00:00Z",
      "title": "Vídeo 1",
      "channel": "channel-x",
      "owner": "user-1",
      "visibility_mode": "scheduled",
      "visibility_is_public": false,
      "retry": { "attempts": 1, "max_attempts": 3 },
      "publish_time": "2026-07-23T10:30:00Z"
    }
  ]
}
```

---

## Padrões referência

1. **BullMQ / Redis**
   - Filas tipam-se por nome; job é payload JSON arbitrário.
   - Estados sugeridos: `pending`, `ready`, `delayed`, `executing`, `succeeded`, `failed`, `canceled`.
   - Campos comuns: `id`, `name`, `data`, `opts` (`delay`, `priority`, `removeOnComplete`, `backoff`).
   - Uso para este projeto: `youtube-upload` e `youtube-publish` como queues separadas.

2. **Celery**
   - Task label + ETA/countdown substituem cron explícito.
   - Status finitos: `PENDING`, `RECEIVED`, `STARTED`, `SUCCESS`, `RETRY`, `FAILURE`, `REVOKED`.
   - `rate_limit` define janela por task.
   - Mapeamento: `scheduled_at` = ETA; `daily_limit` = rate_limit agrupado por dia.

3. **Temporal / Schedules**
   - Schedule contém `spec.cron`, `start_time`, `end_time`, `jitter`.
   - Cada trigger pode lançar workflow com payload JSON.
   - Inspiração para regras complexas, mas overhead maior para MCP local.

4. **n8n workflows exportados**
   - JSON com `nodes` e `connections`; agendamento vem do ScheduleTrigger.
   - Campo relevante: `parameters.cronExpression`.
   - Referência para sincronização com ferramentas existentes.

5. **YouTube API semantics**
   - `privacyStatus` aceita `public`, `private`, `unlisted`.
   - `publishAt` só tem efeito quando status do upload é `private`.
   - Portanto: `visibility.mode = scheduled` mapeia para `privacyStatus=private` + `publishAt=futuro`.

---

## Decisões de modelagem

- `type` separado (`upload` / `publish_draft`) evita schema union muito grande;
  usa-se `job_type + draft_id` para determinar ação.
- Estado explícito distinto de execução: `skipped_rate_limited` e `skipped_window_closed`
  preservam auditoria sem perder a intenção original.
- `quota` no cabeçalho permite recálculo rápido e reescrita mínima.
- Variante `youtube-schedule.pending.json` replica padrão comum de "view pronta"
  usado por ferramentas de conteúdo (ex.: batch de 15 em 15).

---

## Referências de padrões consultados
- BullMQ docs: jobs, delayed, retrying.
- Celery calling docs: ETA/countdown, rate_limit.
- Temporal docs: schedules/workflows.
- n8n docs: Schedule Trigger/cron JSON.
- YouTube Help & bulk uploaders: publishAt behavior, daily quota guidance.
