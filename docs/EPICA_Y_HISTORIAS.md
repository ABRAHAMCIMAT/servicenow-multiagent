# Épica e Historias de Usuario — ServiceNow Multi-Agent Conversational System

> **Versión 2.0** — Incluye observabilidad, dashboard de 4 dimensiones, LLMOps y control total del sistema.

## 🎯 ÉPICA

**EPIC-001 · Sistema Multiagente Conversacional de Soporte TI sobre ServiceNow**

> **Como** usuario final de TI (empleado) y **como** agente de soporte (Nivel 1/2/3),
> **quiero** resolver incidentes, solicitudes de servicio y consultas de conocimiento mediante una conversación en lenguaje natural que orquesta agentes especializados (triaje, diagnóstico, políticas, ejecución, RAG, seguimiento, escalación y métricas),
> **para** reducir el tiempo de resolución, eliminar tareas manuales repetitivas, evitar transferencias frías, mejorar la experiencia de soporte de extremo a extremo y tener **control total** del sistema mediante observabilidad y métricas en 4 dimensiones.

**Criterios de aceptación de la épica (DoD):**
- El sistema resuelve de extremo a extremo al menos 4 intenciones: incidente, solicitud de servicio, consulta de conocimiento y estado de ticket.
- Las tareas de autoservicio (desbloqueo AD, restablecimiento de contraseña, asignación de licencias) se ejecutan sin intervención humana cuando la política lo permite.
- Las aprobaciones se orquestan notificando al manager por Slack/Teams/WhatsApp y quedan en estado `awaiting_approval`.
- Las escalaciones a Nivel 2/3 entregan un resumen ejecutivo del diagnóstico.
- El sistema es modelo-agnóstico (Jan / OpenAI / mock) y corre en modo demo sin credenciales.
- El sistema emite **telemetría JSON estandarizada** (modelo-agnóstica) para observabilidad.
- El **dashboard de 4 dimensiones** (Negocio, Rendimiento, Costos, Orquestación) es accesible desde el frontend y a través del multiagente.
- Se aplican **mejores prácticas LLMOps**: logging estructurado, control de errores, guardrails, evaluación y patrones de diseño.
- El **Agente de Métricas** responde consultas de KPIs y estado del sistema en lenguaje natural.

---

## 📋 HISTORIAS DE USUARIO (método INVEST)

> Cada historia cumple **INVEST**: **I**ndependiente, **N**egociable, **V**aliosa, **E**stimable, **S**mall (pequeña), **T**estable.

---

### HU-001 · Conversación en lenguaje natural con el Coordinador
**Como** usuario final, **quiero** escribir mi problema en lenguaje natural y recibir una respuesta conversacional, **para** no depender de formularios ni conocer la terminología de ServiceNow.

- **I**ndependiente: sí, no depende de otras historias.
- **N**egociable: el alcance del orquestador puede ajustarse.
- **V**aliosa: elimina la fricción de entrada.
- **E**stimable: 3–5 pts.
- **S**mall: un único punto de entrada.
- **T**estable: enviar un mensaje libre y verificar respuesta del Coordinador.

**Criterios de aceptación:**
- El Coordinador recibe el mensaje y crea una conversación con estado.
- Responde en lenguaje natural sin exponer detalles técnicos internos.
- Mantiene el contexto a lo largo de la conversación.
- Emite telemetría de la conversación (trace) para observabilidad.

---

### HU-002 · Triaje automático de intención, categoría y prioridad SLA
**Como** usuario, **quiero** que el sistema clasifique automáticamente mi solicitud (intención, categoría, subcategoría, Assignment Group y prioridad SLA), **para** que el ticket se enrute correctamente sin intervención humana.

- **I**ndependiente: sí.
- **N**egociable: la matriz de categorías es configurable.
- **V**aliosa: elimina la categorización errónea y los incidentes críticos sepultados.
- **E**stimable: 5 pts.
- **S**mall: un agente, una responsabilidad.
- **T**estable: enviar textos de prueba y validar la salida JSON.

