# ServiceNow Multi-Agent Conversational System

Sistema multiagente conversacional que resuelve los problemas de un servicio de ServiceNow: **triaje y enrutamiento inteligente, autoservicio (Nivel 0/1), orquestación de aprobaciones, ciclo de vida del ticket y escalación a agentes humanos (Nivel 2/3)** — todo desde una conversación en lenguaje natural.

## 🧠 Arquitectura Multiagente

```
[Usuario] ──> 🤖 Agente Coordinador (orquestador)
                  │
                  ├──> 📋 Agente Clasificador (triaje, categoría, prioridad SLA)
                  │
                  ├──> 🔍 Agente de Diagnóstico (causa raíz en el sistema)
                  │
                  ├──> ⚖️ Agente de Políticas (¿requiere aprobación?)
                  │
                  ├──> ⚡ Agente de Ejecución (autoservicio: AD, contraseñas, licencias)
                  │
                  ├──> 📚 Agente de Conocimiento (RAG sobre la KB de ServiceNow)
                  │
                  ├──> 🔄 Agente de Seguimiento (actualizaciones proactivas del ticket)
                  │
                  └──> 🚨 Agente de Escalación (transferencia a humano Nivel 2/3 con contexto)
```

> Diagrama simplificado. La arquitectura completa (Contexto, Contenedores,
> Componentes y Código, con diagramas) está en
> **[docs/c4/00_INDICE.md](docs/c4/00_INDICE.md)** — incluye, por ejemplo,
> que "Seguimiento" es un método del Coordinador, no una clase propia, y que
> la escalación a Nivel 2/3 se dispara **automáticamente** (no requiere un
> paso manual) cuando el sistema no puede resolver un caso.

## ✅ Problemas que resuelve

| # | Problema | Solución |
|---|----------|----------|
| 1 | Categorización errónea | El **Clasificador** analiza el texto libre, identifica la intención y asigna categoría/subcategoría/Assignment Group sin intervención humana |
| 1 | Incidentes críticos sepultados | **Priorización SLA** por impacto, urgencia, sentimiento y palabras clave |
| 2 | Enlaces en vez de respuestas | El **Agente de Conocimiento (RAG)** extrae la respuesta exacta y la explica paso a paso |
| 2 | Tareas manuales repetitivas | El **Agente de Ejecución** desbloquea cuentas AD, restablece contraseñas y asigna licencias desde el chat |
| 3 | Cuellos de botella en aprobaciones | El **Coordinador** busca al manager en la org de ServiceNow y envía notificación push (Slack/Teams/WhatsApp) con aprobación en tiempo real |
| 4 | Falta de actualizaciones | El **Agente de Seguimiento** notifica cambios de estado y notas |
| 4 | Documentación deficiente | **Resolution Notes** estructuradas al cerrar el caso |
| 5 | Transferencias frías | El **Agente de Escalación** entrega un resumen ejecutivo del diagnóstico al técnico humano |

## 🚀 Inicio rápido (demo, sin credenciales)

```bash
pip install -r requirements.txt
./scripts/run_demo.sh
```

Luego abre la consola avanzada en **http://localhost:8000/app** — la sirve el propio backend, mismo origen que la API, sin CORS ni servidor aparte.

También puedes probar la demo interactiva en terminal:

```bash
python3 scripts/demo.py
```

## 🔌 Integración con Jan

El backend implementa el contrato **OpenAI-compatible** que Jan consume para un proveedor personalizado, incluida la ruta de descubrimiento de modelos y el streaming SSE en formato estricto.

1. Abre Jan → **Settings → Model Providers → Add Provider**.
2. Elige **OpenAI-compatible** y configura:
   - **Base URL:** `http://localhost:8000/v1` *(debe terminar en `/v1`)*
   - **API Key:** el valor de tu credencial `API_KEYS` — Jan la envía como `Authorization: Bearer <valor>`.
   - **Model ID:** `servicenow-multiagent`
3. Jan consulta `GET /v1/models` al guardar el proveedor y lista `servicenow-multiagent` automáticamente.
4. Selecciónalo en el chat y conversa con el sistema multiagente.

