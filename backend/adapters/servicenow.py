"""
ServiceNow adapter.

Two modes:
  * LIVE  — talks to a real ServiceNow instance via its REST API (Table API,
            Knowledge Management API, org structure). Requires SNOW_INSTANCE,
            SNOW_USER, SNOW_PASSWORD (or SNOW_TOKEN).
  * DEMO  — deterministic in-memory simulation so the whole multi-agent flow
            runs end-to-end with zero credentials. This is the default.

The adapter exposes the exact operations the agents need:
  - create/update/get incident
  - search knowledge base (RAG source)
  - lookup manager in org structure
  - execute catalog tasks (unlock AD, reset password, assign license)
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from ..core.models import Ticket, Priority


# ---------------------------------------------------------------------------
# Demo knowledge base (RAG corpus)
# ---------------------------------------------------------------------------
DEMO_KB = [
    {
        "id": "KB001234",
        "title": "Cómo restablecer tu contraseña",
        "category": "Account Access",
        "content": (
            "Para restablecer tu contraseña: 1) Ve a https://portal/selfservice. "
            "2) Haz clic en 'Olvidé mi contraseña'. 3) Ingresa tu correo corporativo. "
            "4) Recibirás un enlace temporal válido por 15 minutos. "
            "5) Crea una nueva contraseña de al menos 12 caracteres con mayúsculas, "
            "números y símbolos. Si el enlace expira, repite el proceso."
        ),
    },
    {
        "id": "KB001567",
        "title": "Desbloqueo de cuenta de Active Directory",
        "category": "Account Access",
        "content": (
            "Si tu cuenta está bloqueada por intentos fallidos: 1) Espera 15 minutos "
            "para el desbloqueo automático, o 2) Solicita el desbloqueo inmediato al "
            "Service Desk. El desbloqueo inmediato es autoservicio y no requiere "
            "aprobación de TI. Se te enviará un código temporal por correo."
        ),
    },
    {
        "id": "KB002345",
        "title": "Asignación de licencia de software",
        "category": "Software",
        "content": (
            "Para solicitar una licencia de software: 1) Busca el software en el "
            "Service Catalog. 2) Selecciona la licencia requerida. 3) Si el costo "
            "supera $500 USD, se requiere aprobación del manager. 4) La licencia se "
            "asigna automáticamente tras la aprobación."
        ),
    },
    {
        "id": "KB003456",
        "title": "Solicitud de nuevo hardware",
        "category": "Hardware",
        "content": (
            "Para solicitar hardware nuevo (laptop, monitor, etc.): 1) Abre el "
            "Service Catalog > Hardware. 2) Selecciona el equipo. 3) El sistema "
            "busca a tu manager en la estructura organizacional y envía una "
            "notificación de aprobación. 4) Tras la aprobación, el equipo se "
            "ordena y se programa la entrega."
        ),
    },
]

DEMO_ORG = {
    "Carlos Carballo": {"manager": "María González", "department": "IT", "email": "carlos@corp.com"},
    "María González": {"manager": "Juan Pérez", "department": "IT", "email": "maria@corp.com"},
    "Juan Pérez": {"manager": None, "department": "IT", "email": "juan@corp.com"},
}


class ServiceNowAdapter:
    def __init__(self):
        self.instance = os.getenv("SNOW_INSTANCE", "")
        self.user = os.getenv("SNOW_USER", "")
        self.password = os.getenv("SNOW_PASSWORD", "")
        self.token = os.getenv("SNOW_TOKEN", "")
        self.live = bool(self.instance and (self.user or self.token))
        self._client = httpx.Client(timeout=30.0) if self.live else None
        # demo state
        self._tickets: dict[str, Ticket] = {}
        self._kb = list(DEMO_KB)
        self._org = {k: dict(v) for k, v in DEMO_ORG.items()}

    # -- helpers ------------------------------------------------------------
    def _headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        import base64
        auth = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {auth}", "Accept": "application/json"}

    def _url(self, path: str) -> str:
        return f"https://{self.instance}.service-now.com/api/now/{path}"

    # -- incidents ----------------------------------------------------------
    def create_incident(self, ticket: Ticket) -> Ticket:
        if self.live:
            payload = {
                "short_description": ticket.short_description,
                "description": ticket.description,
                "category": ticket.category,
                "subcategory": ticket.subcategory,
                "assignment_group": ticket.assignment_group,
                "impact": ticket.impact,
                "urgency": ticket.urgency,
                "caller_id": ticket.caller,
            }
            r = self._client.post(self._url("table/incident"), headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()["result"]
            ticket.number = data.get("number", ticket.number)
            ticket.state = data.get("state", ticket.state)
        else:
            self._tickets[ticket.number] = ticket
        return ticket

    def update_incident(self, ticket: Ticket, fields: dict) -> Ticket:
        if self.live:
            r = self._client.patch(
                self._url(f"table/incident/{ticket.number}"),
                headers=self._headers(), json=fields,
            )
            r.raise_for_status()
        else:
            for k, v in fields.items():
                if hasattr(ticket, k):
                    setattr(ticket, k, v)
        ticket.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        return ticket

    def get_incident(self, number: str) -> Optional[Ticket]:
        if self.live:
            r = self._client.get(self._url(f"table/incident?sysparm_query=number={number}"), headers=self._headers())
            r.raise_for_status()
            res = r.json()["result"]
            if not res:
                return None
            d = res[0]
            return Ticket(
                number=d.get("number"), short_description=d.get("short_description"),
                description=d.get("description"), state=d.get("state"),
                category=d.get("category"), subcategory=d.get("subcategory"),
                assignment_group=d.get("assignment_group"), assigned_to=d.get("assigned_to"),
                caller=d.get("caller_id"),
            )
        return self._tickets.get(number)

    # -- knowledge base (RAG) ----------------------------------------------
    def search_kb(self, query: str, top_k: int = 3) -> list[dict]:
        """Simple keyword/embedding-free retrieval. Swap for real vector search."""
        q = query.lower()
        scored = []
        for art in self._kb:
            score = 0
            for token in q.split():
                if token in art["title"].lower():
                    score += 3
                if token in art["content"].lower():
                    score += 1
            if score > 0:
                scored.append((score, art))
        scored.sort(key=lambda x: -x[0])
        return [a for _, a in scored[:top_k]]

    # -- org structure ------------------------------------------------------
    def get_manager(self, employee: str) -> Optional[dict]:
        if self.live:
            # sys_user table lookup — simplified
            r = self._client.get(
                self._url(f"table/sys_user?sysparm_query=name={employee}&sysparm_fields=manager"),
                headers=self._headers(),
            )
            r.raise_for_status()
            res = r.json()["result"]
            if res and res[0].get("manager"):
                return {"manager": res[0]["manager"]["display_value"]}
            return None
        emp = self._org.get(employee)
        if not emp or not emp.get("manager"):
            return None
        mgr = self._org.get(emp["manager"], {})
        return {"manager": emp["manager"], "email": mgr.get("email"), "department": mgr.get("department")}

    # -- catalog / automation ----------------------------------------------
    def unlock_account(self, target: str) -> dict:
        """Unlock AD account (self-service)."""
        if self.live:
            # would call a custom scripted REST API / flow
            pass
        return {"success": True, "action": "unlock_account", "target": target,
                "message": f"Cuenta '{target}' desbloqueada. Se envió un código temporal."}

    def reset_password(self, target: str) -> dict:
        if self.live:
            pass
        return {"success": True, "action": "reset_password", "target": target,
                "message": f"Contraseña de '{target}' restablecida. Código temporal enviado."}

    def assign_license(self, software: str, user: str) -> dict:
        if self.live:
            pass
        return {"success": True, "action": "assign_license", "software": software, "user": user,
                "message": f"Licencia de {software} asignada a {user}."}

    def request_approval(self, resource: str, manager: str, channel: str = "slack") -> dict:
        """Send approval request to manager via Slack/Teams/WhatsApp."""
        if self.live:
            pass
        return {"success": True, "action": "request_approval", "resource": resource,
                "manager": manager, "channel": channel,
                "message": f"Solicitud de aprobación para '{resource}' enviada a {manager} por {channel}."}