**Criterios de aceptación:**
- Identifica la intención (incident, service_request, knowledge, approval, status, escalation, general).
- Asigna categoría, subcategoría y Assignment Group.
- Calcula la prioridad SLA a partir de impacto, urgencia, sentimiento y palabras clave.
- Devuelve JSON estructurado con heurísticas de respaldo.
- Aplica **guardrails** de entrada (longitud, anti inyección de prompt).
- Evalúa la salida (esquema JSON, intención válida) y registra el resultado.

---

### HU-003 · Creación de ticket en ServiceNow
**Como** usuario, **quiero** que al detectarse un incidente o solicitud se cree automáticamente el ticket en ServiceNow, **para** tener un registro formal y trazable.

- **I**ndependiente: depende de HU-002 (clasificación).
- **N**egociable: campos del ticket configurables.
- **V**aliosa: trazabilidad y registro formal.
- **E**stimable: 3 pts.
- **S**mall: una acción de integración.
- **T**estable: verificar ticket creado en ServiceNow (o demo).

**Criterios de aceptación:**
- Se crea el ticket con categoría, prioridad y Assignment Group del clasificador.
- Funciona en modo LIVE (REST) y DEMO.
- Devuelve el número de ticket al usuario.

---

### HU-004 · Diagnóstico de causa raíz
**Como** usuario, **quiero** que el sistema revise el estado real de mi cuenta/sistema y determine la causa raíz, **para** resolver el problema de fondo y no solo el síntoma.

- **I**ndependiente: sí.
- **N**egociable: fuentes de diagnóstico ampliables.
- **V**aliosa: resolución correcta a la primera.
- **E**stimable: 5 pts.
- **S**mall: un agente de diagnóstico.
- **T**estable: simular cuenta bloqueada y verificar causa raíz.

**Criterios de aceptación:**
- Consulta el estado real (AD, CRM, etc.).
- Determina la causa raíz (p. ej. cuenta bloqueada por intentos fallidos).
- Recomienda la acción a ejecutar.

---

### HU-005 · Aplicación de políticas y decisión de aprobación
**Como** usuario, **quiero** que el sistema aplique la matriz de políticas de la organización y decida si mi acción es autoservicio o requiere aprobación, **para** cumplir las reglas de negocio sin fricción.

- **I**ndependiente: sí.
- **N**egociable: la matriz de políticas es configurable.
- **V**aliosa: control de cumplimiento y seguridad.
- **E**stimable: 3 pts.
- **S**mall: un agente de políticas.
- **T**estable: verificar decisión autoservicio vs aprobación.

**Criterios de aceptación:**
- Determina si la acción es autoservicio o requiere aprobación.
- Identifica quién debe aprobar (manager).
- Devuelve la decisión de forma estructurada.

---

### HU-006 · Autoservicio: desbloqueo de cuenta AD
**Como** usuario, **quiero** desbloquear mi cuenta de Active Directory desde el chat, **para** recuperar el acceso sin abrir un ticket ni esperar a un agente.

- **I**ndependiente: sí.
- **N**egociable: alcance de cuentas permitidas.
- **V**aliosa: resolución inmediata de un problema común.
- **E**stimable: 3 pts.
- **S**mall: una tarea de ejecución.
- **T**estable: ejecutar desbloqueo y verificar estado.

**Criterios de aceptación:**
- Ejecuta el desbloqueo vía ServiceNow/AD (LIVE o DEMO).
- Confirma el resultado al usuario.
- Respeta la política de aprobación si aplica.

---

### HU-007 · Autoservicio: restablecimiento de contraseña
**Como** usuario, **quiero** restablecer mi contraseña desde el chat, **para** recuperar el acceso de forma autónoma y segura.

- **I**ndependiente: sí.
- **N**egociable: método de verificación.
- **V**aliosa: reduce tickets de contraseña.
- **E**stimable: 3 pts.
- **S**mall: una tarea de ejecución.
- **T**estable: ejecutar restablecimiento y verificar.

**Criterios de aceptación:**
- Ejecuta el restablecimiento de forma segura.
- Confirma el resultado al usuario.
- Respeta la política de aprobación si aplica.

---