| Endpoint | Rol mínimo | Para qué |
|---|---|---|
| `GET /v1/models` · `GET /v1/models/{id}` | user | Descubrimiento de modelos (lo que Jan llama al guardar el proveedor) |
| `POST /v1/chat/completions` | user | Conversación, con o sin `stream` |
| `GET /app` | público (estático) | Consola web: chat, inspector, dashboard y Jan/API |

La consola web incluye una pestaña **Jan / API** que muestra estos valores con botones de copia y lanza las tres peticiones reales contra el backend, para verificar la integración sin abrir Jan.

> Jan también puede ejecutar el LLM localmente (servidor `localhost:1337`) y este sistema lo usa como proveedor de razonamiento para los agentes: `LLM_PROVIDER=jan`. Detalle completo en [docs/INTEGRACION_JAN.md](docs/INTEGRACION_JAN.md).

## 🔐 Seguridad (Fase 0)

Todos los endpoints salvo `GET /api/health` exigen una credencial. Sin
`API_KEYS` configurada, en modo `development` se genera una clave admin de
un solo uso y se imprime en consola al arrancar; en `APP_ENV=production` el
servidor **no arranca** sin `API_KEYS` ni `CORS_ORIGINS` explícitas.

```bash
export API_KEYS="mi_clave_admin:admin,mi_clave_agente:agent"
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: mi_clave_admin" -H "Content-Type: application/json" \
  -d '{"message": "No puedo entrar al CRM"}'
```

Tres roles con jerarquía (`user` < `agent` < `admin`): `user` solo conversa
(`/api/chat`, `/v1/chat/completions`); `agent` además lee conversaciones,
el dashboard y genera matrices de pruebas; `admin` además ve
`/api/health/detail` y los eventos crudos de telemetría. Ver
[docs/llmops/07_GUARDRAILS.md](docs/llmops/07_GUARDRAILS.md) y
[docs/SEGURIDAD.md](docs/SEGURIDAD.md).

## ⚙️ Configuración

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `jan` \| `openai` \| `mock` | `jan` |
| `LLM_BASE_URL` | URL del LLM compatible con OpenAI | `http://localhost:1337/v1` |
| `LLM_MODEL` | Modelo a usar | `gpt-oss:latest` |
| `LLM_API_KEY` | Clave para el proveedor LLM (obligatoria si `LLM_PROVIDER=openai`) | — |
| `PORT` | Puerto del API | `8000` |
| `APP_ENV` | `development` \| `production` — en `production`, `API_KEYS`/`CORS_ORIGINS` son obligatorias | `development` |
| `API_KEYS` | Credenciales `clave:rol,clave:rol` (roles: `user`, `agent`, `admin`) | clave de desarrollo autogenerada |
| `CORS_ORIGINS` | Orígenes permitidos, separados por comas (nunca `*`) | `localhost:8000` en dev |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` | Límite de solicitudes por credencial/IP y ventana en segundos | `60` / `60` |
| `LOG_USER_CONTENT` | Si `true`, registra el mensaje del usuario (redactado de PII) en logs | `false` |
| `DATA_DIR` | Directorio de datos (logs, telemetría, conversaciones, auditoría) | `backend/data` |
| `TELEMETRY_MAX_EVENTS` | Límite de eventos en memoria del buffer de telemetría | `5000` |
| `ENABLE_LLM_JUDGE` | Activa el check LLM-as-judge en el Agente de Conocimiento (llamada LLM extra) | `false` |
| `SNOW_INSTANCE` | Instancia de ServiceNow (vacío = demo) | — |
| `SNOW_USER` / `SNOW_PASSWORD` / `SNOW_TOKEN` | Credenciales ServiceNow | — |
| `NOTIFY_CHANNEL` | `slack` \| `teams` \| `whatsapp` | `slack` |
| `SLACK_WEBHOOK_URL` | Webhook de Slack | — |
| `TEAMS_WEBHOOK_URL` | Webhook de Teams | — |
| `WHATSAPP_API_URL` | API de WhatsApp | — |

Copia `.env.example` a `.env` para arrancar con todos los defaults de modo demo.

### Modo live

```bash
export LLM_PROVIDER=jan
export APP_ENV=production
export API_KEYS="clave_admin:admin"
export CORS_ORIGINS="https://tu-dominio.com"
export SNOW_INSTANCE=tuinstancia
export SNOW_USER=admin
export SNOW_PASSWORD=...
export NOTIFY_CHANNEL=slack
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
./scripts/run_live.sh
```

### Docker (recomendado para producción)

```bash
cp .env.example .env   # o exporta API_KEYS/CORS_ORIGINS a mano
docker compose up --build
```

Imagen multi-stage (< 300 MB), usuario sin privilegios, healthcheck
integrado. Ver [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).

## 📁 Estructura

```
servicenow-multiagent/
├── backend/
│   ├── core/          # LLM, modelos, estado, ConversationStorage
│   ├── agents/        # 8 agentes especializados
│   ├── adapters/      # ServiceNow, notificaciones
│   ├── security/       # Auth RBAC, rate limit, redacción PII, audit trail
│   ├── llmops/         # Prompts, evals, guardrails, errores, patrones
│   ├── config.py       # Configuración centralizada por entorno
│   └── server.py       # API REST + endpoint OpenAI-compatible
├── frontend/
│   └── index.html     # Consola avanzada: streaming SSE, markdown, historial, inspector
├── scripts/            # run_demo, run_live, demo interactiva, run_evals, generate_test_matrix
├── tests/               # unit/ · integration/ · e2e/ (pytest)
├── Dockerfile, docker-compose.yml
└── docs/
    ├── c4/              # Arquitectura — Modelo C4
    └── llmops/          # Documentación por fase LLMOps
