"""Verificação de canais antes do envio.

E-mail, dois modos:
  reacher  Reacher (check-if-email-exists) conversa com o servidor de e-mail e
           responde safe | risky | invalid | unknown sem mandar mensagem.
           Precisa da porta 25 de saída, que operadoras residenciais e nuvens
           gratuitas bloqueiam — por isso é opcional.
  mx       Padrão quando não há Reacher. Só consulta o DNS: domínio sem
           servidor de e-mail vira 'unverified' e nunca recebe envio. O resto
           segue 'unknown' com a data da checagem e pode entrar em campanha; o
           bounce que voltar é suprimido pela leitura da caixa (inbound.py).

Telefone: o próprio Evolution API diz se o número tem WhatsApp. Bounce e número
inexistente derrubam reputação de conta e de chip, então só canal checado entra
em campanha.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import dns.exception
import dns.resolver
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


_PENDING_EMAILS = """
    select ct.id, ct.email from contacts ct join prospects p on p.company_id = ct.company_id
     where ct.organization_id = %s and ct.email is not null and not ct.email_shared
       and ct.email_status = 'unknown' and p.stage = 'prioritized'
       and (ct.email_checked_at is null or ct.email_checked_at < now() - interval '30 days')
     order by p.priority desc limit %s
"""


DNS_CANARY = "gmail.com"


def _has_mail_server(domain: str) -> bool | None:
    """True/False pelo DNS; None quando o DNS não respondeu (tenta de novo depois)."""
    for record in ("MX", "A"):  # sem MX, o RFC 5321 manda entregar no registro A
        try:
            dns.resolver.resolve(domain, record, lifetime=10)
            return True
        except dns.resolver.NXDOMAIN:
            return False
        except dns.resolver.NoNameservers:
            return None  # servidor de nomes falhou: não é prova de que o domínio não existe
        except dns.resolver.NoAnswer:
            continue
        except dns.exception.DNSException:
            return None
    return False


def emails_mx(conn: psycopg.Connection, org_id: str, limit: int = 500,
              has_mail_server: Callable[[str], bool | None] = _has_mail_server) -> dict[str, int]:
    rows = conn.execute(_PENDING_EMAILS, (org_id, limit)).fetchall()
    stats = {"dominio_ok": 0, "dominio_invalido": 0, "dns_sem_resposta": 0}
    if rows and has_mail_server(DNS_CANARY) is not True:
        # DNS que nega até o Gmail está quebrado (queda de internet, portal de
        # Wi-Fi, filtro). Marcar e-mails como inválidos agora seria perder lead bom.
        log.warning("DNS não confirmou %s; checagem de e-mails fica para o próximo ciclo", DNS_CANARY)
        stats["dns_sem_resposta"] = len(rows)
        return stats
    cache: dict[str, bool | None] = {}
    for row in rows:
        domain = row["email"].rsplit("@", 1)[-1].lower()
        if domain not in cache:
            cache[domain] = has_mail_server(domain)
        ok = cache[domain]
        if ok is None:
            stats["dns_sem_resposta"] += 1
            continue
        conn.execute(
            "update contacts set email_status = case when %s then email_status else 'unverified' end, "
            "email_checked_at = now(), updated_at = now() where id = %s",
            (ok, row["id"]),
        )
        stats["dominio_ok" if ok else "dominio_invalido"] += 1
    conn.commit()
    return stats


def emails(conn: psycopg.Connection, org_id: str, settings: Settings, client: ReacherClient,
           limit: int = 200) -> dict[str, int]:
    rows = conn.execute(_PENDING_EMAILS, (org_id, limit)).fetchall()
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