### HU-008 · Autoservicio: asignación de licencias
**Como** usuario, **quiero** solicitar la asignación de una licencia desde el chat, **para** obtener el acceso a la herramienta sin pasar por un agente.

- **I**ndependiente: sí.
- **N**egociable: catálogo de licencias.
- **V**aliosa: automatiza una tarea repetitiva.
- **E**stimable: 3 pts.
- **S**mall: una tarea de ejecución.
- **T**estable: solicitar licencia y verificar asignación.

**Criterios de aceptación:**
- Ejecuta la asignación vía catálogo/ServiceNow.
- Confirma el resultado al usuario.
- Respeta la política de aprobación si aplica.

---

### HU-009 · Respuesta de conocimiento con RAG paso a paso
**Como** usuario, **quiero** hacer una pregunta sobre la base de conocimientos y recibir la respuesta exacta explicada paso a paso, **para** resolver mi duda sin enlaces ni búsquedas manuales.

- **I**ndependiente: sí.
- **N**egociable: fuentes de la KB.
- **V**aliosa: respuestas directas en vez de enlaces.
- **E**stimable: 5 pts.
- **S**mall: un agente de conocimiento.
- **T**estable: consultar la KB y verificar la respuesta.

**Criterios de aceptación:**
- Busca en la KB de ServiceNow (RAG).
- Extrae la respuesta exacta.
- Explica el procedimiento paso a paso en el chat.
- Registra el **hit rate de RAG** en telemetría.

---

### HU-010 · Orquestación de aprobaciones con notificación al manager
**Como** usuario, **quiero** que cuando mi solicitud requiera aprobación, el sistema notifique a mi manager por Slack/Teams/WhatsApp y quede en espera, **para** que la aprobación fluya en tiempo real sin cuellos de botella.

- **I**ndependiente: sí.
- **N**egociable: canales y plantillas.
- **V**aliosa: elimina cuellos de botella en aprobaciones.
- **E**stimable: 5 pts.
- **S**mall: un flujo de aprobación.
- **T**estable: simular aprobación y verificar estado.

**Criterios de aceptación:**
- Busca al manager en la org de ServiceNow.
- Envía notificación push (Slack/Teams/WhatsApp).
- El ticket queda en estado `awaiting_approval`.
- Al aprobar/rechazar, el flujo continúa.
- Registra el evento de aprobación en telemetría.

---

### HU-011 · Seguimiento proactivo del ticket
**Como** usuario, **quiero** recibir notificaciones proactivas de cambios de estado y notas de mi ticket, **para** no tener que preguntar "¿cómo va mi ticket?".

- **I**ndependiente: sí.
- **N**egociable: eventos y canales de notificación.
- **V**aliosa: reduce llamadas de seguimiento.
- **E**stimable: 3 pts.
- **S**mall: un agente de seguimiento.
- **T**estable: cambiar estado y verificar notificación.

**Criterios de aceptación:**
- Notifica cambios de estado, notas y solicitudes de información.
- Usa el canal configurado (Slack/Teams/WhatsApp).
- Reduce la necesidad de consultas manuales.

---

### HU-012 · Escalación a agente humano con resumen ejecutivo
**Como** agente de soporte Nivel 2/3, **quiero** recibir el caso escalado con un resumen ejecutivo del diagnóstico, **para** retomar el problema con contexto y evitar transferencias frías.

- **I**ndependiente: sí.
- **N**egociable: formato del resumen.
- **V**aliosa: transferencias cálidas y resolución más rápida.
- **E**stimable: 3 pts.
- **S**mall: un agente de escalación.
- **T**estable: escalar un caso y verificar el resumen.

**Criterios de aceptación:**
- Transfiere el caso al Workspace de ServiceNow.
- Entrega un resumen ejecutivo del diagnóstico.
- El agente humano recibe el contexto completo.
- Registra el evento de escalación en telemetría.
- **Se dispara automáticamente** desde `CoordinatorAgent` (sin paso manual)
  cuando el diagnóstico no tiene una acción automatizable o la ejecución
  falla — antes de la corrección de la auditoría LLMOps, `EscalationAgent`
  solo era alcanzable vía `POST /api/escalate`, nunca desde el flujo
  automático (ver `tests/integration/test_escalation.py`).

