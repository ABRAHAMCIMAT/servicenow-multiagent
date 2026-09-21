# Guía de pruebas

> Sistema Multiagente ServiceNow · Fase 1
> Última actualización: 21 de septiembre de 2026

## 1. Resumen

| Métrica | Valor |
|---------|-------|
| Pruebas | **408** |
| Archivos | 21 |
| Cobertura | **87 %** (umbral 70 %) |
| Duración | ~7 s |
| Red requerida | Ninguna |
| Credenciales requeridas | Ninguna |

## 2. Pirámide de pruebas

```
        ┌──────────────────────────────┐
        │  e2e (9)                     │  Flujo conversacional completo
        ├──────────────────────────────┤
        │  integración (~180)          │  API, 7 agentes, adaptadores
        ├──────────────────────────────┤
        │  unitarias (~220)            │  Módulos aislados
        └──────────────────────────────┘
```

Cada nivel tiene su marcador de pytest:

| Marcador | Comando | Qué cubre |
|----------|---------|-----------|
| `unit` | `pytest -m unit` | Módulos aislados, sin E/S salvo tmp |
| `integration` | `pytest -m integration` | API, agentes, adaptadores |
| `e2e` | `pytest -m e2e` | Flujo completo hasta escalación |

## 3. Por qué el LLM en modo mock

Toda la suite corre con `LLM_PROVIDER=mock`. El `MockLLM` es **determinista**:
devuelve un JSON fijo por escenario (incidente de acceso, contraseña, hardware,
licencia, conocimiento, estado). Ventajas:

- **Sin red** → el CI no depende de ningún proveedor externo.
- **Sin coste** → no se consumen tokens.
- **Reproducible** → un fallo se reproduce siempre igual.
- **Rápido** → la suite completa tarda ~7 segundos.

Esto permite probar el sistema **completo** (8 agentes, adaptadores, API) sin
infraestructura. Es la base de la estrategia.

## 4. Cómo ejecutar

```bash
make test           # todas las pruebas
make test-unit      # solo unitarias (rápidas)
make test-int       # solo integración
make test-e2e       # solo end-to-end
make cov            # con reporte HTML en htmlcov/

# Directo con pytest
pytest -q
pytest -m unit -q
pytest tests/unit/test_security_redaction.py -v
pytest -k "telemetry or metrics"
```

## 5. Aislamiento

La fixture autouse `_isolated_env` (en `tests/conftest.py`) garantiza que:

- **Ninguna prueba escribe en `backend/data/`.** Todas usan `tmp_path`.
- El LLM siempre es `mock`, sin importar el entorno del desarrollador.
- `LOG_USER_CONTENT=false` (privacidad primero).
- Los globales de seguridad se resetean: `auth._API_KEYS`, `limiter._hits`,
  `audit._log`.
- Las credenciales de ServiceNow y los webhooks se eliminan.

**Regla:** si una prueba necesita mutar un flag del módulo `config`, usa
`monkeypatch.setattr` — mutarlo directamente contamina las pruebas siguientes.

## 6. Cómo escribir una prueba nueva

```python
"""Pruebas de <modulo>."""
import pytest

pytestmark = pytest.mark.integration   # o unit / e2e


def test_descripcion_del_comportamiento(agent_factory):
    # Arrange
    agente = agent_factory("classifier")

    # Act
    resultado = agente.classify("No puedo entrar al CRM")

    # Assert
    assert resultado.intent == Intent.INCIDENT
```

Convenciones:

- Un archivo por módulo bajo prueba: `tests/unit/test_<modulo>.py`.
- Nombres de test descriptivos del **comportamiento**, no de la implementación.
- Usa las fixtures compartidas (`agent_factory`, `mock_llm`, `client`,
  `coordinator`, `sample_conversation`) en lugar de construir objetos a mano.
- Añade un comentario cuando el test cubre una **regresión** concreta.

## 7. Cobertura

```bash
make cov
# Abre htmlcov/index.html
```

El umbral está en `pyproject.toml` (`fail_under`). Módulos excluidos con
justificación:

- `observability/langfuse_integration.py` — dependencia opcional, requiere red.
- `*/__init__.py` — solo reexportaciones.

## 8. Pruebas de regresión de la Fase 0

Estas pruebas blindan hallazgos concretos. **No las elimines sin entender qué
protegen:**

| Prueba | Protege contra |
|--------|----------------|
| `test_no_hardcoded_agent_task_paths_in_code` | Reintroducir rutas `/agent/task` |
| `test_no_default_api_key` | Reintroducir la clave `"jan"` embebida |
| `test_cors_rejects_wildcard` | Reintroducir `allow_origins=["*"]` |
| `test_cors_never_returns_wildcard` | Idem, a nivel de respuesta HTTP |
| `test_preview_hides_content_by_default` | Registrar contenido del usuario sin opt-in |
| `test_free_text_fields_are_redacted` (telemetría) | Fuga de PII en eventos |
| `test_dashboard_events_contain_no_raw_pii` | Fuga de PII vía la API |
| `test_pii_not_written_to_logs` | Fuga de PII en el log |
| `test_redacts_each_pii_kind_with_correct_label` | Que el patrón genérico `phone` vuelva a tragarse tarjetas/IPs/SSN |
| `test_prompt_injection_is_detected` | Que el guardrail de inyección se relaje |
| `test_audit_never_stores_raw_key` | Guardar la credencial en claro en la auditoría |
| `test_health_exposes_no_sensitive_config` | Filtrar configuración en el health público |
| `test_retries_on_transient_error` / `test_does_not_retry_on_400` | Que el retry deje de funcionar o reintente errores de cliente |
| `test_ring_buffer_caps_in_memory_events` | Fuga de memoria en procesos largos |
| `test_knowledge_extracts_steps` | Que la extracción de pasos del RAG devuelva vacío |

## 9. Depuración

```bash
# Ver el detalle de un fallo
pytest tests/unit/test_llm.py::test_retries_on_transient_error -vv

# Detenerse en el primer fallo
pytest -x

# Mostrar los prints
pytest -s

# Solo los que fallaron la última vez
pytest --lf
```

Si un test pasa aislado pero falla en la suite, sospecha de **estado global
compartido** (módulos `config`, `auth`, `rate_limit`, `audit`) — no de lógica.
