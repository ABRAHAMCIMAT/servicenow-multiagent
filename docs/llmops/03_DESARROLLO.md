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

### Qué agentes usan el LLM

De los 8 agentes, solo 2 invocan al LLM: **Clasificador** (triaje/prioridad)
y **Conocimiento** (síntesis de la respuesta RAG). **Diagnóstico**,
**Políticas** y **Ejecución** son deterministas por diseño (reglas/matriz de
decisión), no una limitación temporal: alimentan directamente acciones sobre
cuentas, accesos y aprobaciones de gasto, y en un sistema de ITSM real esa
cadena debe ser auditable y reproducible, no generada por un modelo. Los
tres igual pasan su salida por `Evaluator`/`check_json_schema` (Fase 4) como
red de seguridad ante regresiones de código.

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
│  - Escalación (automática)                  │
├─────────────────────────────────────────────┤
│  Seguridad (auth RBAC, rate limit,          │
│  redacción PII, audit trail)                │
├─────────────────────────────────────────────┤
│  LLMOps (logging, errors, prompts, evals,   │
│  guardrails, patterns, test_matrix)         │
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
├── core/            # LLM, modelos, estado, ConversationStorage
├── security/        # Auth RBAC, rate limit, redacción PII, audit trail
├── llmops/          # Mejores prácticas LLMOps
├── observability/   # Telemetría, métricas, dashboard
├── config.py        # Configuración centralizada por entorno
└── server.py        # API Server
```

## Manejo de errores (`backend/llmops/errors.py`)
- **Excepciones jerárquicas**: `LLMOpsError` como base, con subtipos
  (`ConfigurationError`, `ProviderError`, `RetryableError`, `ValidationError`,
  `AgentError`) — todas se usan en tiempo de ejecución, no solo declaradas:
  - `ConfigurationError`: fail-fast en `LLMConfig.from_env()` si
    `LLM_PROVIDER=openai` sin `LLM_API_KEY`; y en `config.py` si
    `APP_ENV=production` sin `API_KEYS`/`CORS_ORIGINS`.
  - `RetryableError` / `ProviderError`: `OpenAICompatLLM.complete()`
    (core/llm.py) y `ServiceNowAdapter._request()` (adapters/servicenow.py)
    las lanzan según el código de estado HTTP.
  - `AgentError`: `CoordinatorAgent._run()` envuelve cualquier fallo
    inesperado de un agente que no sea ya un `LLMOpsError`.
  - `ValidationError`: guardrails de entrada/salida.
- **Reintentos con backoff exponencial + jitter** para errores transitorios:
  aplica a las llamadas HTTP reales al proveedor LLM y a ServiceNow
  (timeout, error de red, 429, 5xx → reintenta; 4xx → falla directo, sin
  reintentar).
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
- **Sin PII cruda**: el mensaje del usuario nunca se registra en claro por
  defecto (`backend/security/redaction.py`, `preview()`) — solo con
  `LOG_USER_CONTENT=true`, y aun así redactado.

## Tests y CI
- Suite de `pytest` en `tests/` (`unit/`, `integration/`, `e2e/`;
  `pip install -r requirements-dev.txt && pytest`): guardrails, agentes,
  coordinador, escalación automática, seguridad (auth/rate limit/redacción/
  audit), adaptadores, generador de matrices de pruebas (HU-004).
- `tests/conftest.py` fuerza `LLM_PROVIDER=mock` y aísla cada prueba en un
  directorio temporal — la suite nunca escribe en `DATA_DIR` real.
- `.github/workflows/ci.yml`: lint (`ruff`), tipos (`mypy`), tests con
  cobertura (matriz Python 3.11/3.12), seguridad (`bandit`, `pip-audit`) y
  build + smoke test de Docker en cada push/PR.

## Configuración
| Variable | Descripción | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Nivel de logging | `INFO` |
| `LOG_FILE` | Ruta del archivo de log | `DATA_DIR/app.log` |
| `LLM_PROVIDER` | `jan` \| `openai` \| `mock` | `jan` |
| `LANGFUSE_PUBLIC_KEY` | Clave pública Langfuse | — |
| `LANGFUSE_SECRET_KEY` | Clave secreta Langfuse | — |

> Lista completa de variables en [.env.example](../../.env.example) y
> [README.md](../../README.md#️-configuración).
