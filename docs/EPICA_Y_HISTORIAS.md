# Épica e Historias de Usuario — ServiceNow Multi-Agent Conversational System

## 🎯 ÉPICA

**EPIC-001 · Sistema Multiagente Conversacional de Soporte TI sobre ServiceNow**

> **Como** usuario final de TI (empleado) y **como** agente de soporte (Nivel 1/2/3),
> **quiero** resolver incidentes, solicitudes de servicio y consultas de conocimiento mediante una conversación en lenguaje natural que orquesta agentes especializados (triaje, diagnóstico, políticas, ejecución, RAG, seguimiento y escalación),
> **para** reducir el tiempo de resolución, eliminar tareas manuales repetitivas, evitar transferencias frías y mejorar la experiencia de soporte de extremo a extremo.

**Criterios de aceptación de la épica (DoD):**
- El sistema resuelve de extremo a extremo al menos 4 intenciones: incidente, solicitud de servicio, consulta de conocimiento y estado de ticket.
- Las tareas de autoservicio (desbloqueo AD, restablecimiento de contraseña, asignación de licencias) se ejecutan sin intervención humana cuando la política lo permite.
- Las aprobaciones se orquestan notificando al manager por Slack/Teams/WhatsApp y quedan en estado `awaiting_approval`.
- Las escalaciones a Nivel 2/3 entregan un resumen ejecutivo del diagnóstico.
- El sistema es modelo-agnóstico (Jan / OpenAI / mock) y corre en modo demo sin credenciales.

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

### HU-004 · Generación de matrices de pruebas
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
- Disponible como script CLI (`scripts/generate_test_matrix.py`) y como endpoint (`POST /api/test-matrix`), compartiendo la misma lógica de generación.
- Funciona en modo demo (`LLM_PROVIDER=mock`) sin credenciales, igual que el resto del sistema.

> **Nota:** esta historia reemplaza al HU-004 original ("Diagnóstico de causa raíz"), reubicado sin cambios de contenido como **[HU-016](#hu-016--diagnóstico-de-causa-raíz)** al final de este documento, para no perder su alcance ni sus criterios de aceptación.

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

---

### HU-016 · Diagnóstico de causa raíz
*(Antes HU-004 — reubicada aquí sin cambios de contenido para liberar ese ID a [HU-004 · Generación de matrices de pruebas](#hu-004--generación-de-matrices-de-pruebas). Ver nota en HU-004.)*

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

## 📊 Resumen

| ID | Historia | Prioridad | Estimación |
|----|----------|-----------|------------|
| HU-001 | Conversación con el Coordinador | Alta | 3–5 |
| HU-002 | Triaje automático (intención/categoría/SLA) | Alta | 5 |
| HU-003 | Creación de ticket en ServiceNow | Alta | 3 |
| HU-004 | Generación de matrices de pruebas | Alta | 5 |
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
| HU-016 | Diagnóstico de causa raíz *(antes HU-004)* | Alta | 5 |

**Total estimado:** ~55 puntos · **16 historias** · **1 épica**
