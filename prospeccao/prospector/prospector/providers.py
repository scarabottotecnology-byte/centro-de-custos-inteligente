"""Canais de envio: WhatsApp (Evolution API) e e-mail (SMTP)."""

from __future__ import annotations

import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

log = logging.getLogger(__name__)


@dataclass
class SendResult:
    provider_message_id: str
    dry_run: bool = False


class EvolutionClient:
    """Evolution API v2 — rotas /chat/whatsappNumbers e /message/sendText."""

    def __init__(self, base_url: str, apikey: str, instance: str, timeout: float = 30):
        self.instance = instance
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, headers={"apikey": apikey})

    def check_numbers(self, numbers: list[str]) -> dict[str, str]:
        """Número -> JID, só para os que têm WhatsApp."""
        resp = self.http.post(f"/chat/whatsappNumbers/{self.instance}", json={"numbers": numbers})
        resp.raise_for_status()
        found: dict[str, str] = {}
        for item in resp.json():
            if item.get("exists"):
                # Evolution devolve o número como enviado, ou o normalizado pelo WhatsApp.
                key = item.get("number") or item.get("jid", "").split("@")[0]
                for n in numbers:
                    if key == n or key.endswith(n[-8:]):
                        found[n] = item.get("jid") or f"{key}@s.whatsapp.net"
        return found

    def send_text(self, number: str, text: str, typing_ms: int = 1500) -> SendResult:
        resp = self.http.post(f"/message/sendText/{self.instance}",
                              json={"number": number, "text": text, "delay": typing_ms})
        resp.raise_for_status()
        data = resp.json()
        return SendResult(provider_message_id=(data.get("key") or {}).get("id") or str(uuid.uuid4()))

    def is_connected(self) -> bool:
        try:
            resp = self.http.get(f"/instance/connectionState/{self.instance}")
            resp.raise_for_status()
        except httpx.HTTPError:
            return False
        return (resp.json().get("instance") or {}).get("state") == "open"

    def create_instance(self, webhook_url: str) -> dict:
        resp = self.http.post("/instance/create", json={
            "instanceName": self.instance, "integration": "WHATSAPP-BAILEYS", "qrcode": True,
            "webhook": {"url": webhook_url, "byEvents": False, "base64": False,
                        "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]},
        })
        resp.raise_for_status()
        return resp.json()

    def connect(self) -> dict:
        resp = self.http.get(f"/instance/connect/{self.instance}")
        resp.raise_for_status()
        return resp.json()


class SmtpSender:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, sender_name: str):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.sender, self.sender_name = sender, sender_name

    def send(self, to: str, subject: str, body: str, unsubscribe_url: str) -> SendResult:
        msg = EmailMessage()
        msg["From"] = formataddr((self.sender_name, self.sender))
        msg["To"] = to
        msg["Subject"] = subject
        msg_id = make_msgid(domain=self.sender.split("@")[-1])
        msg["Message-ID"] = msg_id
        # Descadastro em um clique (RFC 8058) — Gmail e Yahoo exigem para envio em volume.
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg.set_content(body)
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=30) as s:
                s.login(self.user, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                s.starttls(context=context)
                s.login(self.user, self.password)
                s.send_message(msg)
        return SendResult(provider_message_id=msg_id)
