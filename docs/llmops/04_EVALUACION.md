# Fase 4 — Evaluación

## Marco de evaluación (`backend/llmops/evals.py`)

El sistema incluye un marco de evaluación para medir la calidad de las salidas
de los agentes y detectar regresiones al cambiar prompts, modelos o lógica.

### Estrategias de evaluación
| Estrategia | Descripción |
|------------|-------------|
| **Checks deterministas** | Validación de esquema JSON, intención válida, prioridad válida |
| **LLM-as-judge** | Un LLM evalúa la calidad de la respuesta (extensible) |
| **Métricas de exactitud** | Comparación con respuestas de referencia |

### Checks implementados
- `check_json_schema`: verifica que la salida contenga los campos requeridos.
- `check_intent_valid`: valida que la intención sea una de las permitidas.
- `check_output_priority`: valida que la prioridad sea P1-P4.

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

## Evaluación continua
- Ejecutar el test set tras cada cambio de prompt o modelo.
- Registrar los resultados en telemetría para seguimiento histórico.
- Comparar versiones de prompts (A/B) con el mismo test set.
