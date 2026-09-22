# Fase 4 — Evaluación

## Marco de evaluación (`backend/llmops/evals.py`)

El sistema incluye un marco de evaluación para medir la calidad de las salidas
de los agentes y detectar regresiones al cambiar prompts, modelos o lógica.

### Estrategias de evaluación
| Estrategia | Descripción |
|------------|-------------|
| **Checks deterministas** | Validación de esquema JSON, intención válida, prioridad válida |
| **LLM-as-judge** | `check_llm_judge()` (llmops/evals.py) — un LLM evalúa si un texto libre cumple un criterio dado. Best-effort: si el LLM o el parseo fallan, no bloquea (`passed=True`) |
| **Métricas de exactitud** | Comparación con respuestas de referencia (ver `scripts/run_evals.py`) |

### Qué agente evalúa qué
| Agente | Checks | ¿Bloquea si falla? |
|--------|--------|---------------------|
| Clasificador | `json_schema`, `intent_valid` | Sí — degrada a heurística determinista |
| Conocimiento | `json_schema`; `llm_judge` opcional (`ENABLE_LLM_JUDGE=true`, cuesta una llamada LLM extra) | No — solo se registra en el log (evaluación de calidad, no de seguridad) |
| Diagnóstico / Políticas / Ejecución | `json_schema` | No — son deterministas; un fallo indica un bug de código, no un dato dudoso a reintentar |

### Checks implementados (`llmops/evals.py`)
- `check_json_schema`: verifica que la salida contenga los campos requeridos.
- `check_intent_valid`: valida que la intención sea una de las permitidas.
- `check_llm_judge(llm, criteria, field_name)`: LLM-as-judge genérico.

> `check_output_intent` y `check_output_priority` son checks equivalentes
> pero viven en `llmops/guardrails.py`, no aquí — se ejecutan como
> **guardrail de salida** (bloquean/degradan) en vez de como evaluación
> observacional. Ver [07_GUARDRAILS.md](07_GUARDRAILS.md).

### Uso
```python
from backend.llmops.evals import Evaluator, check_json_schema, check_intent_valid

evaluator = Evaluator()
evaluator.register("json_schema", lambda o: check_json_schema(o, ["intent", "category"]))
evaluator.register("intent_valid", check_intent_valid)

resultados = evaluator.run({"intent": "incident", "category": "Incident"})
for r in resultados:
    print(r.name, r.passed)
```

## Conjunto de evaluación (test set)
| Caso | Entrada | Intención esperada | Prioridad esperada |
|------|---------|--------------------|--------------------|
| 1 | "No puedo entrar al CRM" | incident | P2/P3 |
| 2 | "¿Cómo restablezco mi contraseña?" | knowledge | P4 |
| 3 | "Necesito una laptop nueva" | approval | P4 |
| 4 | "¿Cómo va mi ticket?" | status | P4 |
| 5 | "Quiero una licencia de Office" | service_request | P4 |

## Métricas de calidad
- **Tasa de acierto de clasificación**: % de intenciones correctas.
- **Tasa de acierto de RAG**: % de consultas con respuesta útil.
- **Tasa de resolución (FCR)**: % de interacciones resueltas sin humano.
- **Tasa de error**: % de llamadas LLM fallidas.

## Generación de matrices de pruebas (HU-004, `backend/llmops/test_matrix.py`)

Complementa el test set manual de arriba: genera con el LLM un lote de
casos **positivos, negativos y de borde/límite** para un agente o endpoint
registrado como objetivo (`clasificador`, `guardrails_entrada`,
`conocimiento`, `api_chat`, `api_chat_completions`), con un **límite duro de
30 casos por lote** (`MAX_BATCH_SIZE`) — si el LLM devuelve más, se truncan.

- Prompt versionado en el `PromptRegistry` central (`generador_matriz_pruebas`),
  no hardcodeado — mismo patrón que `clasificador`/`conocimiento`.
- Catálogo de objetivos vía `patterns.Registry` (`register_target`/`get_target`/`list_targets`).
- Sin fallback determinista ante error del LLM (a diferencia del clasificador):
  la generación creativa de casos no tiene un sustituto heurístico razonable;
  los errores del proveedor se propagan como `ProviderError`/`RetryableError`.
- Disponible como CLI (`scripts/generate_test_matrix.py`) y como API
  (`GET /api/test-matrix/targets`, `POST /api/test-matrix`).

```bash
python3 scripts/generate_test_matrix.py --target clasificador --count 15
```

## Evaluación continua
- Ejecutar el test set tras cada cambio de prompt o modelo:
  ```bash
  python3 scripts/run_evals.py
  ```
  Corre los 5 casos de esta página contra el `ClassifierAgent` real (proveedor
  `mock`, determinista) y sale con código 1 si alguno falla — apto para CI.
- Registrar los resultados en telemetría para seguimiento histórico.
- Comparar versiones de prompts (A/B) con el mismo test set.
