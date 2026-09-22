# Nivel 1 — Diagrama de Contexto

Muestra el sistema como una única caja, y quién/qué interactúa con él. Es la
vista para alguien que nunca vio el proyecto: "¿qué hace esto y con qué
otros sistemas habla?"

```mermaid
C4Context
    title Contexto del Sistema — ServiceNow Multi-Agent

    Person(usuario, "Usuario final de TI", "Empleado que reporta incidentes, pide servicios o consulta la KB")
    Person(manager, "Manager", "Aprueba solicitudes de hardware/licencias")
    Person(agenteL2, "Agente de soporte Nivel 2/3", "Recibe casos escalados con contexto")

    System(sistema, "ServiceNow Multi-Agent System", "Orquesta 8 agentes especializados para resolver incidentes, solicitudes y consultas de conocimiento por chat")

    System_Ext(servicenow, "ServiceNow", "ITSM: tickets, base de conocimientos, estructura organizacional; también el punto de integración con Active Directory")
    System_Ext(llm, "Proveedor LLM", "Jan (servidor local) u OpenAI — razonamiento de Clasificador y Conocimiento")
    System_Ext(notif, "Slack / Teams / WhatsApp", "Canales de notificación de aprobaciones y seguimiento")
    System_Ext(jan_cliente, "Jan (como cliente)", "Frontend de chat que consume el sistema como proveedor OpenAI-compatible")
    System_Ext(langfuse, "Langfuse", "Observabilidad LLM nativa (opcional)")

    Rel(usuario, sistema, "Escribe su problema o solicitud", "HTTPS / chat web")
    Rel(sistema, manager, "Solicita aprobación", "Slack/Teams/WhatsApp")
    Rel(sistema, agenteL2, "Escala con resumen ejecutivo", "ServiceNow Workspace")

    Rel(sistema, servicenow, "Crea/actualiza tickets, busca KB, consulta org, ejecuta acciones AD", "REST API")
    Rel(sistema, llm, "Clasifica intención y sintetiza respuestas", "API OpenAI-compatible")
    Rel(sistema, notif, "Envía notificaciones", "Webhooks")
    Rel(jan_cliente, sistema, "Conversa usando el sistema como proveedor personalizado", "/v1/chat/completions")
    Rel(sistema, langfuse, "Envía trazas, spans y costos", "Ingestion API")
```

## Actores

| Actor | Rol |
|-------|-----|
| **Usuario final de TI** | Reporta incidentes, pide servicios (hardware, licencias), consulta la KB, consulta el estado de sus tickets — todo en lenguaje natural. |
| **Manager** | Recibe la notificación de aprobación (Slack/Teams/WhatsApp) cuando una solicitud de un reporte directo la requiere. |
| **Agente de soporte Nivel 2/3** | Recibe el caso en el Workspace de ServiceNow cuando el sistema no puede resolverlo solo, con el resumen ejecutivo del diagnóstico ya construido — nunca una transferencia fría. |

## Sistemas externos

| Sistema | Para qué se usa | Modo |
|---------|------------------|------|
| **ServiceNow** | Tickets, KB (fuente del RAG), estructura organizacional, acciones de AD (desbloqueo, reset de contraseña) | LIVE (REST) / DEMO (simulado en memoria, sin credenciales) |
| **Proveedor LLM** (Jan / OpenAI) | Razonamiento de 2 de los 8 agentes (Clasificador, Conocimiento) — el resto son deterministas por diseño | `jan` / `openai` / `mock` |
| **Slack / Teams / WhatsApp** | Notificar aprobaciones y actualizaciones de ticket | LIVE (webhooks) / DEMO (log) |
| **Jan** (rol dual) | (a) proveedor del LLM local en el puerto 1337; (b) cliente que consume `/v1/chat/completions` del sistema en el puerto 8000 — son dos roles y dos conexiones distintas, no confundirlos | — |
| **Langfuse** | Observabilidad LLM nativa: trazas, spans, costos automáticos | Opcional — solo si `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` están configuradas |

**Nota sobre Active Directory:** el código no tiene una integración directa
con AD — las acciones de desbloqueo/reset de contraseña pasan por
`ServiceNowAdapter`, que en modo LIVE llamaría a un flow/scripted REST API
de ServiceNow que a su vez toca AD. Se documenta así para reflejar el
código real, no una integración directa que no existe.
