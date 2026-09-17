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

## Seguridad
1. **Anti inyección de prompt**: detección de patrones maliciosos.
2. **Validación de entrada**: longitud máxima y normalización.
3. **Validación de salida**: esquema JSON e intención/prioridad válidas.
4. **Sin datos inventados**: los prompts instruyen a usar solo lo que dice el usuario.
5. **Credenciales por variables de entorno**: nunca en el código.

## Buenas prácticas de mantenimiento
1. **Logging estructurado** con contexto por conversación/traza.
2. **Excepciones tipadas** para diagnóstico rápido.
3. **Reintentos con backoff** para errores transitorios.
4. **Degradación elegante** para pasos no críticos.
5. **Patrones de diseño** (Registry, Strategy, Chain, Facade, Observer).
6. **Documentación por fase** en español.
