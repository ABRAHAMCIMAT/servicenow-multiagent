# Fase 2 — Datos y Prompts

## Gestión de datos

### Fuentes de datos
| Fuente | Uso | Modo |
|--------|-----|------|
| ServiceNow (incidentes) | Creación/actualización de tickets | LIVE / DEMO |
| Base de Conocimientos (KB) | Fuente RAG para respuestas | LIVE / DEMO |
| Estructura organizacional | Búsqueda de manager para aprobaciones | LIVE / DEMO |
| Active Directory | Diagnóstico y autoservicio (desbloqueo, contraseña) | LIVE / DEMO |

### Calidad de datos
- **Validación de entrada**: longitud máxima, anti inyección de prompt.
- **Normalización**: limpieza de texto antes del procesamiento.
- **RAG**: recuperación por palabras clave (intercambiable por búsqueda vectorial).

## Gestión de prompts

### Registro central de prompts (`backend/llmops/prompts.py`)
Todos los prompts se centralizan en un `PromptRegistry` con:
- **Versionado** (semver): cada cambio de prompt incrementa la versión.
- **Huella (fingerprint)**: hash SHA-256 del contenido para detectar cambios.
- **Metadatos**: descripción, modelo objetivo, variables.
- **Renderizado parametrizado**: plantillas con variables tipadas.

### Prompts registrados
| Clave | Versión | Descripción |
|-------|---------|-------------|
| `clasificador` | 1.0.0 | Triaje, categoría y prioridad SLA |
| `conocimiento` | 1.0.0 | Respuesta RAG paso a paso |

### Buenas prácticas de prompts aplicadas
1. **Instrucciones claras y específicas** — cada agente tiene un rol definido.
2. **Salida JSON estructurada** — facilita la integración y validación.
3. **Reglas explícitas** — matriz de prioridad SLA documentada en el prompt.
4. **Sin datos inventados** — el prompt instruye a usar solo lo que dice el usuario.
5. **Versionado** — permite A/B testing y rollback.

## Versionado de prompts
```python
from backend.llmops.prompts import registry

# Registrar un nuevo prompt
registry.register(PromptTemplate(
    key="mi_prompt",
    version="1.0.0",
    description="Descripción",
    template="Plantilla con {variable}",
    variables=["variable"],
))

# Renderizar
texto = registry.render("mi_prompt", variable="valor")
```
