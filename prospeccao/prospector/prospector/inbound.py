"""Respostas e descadastros (A8 / WF-011).

Toda resposta para a sequência daquele contato. Depois, conforme a
classificação:
  optout          → suppression_list (hash) e nunca mais é contatado
  interested      → lead + aviso imediato ao dono no WhatsApp
  question        → lead + aviso (pergunta não respondida esfria rápido)
  not_interested  → prospect desqualificado
"""

from __future__ import annotations

import email
import imaplib
import logging
import re
import unicodedata
from email.utils import parseaddr

import anthropic
import psycopg
from psycopg.types.json import Jsonb

from . import db, messages, phones
from .llm import Claude

log = logging.getLogger(__name__)

# Termos terminados em "*" casam por prefixo; os demais, por palavra inteira.
_OPTOUT = ["sair", "parar", "pare", "remover", "remova", "descadastr*", "nao quero receber", "nao mande",
           "nao me mande", "para de mandar", "pare de mandar", "bloquear", "denunciar", "spam", "engano",
           "numero errado", "unsubscribe", "stop"]
_NOT_INTERESTED = ["nao quero", "nao tenho interesse", "sem interesse", "nao temos interesse", "ja temos", "ja tenho",
                   "nao precisamos", "nao preciso", "nao e o momento", "agora nao"]
_INTERESTED = ["tenho interesse", "temos interesse", "quero", "pode sim", "podemos", "vamos conversar",
               "agendar", "reuniao", "horario", "proposta", "orcamento", "quanto custa", "valor", "preco",
               "me liga", "pode ligar", "pode me ligar", "sim"]


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def _has(text: str, terms: list[str]) -> bool:
    for term in terms:
        if term.endswith("*"):
            pattern = rf"(^|\W){re.escape(term[:-1])}"
        else:
            pattern = rf"(^|\W){re.escape(term)}($|\W)"
        if re.search(pattern, text):
            return True
    return False


def classify_keywords(reply: str) -> str:
    t = _plain(reply)
    if not t:
        return "other"
    if _has(t, _OPTOUT):
        return "optout"
    if _has(t, _NOT_INTERESTED):
        return "not_interested"
    if _has(t, _INTERESTED):
        return "interested"
    if "?" in reply:
        return "question"
    return "other"


def classify(claude: Claude | None, our_message: str | None, reply: str) -> tuple[str, str]:
    keyword = classify_keywords(reply)
    # Descadastro explícito não depende de modelo: é decidido por regra, sempre.
    if keyword == "optout" or not claude:
        return keyword, "palavras-chave"
    try:
        result = claude.classify(our_message, reply)
    except anthropic.APIError as exc:
        log.warning("classificação pelo Claude falhou (%s); usando palavras-chave", exc)
        return keyword, "palavras-chave"
    return (result.label, "claude") if result else (keyword, "palavras-chave")


def _find_contact(conn: psycopg.Connection, org_id: str, *, phone: str | None = None,
                  jid: str | None = None, email_addr: str | None = None) -> dict | None:
    if email_addr:
        return conn.execute(
            "select * from contacts where organization_id = %s and lower(email) = lower(%s) "
            "order by updated_at desc limit 1",
            (org_id, email_addr),
        ).fetchone()
    return conn.execute(
        "select * from contacts where organization_id = %s and (whatsapp_jid = %s or phone = %s) "
        "order by (whatsapp_jid = %s) desc limit 1",
        (org_id, jid, phone, jid),
    ).fetchone()


def handle_reply(conn: psycopg.Connection, org_id: str, claude: Claude | None, contact: dict,
                 channel: str, text: str, provider_id: str | None, notify=None) -> str:
    last = conn.execute(
        "select body, campaign_contact_id from outreach_messages where contact_id = %s and direction = 'outbound' "
        "order by created_at desc limit 1",
        (contact["id"],),
    ).fetchone()
    label, method = classify(claude, last["body"] if last else None, text)
    key = f"in:{provider_id}" if provider_id else f"in:{contact['id']}:{db.value_hash(text)}"
    inserted = conn.execute(
        """
        insert into outreach_messages (organization_id, campaign_contact_id, contact_id, channel, direction,
                                       provider_message_id, body, status, classification, replied_at,
                                       idempotency_key, personalization)
        values (%s, %s, %s, %s, 'inbound', %s, %s, 'received', %s, now(), %s, %s)
        on conflict (organization_id, idempotency_key) do nothing returning id
        """,
        (org_id, last["campaign_contact_id"] if last else None, contact["id"], channel, provider_id, text,
         label, key, Jsonb({"metodo": method})),
    ).fetchone()
    if inserted is None:
        conn.commit()
        return label  # webhook repetido

    conn.execute(
        "update campaign_contacts set state = %s, stopped_reason = %s where contact_id = %s and state in ('active','pending')",
        ("suppressed" if label == "optout" else "replied", f"reply:{label}", contact["id"]),
    )
    prospect = conn.execute("select id from prospects where company_id = %s", (contact["company_id"],)).fetchone()
    if label == "optout":
        for ch, value in (("whatsapp", contact.get("phone")), ("email", contact.get("email"))):
            if value:
                db.suppress(conn, org_id, ch, value, "opt_out")
        conn.execute("update contacts set consent_status = 'revoked' where id = %s", (contact["id"],))
        if prospect:
            conn.execute("update prospects set stage = 'disqualified' where id = %s", (prospect["id"],))
    elif label == "not_interested":
        if prospect:
            conn.execute("update prospects set stage = 'disqualified' where id = %s", (prospect["id"],))
    else:
        if prospect:
            conn.execute("update prospects set stage = 'engaged', last_touch_at = now() where id = %s",
                         (prospect["id"],))
        if label in ("interested", "question"):
            lead = conn.execute(
                """
                insert into leads (organization_id, company_id, contact_id, prospect_id, origin_channel, first_message)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (organization_id, contact_id) do nothing returning id
                """,
                (org_id, contact["company_id"], contact["id"], prospect["id"] if prospect else None, channel, text),
            ).fetchone()
            if lead and notify:
                company = conn.execute("select razao_social, nome_fantasia, municipio, uf from companies where id = %s",
                                       (contact["company_id"],)).fetchone()
                try:
                    notify(_lead_alert(company, contact, channel, label, text))
                    conn.execute("update leads set notified_at = now() where id = %s", (lead["id"],))
                except Exception as exc:  # noqa: BLE001 - aviso falho não pode perder o lead
                    log.warning("não consegui avisar o dono do lead: %s", exc)
    db.audit(conn, org_id, f"reply.{label}", "contact", str(contact["id"]), {"canal": channel})
    conn.commit()
    return label