---

### HU-013 · Integración con Jan (endpoint OpenAI-compatible)
**Como** usuario, **quiero** conectar el sistema a Jan como proveedor personalizado, **para** conversar con el multiagente desde la interfaz de Jan.

- **I**ndependiente: sí.
- **N**egociable: modelo y proveedor.
- **V**aliosa: usa la interfaz local de Jan.
- **E**stimable: 3 pts.
- **S**mall: un endpoint de integración.
- **T**estable: conectar Jan y conversar.

**Criterios de aceptación:**
- El backend expone `/v1/chat/completions` compatible con OpenAI.
- Jan se conecta con Base URL `http://localhost:8000/v1`.
- El modelo `servicenow-multiagent` responde en el chat de Jan.

---

### HU-014 · Modo demo sin credenciales
**Como** desarrollador, **quiero** ejecutar el sistema en modo demo determinista sin credenciales, **para** validar el flujo completo de extremo a extremo.

- **I**ndependiente: sí.
- **N**egociable: datos de demo.
- **V**aliosa: validación rápida y sin setup.
- **E**stimable: 2 pts.
- **S**mall: un modo de ejecución.
- **T**estable: ejecutar demo y verificar flujo.

**Criterios de aceptación:**
- Corre sin credenciales de ServiceNow/AD/notificaciones.
- Reproduce el flujo completo de forma determinista.
- Permite probar todas las intenciones.
- Genera telemetría de demo para poblar el dashboard.

---

### HU-015 · Modelo-agnóstico (Jan / OpenAI / mock)
**Como** desarrollador, **quiero** cambiar el proveedor de LLM (Jan, OpenAI o mock) mediante configuración, **para** no acoplarme a un único modelo.

- **I**ndependiente: sí.
- **N**egociable: lista de proveedores.
- **V**aliosa: flexibilidad y portabilidad.
- **E**stimable: 3 pts.
- **S**mall: una capa de abstracción.
- **T**estable: cambiar `LLM_PROVIDER` y verificar.

**Criterios de aceptación:**
- El LLM se abstrae detrás de una interfaz única.
- Se configura vía `LLM_PROVIDER` (`jan` | `openai` | `mock`).
- El sistema funciona con cualquiera de los tres.
- La telemetría es **idéntica** sin importar el proveedor (modelo-agnóstica).

---

### HU-016 · Telemetría JSON estandarizada (modelo-agnóstica)
**Como** desarrollador/operador, **quiero** que el sistema emita eventos JSON estandarizados (traces, spans, LLM calls, conversaciones, RAG, aprobaciones, escalaciones), **para** tener observabilidad consistente sin importar el proveedor LLM.

- **I**ndependiente: sí.
- **N**egociable: esquema de eventos.
- **V**aliosa: observabilidad consistente y portable.
- **E**stimable: 5 pts.
- **S**mall: una capa de telemetría.
- **T**estable: verificar eventos JSON en el log.

**Criterios de aceptación:**
- Emite eventos JSONL estandarizados para cada tipo de actividad.
- Funciona igual con OpenAI, Jan o Mock.
- Incluye latencia, tokens, costo y estado en cada llamada LLM.
- Permite alimentar herramientas de observabilidad (ELK, Datadog, Langfuse).

---

### HU-017 · Dashboard de 4 dimensiones
**Como** operador/gestor, **quiero** ver un dashboard con métricas en 4 dimensiones (Negocio/Operación, Rendimiento/IA, Costos, Orquestación), **para** tener control total del sistema.

- **I**ndependiente: sí.
- **N**egociable: métricas y layout.
- **V**aliosa: control total y toma de decisiones.
- **E**stimable: 8 pts.
- **S**mall: un dashboard.
- **T**estable: verificar que las métricas se calculan correctamente.

