"""
Agente Coordinador — Orquestador principal.

Recibe el mensaje del usuario y orquesta a los agentes especializados:
Clasificador → Diagnóstico → Políticas → Ejecución / Conocimiento,
manejando aprobaciones y escalaciones. Es el punto de entrada único.
"""

from __future__ import annotations

from ..adapters.notifications import NotificationAdapter
from ..adapters.servicenow import ServiceNowAdapter
from ..core.llm import LLM
from ..core.models import Conversation, Intent, Ticket
from ..llmops.errors import AgentError, LLMOpsError
from ..llmops.logging import get_logger
from ..security.redaction import preview
from .classifier import ClassifierAgent
from .diagnostic import DiagnosticAgent
from .escalation import EscalationAgent
from .execution import ExecutionAgent
from .knowledge import KnowledgeAgent
from .metrics import MetricsAgent
from .policy import PolicyAgent

log = get_logger("agente.coordinador")


class CoordinatorAgent:
    def __init__(self, llm: LLM, snow: ServiceNowAdapter, notifier: NotificationAdapter):
        self.llm = llm
        self.snow = snow
        self.notifier = notifier
        self.classifier = ClassifierAgent(llm)
        self.diagnostic = DiagnosticAgent(llm, snow)
        self.policy = PolicyAgent(llm)
        self.execution = ExecutionAgent(llm, snow)
        self.knowledge = KnowledgeAgent(llm, snow)
        self.escalation = EscalationAgent(llm, snow)
        self.metrics = MetricsAgent()

    # -- ejecución de agentes con manejo de errores tipado -------------------
    def _run(self, agent_name: str, fn, *args, **kwargs):
        """Ejecuta la llamada a un agente traduciendo fallos inesperados a
        `AgentError` (ver llmops/errors.py). Los errores ya tipados
        (ValidationError, RetryableError, ProviderError...) no se envuelven
        de nuevo -- ya traen contexto suficiente."""
        try:
            return fn(*args, **kwargs)
        except LLMOpsError:
            raise
        except Exception as e:
            log.error(
                f"fallo inesperado en agente '{agent_name}'", extra={"agent": agent_name, "error": str(e)}
            )
            raise AgentError(f"El agente '{agent_name}' falló: {e}") from e

    def handle(self, user_message: str, caller: str = "Usuario") -> Conversation:
        # Fase 0: nunca registrar el mensaje crudo del usuario
        # (preview() lo omite salvo LOG_USER_CONTENT=true)
        log.info(
            "conversación iniciada", extra={"caller": caller, "user_message": preview(user_message, 120)}
        )
        conv = Conversation(user_message=user_message)
        conv.add("coordinador", "🤖 Recibí tu solicitud. Voy a analizarla y enrutarla al agente adecuado.")

        # 1) Clasificación / triaje
        conv.classification = self._run("clasificador", self.classifier.classify, user_message)
        cl = conv.classification
        conv.add(
            "clasificador",
            f"📋 Clasificación: **{cl.intent.value}** · {cl.category} / {cl.subcategory} · "
            f"Grupo: {cl.assignment_group or '—'} · Prioridad: **{cl.priority.value}** "
            f"(impacto {cl.impact}, urgencia {cl.urgency}) · confianza {cl.confidence:.0%}",
            data={"classification": cl.raw},
        )

        # Create ticket for incident/service_request/approval
        if cl.intent in (Intent.INCIDENT, Intent.SERVICE_REQUEST, Intent.APPROVAL):
            conv.ticket = Ticket(
                short_description=cl.summary or user_message[:80],
                description=user_message,
                priority=cl.priority,
                category=cl.category,
                subcategory=cl.subcategory,
                assignment_group=cl.assignment_group,
                caller=caller,
            )
            self.snow.create_incident(conv.ticket)
            conv.add(
                "coordinador",
                f"🎫 Ticket **{conv.ticket.number}** creado con prioridad {cl.priority.value}.",
                data={"ticket": conv.ticket.to_dict()},
            )

        # 2) Route by intent
        if cl.intent == Intent.KNOWLEDGE:
            return self._handle_knowledge(conv)

        if cl.intent == Intent.STATUS:
            return self._handle_status(conv)

        if cl.intent in (Intent.INCIDENT, Intent.SERVICE_REQUEST, Intent.APPROVAL):
            return self._handle_resolution(conv)

        # metrics / dashboard query
        if self._is_metrics_query(user_message):
            result = self.metrics.answer(user_message)
            conv.add("metricas", result["message"], data=result)
            conv.status = "resolved"
            return conv

        # general
        conv.add(
            "coordinador",
            "¿En qué más puedo ayudarte? Puedo resolver incidentes, "
            "responder preguntas de la base de conocimientos, gestionar "
            "solicitudes y aprobaciones.",
        )
        conv.status = "resolved"
        log.info("conversación resuelta", extra={"conversation_id": conv.id, "status": conv.status})
        return conv

    # -- knowledge ----------------------------------------------------------
    def _handle_knowledge(self, conv: Conversation) -> Conversation:
        result = self._run("conocimiento", self.knowledge.answer, conv)
        if result["found"]:
            conv.add(
                "conocimiento",
                f"📚 **{result['title']}** ({result['article_id']})\n\n{result['answer']}",
                data=result,
            )
            conv.status = "resolved"
            return conv
        conv.add("conocimiento", result["message"], data=result)
        return self._escalate(conv)

    # -- status -------------------------------------------------------------
    def _handle_status(self, conv: Conversation) -> Conversation:
        # find most recent ticket for caller
        tickets = list(self.snow._tickets.values()) if hasattr(self.snow, "_tickets") else []
        if tickets:
            t = tickets[-1]
            conv.add(
                "seguimiento",
                f"📊 Tu ticket **{t.number}** está en estado **{t.state}** "
                f"(prioridad {t.priority.value}). {t.work_notes[-1] if t.work_notes else 'Sin notas adicionales.'}",
                data={"ticket": t.to_dict()},
            )
        else:
            conv.add("seguimiento", "No encontré tickets activos para tu usuario.", data={})
        conv.status = "resolved"
        return conv

    # -- resolution flow ----------------------------------------------------
    def _handle_resolution(self, conv: Conversation) -> Conversation:
        # 2) Diagnóstico
        diag = self._run("diagnostico", self.diagnostic.diagnose, conv)
        conv.add("diagnostico", f"🔍 Diagnóstico: {diag['root_cause']}", data=diag)

        action = diag.get("recommended_action", "escalate")

        # El diagnóstico no encontró una acción automatizable: escalar de
        # inmediato en vez de forzarla por la matriz de políticas/ejecución.
        if action == "escalate":
            return self._escalate(conv)

        # 3) Políticas
        policy = self._run("politicas", self.policy.evaluate, conv, action)
        conv.add("politicas", f"⚖️ Política: {policy['reason']}", data=policy)

        if policy["requires_approval"]:
            return self._handle_approval(conv, action, policy)

        # 4) Ejecución (autoservicio)
        result = self._run("ejecucion", self.execution.execute, conv, action)
        if not result.get("success", True):
            conv.add(
                "ejecucion",
                f"⚠️ {result.get('message', 'No se pudo completar la acción automáticamente.')}",
                data=result,
            )
            return self._escalate(conv)

        conv.add("ejecucion", f"✅ {result.get('message', 'Acción ejecutada.')}", data=result)
        if conv.ticket:
            self.snow.update_incident(
                conv.ticket, {"state": "Resolved", "resolution_notes": result.get("message", "")}
            )
            conv.add("coordinador", f"🎫 Ticket **{conv.ticket.number}** resuelto y cerrado.")
        conv.status = "resolved"
        return conv

    # -- escalación -----------------------------------------------------------
    def _escalate(self, conv: Conversation) -> Conversation:
        """Escala el caso a un agente humano de Nivel 2, adjuntando el
        resumen ejecutivo del diagnóstico previo. Se invoca automáticamente
        cada vez que el sistema no puede resolver el caso por sí mismo, para
        evitar transferencias frías (ver EscalationAgent)."""
        result = self._run("escalacion", self.escalation.escalate, conv)
        conv.add("escalacion", result["message"], data=result)
        conv.status = "escalated"
        log.info("conversación escalada a Nivel 2", extra={"conversation_id": conv.id})
        return conv

    # -- approval flow ------------------------------------------------------
    def _handle_approval(self, conv: Conversation, action: str, policy: dict) -> Conversation:
        # find manager in org structure
        manager = self.snow.get_manager(conv.ticket.caller if conv.ticket else "Carlos Carballo")
        mgr_name = (manager or {}).get("manager", "el manager")
        resource = self._resource_for(action, conv.user_message)
        if conv.ticket:
            self.snow.update_incident(conv.ticket, {"state": "Awaiting Approval"})
        # send approval request via Slack/Teams/WhatsApp
        notif = self.notifier.send_approval_request(
            mgr_name, resource, conv.ticket.number if conv.ticket else "N/A"
        )
        conv.add(
            "coordinador",
            f"⏳ La solicitud de **{resource}** requiere aprobación de **{mgr_name}**. "
            f"Se envió la notificación por {notif.get('channel', 'Slack')}. "
            f"Te avisaré cuando se procese.",
            data={"approval": notif, "manager": mgr_name, "resource": resource},
        )
        conv.status = "awaiting_approval"
        return conv

    def _is_metrics_query(self, msg: str) -> bool:
        m = msg.lower()
        keywords = [
            "dashboard",
            "métrica",
            "metrica",
            "kpi",
            "estadística",
            "estadistica",
            "rendimiento",
            "fcr",
            "mttr",
            "costo",
            "costos",
            "tokens",
            "escalación",
            "escalacion",
            "abandono",
            "observabilidad",
            "monitoreo",
        ]
        return any(k in m for k in keywords)

    def _resource_for(self, action: str, msg: str) -> str:
        if action == "request_hardware":
            return "nuevo hardware"
        if action == "assign_license":
            return "licencia de software"
        return "recurso solicitado"
