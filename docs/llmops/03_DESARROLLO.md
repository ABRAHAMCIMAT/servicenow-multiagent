# Fase 3 — Desarrollo

> Esta página resume la arquitectura desde el punto de vista de desarrollo.
> Para el modelo C4 completo (Contexto → Contenedores → Componentes →
> Código, con diagramas), ver [docs/c4/00_INDICE.md](../c4/00_INDICE.md).

## Arquitectura

### Patrones de diseño aplicados (`backend/llmops/patterns.py`)
| Patrón | Aplicación real |
|--------|------------|
| **Registry** | `PromptRegistry` (llmops/prompts.py) y `Evaluator` (llmops/evals.py) delegan su almacenamiento por clave en `patterns.Registry` |
| **Strategy** | `LLM` (core/llm.py) selecciona la implementación del proveedor (mock vs. OpenAI-compatible) vía `patterns.Strategy` |
| **Chain of Responsibility** | `Guardrails` (llmops/guardrails.py) implementa su propia cadena de validaciones secuenciales con corte en el primer error; no reutiliza una clase genérica de `patterns.py` porque su contrato (mensaje de error u `None`) no encaja con un pipeline que transforma datos |
| **Facade** | Interfaz unificada del sistema (LLM, adapters) |

> Nota: `patterns.py` tenía antes también `Pipeline` y `EventBus`, pero ningún módulo los importaba — se retiraron para no dejar código muerto disfrazado de patrón aplicado (ver auditoría LLMOps).

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
│  guardrails, patterns, security, test_matrix)│
├─────────────────────────────────────────────┤
│  Observabilidad (telemetría, Langfuse,      │
│  dashboard)                                 │
├─────────────────────────────────────────────┤
│  Adapters (ServiceNow, Notificaciones, LLM) │
└─────────────────────────────────────────────┘
```

## Qué agentes usan el LLM

De los 8 agentes, solo 2 invocan al LLM: **Clasificador** (triaje/prioridad)
y **Conocimiento** (síntesis de la respuesta RAG). **Diagnóstico**,
**Políticas** y **Ejecución** son deterministas por diseño (reglas/matriz de
decisión), no una limitación temporal: alimentan directamente acciones sobre
cuentas, accesos y aprobaciones de gasto, y en un sistema de ITSM real esa
cadena debe ser auditable y reproducible, no generada por un modelo. Los
tres igual pasan su salida por `Evaluator`/`check_json_schema` (Fase 4) como
red de seguridad ante regresiones de código.

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
  `AgentError`) — todas se usan en tiempo de ejecución, no solo declaradas:
  - `ConfigurationError`: fail-fast en `LLMConfig.from_env()` si
    `LLM_PROVIDER=openai` sin `LLM_API_KEY`.
  - `RetryableError` / `ProviderError`: `OpenAICompatLLM.complete()`
    (core/llm.py) y `ServiceNowAdapter._request()` (adapters/servicenow.py)
    las lanzan según el código de estado HTTP.
  - `AgentError`: `CoordinatorAgent._run()` envuelve cualquier fallo
    inesperado de un agente que no sea ya un `LLMOpsError`.
  - `ValidationError`: guardrails de entrada/salida.
- **Reintentos con backoff exponencial + jitter** para errores transitorios:
  `retry()` envuelve las llamadas HTTP reales al proveedor LLM y a
  ServiceNow (timeout, error de red, 429, 5xx → reintenta; 4xx → falla
  directo con `ProviderError`, sin reintentar).
- **Degradación elegante** con `safe_call` para pasos no críticos.
- **Fail-fast** para errores de configuración.
- **Respuestas HTTP tipadas**: `backend/server.py` registra
  `@app.exception_handler` para `ProviderError` (502), `AgentError` (500) y
  `LLMOpsError` (500 genérico) en vez de dejar que FastAPI devuelva un
  traceback crudo.

## Logging estructurado (`backend/llmops/logging.py`)
- Salida **JSON** de una línea por evento.
- Niveles de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- **Contexto por conversación/traza** (conversation_id, trace_id, agent).
- **Rotación de archivos** (5 MB × 5 backups).

## Tests y CI
- Suite de `pytest` en `tests/` (`pip install -r requirements-dev.txt && pytest`):
  guardrails, clasificador (test set de Fase 4), flujos del coordinador,
  escalación automática, retry/excepciones tipadas, seguridad de la API
  (auth/rate limit), generador de matrices de pruebas (HU-004).
- `tests/conftest.py` fuerza `LLM_PROVIDER=mock` y redirige logs/telemetría/
  conversaciones a un directorio temporal — la suite nunca escribe en
  `backend/data/` (los datos reales del proyecto).
- `.github/workflows/ci.yml` corre `pytest` + `scripts/run_evals.py` en cada
  push/PR.

## Configuración
| Variable | Descripción | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `LOG_FILE` | Ruta del archivo de log | `backend/data/app.log` |
| `LLM_PROVIDER` | `jan` \| `openai` \| `mock` | `jan` |
| `LANGFUSE_PUBLIC_KEY` | Clave pública Langfuse | — |
| `LANGFUSE_SECRET_KEY` | Clave secreta Langfuse | — |

> Lista completa de variables (23) en [.env.example](../../.env.example).
