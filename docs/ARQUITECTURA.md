# Arquitectura del Sistema Multiagente

## Visión general

El sistema es un **orquestador de agentes especializados** que procesa solicitudes de soporte de TI en lenguaje natural y las resuelve de extremo a extremo, integrando ServiceNow, Active Directory, la base de conocimientos y canales de notificación (Slack/Teams/WhatsApp).

## Componentes

### 1. Agente Coordinador (Orquestador)
Punto de entrada único. Recibe el mensaje del usuario, orquesta a los agentes especializados y mantiene el estado de la conversación. Decide la ruta según la intención clasificada.

### 2. Agente Clasificador (Triaje)
- Analiza el texto libre en lenguaje natural.
- Identifica la **intención** (incident, service_request, knowledge, approval, status, escalation, general).
- Asigna **categoría, subcategoría y Assignment Group**.
- Calcula la **prioridad (SLA)** a partir de impacto, urgencia, sentimiento y palabras clave.
- Usa un LLM con salida JSON estructurada + heurísticas de respaldo.

### 3. Agente de Diagnóstico
- Revisa el estado real de la cuenta/sistema (AD, CRM, etc.).
- Determina la **causa raíz** (p. ej. cuenta bloqueada por intentos fallidos).
- Recomienda la acción a ejecutar.

### 4. Agente de Políticas
- Aplica la **matriz de políticas** de la organización.
- Determina si la acción es **autoservicio** o requiere **aprobación** (y de quién).

### 5. Agente de Ejecución
- Ejecuta tareas automatizadas: desbloqueo de cuentas AD, restablecimiento de contraseñas, asignación de licencias.
- Conecta con ServiceNow / AD / catálogo.

### 6. Agente de Conocimiento (RAG)
- Busca en la base de conocimientos de ServiceNow.
- Extrae la respuesta exacta y la explica **paso a paso** en el chat.

### 7. Agente de Seguimiento
- Notifica proactivamente cambios de estado, notas y solicitudes de información.
- Reduce las llamadas de seguimiento ("¿Cómo va mi ticket?").

### 8. Agente de Escalación
- Transfiere el caso a un agente humano (Nivel 2/3) en el Workspace de ServiceNow.
- Entrega un **resumen ejecutivo del diagnóstico** para evitar transferencias frías.

## Flujo de procesamiento

```
1. Usuario envía mensaje
2. Coordinador recibe y crea la conversación
3. Clasificador determina intención + prioridad (SLA)
4. Si es incidente/solicitud → se crea el ticket en ServiceNow
5. Según intención:
   - Knowledge → Agente de Conocimiento (RAG)
   - Status → Agente de Seguimiento
   - Incidente/Solicitud/Aprobación → Diagnóstico → Políticas →
       ├─ Autoservicio → Ejecución → resuelto
       └─ Requiere aprobación → notificación al manager → awaiting_approval
6. Si no se puede resolver → Escalación a humano con contexto
```

## Integraciones

| Sistema | Adapter | Modo |
|---------|---------|------|
| ServiceNow (incidentes, KB, org) | `ServiceNowAdapter` | LIVE (REST API) / DEMO |
| Active Directory | `ServiceNowAdapter.unlock_account` | LIVE / DEMO |
| Slack / Teams / WhatsApp | `NotificationAdapter` | LIVE (webhooks) / DEMO |
| LLM (Jan / OpenAI) | `LLM` | jan / openai / mock |

## Decisiones de diseño

- **Modelo-agnóstico**: el LLM se abstrae detrás de una interfaz única; apunta a Jan, OpenAI o un mock.
- **Demo sin credenciales**: todo corre en modo demo determinista para validar el flujo completo.
- **Salida JSON estructurada**: los agentes devuelven JSON para facilitar la integración con ServiceNow.
- **Endpoint OpenAI-compatible**: permite que Jan (o cualquier cliente) se conecte directamente.
