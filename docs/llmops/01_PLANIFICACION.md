# Fase 1 — Planificación

## Objetivo
Definir el alcance, los objetivos de negocio y los criterios de éxito del
sistema multiagente conversacional de soporte TI sobre ServiceNow.

## Épica
**EPIC-001 · Sistema Multiagente Conversacional de Soporte TI sobre ServiceNow**

## Objetivos de negocio
1. Reducir el tiempo de resolución (MTTR) de incidentes y solicitudes.
2. Eliminar tareas manuales repetitivas mediante autoservicio.
3. Evitar transferencias frías en escalaciones a Nivel 2/3.
4. Mejorar la experiencia de soporte de extremo a extremo.

## Criterios de éxito (KPIs)
| KPI | Meta |
|-----|------|
| Tasa de Resolución en Primer Contacto (FCR) | ≥ 60% |
| Tasa de Deflexión de Tickets | ≥ 40% |
| MTTR | Reducción ≥ 30% vs. humano |
| Tasa de Escalación | ≤ 20% |
| RAG Hit Rate | ≥ 80% |

## Alcance
- 8 agentes especializados (Coordinador, Clasificador, Diagnóstico, Políticas,
  Ejecución, Conocimiento/RAG, Seguimiento, Escalación).
- Integración con ServiceNow, Active Directory, KB y canales de notificación.
- Modelo-agnóstico (OpenAI, Jan, Mock).
- Observabilidad y dashboard de 4 dimensiones.
- Generación de matrices de pruebas para QA/desarrollo (HU-004).
- Suite de tests (`pytest`) + CI (`.github/workflows/ci.yml`).

## Fuera de alcance (v1)
- Integración con sistemas de terceros adicionales.
- Entrenamiento de modelos propios.
- Despliegue en producción multi-tenant.

## Riesgos y mitigaciones
| Riesgo | Mitigación |
|--------|------------|
| Dependencia de un proveedor LLM | Capa de abstracción modelo-agnóstica (`Strategy`, core/llm.py) |
| Costos de tokens | Cálculo de costos y monitoreo por modelo; rate limiting por cliente |
| Alucinaciones del LLM | Guardrails, evaluación y RAG con fuentes |
| Fallos de proveedor | Reintentos con backoff y degradación elegante (`retry()`, `safe_call()` — verificado con tests de fallos transitorios simulados) |
| API abierta sin control de acceso | `API_KEY` (header `X-API-Key` / `Authorization: Bearer`) + rate limiting por cliente (`llmops/security.py`) |
| Regresiones al cambiar prompts/código sin detectarse | Suite de `pytest` (56+ casos) + CI en cada push/PR |
