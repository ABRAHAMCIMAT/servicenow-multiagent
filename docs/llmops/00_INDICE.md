# 📚 Documentación LLMOps — Sistema Multiagente Conversacional

Control de documentación por fase del ciclo de vida LLMOps para el desarrollo
de sistemas multiagentes conversacionales.

> Para la arquitectura del sistema en formato C4 (Contexto → Contenedores →
> Componentes → Código, con diagramas), ver
> **[docs/c4/00_INDICE.md](../c4/00_INDICE.md)**. Para seguridad (auth RBAC,
> rate limiting, redacción de PII, audit trail), ver
> [docs/SEGURIDAD.md](../SEGURIDAD.md).

## Índice de fases

| Fase | Documento | Descripción |
|------|-----------|-------------|
| 0 | [00_INDICE.md](00_INDICE.md) | Índice general de la documentación |
| 1 | [01_PLANIFICACION.md](01_PLANIFICACION.md) | Planificación, objetivos y alcance |
| 2 | [02_DATOS_Y_PROMPTS.md](02_DATOS_Y_PROMPTS.md) | Gestión de datos, prompts y versionado |
| 3 | [03_DESARROLLO.md](03_DESARROLLO.md) | Desarrollo, arquitectura y patrones |
| 4 | [04_EVALUACION.md](04_EVALUACION.md) | Evaluación de agentes y calidad |
| 5 | [05_OBSERVABILIDAD.md](05_OBSERVABILIDAD.md) | Observabilidad, logging y monitoreo |
| 6 | [06_DESPLIEGUE.md](06_DESPLIEGUE.md) | Despliegue, operación y mantenimiento |
| 7 | [07_GUARDRAILS.md](07_GUARDRAILS.md) | Guardrails, seguridad y control de errores |

## Mejores prácticas LLMOps aplicadas

1. **Gestión de prompts versionados** — registro central con versionado y huella.
2. **Evaluación continua** — checks deterministas y LLM-as-judge.
3. **Observabilidad nativa** — telemetría JSON estandarizada (buffer acotado) + Langfuse.
4. **Guardrails** — validación de entrada/salida, anti inyección de prompt.
5. **Logging estructurado** — JSON con contexto por conversación/traza, sin PII cruda.
6. **Control de errores** — excepciones tipadas, reintentos con backoff.
7. **Patrones de diseño** — Registry, Strategy.
8. **Modelo-agnóstico** — funciona con OpenAI, Jan o Mock sin cambios.
9. **Seguridad de la API (Fase 0)** — auth RBAC, rate limiting, redacción de PII, audit trail.
10. **Tests y CI** — suite de pytest (unit/integration/e2e) + lint/tipos/seguridad/Docker en cada push/PR.
11. **Generación de matrices de pruebas** — casos positivos/negativos/de borde vía LLM (HU-004).
