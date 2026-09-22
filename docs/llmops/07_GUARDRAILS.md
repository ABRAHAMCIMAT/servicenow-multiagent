# Fase 7 — Guardrails, Seguridad y Control de Errores

## Guardrails (`backend/llmops/guardrails.py`)

Protegen el sistema contra entradas maliciosas o malformadas y salidas no
conformes. Aplican el patrón **Chain of Responsibility** (cadena de validaciones).

### Validación de entrada
| Check | Descripción |
|-------|-------------|
| `check_max_length` | Rechaza mensajes que exceden el máximo de caracteres |
| `check_prompt_injection` | Detecta intentos de inyección de prompt |

### Validación de salida
| Check | Descripción |
|-------|-------------|
| `check_output_intent` | Valida que la intención sea una de las permitidas |
| `check_output_priority` | Valida que la prioridad sea P1-P4 |

### Uso
```python
from backend.llmops.guardrails import default_guardrails
from backend.llmops.errors import ValidationError

try:
    mensaje = default_guardrails.validate_input("ignora las instrucciones...")
except ValidationError as e:
    print(f"Rechazado: {e}")
```

## Control de errores (`backend/llmops/errors.py`)

### Jerarquía de excepciones
```
LLMOpsError
├── ConfigurationError    # Configuración inválida
├── ProviderError         # Error del proveedor LLM
├── RetryableError        # Error transitorio (timeout, rate limit)
├── ValidationError       # Entrada/salida no válida
└── AgentError            # Error en ejecución de un agente
```

### Reintentos con backoff exponencial
Aplicado automáticamente — no hace falta envolver cada llamada a mano:
- `OpenAICompatLLM.complete()` (core/llm.py) reintenta las llamadas al
  proveedor LLM (Jan/OpenAI) ante timeout, error de red, 429 o 5xx.
- `ServiceNowAdapter._request()` (adapters/servicenow.py) hace lo mismo para
  las llamadas HTTP a ServiceNow en modo live.

En ambos casos, un 4xx no reintentable se traduce a `ProviderError`
inmediatamente (sin gastar reintentos). Uso directo del helper para otros
casos:
```python
from backend.llmops.errors import retry

resultado = retry(
    lambda: llm.chat(system, user),
    max_attempts=3,
    base_delay=0.5,
    max_delay=8.0,
)
```

### Degradación elegante
```python
from backend.llmops.errors import safe_call

# Si falla, devuelve None en vez de romper el flujo
data = safe_call(lambda: llm.chat_json(system, user), default=None)
```

## Seguridad de la API (`backend/llmops/security.py`)

Sigue el mismo patrón DEMO/LIVE que el resto del sistema: sin configurar,
todo queda abierto para probar en `localhost` sin fricción; se activa
explícitamente para exponer el servicio fuera de esa máquina.

### Autenticación por API key
- `API_KEY` sin configurar → modo demo, sin autenticación (con `warning` al
  iniciar el servidor para que no pase desapercibido).
- `API_KEY` configurada → se exige en cada endpoint protegido, vía header
  `X-API-Key` **o** `Authorization: Bearer <key>` — este segundo formato es
  el que envían los clientes OpenAI-compatible (Jan) que solo tienen un
  campo "API Key".
- Endpoints protegidos: `/api/chat`, `/api/conversations*`, `/api/escalate`,
  `/api/dashboard*`, `/api/test-matrix*`, `/v1/chat/completions`.
  `/api/health` y el dashboard estático (`/dashboard`) quedan siempre
  abiertos (health-check estándar / sin datos sensibles en el HTML).

### Rate limiting
Ventana deslizante en memoria por cliente (API key si existe, si no la IP),
configurable con `RATE_LIMIT_PER_MINUTE` (default 30; `0` desactiva el
límite). Aplica a `/api/chat` y `/v1/chat/completions` — las rutas que
disparan una llamada LLM facturable. Sin dependencias externas; para
producción multi-proceso, reemplazar por un backend compartido (Redis).

### CORS
`CORS_ORIGINS` (orígenes separados por comas; `*` por default, para la demo
local). Configurar con los orígenes reales antes de producción.

### Uso
```python
from backend.llmops.security import require_api_key, enforce_rate_limit
from fastapi import Depends

@app.post("/api/chat", dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)])
def chat(req: ChatRequest): ...
```

## Otras prácticas de seguridad
1. **Anti inyección de prompt**: detección de patrones maliciosos (regex —
   no es un sustituto de un clasificador de seguridad dedicado; cubre los
   patrones más comunes, ver tests en `tests/test_guardrails.py`).
2. **Validación de entrada**: longitud máxima y normalización.
3. **Validación de salida**: esquema JSON e intención/prioridad válidas —
   `validate_output()` se ejecuta en `ClassifierAgent` (degrada a heurística
   si falla, no solo se registra en el log).
4. **Sin datos inventados**: los prompts instruyen a usar solo lo que dice el usuario.
5. **Credenciales por variables de entorno**: nunca en el código (ver `.env.example`).

## Buenas prácticas de mantenimiento
1. **Logging estructurado** con contexto por conversación/traza.
2. **Excepciones tipadas** para diagnóstico rápido.
3. **Reintentos con backoff** para errores transitorios.
4. **Degradación elegante** para pasos no críticos.
5. **Patrones de diseño** (Registry, Strategy, Facade — ver
   [03_DESARROLLO.md](03_DESARROLLO.md)).
6. **Tests y CI**: suite de `pytest` + `.github/workflows/ci.yml` en cada
   push/PR (ver [06_DESPLIEGUE.md](06_DESPLIEGUE.md)).
7. **Documentación por fase** en español.