def _lead_alert(company: dict, contact: dict, channel: str, label: str, text: str) -> str:
    nome = messages.company_name(company)
    quem = contact.get("full_name") or "contato"
    canal = contact.get("phone") if channel == "whatsapp" else contact.get("email")
    tipo = "QUER CONVERSAR" if label == "interested" else "FEZ UMA PERGUNTA"
    return (f"🔥 Lead novo — {tipo}\n{nome} ({messages.title(company.get('municipio') or '')}/{company.get('uf')})\n"
            f"{quem} · {channel}: {canal}\n\n\"{text[:400]}\"")


# ── WhatsApp (webhook do Evolution) ─────────────────────────────────────────

def _text_of(message: dict) -> str:
    if not message:
        return ""
    return (message.get("conversation")
            or (message.get("extendedTextMessage") or {}).get("text")
            or (message.get("imageMessage") or {}).get("caption")
            or "")


def handle_evolution(conn: psycopg.Connection, org_id: str, claude: Claude | None, payload: dict, notify=None) -> str | None:
    event = (payload.get("event") or "").lower().replace("_", ".")
    if event != "messages.upsert":
        return None
    data = payload.get("data") or {}
    items = data if isinstance(data, list) else [data]
    result = None
    for item in items:
        key = item.get("key") or {}
        if key.get("fromMe"):
            continue
        jid = key.get("remoteJid") or ""
        if jid.endswith("@lid") and key.get("remoteJidAlt"):
            jid = key["remoteJidAlt"]
        if jid.endswith("@g.us"):
            continue  # grupo
        phone = phones.parse(jid.split("@")[0])
        contact = _find_contact(conn, org_id, phone=phone.e164 if phone else None, jid=jid)
        if not contact:
            continue
        text = _text_of(item.get("message") or {})
        if text:
            result = handle_reply(conn, org_id, claude, contact, "whatsapp", text, key.get("id"), notify)
    return result


# ── Descadastro por link ────────────────────────────────────────────────────

def optout_by_token(conn: psycopg.Connection, token: str) -> bool:
    contact = conn.execute("select * from contacts where optout_token = %s", (token,)).fetchone()
    if not contact:
        return False
    org_id = str(contact["organization_id"])
    for ch, value in (("whatsapp", contact.get("phone")), ("email", contact.get("email"))):
        if value:
            db.suppress(conn, org_id, ch, value, "opt_out")
    conn.execute("update contacts set consent_status = 'revoked' where id = %s", (contact["id"],))
    conn.execute("update campaign_contacts set state = 'suppressed', stopped_reason = 'optout_link' "
                 "where contact_id = %s and state in ('active','pending')", (contact["id"],))
    db.audit(conn, org_id, "optout.link", "contact", str(contact["id"]))
    conn.commit()
    return True


# ── E-mail (IMAP) ───────────────────────────────────────────────────────────

def _body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")


def strip_quoted(text: str) -> str:
    """Remove o histórico citado ("Em ... escreveu:", linhas com '>')."""
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*>", line) or re.match(r"^\s*(Em|On) .+(escreveu|wrote):\s*$", line):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def poll_imap(conn: psycopg.Connection, org_id: str, claude: Claude | None, host: str, user: str,
              password: str, notify=None) -> dict[str, int]:
    stats = {"respostas": 0, "bounces": 0, "ignorados": 0}
    box = imaplib.IMAP4_SSL(host)
    try:
        box.login(user, password)
        box.select("INBOX")
        _, ids = box.search(None, "UNSEEN")
        for num in ids[0].split():
            _, parts = box.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(parts[0][1])
            sender = parseaddr(msg.get("From", ""))[1].lower()
            body = _body(msg)
            if sender.startswith(("mailer-daemon", "postmaster")):
                for addr in set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", body)):
                    contact = _find_contact(conn, org_id, email_addr=addr)
                    if contact:
                        db.suppress(conn, org_id, "email", addr, "bounce")
                        conn.execute("update contacts set email_status = 'unverified' where id = %s", (contact["id"],))
                        conn.execute("update campaign_contacts set state = 'bounced' where contact_id = %s "
                                     "and state = 'active'", (contact["id"],))
                        stats["bounces"] += 1
                conn.commit()
                continue
            contact = _find_contact(conn, org_id, email_addr=sender)
            if not contact:
                stats["ignorados"] += 1
                continue
            handle_reply(conn, org_id, claude, contact, "email", strip_quoted(body),
                         msg.get("Message-ID"), notify)
            stats["respostas"] += 1
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001
            pass
    return stats
