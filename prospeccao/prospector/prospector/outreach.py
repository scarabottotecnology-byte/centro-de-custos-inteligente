"""Pesquisa (A6), entrada em campanha e envio com cadência (WF-009 / WF-010).

Invariantes do envio, nesta ordem, para toda mensagem:
  1. dentro da janela de horário configurada
  2. dentro do limite diário do canal
  3. destinatário fora da suppression_list
  4. chave de idempotência nova (sha de campaign_contact:passo) — reprocessar
     nunca manda duas vezes a mesma mensagem
"""

from __future__ import annotations

import hashlib
import logging
import random
import time as _time
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import anthropic
import psycopg
from psycopg.types.json import Jsonb

from . import db, messages
from .config import Settings
from .llm import Claude

log = logging.getLogger(__name__)

RESEARCH_FIELDS = ["razao_social", "nome_fantasia", "cnae_principal", "cnae_descricao", "data_abertura",
                   "porte", "capital_social", "municipio", "uf", "bairro", "opcao_simples", "website",
                   "google_rating", "google_reviews", "google_category", "qtd_estabelecimentos"]


# ── Pesquisa ────────────────────────────────────────────────────────────────

def research(conn: psycopg.Connection, org_id: str, settings: Settings, claude: Claude | None,
             limit: int = 50) -> int:
    if not claude:
        return 0
    rows = conn.execute(
        """
        select c.* from prospects p join companies c on c.id = p.company_id
         where p.organization_id = %s and p.stage = 'prioritized'
           and not exists (select 1 from company_research r where r.company_id = c.id)
         order by p.priority desc limit %s
        """,
        (org_id, limit),
    ).fetchall()
    done = 0
    for company in rows:
        facts = {k: company[k] for k in RESEARCH_FIELDS if company.get(k) not in (None, "")}
        try:
            result = claude.research(facts, settings.oferta)
        except anthropic.RateLimitError:
            log.warning("limite de taxa do Claude; pesquisa continua no próximo ciclo")
            break
        except anthropic.APIStatusError as exc:
            log.warning("Claude devolveu %s para a empresa %s", exc.status_code, company["id"])
            continue
        except anthropic.APIConnectionError:
            log.warning("sem conexão com a API do Claude")
            break
        if not result:
            continue
        grounded = [f for f in result.grounded_on if f in facts]
        conn.execute(
            """
            insert into company_research (organization_id, company_id, summary, likely_pain,
                                          suggested_approach, opening_line, grounded_on, model)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (org_id, company["id"], result.summary, result.likely_pain, result.suggested_approach,
             result.opening_line, Jsonb(grounded), claude.model),
        )
        conn.commit()
        done += 1
    return done


# ── Entrada em campanha ─────────────────────────────────────────────────────

_BEST_CONTACT = {
    "whatsapp": """
        select ct.id from contacts ct where ct.company_id = %s and ct.phone_status = 'verified'
         order by (ct.full_name is not null) desc, (ct.source = 'receita_federal_open_data') desc limit 1
    """,
    "email": """
        select ct.id from contacts ct where ct.company_id = %s and ct.email is not null
           and not ct.email_shared and ct.email_status = 'verified'
         order by (ct.full_name is not null) desc limit 1
    """,
}


def enqueue(conn: psycopg.Connection, org_id: str, settings: Settings, campaign_ids: dict[str, str]) -> dict[str, int]:
    order = [settings.envio.canal_preferido] + [c for c in ("whatsapp", "email") if c != settings.envio.canal_preferido]
    order = [c for c in order if c in campaign_ids]
    state = "pending" if settings.envio.modo == "approval_required" else "active"
    stats = {c: 0 for c in order} | {"sem_canal": 0}
    prospects = conn.execute(
        """
        select p.id, p.company_id from prospects p
         where p.organization_id = %s and p.stage = 'prioritized'
           and not exists (select 1 from campaign_contacts cc where cc.prospect_id = p.id)
         order by p.priority desc
        """,
        (org_id,),
    ).fetchall()
    for p in prospects:
        for channel in order:
            contact = conn.execute(_BEST_CONTACT[channel], (p["company_id"],)).fetchone()
            if contact:
                conn.execute(
                    """
                    insert into campaign_contacts (organization_id, campaign_id, contact_id, prospect_id,
                                                   state, next_send_at)
                    values (%s, %s, %s, %s, %s, now()) on conflict do nothing
                    """,
                    (org_id, campaign_ids[channel], contact["id"], p["id"], state),
                )
                stats[channel] += 1
                break
        else:
            stats["sem_canal"] += 1
    conn.commit()
    return stats


def approve_all(conn: psycopg.Connection, org_id: str) -> int:
    cur = conn.execute(
        "update campaign_contacts set state = 'active', next_send_at = now() "
        "where organization_id = %s and state = 'pending'",
        (org_id,),
    )
    conn.commit()
    return cur.rowcount


# ── Envio ───────────────────────────────────────────────────────────────────

def in_window(settings: Settings, now: datetime, tz: str) -> bool:
    local = now.astimezone(ZoneInfo(tz))
    j = settings.envio.janela
    return local.weekday() in j.dias and j.inicio <= local.time() <= j.fim


def sent_today(conn: psycopg.Connection, org_id: str, channel: str, now: datetime, tz: str) -> int:
    local_midnight = now.astimezone(ZoneInfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        "select count(*) as n from outreach_messages where organization_id = %s and channel = %s "
        "and direction = 'outbound' and status = 'sent' and sent_at >= %s",
        (org_id, channel, local_midnight),
    ).fetchone()
    return row["n"]


def idempotency_key(campaign_contact_id: str, step: int) -> str:
    return hashlib.sha256(f"{campaign_contact_id}:{step}".encode()).hexdigest()


def optout_url(settings: Settings, token: str) -> str:
    return f"{settings.public_url.rstrip('/')}/saida/{token}"


class Senders:
    """Agrupa os provedores para injeção em teste."""

    def __init__(self, whatsapp=None, email=None):
        self.whatsapp = whatsapp
        self.email = email


def send_due(conn: psycopg.Connection, org_id: str, settings: Settings, senders: Senders,
             now: datetime | None = None, tz: str = "America/Sao_Paulo",
             sleep: Callable[[float], None] = _time.sleep) -> dict[str, int]:
    # Sem relógio injetado, o horário é relido a cada mensagem: um lote de WhatsApp
    # com intervalos longos não pode atravessar o fim da janela.
    clock = (lambda: datetime.now(ZoneInfo(tz))) if now is None else (lambda: now)
    now = clock()
    stats = {"enviadas": 0, "simuladas": 0, "suprimidas": 0, "falhas": 0}
    if not in_window(settings, now, tz):
        log.info("fora da janela de envio")
        return stats
    # Um envio por organização por vez (worker e n8n podem disparar juntos).
    lock = f"prospector:send:{org_id}"
    if not conn.execute("select pg_try_advisory_lock(hashtext(%s)) as ok", (lock,)).fetchone()["ok"]:
        log.info("outro processo já está enviando")
        return stats
    conn.commit()
    try:
        return _send_locked(conn, org_id, settings, senders, clock, tz, sleep, stats)
    finally:
        conn.rollback()
        conn.execute("select pg_advisory_unlock(hashtext(%s))", (lock,))
        conn.commit()


def _send_locked(conn, org_id, settings, senders, clock, tz, sleep, stats) -> dict[str, int]:
    now = clock()
    dry = settings.envio.dry_run
    gap = settings.envio.intervalo_segundos
    remetente = settings.envio.remetente.model_dump()

    for channel in ("whatsapp", "email"):
        sender = getattr(senders, channel)
        cap = settings.envio.limite_diario.get(channel, 0)
        budget = cap - sent_today(conn, org_id, channel, now, tz)
        if budget <= 0 or (sender is None and not dry):
            continue
        due = conn.execute(
            """
            select cc.id as cc_id, cc.current_step, cc.prospect_id, s.subject, s.body, s.is_terminal,
                   s.delay_days, nxt.delay_days as next_delay, ct.id as contact_id, ct.full_name,
                   ct.email, ct.phone, ct.optout_token, c.*, r.opening_line
              from campaign_contacts cc
              join campaigns cp on cp.id = cc.campaign_id and cp.channel = %s and cp.status = 'active'
              join campaign_steps s on s.campaign_id = cc.campaign_id and s.step_index = cc.current_step
              left join campaign_steps nxt on nxt.campaign_id = cc.campaign_id and nxt.step_index = cc.current_step + 1
              join contacts ct on ct.id = cc.contact_id
              join companies c on c.id = ct.company_id
              left join lateral (select opening_line from company_research r where r.company_id = c.id
                                  order by generated_at desc limit 1) r on true
              left join prospects p on p.id = cc.prospect_id
             where cc.organization_id = %s and cc.state = 'active' and cc.next_send_at <= %s
             order by p.priority desc nulls last, cc.next_send_at
             limit %s
            """,
            (channel, org_id, now, budget),
        ).fetchall()

        for i, row in enumerate(due):
            now = clock()
            if not in_window(settings, now, tz):
                log.info("janela de envio terminou no meio do lote")
                return stats
            target = row["phone"] if channel == "whatsapp" else row["email"]
            if db.is_suppressed(conn, org_id, channel, target):
                conn.execute("update campaign_contacts set state = 'suppressed', stopped_reason = 'suppression_list' "
                             "where id = %s", (row["cc_id"],))
                conn.commit()
                stats["suprimidas"] += 1
                continue
            values = messages.variables(row, row, {"opening_line": row["opening_line"]}, remetente,
                                        optout_url(settings, row["optout_token"]))
            body = messages.render(row["body"], values)
            subject = messages.render(row["subject"] or "", values) or None
            key = idempotency_key(str(row["cc_id"]), row["current_step"])
            msg = conn.execute(
                """
                insert into outreach_messages (organization_id, campaign_contact_id, contact_id, step_index,
                                               channel, subject, body, personalization, idempotency_key)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (organization_id, idempotency_key) do update
                   set body = excluded.body, subject = excluded.subject, status = 'queued', error = null
                 where outreach_messages.status in ('dry_run', 'failed')
                returning id
                """,
                (org_id, row["cc_id"], row["contact_id"], row["current_step"], channel, subject, body,
                 Jsonb({k: v for k, v in values.items() if v and k != "link_saida"}), key),
            ).fetchone()
            conn.commit()
            if msg is None:
                # Já enviada antes (ex.: processo caiu depois do envio): só avança.
                _advance(conn, row, now)
                continue

            if dry:
                conn.execute("update outreach_messages set status = 'dry_run' where id = %s", (msg["id"],))
                conn.commit()
                stats["simuladas"] += 1
                log.info("[simulação] %s → %s\n%s", channel, target, body)
                continue

            try:
                if channel == "whatsapp":
                    result = sender.send_text(target, body)
                else:
                    result = sender.send(target, subject or values["empresa"], body,
                                         optout_url(settings, row["optout_token"]))
            except Exception as exc:  # noqa: BLE001 - qualquer falha de provedor vira registro, não queda do ciclo
                conn.execute("update outreach_messages set status = 'failed', error = %s where id = %s",
                             (str(exc)[:500], msg["id"]))
                conn.commit()
                stats["falhas"] += 1
                log.warning("falha no envio %s para %s: %s", channel, row["contact_id"], exc)
                continue
            conn.execute(
                "update outreach_messages set status = 'sent', sent_at = %s, provider_message_id = %s where id = %s",
                (now, result.provider_message_id, msg["id"]),
            )
            _advance(conn, row, now)
            stats["enviadas"] += 1
            if channel == "whatsapp" and i < len(due) - 1:
                sleep(random.uniform(gap.get("min", 60), gap.get("max", 180)))
    return stats


def _advance(conn: psycopg.Connection, row: dict, now: datetime) -> None:
    if row["is_terminal"] or row["next_delay"] is None:
        conn.execute("update campaign_contacts set state = 'completed', current_step = current_step + 1, "
                     "next_send_at = null where id = %s", (row["cc_id"],))
    else:
        wait = timedelta(days=max(0, row["next_delay"] - row["delay_days"]))
        conn.execute("update campaign_contacts set current_step = current_step + 1, next_send_at = %s "
                     "where id = %s", (now + wait, row["cc_id"]))
    conn.execute("update prospects set stage = 'contacted', last_touch_at = %s "
                 "where id = %s and stage in ('discovered','researched','prioritized')",
                 (now, row["prospect_id"]))
    conn.commit()