```

## 📡 API

| Endpoint | Rol mínimo |
|---|---|
| `GET /api/health` | público |
| `GET /api/health/detail` | admin |
| `POST /api/chat` | user |
| `GET /api/conversations`, `GET /api/conversations/{id}` | agent |
| `POST /api/escalate` | agent |
| `GET /api/test-matrix/targets`, `POST /api/test-matrix` (HU-004) | agent |
| `GET /api/dashboard` | agent |
| `GET /api/dashboard/events` | admin |
| `POST /v1/chat/completions` | user |

## 📊 Observabilidad y Dashboard (Control Total)

El sistema incluye una capa de **observabilidad completa** con telemetría JSON estandarizada (modelo-agnóstica) y un **dashboard de 4 dimensiones** para el control total del multiagente.

### Arquitectura de observabilidad

```
[Agentes] ──> Telemetry (JSONL estandarizado) ──> MetricsEngine ──> /api/dashboard
     │                    │
     └──> LLM instrumentado ──> Langfuse (opcional, 1 línea)
```

- **Modelo-agnóstico**: los logs JSON son idénticos sin importar si usas OpenAI, Jan o Mock.
- **Langfuse**: integración nativa opcional (una línea de código) que registra latencias por sub-agente, árboles de ejecución y costos automáticamente.
- **Sin dependencias**: si no configuras Langfuse, todo corre con telemetría local JSONL.

### Las 4 dimensiones del dashboard

| Dimensión | Métricas |
|-----------|----------|
| **1. Negocio/Operación (ITSM)** | FCR, deflexión de tickets, distribución de intenciones, MTTR |
| **2. Rendimiento (Latencia/IA)** | E2E latency, tiempo por agente, TTFT, RAG hit rate |
| **3. Costos y Consumo** | Costo por conversación, tokens (input/output), costo total USD |
| **4. Orquestación/Ciclo de vida** | Tasa de escalación, awaiting_approval, tasa de abandono |

### Uso

```bash
# 1. Generar telemetría de demo (puebla el dashboard)
python3 scripts/demo_telemetry.py

# 2. Levantar el servidor
python3 -m backend.server

# 3. Abrir la consola avanzada (chat + inspector + dashboard + Jan/API)
# http://localhost:8000/app
#    o solo el dashboard: http://localhost:8000/dashboard
```

### Configuración de Langfuse (opcional)

```bash
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

Con esto, cada traza/span/generación se envía a Langfuse para observabilidad LLM nativa (latencias por sub-agente, árboles de ejecución, costos automáticos).

## ✅ Tests

```bash
pip install -r requirements-dev.txt
export APP_ENV=development LLM_PROVIDER=mock
pytest --cov=backend --cov-report=term-missing   # unit/ + integration/ + e2e/
ruff check backend tests && ruff format --check backend tests
mypy backend
python3 scripts/run_evals.py   # test set de la Fase 4 (docs/llmops/04_EVALUACION.md)
```