**Criterios de aceptación:**
- **Negocio/Operación**: FCR, deflexión, distribución de intenciones, MTTR.
- **Rendimiento/IA**: E2E latency, tiempo por agente, TTFT, RAG hit rate.
- **Costos**: costo por conversación, tokens input/output, costo total USD.
- **Orquestación**: tasa de escalación, awaiting_approval, abandono.
- Accesible desde el frontend (pestaña Dashboard) y en `/dashboard`.

---

### HU-018 · Dashboard integrado al frontend
**Como** usuario, **quiero** ver el dashboard de métricas dentro del mismo frontend del asistente, **para** consultar el estado del sistema sin cambiar de aplicación.

- **I**ndependiente: sí.
- **N**egociable: layout de pestañas.
- **V**aliosa: acceso unificado a chat y métricas.
- **E**stimable: 3 pts.
- **S**mall: una pestaña en el frontend.
- **T**estable: alternar entre Chat y Dashboard.

**Criterios de aceptación:**
- El frontend tiene pestañas **Chat** y **Dashboard**.
- El dashboard se carga con datos reales del backend.
- Se actualiza con un botón de refresco.

---

### HU-019 · Agente de Métricas (dashboard vía multiagente)
**Como** usuario, **quiero** preguntarle al asistente por métricas, KPIs y estado del sistema en lenguaje natural, **para** obtener el dashboard a través del multiagente.

- **I**ndependiente: sí.
- **N**egociable: alcance de las consultas.
- **V**aliosa: acceso conversacional a las métricas.
- **E**stimable: 3 pts.
- **S**mall: un agente de métricas.
- **T**estable: preguntar por métricas y verificar respuesta.

**Criterios de aceptación:**
- El Coordinador detecta consultas de métricas (dashboard, KPI, FCR, MTTR, costos, etc.).
- El Agente de Métricas devuelve un resumen en lenguaje natural.
- Incluye las 4 dimensiones en la respuesta.
- Indica cómo ver el dashboard completo.

---

### HU-020 · Logging estructurado (JSON)
**Como** desarrollador/operador, **quiero** que el sistema registre logs estructurados en JSON con contexto por conversación/traza, **para** diagnosticar problemas y correlacionar eventos.

- **I**ndependiente: sí.
- **N**egociable: formato y niveles.
- **V**aliosa: diagnóstico y trazabilidad.
- **E**stimable: 3 pts.
- **S**mall: una capa de logging.
- **T**estable: verificar logs JSON con contexto.

**Criterios de aceptación:**
- Emite logs JSON de una línea por evento.
- Incluye niveles de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- Añade contexto (conversation_id, trace_id, agent, intent).
- Rotación de archivos (5 MB × 5 backups).

---

### HU-021 · Control de errores y reintentos
**Como** desarrollador, **quiero** que el sistema maneje errores con excepciones tipadas, reintentos con backoff y degradación elegante, **para** mejorar la robustez y el mantenimiento.

- **I**ndependiente: sí.
- **N**egociable: políticas de reintento.
- **V**aliosa: robustez y resiliencia.
- **E**stimable: 3 pts.
- **S**mall: una capa de errores.
- **T**estable: simular fallos y verificar manejo.

**Criterios de aceptación:**
- Excepciones jerárquicas (LLMOpsError y subtipos).
- Reintentos con backoff exponencial + jitter para errores transitorios.
- Degradación elegante con `safe_call` para pasos no críticos.
- Fail-fast para errores de configuración.

---

### HU-022 · Guardrails de entrada y salida
**Como** operador, **quiero** que el sistema valide entradas y salidas (longitud, anti inyección de prompt, intención/prioridad válidas), **para** proteger el sistema contra abusos y errores.

- **I**ndependiente: sí.
- **N**egociable: reglas de validación.
- **V**aliosa: seguridad y calidad.
- **E**stimable: 3 pts.
- **S**mall: una capa de guardrails.
- **T**estable: enviar entradas maliciosas y verificar rechazo.

**Criterios de aceptación:**
- Rechaza mensajes que exceden la longitud máxima.
- Detecta intentos de inyección de prompt.
- Valida intención y prioridad en las salidas.
- Aplica el patrón Chain of Responsibility.

---

