# Auditoría LLMOps — Sistema Multiagente ServiceNow

> **Fecha:** 21 de septiembre de 2026
> **Alcance:** repositorio `ABRAHAMCIMAT/servicenow-multiagent` (51 archivos · 3,068 LOC Python)
> **Marco de referencia:** los 7 componentes LLMOps (Model Development, Deployment, Monitoring, Prompt Management, Security, Evaluation, Data Management) y el catálogo curado [pmady/llmops](https://github.com/pmady/llmops)
> **Objetivo:** determinar las mejoras necesarias para llevar la aplicación a producción, en un roadmap por fases.

---

## 1. Resumen ejecutivo

El sistema es un **prototipo funcional avanzado** con una base LLMOps ya iniciada: telemetría JSON estandarizada, dashboard de 4 dimensiones, logging estructurado, registro de prompts versionado, guardrails básicos, marco de evaluación y capa de errores. Eso lo coloca por delante de la mayoría de PoCs.

Sin embargo, **no está listo para producción**. Las brechas críticas son de **operación y seguridad**, no de arquitectura:

| # | Hallazgo crítico | Impacto |
|---|------------------|---------|
| 1 | **Sin autenticación** en ninguno de los 8 endpoints expuestos | Cualquiera puede invocar el multiagente y leer conversaciones |
| 2 | **CORS `allow_origins=["*"]`** | Exposición cross-origin total |
| 3 | **Sin pruebas automatizadas** (0 tests) ni **CI/CD** | Regresiones silenciosas; sin red de seguridad |
| 4 | **Sin Dockerfile ni empaquetado reproducible** | Despliegue manual y frágil |
| 5 | **Rutas absolutas hardcodeadas** (`/agent/task/servicenow-multiagent/...`) | Rompe en cualquier entorno que no sea el sandbox |
| 6 | **Datos de usuario (PII) en logs sin redacción** | Riesgo de cumplimiento (GDPR/ISO) |
| 7 | **RAG por coincidencia de palabras clave** (sin embeddings ni vector store) | Baja precisión y sin escalabilidad del conocimiento |
| 8 | **Estado en memoria + JSON** sin base de datos | Sin concurrencia, sin escalado horizontal, pérdida de datos |
| 9 | **`retry()` con backoff definido pero NO conectado** al flujo real | Los fallos transitorios del LLM rompen la conversación |
| 10 | **Sin alertas ni presupuesto de costo** | Los costos de tokens pueden dispararse sin aviso |

**Puntuación de madurez global estimada: ~36 / 100** (prototipo → producción requiere cerrar las brechas anteriores).

---

## 2. Metodología

Se auditó el código contra cada uno de los 7 componentes LLMOps, con evidencia extraída directamente del repositorio (grep + lectura de archivos). El repositorio de referencia `pmady/llmops` es un **catálogo curado de herramientas** (awesome-list) organizado en las mismas 7 categorías; se usó como fuente de las soluciones recomendadas por componente.

**Fortalezas ya presentes (base reutilizable):**
- `backend/observability/` — telemetría JSONL modelo-agnóstica, métricas de 4 dimensiones, integración Langfuse opcional.
- `backend/llmops/` — logging estructurado, errores tipados, prompts versionados, evals, guardrails, patrones.
- `backend/core/llm.py` — abstracción LLM modelo-agnóstica (Jan / OpenAI / mock).
- `dashboard/` + pestaña en `frontend/` + Agente de Métricas (dashboard vía chat).

---

## 3. Auditoría por componente

### 3.1 Model Development (desarrollo, fine-tuning, optimización)
**Estado actual:** ✅ Capa de abstracción modelo-agnóstica (`LLMConfig` con `jan` | `openai` | `mock`), proveedor mock determinista para CI/demos, extracción robusta de JSON.
**Brechas:**
- ❌ Sin **registro de modelos** ni control de versiones del modelo por agente.
- ❌ Sin **experiment tracking** (W&B, MLflow, Aim).
- ❌ Sin fine-tuning ni evaluación de modelos alternativos (no hay comparativa de calidad/costo).
- ❌ Sin caché semántica ni optimización de inferencia (vLLM, quantización).
- ❌ `temperature`/`max_tokens` globales, no por agente.

**Madurez: 30%**

### 3.2 Deployment (servicio eficiente a escala)
**Estado actual:** ⚠️ Servidor FastAPI funcional (`uvicorn`), endpoint OpenAI-compatible, montaje de estáticos.
**Brechas:**
- ❌ **Sin Dockerfile / docker-compose** → despliegue no reproducible.
- ❌ **Sin CI/CD** (`.github/workflows` vacío).
- ❌ **Rutas absolutas hardcodeadas** (`/agent/task/servicenow-multiagent/...`) en `server.py`, `telemetry.py`, `metrics.py`.
- ❌ **Estado en memoria** (`ConversationStore`) + JSON → no escala horizontalmente.
- ❌ Sin gestión de secretos (Vault, AWS/GCP Secret Manager); solo `os.getenv`.
- ❌ Sin *graceful shutdown*, sin *readiness/liveness* diferenciados, sin *reverse proxy* (nginx/Traefik).
- ❌ Sin versionado de configuración por entorno (dev/staging/prod).

**Madurez: 20%**

### 3.3 Monitoring (rendimiento, costos, calidad)
**Estado actual:** ✅ Telemetría JSONL estandarizada (traces, spans, LLM calls, conversaciones, RAG, aprobaciones, escalaciones), dashboard de 4 dimensiones (Negocio/ITSM, Rendimiento/IA, Costos, Orquestación), logging estructurado JSON, integración Langfuse opcional.
**Brechas:**
- ❌ **Sin alertas** (tasa de error, latencia E2E, costo diario, tasa de escalación).
- ❌ **Sin presupuesto de costo** ni *kill-switch* por gasto de tokens.
- ❌ `Telemetry._events` es una **lista en memoria sin límite** → fuga de memoria en procesos largos.
- ❌ Sin **OpenTelemetry** (traces distribuidos estándar) — el formato es propio.
- ❌ Sin **drift detection** de calidad en producción (Evidently, Phoenix).
- ❌ Dashboard en memoria: se pierde al reiniciar y no agrega histórico.

**Madurez: 65%** ← el componente más maduro

### 3.4 Prompt Management (versionado y optimización)
**Estado actual:** ✅ `PromptRegistry` con versionado semver, huella SHA-256, variables tipadas y exportación JSON.
**Brechas:**
- ❌ Solo **2 prompts registrados** (clasificador, conocimiento); el resto de agentes tiene prompts embebidos.
- ❌ Sin **A/B testing** ni *prompt playground*.
- ❌ Sin **revisión/aprobación** de cambios de prompt (CODEOWNERS, PR review).
- ❌ Sin *prompt injection* testing sistemático por prompt.
- ❌ Sin *prompt caching* ni compresión.

**Madurez: 50%**

### 3.5 Security (uso seguro y responsable)
**Estado actual:** ✅ Guardrails con patrón Chain of Responsibility (longitud máxima, anti-inyección de prompt, validación de intención/prioridad), secretos por variables de entorno (sin hardcode).
**Brechas (las más graves de la auditoría):**
- 🔴 **Cero autenticación** en los 8 endpoints (`/api/chat`, `/api/conversations`, `/api/escalate`, `/v1/chat/completions`, etc.).
- 🔴 **CORS `allow_origins=["*"]`** con `allow_methods=["*"]`.
- 🔴 **PII en logs**: se registra el mensaje del usuario (`user_message[:100]`, `req.message[:100]`) sin redacción.
- ❌ **Sin rate limiting** por usuario/IP.
- ❌ Sin **PII detection/redaction** (Presidio, LLM Guard).
- ❌ Sin **RBAC** ni aislamiento por tenant.
- ❌ Sin *audit trail* de acciones sensibles (desbloqueos AD, aprobaciones).
- ❌ Sin detección de *jailbreak* avanzada (Rebuff, NeMo Guardrails).
- ❌ API key con valor por defecto `"jan"` en el dataclass.

**Madurez: 30%**

### 3.6 Evaluation (pruebas y validación de salidas)
**Estado actual:** ✅ Marco `Evaluator` con checks deterministas (esquema JSON, intención válida) y soporte de *pass rate*; enganchado al **Clasificador**.
**Brechas:**
- ❌ **Sin LLM-as-judge implementado** (solo mencionado).
- ❌ **Sin suite de regresión** (golden dataset) ni ejecución en CI.
- ❌ Evaluador enganchado **solo en 1 de 8 agentes**.
- ❌ Sin **0 tests** (`pytest`) en el repositorio.
- ❌ Sin evaluación de **fidelidad RAG** (Ragas, DeepEval).
- ❌ Sin métricas de *hallucination* ni *groundedness*.

**Madurez: 35%**

### 3.7 Data Management (datos de entrenamiento y embeddings)
**Estado actual:** ⚠️ Persistencia de conversaciones en JSON; RAG con recuperación por palabras clave (explícitamente marcado `# Swap for real vector search`).
**Brechas:**
- ❌ **Sin vector store** (Chroma, Qdrant, pgvector, FAISS) ni embeddings.
- ❌ RAG por coincidencia de texto → baja precisión, sin *semantic search*.
- ❌ **Sin data versioning** (DVC, lakeFS).
- ❌ Sin **gobernanza de datos** ni retención/borrado (derecho al olvido).
- ❌ Sin **anonimización** de datos antes de almacenar.
- ❌ Sin *chunking* ni *reranking* de la base de conocimiento.

**Madurez: 20%**

---

## 4. Matriz de madurez

| Componente LLMOps | Madurez | Estado | Prioridad |
|-------------------|:-------:|--------|:---------:|
| Monitoring | 65% | Base sólida, falta alertas y OTel | Alta |
| Prompt Management | 50% | Registro listo, falta cobertura y A/B | Media |
| Evaluation | 35% | Marco listo, falta suite y CI | Alta |
| Model Development | 30% | Abstracción lista, falta registry | Media |
| Security | 30% | **Sin auth ni redacción PII** | 🔴 Crítica |
| Deployment | 20% | **Sin Docker ni CI/CD** | 🔴 Crítica |
| Data Management | 20% | **Sin vector store** | 🔴 Crítica |
| **Global** | **~36%** | Prototipo avanzado | — |

---

## 5. Roadmap por fases hacia producción

### 🔴 Fase 0 — Higiene y seguridad base (1–2 semanas · bloqueante)
> Sin esta fase, **no se puede exponer el sistema**. Es el mínimo de seguridad y reproducibilidad.

1. **Autenticación y autorización**
   - API keys / JWT en todos los endpoints (`Depends` de FastAPI), OAuth2 para usuarios.
   - RBAC básico (usuario / agente N1 / admin).
   - *(Ref: Auth0, Keycloak, FastAPI Security)*
2. **Endurecer CORS**: reemplazar `["*"]` por lista blanca de orígenes.
3. **Redacción de PII en logs** (Presidio o LLM Guard): nunca registrar el mensaje crudo.
4. **Rate limiting** por usuario/IP (slowapi, API Gateway).
5. **Eliminar rutas hardcodeadas**: todo por variables de entorno con *defaults* relativos.
6. **`.gitignore` + `.env.example`**; eliminar el default `"jan"` de la API key.
7. **Audit trail** de acciones sensibles (AD, aprobaciones, escalaciones).

**Entregable:** sistema seguro y configurable por entorno.

---

### 🟠 Fase 1 — Reproducibilidad y CI/CD (2–3 semanas)
1. **Dockerfile multi-stage + docker-compose** (app + vector DB + observabilidad).
2. **CI/CD en GitHub Actions**: lint (ruff), type-check (mypy), tests, build de imagen.
3. **Suite de pruebas** (`pytest`): unitarias de agentes, guardrails, prompts, telemetría; integración del flujo end-to-end con el proveedor mock.
4. **Golden dataset de regresión** ejecutado en CI (bloquea PRs si baja el *pass rate*).
5. **Gestión de secretos** (Vault / Secret Manager), rotación de claves.
6. **Config por entorno** (dev / staging / prod) con validación al arranque.

**Entregable:** pipeline verde, despliegue reproducible de un comando.

---

### 🟡 Fase 2 — Datos, RAG y evaluación real (3–4 semanas)
1. **Vector store** (Qdrant / pgvector / Chroma) + embeddings; migrar el RAG de palabras clave a **búsqueda semántica**.
2. **Chunking + reranking** de la base de conocimiento; medir **RAG hit rate / faithfulness** (Ragas).
3. **LLM-as-judge** implementado y enganchado a los 8 agentes.
4. **Persistencia en base de datos** (PostgreSQL/Redis) reemplazando el JSON en memoria.
5. **Data versioning** (DVC) del golden dataset y la base de conocimiento.
6. **Gobernanza de datos**: retención, anonimización y borrado (derecho al olvido).

**Entregable:** conocimiento escalable y calidad medible con regresión.

---

### 🟢 Fase 3 — Observabilidad de producción y costos (2–3 semanas)
1. **OpenTelemetry** nativo (traces distribuidos) además del JSONL propio.
2. **Alertas**: tasa de error, latencia E2E, costo diario, escalación, abandono (Grafana / PagerDuty).
3. **Presupuesto de costo y kill-switch** por umbral de tokens.
4. **Acotar `Telemetry._events`** (ring buffer) y persistir histórico (ClickHouse/BigQuery).
5. **Drift detection** de calidad (Evidently / Phoenix).
6. **Dashboard histórico** (no solo en memoria) + export a Langfuse/LangSmith.

**Entregable:** operación observable con alertas y control de gasto.

---

### 🔵 Fase 4 — Madurez LLMOps y escalado (3–4 semanas)
1. **Model registry** + *experiment tracking* (MLflow / W&B); comparativa calidad/costo por modelo.
2. **A/B testing de prompts** con métricas de calidad por versión.
3. **Caché semántica** y optimización de inferencia (vLLM, quantización) para costo/latencia.
4. **Escalado horizontal**: stateless + cola (Redis/Celery), *load balancing*, *autoscaling*.
5. **Fine-tuning / adaptación** con datos de producción anonimizados (opcional según ROI).
6. **Guardrails avanzados** (NeMo Guardrails / Rebuff) + *red teaming* periódico.

**Entregable:** sistema escalable, optimizado y en mejora continua.

---

### ⚪ Fase 5 — Producción sostenida (continuo)
1. **SLOs/SLAs** y *error budget*; *chaos testing*.
2. **Runbooks** y respuesta a incidentes; *on-call*.
3. **Cumplimiento**: ISO 27001 / SOC2 / GDPR según el sector.
4. **Gobierno de IA**: comité, políticas de uso responsable, revisión de sesgos.
5. **Feedback loop** usuario → evaluación → prompts → modelo.

**Entregable:** operación de producción gobernada y sostenible.

---

## 6. Quick wins (esta semana, alto impacto / bajo esfuerzo)

| # | Acción | Esfuerzo | Impacto |
|---|--------|:--------:|:-------:|
| 1 | Añadir API key a los endpoints | Bajo | 🔴 Crítico |
| 2 | Restringir CORS a orígenes conocidos | Bajo | 🔴 Crítico |
| 3 | Redactar PII en los logs (quitar el mensaje crudo) | Bajo | 🔴 Crítico |
| 4 | Añadir `Dockerfile` + `docker-compose` | Bajo | Alto |
| 5 | Sustituir rutas absolutas por env vars | Bajo | Alto |
| 6 | Conectar `retry()` al `LLMOps.call` del LLM | Bajo | Alto |
| 7 | Acotar `Telemetry._events` (ring buffer) | Bajo | Medio |
| 8 | Añadir `.gitignore` + `.env.example` | Bajo | Medio |
| 9 | Primeros tests (`pytest`) + workflow de CI | Medio | Alto |
| 10 | Registrar los prompts de los 6 agentes restantes | Medio | Medio |

---

## 7. Riesgos si se despliega sin estas mejoras

| Riesgo | Probabilidad | Impacto | Mitigación (fase) |
|--------|:------------:|:-------:|-------------------|
| Acceso no autorizado a datos/conversaciones | Alta | Crítico | Fase 0 |
| Fuga de PII en logs | Alta | Crítico (legal) | Fase 0 |
| Caída por fallo transitorio del LLM | Media | Alto | Fase 0/3 |
| Costos de tokens descontrolados | Media | Alto | Fase 3 |
| Pérdida de datos (JSON en memoria) | Media | Alto | Fase 2 |
| Respuestas RAG imprecisas | Alta | Medio | Fase 2 |
| Regresiones sin detección | Alta | Medio | Fase 1 |
| Imposibilidad de escalar | Media | Alto | Fase 4 |

---

## 8. Conclusión

El sistema tiene una **arquitectura LLMOps correcta y bien pensada** para un prototipo: modelo-agnóstico, telemetría estandarizada, prompts versionados, guardrails, evaluación y patrones de diseño. El trabajo pendiente **no es rehacer la arquitectura**, sino **endurecerla para producción**:

1. **Seguridad primero** (Fase 0) — es el bloqueante absoluto.
2. **Reproducibilidad** (Fase 1) — Docker + CI/CD + tests.
3. **Datos y calidad** (Fase 2) — vector store + evaluación real.
4. **Observabilidad de producción** (Fase 3) — alertas + costos.
5. **Escalado y madurez** (Fases 4–5).

Cubriendo las Fases 0–3 (≈ **8–12 semanas** con un equipo pequeño) el sistema pasa de **~36% a ~80% de madurez** y queda apto para producción controlada. Las Fases 4–5 son de mejora continua.

---

## Anexo A — Herramientas recomendadas (del catálogo pmady/llmops)

| Componente | Herramientas sugeridas |
|------------|------------------------|
| Deployment / Serving | Docker, vLLM, BentoML, Ray Serve, Triton |
| Observabilidad | **Langfuse** (ya integrado), Phoenix, Helicone, OpenLIT, OpenTelemetry |
| Evaluación | **Ragas**, DeepEval, PromptFoo, Evidently |
| Seguridad | NeMo Guardrails, Guardrails AI, LLM Guard, Rebuff, Presidio |
| Vector / RAG | Qdrant, pgvector, Chroma, FAISS, LanceDB |
| Prompt Mgmt | LangSmith, PromptLayer, Agenta, Humanloop |
| Experiment tracking | MLflow, W&B, Aim |
| Data versioning | DVC, lakeFS, Delta Lake |
| Orquestación | LangGraph, CrewAI, AutoGen, Prefect |
| Agentes (monitoreo) | AgentOps, Langfuse, LangSmith |

## Anexo B — Evidencia de la auditoría

- 51 archivos · 3,068 LOC Python · 0 tests · sin `.github/workflows` · sin Dockerfile · sin `.gitignore` · sin `.env.example`.
- 8 endpoints sin autenticación (`server.py`).
- `allow_origins=["*"]` (`server.py:51`).
- PII en logs: `server.py:107`, `coordinator.py:39`.
- Rutas absolutas: `server.py:45,62`, `telemetry.py:35`, `metrics.py:24`.
- `retry()` definido en `errors.py:57` y **no invocado** en el flujo; solo `safe_call` en 2 sitios.
- `Evaluator` enganchado solo en `classifier.py:84`.
- RAG sin embeddings: `servicenow.py:165`.
- `Telemetry._events` lista sin límite (`telemetry.py:38,47`).
