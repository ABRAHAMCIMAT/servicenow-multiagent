# Nivel 4 — Código

El nivel más detallado de C4: clases y flujos concretos de las partes más
importantes del sistema. No pretende ser exhaustivo — cubre lo que un
diagrama de clases o de secuencia explica mejor que prosa.

## Modelo de dominio (`backend/core/models.py`)

```mermaid
classDiagram
    class Conversation {
        +str id
        +str user_message
        +Classification classification
        +Ticket ticket
        +list~AgentMessage~ messages
        +str status
        +add(agent, content, data, role) AgentMessage
        +to_dict() dict
    }
    class Classification {
        +Intent intent
        +str category
        +str subcategory
        +str assignment_group
        +int impact
        +int urgency
        +Priority priority
        +float confidence
        +str sentiment
        +list~str~ keywords
        +str summary
    }
    class Ticket {
        +str number
        +str short_description
        +str state
        +Priority priority
        +str assignment_group
        +str caller
        +list~str~ work_notes
        +to_dict() dict
    }
    class AgentMessage {
        +str agent
        +str role
        +str content
        +dict data
        +str timestamp
    }
    class Intent {
        <<enumeration>>
        INCIDENT
        SERVICE_REQUEST
        KNOWLEDGE
        APPROVAL
        STATUS
        ESCALATION
        GENERAL
    }
    class Priority {
        <<enumeration>>
        P1
        P2
        P3
        P4
    }

    Conversation "1" --> "0..1" Classification
    Conversation "1" --> "0..1" Ticket
    Conversation "1" --> "*" AgentMessage
    Classification --> Intent
    Classification --> Priority
    Ticket --> Priority
```

`status` de `Conversation` es una máquina de estados simple (`str`, no un
enum tipado): `in_progress → resolved | escalated | awaiting_approval`.

## Jerarquía de excepciones (`backend/llmops/errors.py`)

```mermaid
classDiagram
    class LLMOpsError {
        <<exception>>
    }
    class ConfigurationError {
        <<exception>>
        Config inválida — fail-fast al iniciar
    }
    class ProviderError {
        <<exception>>
        HTTP no reintentable del LLM/ServiceNow
    }
    class RetryableError {
        <<exception>>
        Timeout, red, 429, 5xx — dispara retry()
    }
    class ValidationError {
        <<exception>>
        Guardrail de entrada/salida rechazado
    }
    class AgentError {
        <<exception>>
        Fallo inesperado dentro de un agente
    }

    LLMOpsError <|-- ConfigurationError
    LLMOpsError <|-- ProviderError
    LLMOpsError <|-- RetryableError
    LLMOpsError <|-- ValidationError
    LLMOpsError <|-- AgentError
```

`backend/server.py` mapea esta jerarquía a HTTP vía
`@app.exception_handler`: `ProviderError` → 502, `AgentError` → 500,
cualquier otro `LLMOpsError` → 500 genérico — nunca un traceback crudo.

## Secuencia — camino feliz (incidente resuelto por autoservicio)

```mermaid
sequenceDiagram
    actor U as Usuario
    participant S as server.py
    participant C as CoordinatorAgent
    participant CL as ClassifierAgent
    participant SN as ServiceNowAdapter
    participant D as DiagnosticAgent
    participant P as PolicyAgent
    participant E as ExecutionAgent

    U->>S: POST /api/chat {message}
    S->>S: validate_input() (guardrail)
    S->>C: handle(message)
    C->>CL: classify(message)
    CL->>CL: LLM (o heurística si falla / no pasa el eval)
    CL-->>C: Classification(intent=incident, priority=P2)
    C->>SN: create_incident(ticket)
    C->>D: diagnose(conv)
    D-->>C: {root_cause, recommended_action: "unlock_account"}
    C->>P: evaluate(conv, "unlock_account")
    P-->>C: {requires_approval: false}
    C->>E: execute(conv, "unlock_account")
    E->>SN: unlock_account(target)
    SN-->>E: {success: true}
    E-->>C: {success: true, message}
    C->>SN: update_incident(state="Resolved")
    C-->>S: Conversation(status="resolved")
    S-->>U: 200 {messages, status}
```

## Secuencia — escalación automática

Se dispara en dos puntos distintos de `CoordinatorAgent`, ambos sin
intervención manual (ver `tests/test_coordinator_escalation.py`):

```mermaid
sequenceDiagram
    participant C as CoordinatorAgent
    participant D as DiagnosticAgent
    participant Es as EscalationAgent
    participant SN as ServiceNowAdapter

    C->>D: diagnose(conv)
    D-->>C: {recommended_action: "escalate"}
    Note over C: recommended_action == "escalate" → no hay acción automatizable
    C->>Es: escalate(conv)
    Es->>Es: build_summary(conv) — resumen ejecutivo
    Es->>SN: update_incident(assignment_group="L2 Support")
    Es-->>C: {message}
    C-->>C: conv.status = "escalated"
```

El segundo disparador es simétrico: si `ExecutionAgent.execute()` devuelve
`{"success": false}` (acción no soportada, o falla la operación real),
`Coordinator` llama a `Escalation` de la misma forma — nunca marca la
conversación como `resolved` sobre un resultado fallido. Antes de la
corrección documentada en la auditoría LLMOps, `Coordinator` no invocaba a
`EscalationAgent` en ningún camino automático; estos dos disparadores son
exactamente la regresión que cubren los tests.