### HU-023 · Gestión y versionado de prompts
**Como** desarrollador, **quiero** centralizar y versionar los prompts del sistema, **para** mantenerlos, experimentar (A/B) y hacer rollback.

- **I**ndependiente: sí.
- **N**egociable: esquema de versionado.
- **V**aliosa: mantenibilidad y experimentación.
- **E**stimable: 3 pts.
- **S**mall: un registro de prompts.
- **T**estable: registrar, renderizar y versionar prompts.

**Criterios de aceptación:**
- Registro central de prompts (PromptRegistry).
- Versionado semver con huella SHA-256.
- Renderizado parametrizado con variables.
- Exportación del registro.

---

### HU-024 · Evaluación de salidas de agentes
**Como** desarrollador, **quiero** evaluar la calidad de las salidas de los agentes (checks deterministas, LLM-as-judge), **para** detectar regresiones al cambiar prompts o modelos.

- **I**ndependiente: sí.
- **N**egociable: estrategias de evaluación.
- **V**aliosa: calidad y detección de regresiones.
- **E**stimable: 3 pts.
- **S**mall: un marco de evaluación.
- **T**estable: ejecutar evaluaciones y verificar resultados.

**Criterios de aceptación:**
- Checks deterministas (esquema JSON, intención válida, prioridad válida).
- Extensible a LLM-as-judge.
- Reporte de tasa de aprobación.
- Registro de resultados en telemetría.

---

### HU-025 · Integración con Langfuse (observabilidad LLM nativa)
**Como** operador, **quiero** integrar Langfuse (opcional, una línea de código) para registrar latencias por sub-agente, árboles de ejecución y costos automáticos, **para** tener observabilidad LLM nativa.

- **I**ndependiente: sí.
- **N**egociable: plataforma de observabilidad.
- **V**aliosa: observabilidad LLM nativa.
- **E**stimable: 3 pts.
- **S**mall: una integración opcional.
- **T**estable: configurar Langfuse y verificar envío.

**Criterios de aceptación:**
- Se integra con una línea de código.
- Registra latencias por sub-agente.
- Muestra árboles de ejecución detallados.
- Calcula costos automáticamente sin importar el modelo.
- Funciona sin Langfuse (degradación elegante).

---

### HU-026 · Patrones de diseño para mantenibilidad
**Como** desarrollador, **quiero** que el sistema aplique patrones de diseño realmente usados en tiempo de ejecución (no declarados y sin conectar), **para** mejorar el mantenimiento y la extensibilidad sin código muerto.

- **I**ndependiente: sí.
- **N**egociable: patrones aplicados.
- **V**aliosa: mantenibilidad y extensibilidad.
- **E**stimable: 3 pts.
- **S**mall: una capa de patrones.
- **T**estable: verificar uso de patrones en el código.

**Criterios de aceptación:**
- Registry: `PromptRegistry` y `Evaluator` delegan su almacenamiento en `patterns.Registry`.
- Strategy: `LLM` selecciona la implementación del proveedor (mock/OpenAI-compatible) vía `patterns.Strategy`.
- Facade para interfaz unificada.
- `Guardrails` implementa su propia cadena de validaciones (Chain of Responsibility) sin depender de una clase genérica de `patterns.py` — su contrato (mensaje de error u `None`, corte en el primer fallo) no encaja con un `Pipeline` que transforma datos paso a paso.

> **Nota:** esta historia se corrigió tras la auditoría LLMOps —
> `patterns.py` incluía además `Pipeline` y `EventBus`, pero ningún módulo
> los importaba en todo el repositorio (código muerto disfrazado de patrón
> aplicado). Se retiraron en vez de forzar su uso artificialmente.

---

### HU-027 · Documentación por fase (LLMOps) en español
**Como** desarrollador/operador, **quiero** tener documentación de cada fase del ciclo de vida LLMOps en español, **para** mantener y operar el sistema con buenas prácticas.

- **I**ndependiente: sí.
- **N**egociable: estructura de la documentación.
- **V**aliosa: mantenibilidad y transferencia de conocimiento.
- **E**stimable: 3 pts.
- **S**mall: documentación por fase.
- **T**estable: verificar que cada fase está documentada.

