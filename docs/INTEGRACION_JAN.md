# Integración con Jan

[Jan](https://github.com/janhq/jan) es un frontend de chat open-source que ejecuta LLMs localmente con privacidad. Este sistema multiagente se integra con Jan de tres formas complementarias, y las tres están implementadas y verificadas.

---

## Opción A: Jan como proveedor de LLM para los agentes

El backend usa Jan como motor de razonamiento de los agentes. Jan expone un **servidor local compatible con OpenAI** en `http://localhost:1337/v1`.

1. Abre Jan → **Settings → Advanced → Local API Server** → activa el servidor.
2. Descarga un modelo (p. ej. `gpt-oss:latest`) desde el Hub de Jan.
3. Ejecuta el backend apuntando a Jan:

```bash
export LLM_PROVIDER=jan
export LLM_BASE_URL=http://localhost:1337/v1
export LLM_MODEL=gpt-oss:latest
./scripts/run_live.sh
```

Los agentes (clasificador, diagnóstico, etc.) usan el modelo local de Jan para razonar, manteniendo los datos en tu máquina. Toda la capa LLM está detrás de `backend/core/llm.py`, así que cambiar de proveedor es una variable de entorno.

---

## Opción B: Jan como frontend del sistema multiagente

El backend expone el contrato que Jan consume para un **proveedor personalizado OpenAI-compatible**. En Jan: **Settings → Model Providers → Add Provider**.

| Campo | Valor |
|---|---|
| **Formato de API** | OpenAI-compatible |
| **Provider name** | ServiceNow Multi-Agent |
| **Base URL** | `http://localhost:8000/v1` |
| **API key** | una de las claves de `API_KEYS` |
| **Model ID** | `servicenow-multiagent` |

> La Base URL **debe** terminar en `/v1`. Jan intenta descubrir los modelos llamando a `{base_url}/models` al guardar el proveedor; si esa ruta no existe, hay que añadir el modelo a mano. Aquí sí existe, así que Jan lista `servicenow-multiagent` automáticamente.

### El contrato que Jan exige

Jan no es tolerante con desviaciones del formato OpenAI. El backend implementa exactamente:

**`GET /v1/models`** — descubrimiento. Devuelve `{"object":"list","data":[{id,object,created,owned_by}]}`.
También existe `GET /v1/models/{model_id}`.

**`POST /v1/chat/completions`** — conversación. Respuesta completa:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1790184890,
  "model": "servicenow-multiagent",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

Y con `"stream": true`, SSE en el orden correcto:

1. Un primer chunk con `delta: {"role": "assistant"}`.
2. Los chunks de contenido, todos con `object: "chat.completion.chunk"`, `id` y `created`.
3. Un chunk final con `delta: {}` y `finish_reason: "stop"`.
4. El terminador `data: [DONE]`.

Sin el chunk final, los clientes dejan la respuesta abierta indefinidamente. Los campos extra que Jan envía (`temperature`, `top_p`, `stream_options`, `max_tokens`) se aceptan y se ignoran a propósito: el orquestador decide el razonamiento, no el cliente.

Cada mensaje que envíes a Jan se enruta al orquestador, que ejecuta el flujo multiagente completo y devuelve la respuesta.

---

## Opción C: Consola web incluida (estilo Jan)

El proyecto incluye una consola avanzada en `frontend/index.html`, servida por el propio backend en **`http://localhost:8000/app`** — mismo origen que la API, así que no hay CORS de por medio.

```bash
./scripts/run_demo.sh          # o run_live.sh
# abre http://localhost:8000/app
```

Qué trae:

| Capacidad | Detalle |
|---|---|
| **Streaming en vivo** | Consume `/v1/chat/completions` con SSE — el mismo contrato que Jan, así que la consola valida la integración de verdad |
| **Markdown** | Negritas, listas, encabezados, código en línea y bloques, sin dependencias externas |
| **Historial** | Barra lateral con conversaciones persistidas, estado por color y reapertura completa |
| **Inspector de agentes** | Traza en vivo: agentes ejecutados, clasificación con confianza, ticket generado |
| **Pestaña Jan/API** | Muestra Base URL, API key y Model ID con botones de copia, más pruebas reales del contrato en un clic |
| **Dashboard** | Las 4 dimensiones de observabilidad |
| **Tema** | Claro y oscuro |

La pestaña **Jan / API** es la forma más rápida de verificar la integración: lanza las tres peticiones reales (`/v1/models`, streaming, respuesta completa) y muestra la respuesta cruda del backend.

---

## Resumen de puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Jan Local API | 1337 | LLM local de Jan |
| Backend multiagente | 8000 | API REST + contrato OpenAI-compatible |
| Consola web | 8000 | `/app` (mismo origen, sin CORS) |
| Dashboard | 8000 | `/dashboard` |

---

## Pruebas de la integración

`tests/e2e/test_jan_integration.py` levanta un proceso **uvicorn real** en un puerto libre y habla con él por HTTP — exactamente lo que hace Jan al conectarse. Cubre:

- `GET /v1/models` con `Authorization: Bearer` responde 200 y lista el modelo.
- Sin credencial responde 401/403.
- Recuperación de un modelo concreto.
- Flujo completo de Jan: descubrir modelo → elegirlo → conversar.
- Contrato SSE: cada chunk es JSON válido con `object`, `id`, `created`; existe el primer chunk con rol, el chunk final con `finish_reason` y el terminador `[DONE]`.
- Los campos extra de OpenAI no rompen la petición.
- El guardrail rechaza inyección de prompt con 400 y formato de error OpenAI.
- La consola se sirve en `/app` y contiene streaming, markdown e inspector.
- Flujos conversacionales completos (incidente, aprobación, conocimiento), persistencia, dashboard y ausencia de PII en telemetría.

```bash
python -m pytest tests/e2e/test_jan_integration.py -v
```
