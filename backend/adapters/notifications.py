"""
Notification adapter for approval flows and proactive ticket updates.

Supports Slack, Microsoft Teams, and WhatsApp. In demo mode it logs the
message; in live mode it posts via webhooks. Configure via env vars:
  NOTIFY_CHANNEL=slack|teams|whatsapp
  SLACK_WEBHOOK_URL / TEAMS_WEBHOOK_URL / WHATSAPP_API_URL
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


class NotificationAdapter:
    def __init__(self):
        self.channel = os.getenv("NOTIFY_CHANNEL", "slack").lower()
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
        self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL", "")
        self.whatsapp_url = os.getenv("WHATSAPP_API_URL", "")
        self.live = bool(self.slack_webhook or self.teams_webhook or self.whatsapp_url)
        self._client = httpx.Client(timeout=20.0)

    def send(self, to: str, subject: str, body: str, channel: Optional[str] = None) -> dict:
        ch = (channel or self.channel).lower()
        if self.live:
            try:
                if ch == "slack" and self.slack_webhook:
                    self._client.post(self.slack_webhook, json={"text": f"*{subject}*\n{body}"})
                elif ch == "teams" and self.teams_webhook:
                    self._client.post(self.teams_webhook, json={"text": f"**{subject}**\n\n{body}"})
                elif ch == "whatsapp" and self.whatsapp_url:
                    self._client.post(self.whatsapp_url, json={"to": to, "message": f"{subject}\n{body}"})
            except Exception as e:
                return {"success": False, "error": str(e)}
        # demo: log
        return {"success": True, "channel": ch, "to": to, "subject": subject, "body": body,
                "delivered": "live" if self.live else "demo"}

    def send_approval_request(self, manager: str, resource: str, ticket_number: str, channel: Optional[str] = None) -> dict:
        subject = f"🔔 Aprobación requerida: {resource}"
        body = (
            f"Se requiere tu aprobación para: **{resource}**\n"
            f"Ticket: {ticket_number}\n"
            f"Responde 'aprobar' o 'rechazar' para procesar en tiempo real."
        )
        return self.send(manager, subject, body, channel)

    def send_ticket_update(self, user: str, ticket_number: str, state: str, note: str, channel: Optional[str] = None) -> dict:
        subject = f"🔄 Actualización de tu ticket {ticket_number}"
        body = f"Estado: **{state}**\n{note}"
        return self.send(user, subject, body, channel)
