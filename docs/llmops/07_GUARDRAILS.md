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

## Seguridad de la API (`backend/security/`, Fase 0)

Sin `API_KEYS`, en `APP_ENV=development` se genera una clave admin de
desarrollo (impresa una vez en consola); en `APP_ENV=production` el
servidor **no arranca** sin `API_KEYS` ni `CORS_ORIGINS` explícitas
(`backend/config.py`, fail-fast).

### Autenticación y RBAC (`security/auth.py`)
- Credenciales `API_KEYS="clave:rol,clave:rol"`, tres roles con jerarquía:
  `user` < `agent` < `admin`.
- Se envían como header `X-API-Key` o `Authorization: Bearer <clave>` — este
  segundo formato es el que usan los clientes OpenAI-compatible (Jan).
- `require_auth` exige cualquier rol; `require_role(ROLE_X)` exige un rol
  mínimo. Ver la tabla de endpoints en el [README](../../README.md#-api).
- El actor se identifica por `key_id` (hash SHA-256 truncado de la
  credencial) — la clave cruda nunca se registra ni se audita.

### Rate limiting (`security/rate_limit.py`)
Ventana deslizante en memoria por credencial (o IP si es anónimo),
configurable con `RATE_LIMIT_MAX`/`RATE_LIMIT_WINDOW` (default 60/60s).
Para producción multi-réplica, mover a un backend compartido (Redis) — la
interfaz (`RateLimiter.check`) se mantiene igual.

### Redacción de PII (`security/redaction.py`)
Detecta y enmascara email, teléfono, tarjeta, IPv4 y SSN antes de escribir
cualquier log o traza. El mensaje crudo del usuario **nunca se registra por
defecto** (`preview()` devuelve `"[contenido del usuario omitido]"`); con
`LOG_USER_CONTENT=true` se registra, pero siempre redactado.

### Audit trail (`security/audit.py`)
Log append-only (`DATA_DIR/audit.jsonl`) de acciones sensibles: chat
recibido/rechazado, escalaciones, generación de matrices de pruebas. Cada
entrada tiene actor (`key_id`), acción, destino y resultado — nunca lanza
excepciones (best-effort, no debe romper el flujo del usuario).

## Otras prácticas de seguridad
1. **Anti inyección de prompt**: detección de patrones maliciosos (regex —
   no es un sustituto de un clasificador de seguridad dedicado).
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
5. **Patrones de diseño** (Registry, Strategy — ver
   [03_DESARROLLO.md](03_DESARROLLO.md)).
6. **Tests y CI**: suite de `pytest` + `.github/workflows/ci.yml` en cada
   push/PR (ver [06_DESPLIEGUE.md](06_DESPLIEGUE.md)).
7. **Documentación por fase** en español.
