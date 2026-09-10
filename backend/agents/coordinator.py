"""
Agente Coordinador — Orquestador principal.

Recibe el mensaje del usuario y orquesta a los agentes especializados:
Clasificador → Diagnóstico → Políticas → Ejecución / Conocimiento,
manejando aprobaciones y escalaciones. Es el punto de entrada único.
"""
from __future__ import annotations

from ..core.llm import LLM
from ..core.models import Conversation, Intent, Ticket
from ..adapters.servicenow import ServiceNowAdapter
from ..adapters.notifications import NotificationAdapter
from .classifier import ClassifierAgent
from .diagnostic import DiagnosticAgent
from .policy import PolicyAgent
from .execution import ExecutionAgent
from .knowledge import KnowledgeAgent


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

    def handle(self, user_message: str, caller: str = "Usuario") -> Conversation:
        conv = Conversation(user_message=user_message)
        conv.add("coordinador", "🤖 Recibí tu solicitud. Voy a analizarla y enrutarla al agente adecuado.")

        # 1) Clasificación / triaje
        conv.classification = self.classifier.classify(user_message)
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
            conv.add("coordinador", f"🎫 Ticket **{conv.ticket.number}** creado con prioridad {cl.priority.value}.",
                     data={"ticket": conv.ticket.to_dict()})

        # 2) Route by intent
        if cl.intent == Intent.KNOWLEDGE:
            return self._handle_knowledge(conv)

        if cl.intent == Intent.STATUS:
            return self._handle_status(conv)

        if cl.intent in (Intent.INCIDENT, Intent.SERVICE_REQUEST, Intent.APPROVAL):
            return self._handle_resolution(conv)

        # general
        conv.add("coordinador", "¿En qué más puedo ayudarte? Puedo resolver incidentes, "
                                "responder preguntas de la base de conocimientos, gestionar "
                                "solicitudes y aprobaciones.")
        conv.status = "resolved"
        return conv

    # -- knowledge ----------------------------------------------------------
    def _handle_knowledge(self, conv: Conversation) -> Conversation:
        result = self.knowledge.answer(conv)
        if result["found"]:
            conv.add("conocimiento", f"📚 **{result['title']}** ({result['article_id']})\n\n{result['answer']}",
                     data=result)
            conv.status = "resolved"
        else:
            conv.add("conocimiento", result["message"], data=result)
            conv.status = "escalated"
        return conv

    # -- status -------------------------------------------------------------
    def _handle_status(self, conv: Conversation) -> Conversation:
        # find most recent ticket for caller
        tickets = [t for t in self.snow._tickets.values()] if hasattr(self.snow, "_tickets") else []
        if tickets:
            t = tickets[-1]
            conv.add("seguimiento", f"📊 Tu ticket **{t.number}** está en estado **{t.state}** "
                                    f"(prioridad {t.priority.value}). {t.work_notes[-1] if t.work_notes else 'Sin notas adicionales.'}",
                     data={"ticket": t.to_dict()})
        else:
            conv.add("seguimiento", "No encontré tickets activos para tu usuario.", data={})
        conv.status = "resolved"
        return conv

    # -- resolution flow ----------------------------------------------------
    def _handle_resolution(self, conv: Conversation) -> Conversation:
        # 2) Diagnóstico
        diag = self.diagnostic.diagnose(conv)
        conv.add("diagnostico", f"🔍 Diagnóstico: {diag['root_cause']}",
                 data=diag)

        action = diag.get("recommended_action", "escalate")

        # 3) Políticas
        policy = self.policy.evaluate(conv, action)
        conv.add("politicas", f"⚖️ Política: {policy['reason']}", data=policy)

        if policy["requires_approval"]:
            return self._handle_approval(conv, action, policy)

        # 4) Ejecución (autoservicio)
        result = self.execution.execute(conv, action)
        conv.add("ejecucion", f"✅ {result.get('message', 'Acción ejecutada.')}", data=result)
        if conv.ticket:
            self.snow.update_incident(conv.ticket, {"state": "Resolved",
                                                    "resolution_notes": result.get("message", "")})
            conv.add("coordinador", f"🎫 Ticket **{conv.ticket.number}** resuelto y cerrado.")
        conv.status = "resolved"
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
        conv.add("coordinador",
                 f"⏳ La solicitud de **{resource}** requiere aprobación de **{mgr_name}**. "
                 f"Se envió la notificación por {notif.get('channel', 'Slack')}. "
                 f"Te avisaré cuando se procese.",
                 data={"approval": notif, "manager": mgr_name, "resource": resource})
        conv.status = "awaiting_approval"
        return conv

    def _resource_for(self, action: str, msg: str) -> str:
        if action == "request_hardware":
            return "nuevo hardware"
        if action == "assign_license":
            return "licencia de software"
        return "recurso solicitado"
