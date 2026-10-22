"""Etapas do ciclo de prospecção, compartilhadas pela CLI, pelo daemon e pela API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import psycopg

from . import db, inbound, llm, maps, outreach, receita, scoring, verify
from .config import Settings
from .providers import EvolutionClient, SmtpSender

log = logging.getLogger(__name__)


@dataclass
class Context:
    settings: Settings
    conn: psycopg.Connection
    org_id: str = ""
    icp_id: str = ""
    campaign_ids: dict[str, str] = field(default_factory=dict)

    @classmethod
    def open(cls, settings: Settings, conn: psycopg.Connection) -> "Context":
        ctx = cls(settings, conn)
        ctx.org_id = db.ensure_org(conn, settings)
        ctx.icp_id = db.ensure_icp(conn, ctx.org_id, settings)
        ctx.campaign_ids = db.ensure_campaigns(conn, ctx.org_id, ctx.icp_id, settings)
        return ctx

    @cached_property
    def claude(self) -> llm.Claude | None:
        return llm.build(self.settings.anthropic_model, self.settings.llm_enabled)

    @cached_property
    def evolution(self) -> EvolutionClient | None:
        s = self.settings
        return EvolutionClient(s.evolution_url, s.evolution_apikey, s.evolution_instance) if s.evolution_apikey else None

    @cached_property
    def whatsapp(self) -> EvolutionClient | None:
        """Evolution só conta como canal quando o chip está pareado e online."""
        if self.evolution and self.evolution.is_connected():
            return self.evolution
        if self.evolution:
            log.warning("WhatsApp desconectado: rode 'prospector whatsapp-conectar' e leia o QR code")
        return None

    @cached_property
    def smtp(self) -> SmtpSender | None:
        s = self.settings
        if not s.smtp_host or not s.smtp_user:
            return None
        return SmtpSender(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password,
                          s.smtp_from or s.smtp_user, s.envio.remetente.nome)

    def notify_owner(self, text: str) -> None:
        owner = self.settings.envio.aviso_dono_whatsapp
        if owner and self.whatsapp and not self.settings.envio.dry_run:
            self.whatsapp.send_text(owner, text, typing_ms=0)
        else:
            log.info("AVISO DE LEAD:\n%s", text)


def whatsapp_webhook(settings: Settings) -> str:
    """Endereço que a Evolution chama a cada mensagem recebida no chip."""
    return f"{settings.webhook_base_url.rstrip('/')}/webhooks/evolution?token={settings.api_token}"


def receita_baixar(ctx: Context) -> dict:
    return {"pasta": str(receita.download(ctx.settings))}


def receita_carregar(ctx: Context, pasta: str | None = None) -> dict:
    base = ctx.settings.data_dir / "receita"
    folder = Path(pasta) if pasta else max((p for p in base.iterdir() if (p / ".completo").exists()), default=None)
    if folder is None:
        raise RuntimeError(f"nenhum download completo em {base}; rode 'receita-baixar' antes")
    sel = receita.select(folder, ctx.settings.icp.filtros)
    n = receita.store(ctx.conn, ctx.org_id, sel, ctx.settings.receita_share_token)
    novos = scoring.discover(ctx.conn, ctx.org_id, ctx.icp_id)
    return {"empresas": n, "novos_prospects": novos, "mes": sel.month}


def pontuar(ctx: Context) -> dict:
    scoring.discover(ctx.conn, ctx.org_id, ctx.icp_id)
    return scoring.run(ctx.conn, ctx.org_id, ctx.icp_id, ctx.settings.icp)


def maps_enriquecer(ctx: Context) -> dict:
    if not ctx.settings.enriquecimento.google_maps:
        return {"desligado": True}
    client = maps.GmapsClient(ctx.settings.gmaps_url)
    collected = maps.collect(ctx.conn, ctx.org_id, client)
    created = maps.submit(ctx.conn, ctx.org_id, ctx.settings, client)
    return collected | {"jobs_criados": created}


def verificar(ctx: Context) -> dict:
    out = {}
    s = ctx.settings
    if s.reacher_url:
        out["email"] = verify.emails(ctx.conn, ctx.org_id, s, verify.ReacherClient(s.reacher_url, s.reacher_secret))
    else:
        out["email_dns"] = verify.emails_mx(ctx.conn, ctx.org_id)
    if ctx.whatsapp:
        out["whatsapp"] = verify.whatsapp(ctx.conn, ctx.org_id, ctx.whatsapp)
    return out


def pesquisar(ctx: Context) -> dict:
    return {"pesquisadas": outreach.research(ctx.conn, ctx.org_id, ctx.settings, ctx.claude)}


def enfileirar(ctx: Context) -> dict:
    return outreach.enqueue(ctx.conn, ctx.org_id, ctx.settings, ctx.campaign_ids)


def enviar(ctx: Context) -> dict:
    senders = outreach.Senders(whatsapp=ctx.whatsapp, email=ctx.smtp)
    return outreach.send_due(ctx.conn, ctx.org_id, ctx.settings, senders)


def caixa_de_entrada(ctx: Context) -> dict:
    s = ctx.settings
    # O .env.example já traz o host do Gmail; sem usuário, o e-mail não foi configurado.
    if not s.imap_host or not s.imap_user:
        return {"desligado": True}
    return inbound.poll_imap(ctx.conn, ctx.org_id, ctx.claude, s.imap_host, s.imap_user, s.imap_password,
                             notify=ctx.notify_owner)


def funil(ctx: Context) -> dict:
    row = ctx.conn.execute("select * from v_funil where organizacao = %s", (ctx.settings.organizacao.slug,)).fetchone()
    return dict(row or {})


STEPS = {
    "receita-baixar": receita_baixar,
    "receita-carregar": receita_carregar,
    "pontuar": pontuar,
    "maps": maps_enriquecer,
    "verificar": verificar,
    "pesquisar": pesquisar,
    "enfileirar": enfileirar,
    "enviar": enviar,
    "caixa": caixa_de_entrada,
    "funil": funil,
}

# Ciclo diário. A carga da Receita fica de fora: é mensal e pesada.
CYCLE = ["maps", "pontuar", "verificar", "pesquisar", "enfileirar", "caixa", "enviar"]


def run_step(ctx: Context, name: str) -> dict:
    try:
        result = STEPS[name](ctx)
    except Exception:
        ctx.conn.rollback()
        raise
    log.info("%s: %s", name, result)
    return result


def cycle(ctx: Context) -> dict:
    results = {}
    for name in CYCLE:
        try:
            results[name] = run_step(ctx, name)
        except Exception as exc:  # noqa: BLE001 - uma etapa com problema não para as outras
            log.exception("etapa %s falhou", name)
            results[name] = {"erro": str(exc)}
    return results