**Criterios de aceptación:**
- Documentación de 7 fases (Planificación, Datos/Prompts, Desarrollo, Evaluación, Observabilidad, Despliegue, Guardrails).
- Todo en español.
- Índice general con enlaces.
- Referenciada desde el README.

---

### HU-028 · Generación de matrices de pruebas
**Como** desarrollador/QA del sistema, **quiero** generar automáticamente una matriz de casos de prueba (positivos, negativos y de borde/límite) para cualquier agente o endpoint del sistema, **para** ampliar la cobertura de pruebas sin escribirlas todas a mano.

- **I**ndependiente: sí — usa la capa LLM y el registro de objetivos, no depende de otras historias.
- **N**egociable: el catálogo de objetivos (agentes/endpoints) es ampliable.
- **V**aliosa: acelera la escritura de pruebas de regresión (ver `scripts/run_evals.py`, Fase 4 de Evaluación).
- **E**stimable: 5 pts.
- **S**mall: un módulo generador (`backend/llmops/test_matrix.py`) + un script CLI + un endpoint.
- **T**estable: generar un lote para un objetivo y verificar que contiene los 3 tipos de caso.

**Criterios de aceptación:**
- Genera casos positivos, negativos y de borde/límite para un objetivo dado (agente o endpoint del sistema).
- Límite duro de **30 casos por lote** — si el LLM devuelve más, se truncan (nunca se amplía el lote).
- Disponible como script CLI (`scripts/generate_test_matrix.py`) y como endpoint (`POST /api/test-matrix`, rol `agent`), compartiendo la misma lógica de generación.
- Protegido por la misma auth RBAC del resto de la API (Fase 0) y auditado (`security/audit.py`).
- Funciona en modo demo (`LLM_PROVIDER=mock`) sin credenciales, igual que el resto del sistema.

---

## 📊 Resumen

| ID | Historia | Prioridad | Estimación |
|----|----------|-----------|------------|
| HU-001 | Conversación con el Coordinador | Alta | 3–5 |
| HU-002 | Triaje automático (intención/categoría/SLA) | Alta | 5 |
| HU-003 | Creación de ticket en ServiceNow | Alta | 3 |
| HU-004 | Diagnóstico de causa raíz | Alta | 5 |
| HU-005 | Aplicación de políticas | Alta | 3 |
| HU-006 | Autoservicio: desbloqueo AD | Media | 3 |
| HU-007 | Autoservicio: restablecer contraseña | Media | 3 |
| HU-008 | Autoservicio: asignar licencias | Media | 3 |
| HU-009 | Conocimiento RAG paso a paso | Alta | 5 |
| HU-010 | Orquestación de aprobaciones | Alta | 5 |
| HU-011 | Seguimiento proactivo del ticket | Media | 3 |
| HU-012 | Escalación con resumen ejecutivo | Alta | 3 |
| HU-013 | Integración con Jan | Media | 3 |
| HU-014 | Modo demo sin credenciales | Alta | 2 |
| HU-015 | Modelo-agnóstico | Media | 3 |
| HU-016 | Telemetría JSON estandarizada | Alta | 5 |
| HU-017 | Dashboard de 4 dimensiones | Alta | 8 |
| HU-018 | Dashboard integrado al frontend | Media | 3 |
| HU-019 | Agente de Métricas (vía multiagente) | Media | 3 |
| HU-020 | Logging estructurado (JSON) | Alta | 3 |
| HU-021 | Control de errores y reintentos | Alta | 3 |
| HU-022 | Guardrails de entrada y salida | Alta | 3 |
| HU-023 | Gestión y versionado de prompts | Media | 3 |
| HU-024 | Evaluación de salidas de agentes | Media | 3 |
| HU-025 | Integración con Langfuse | Media | 3 |
| HU-026 | Patrones de diseño | Media | 3 |
| HU-027 | Documentación por fase (LLMOps) | Media | 3 |
| HU-028 | Generación de matrices de pruebas | Alta | 5 |

**Total estimado:** ~95 puntos · **28 historias** · **1 épica** · **Versión 2.1**