CI (`.github/workflows/ci.yml`) corre lint, tipos, tests (matriz 3.11/3.12
con cobertura), `bandit`/`pip-audit` y un build + smoke test de Docker en
cada push/PR. Ver [docs/TESTING.md](docs/TESTING.md).

## 🧪 Generación de matrices de pruebas (HU-004)

Genera, con el LLM, casos de prueba **positivos, negativos y de borde/límite** para cualquier agente o endpoint del sistema, con un límite duro de **30 casos por lote**.

```bash
python3 scripts/generate_test_matrix.py --list-targets
python3 scripts/generate_test_matrix.py --target clasificador --count 15
```

```bash
curl -X POST http://localhost:8000/api/test-matrix \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"target": "guardrails_entrada", "count": 20}'
```

Funciona en modo demo (`LLM_PROVIDER=mock`) sin credenciales. Ver [docs/llmops/04_EVALUACION.md](docs/llmops/04_EVALUACION.md).

## 🧠 Mejores Prácticas LLMOps

El sistema aplica las mejores prácticas de **LLMOps** para el desarrollo de
sistemas multiagentes conversacionales, con documentación de cada fase en español.

### Paquete LLMOps (`backend/llmops/`)
| Módulo | Función |
|--------|---------|
| `logging.py` | Logging estructurado (JSON) con contexto por conversación |
| `errors.py` | Excepciones tipadas, reintentos con backoff, degradación elegante |
| `prompts.py` | Gestión y versionado de prompts (Registry) |
| `evals.py` | Evaluación de salidas de agentes (checks deterministas + LLM-as-judge) |
| `guardrails.py` | Validación de entrada/salida, anti inyección de prompt |
| `patterns.py` | Patrones de diseño (Registry, Strategy) |
| `test_matrix.py` | Generador de matrices de pruebas (HU-004) |

### Paquete de seguridad (`backend/security/`, Fase 0)
| Módulo | Función |
|--------|---------|
| `auth.py` | Autenticación por API key + RBAC (roles `user`/`agent`/`admin`) |
| `rate_limit.py` | Rate limiting por credencial/IP (ventana deslizante) |
| `redaction.py` | Redacción de PII (email, teléfono, tarjeta, IP, SSN) en logs/telemetría |
| `audit.py` | Audit trail append-only (JSONL) de acciones sensibles |

### Arquitectura (Modelo C4)
| Nivel | Documento |
|------|-----------|
| Índice | [docs/c4/00_INDICE.md](docs/c4/00_INDICE.md) |
| 1. Contexto | [docs/c4/01_CONTEXTO.md](docs/c4/01_CONTEXTO.md) |
| 2. Contenedores | [docs/c4/02_CONTENEDORES.md](docs/c4/02_CONTENEDORES.md) |
| 3. Componentes | [docs/c4/03_COMPONENTES.md](docs/c4/03_COMPONENTES.md) |
| 4. Código | [docs/c4/04_CODIGO.md](docs/c4/04_CODIGO.md) |

### Documentación por fase LLMOps (en español)
| Fase | Documento |
|------|-----------|
| Índice | [docs/llmops/00_INDICE.md](docs/llmops/00_INDICE.md) |
| 1. Planificación | [docs/llmops/01_PLANIFICACION.md](docs/llmops/01_PLANIFICACION.md) |
| 2. Datos y Prompts | [docs/llmops/02_DATOS_Y_PROMPTS.md](docs/llmops/02_DATOS_Y_PROMPTS.md) |
| 3. Desarrollo | [docs/llmops/03_DESARROLLO.md](docs/llmops/03_DESARROLLO.md) |
| 4. Evaluación | [docs/llmops/04_EVALUACION.md](docs/llmops/04_EVALUACION.md) |
| 5. Observabilidad | [docs/llmops/05_OBSERVABILIDAD.md](docs/llmops/05_OBSERVABILIDAD.md) |
| 6. Despliegue | [docs/llmops/06_DESPLIEGUE.md](docs/llmops/06_DESPLIEGUE.md) |
| 7. Guardrails | [docs/llmops/07_GUARDRAILS.md](docs/llmops/07_GUARDRAILS.md) |
