# Fase 3 — Desarrollo

## Arquitectura

### Patrones de diseño aplicados (`backend/llmops/patterns.py`)
| Patrón | Aplicación |
|--------|------------|
| **Registry** | Registro de agentes, prompts y estrategias |
| **Strategy** | Selección de proveedor LLM y de agentes |
| **Chain of Responsibility** | Pipeline de procesamiento y guardrails |
| **Facade** | Interfaz unificada del sistema (LLM, adapters) |
| **Observer** | Bus de eventos para telemetría y notificaciones |

### Capas del sistema
```
┌─────────────────────────────────────────────┐
│  Frontend (Jan / Web)                       │
├─────────────────────────────────────────────┤
│  API Server (FastAPI)                       │
│  - REST API (/api/*)                        │
│  - OpenAI-compatible (/v1/chat/completions) │
├─────────────────────────────────────────────┤
│  Orquestación (Coordinador)                 │
│  - Clasificador → Diagnóstico → Políticas   │
│  - Ejecución / Conocimiento / Seguimiento   │
│  - Escalación                               │
├─────────────────────────────────────────────┤
│  LLMOps (logging, errors, prompts, evals,   │
│  guardrails, patterns)                      │
├─────────────────────────────────────────────┤
│  Observabilidad (telemetría, Langfuse,      │
│  dashboard)                                 │
├─────────────────────────────────────────────┤
│  Adapters (ServiceNow, Notificaciones, LLM) │
└─────────────────────────────────────────────┘
```

## Estructura de código
```
backend/
├── agents/          # Agentes especializados
├── adapters/        # ServiceNow, notificaciones
├── core/            # LLM, modelos, estado
├── llmops/          # Mejores prácticas LLMOps
├── observability/   # Telemetría, métricas, dashboard
└── server.py        # API Server
```

## Manejo de errores (`backend/llmops/errors.py`)
- **Excepciones jerárquicas**: `LLMOpsError` como base, con subtipos
  (`ConfigurationError`, `ProviderError`, `RetryableError`, `ValidationError`,
  `AgentError`).
- **Reintentos con backoff exponencial + jitter** para errores transitorios.
- **Degradación elegante** con `safe_call` para pasos no críticos.
- **Fail-fast** para errores de configuración.

## Logging estructurado (`backend/llmops/logging.py`)
- Salida **JSON** de una línea por evento.
- Niveles de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- **Contexto por conversación/traza** (conversation_id, trace_id, agent).
- **Rotación de archivos** (5 MB × 5 backups).

## Configuración
| Variable | Descripción | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `LOG_FILE` | Ruta del archivo de log | `backend/data/app.log` |
| `LLM_PROVIDER` | `jan` \| `openai` \| `mock` | `jan` |
| `LANGFUSE_PUBLIC_KEY` | Clave pública Langfuse | — |
| `LANGFUSE_SECRET_KEY` | Clave secreta Langfuse | — |
