# Fase 5 — Observabilidad

## Telemetría estandarizada (`backend/observability/telemetry.py`)

El sistema emite **eventos JSON estandarizados** (JSONL) independientemente del
proveedor LLM (OpenAI, Jan o Mock). Esto permite leer un formato de log
consistente para el dashboard y herramientas de observabilidad.

### Tipos de eventos
| Tipo | Descripción |
|------|-------------|
| `trace_start` / `trace_end` | Ciclo de vida de una conversación |
| `agent_span` | Ejecución de un agente (latencia, estado) |
| `llm_call` | Llamada LLM (tokens, latencia, costo) |
| `conversation` | Resultado final (FCR, deflexión, escalación) |
| `rag_hit` | Acierto/fallo de RAG |
| `approval` | Solicitud de aprobación |
| `escalation` | Escalación a humano |

### Ejemplo de evento
```json
{
  "type": "llm_call",
  "trace_id": "abc123",
  "agent": "clasificador",
  "provider": "mock",
  "model": "gpt-oss:latest",
  "prompt_tokens": 120,
  "completion_tokens": 45,
  "total_tokens": 165,
  "duration_ms": 250,
  "cost_usd": 0.0,
  "status": "ok"
}
```

## Langfuse (observabilidad LLM nativa)

Langfuse se integra con **una línea de código** y registra:
- Latencias de cada sub-agente.
- Árboles de ejecución detallados.
- Costos automáticamente (sin importar el modelo).

### Configuración
```bash
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

### Integración
```python
from backend.observability.langfuse_integration import get_langfuse
langfuse = get_langfuse()  # None si no está configurado
```

## Dashboard de 4 dimensiones

### 1. Negocio/Operación (ITSM)
- Tasa de Resolución en Primer Contacto (FCR)
- Tasa de Deflexión de Tickets
- Distribución de Intenciones
- Tiempo Medio de Resolución (MTTR)

### 2. Rendimiento (Latencia/IA)
- Latencia Extremo a Extremo (E2E)
- Tiempo por Agente Especializado
- Tiempo al Primer Token (TTFT)
- Tasa de Acierto de RAG

### 3. Costos y Consumo
- Costo por Conversación/Ticket
- Consumo de Tokens (Input/Output)
- Costo Total Acumulado (USD)

### 4. Orquestación/Ciclo de Vida
- Tasa de Escalación
- Tickets en Espera de Aprobación
- Tasa de Abandono

## Endpoints de observabilidad
| Endpoint | Descripción | Requiere `API_KEY`* |
|----------|-------------|:---:|
| `GET /api/dashboard` | Métricas de las 4 dimensiones | Sí |
| `GET /api/dashboard/events` | Eventos de telemetría crudos | Sí |
| `GET /dashboard` | Dashboard web (estático) | No |
| `GET /api/health` | Estado del sistema + observabilidad | No |

\* Solo si `API_KEY` está configurada en el entorno (ver
[07_GUARDRAILS.md](07_GUARDRAILS.md) — "Seguridad de la API"); en modo demo
sin configurarla, todo queda abierto. El dashboard web estático (`/dashboard`)
no requiere key, pero sus propias llamadas `fetch` a `/api/dashboard` sí la
necesitan si está activa — el frontend la pide una vez y la guarda en
`localStorage`.
