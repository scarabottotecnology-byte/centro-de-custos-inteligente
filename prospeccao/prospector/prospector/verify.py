"""Verificação de canais antes do envio.

E-mail: Reacher (check-if-email-exists) responde safe | risky | invalid | unknown
sem mandar mensagem. Telefone: o próprio Evolution API diz se o número tem
WhatsApp. Só canal verificado entra em campanha — bounce e número inexistente
derrubam reputação de domínio e de chip.
"""

from __future__ import annotations

import logging

import httpx
import psycopg

from .config import Settings
from .providers import EvolutionClient

log = logging.getLogger(__name__)

REACHER_STATUS = {"safe": "verified", "invalid": "unverified"}


class ReacherClient:
    def __init__(self, base_url: str, secret: str = "", timeout: float = 90):
        headers = {"x-reacher-secret": secret} if secret else {}
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, headers=headers)

    def check(self, email: str) -> str:
        resp = self.http.post("/v0/check_email", json={"to_email": email})
        resp.raise_for_status()
        return resp.json().get("is_reachable", "unknown")


def emails(conn: psycopg.Connection, org_id: str, settings: Settings, client: ReacherClient,
           limit: int = 200) -> dict[str, int]:
    rows = conn.execute(
        """
        select ct.id, ct.email from contacts ct join prospects p on p.company_id = ct.company_id
         where ct.organization_id = %s and ct.email is not null and not ct.email_shared
           and ct.email_status = 'unknown' and p.stage = 'prioritized'
           and (ct.email_checked_at is null or ct.email_checked_at < now() - interval '30 days')
         order by p.priority desc limit %s
        """,
        (org_id, limit),
    ).fetchall()
    stats = {"safe": 0, "risky": 0, "invalid": 0, "unknown": 0, "erro": 0}
    for row in rows:
        try:
            result = client.check(row["email"])
        except httpx.HTTPError as exc:
            log.warning("reacher falhou para %s: %s", row["id"], exc)
            stats["erro"] += 1
            continue
        stats[result if result in stats else "unknown"] += 1
        status = REACHER_STATUS.get(result)
        if result == "risky" and settings.enriquecimento.aceitar_email_risky:
            status = "verified"  # catch-all é comum em PME; aceitar é decisão do YAML
        # unknown fica unknown, mas com a data da tentativa: só tenta de novo em 30 dias
        conn.execute(
            "update contacts set email_status = coalesce(%s::verification_status, email_status), email_checked_at = now(), "
            "updated_at = now() where id = %s",
            (status, row["id"]),
        )
    conn.commit()
    return stats


def whatsapp(conn: psycopg.Connection, org_id: str, client: EvolutionClient, limit: int = 200) -> dict[str, int]:
    rows = conn.execute(
        """
        select ct.id, ct.phone from contacts ct join prospects p on p.company_id = ct.company_id
         where ct.organization_id = %s and ct.phone is not null and ct.phone_status = 'unknown'
           and p.stage = 'prioritized'
         order by p.priority desc limit %s
        """,
        (org_id, limit),
    ).fetchall()
    stats = {"com_whatsapp": 0, "sem_whatsapp": 0}
    for i in range(0, len(rows), 50):
        chunk = rows[i:i + 50]
        found = client.check_numbers([r["phone"] for r in chunk])
        for row in chunk:
            jid = found.get(row["phone"])
            conn.execute(
                "update contacts set phone_status = %s, whatsapp_jid = %s, updated_at = now() where id = %s",
                ("verified" if jid else "unverified", jid, row["id"]),
            )
            stats["com_whatsapp" if jid else "sem_whatsapp"] += 1
    conn.commit()
    return stats
