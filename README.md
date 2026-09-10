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

Luego abre `frontend/index.html` en tu navegador (o sirve el frontend con `python3 -m http.server 8080 --directory frontend`).

También puedes probar la demo interactiva en terminal:

```bash
python3 scripts/demo.py
```

## 🔌 Integración con Jan

El backend expone un **endpoint compatible con OpenAI** en `http://localhost:8000/v1/chat/completions`, por lo que Jan puede conectarse como proveedor personalizado:

1. Abre Jan → **Settings → Advanced → OpenAI-compatible API** (o añade un proveedor personalizado).
2. Configura:
   - **Base URL:** `http://localhost:8000/v1`
   - **API Key:** `jan` (cualquier valor)
   - **Model:** `servicenow-multiagent`
3. Selecciona el modelo en el chat de Jan y conversa con el sistema multiagente.

> Jan también puede ejecutar el LLM localmente (servidor `localhost:1337`) y este sistema lo usa como proveedor de razonamiento para los agentes.

## ⚙️ Configuración

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `jan` \| `openai` \| `mock` | `jan` |
| `LLM_BASE_URL` | URL del LLM compatible con OpenAI | `http://localhost:1337/v1` |
| `LLM_MODEL` | Modelo a usar | `gpt-oss:latest` |
| `PORT` | Puerto del API | `8000` |
| `SNOW_INSTANCE` | Instancia de ServiceNow (vacío = demo) | — |
| `SNOW_USER` / `SNOW_PASSWORD` | Credenciales ServiceNow | — |
| `NOTIFY_CHANNEL` | `slack` \| `teams` \| `whatsapp` | `slack` |
| `SLACK_WEBHOOK_URL` | Webhook de Slack | — |
| `TEAMS_WEBHOOK_URL` | Webhook de Teams | — |
| `WHATSAPP_API_URL` | API de WhatsApp | — |

### Modo live

```bash
export LLM_PROVIDER=jan
export SNOW_INSTANCE=tuinstancia
export SNOW_USER=admin
export SNOW_PASSWORD=...
export NOTIFY_CHANNEL=slack
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
./scripts/run_live.sh
```

## 📁 Estructura

```
servicenow-multiagent/
├── backend/
│   ├── core/          # LLM, modelos, estado
│   ├── agents/        # 8 agentes especializados
│   ├── adapters/      # ServiceNow, notificaciones
│   └── server.py      # API REST + endpoint OpenAI-compatible
├── frontend/
│   └── index.html     # Chat web (estilo Jan)
├── scripts/           # run_demo, run_live, demo interactiva
└── docs/              # Documentación
```

## 📡 API

- `GET /api/health` — estado del sistema
- `POST /api/chat` — enviar mensaje al multiagente
- `GET /api/conversations` — listar conversaciones
- `GET /api/conversations/{id}` — detalle
- `POST /api/escalate` — escalar a humano
- `POST /v1/chat/completions` — endpoint OpenAI-compatible (para Jan)
