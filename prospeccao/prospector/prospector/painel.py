"""Painel local: o que o robô está fazendo, num retrato só para a tela do dono."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

from . import outreach
from .config import Settings

HTML = Path(__file__).with_name("painel.html")


def receita_status(data_dir: Path) -> dict:
    """Situação da base da Receita pelas marcas que o download e a carga deixam na pasta do mês."""
    months = sorted(p for p in (data_dir / "receita").glob("????-??") if p.is_dir())
    for folder in reversed(months):
        if (folder / ".carregado").exists():
            return {"estado": "carregada", "mes": folder.name}
    if not months:
        return {"estado": "aguardando", "mes": None}
    latest = months[-1]
    return {"estado": "carregando" if (latest / ".completo").exists() else "baixando", "mes": latest.name}


def snapshot(conn: psycopg.Connection, settings: Settings, org_id: str,
             whatsapp: bool | None, now: datetime | None = None) -> dict:
    """`whatsapp`: True pareado, False desconectado, None sem Evolution configurada."""
    org = conn.execute("select display_name, timezone from organizations where id = %s", (org_id,)).fetchone()
    tz = org["timezone"]
    now = now or datetime.now(ZoneInfo(tz))
    local_midnight = now.astimezone(ZoneInfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0)

    funil = conn.execute("select * from v_funil where organizacao = %s", (settings.organizacao.slug,)).fetchone()
    funil = {k: v for k, v in dict(funil or {}).items() if k != "organizacao"}
    funil["simuladas_hoje"] = conn.execute(
        "select count(*) as n from outreach_messages where organization_id = %s and direction = 'outbound' "
        "and status = 'dry_run' and created_at >= %s",
        (org_id, local_midnight),
    ).fetchone()["n"]

    leads = conn.execute(
        """
        select coalesce(nullif(c.nome_fantasia, ''), c.razao_social) as empresa, c.municipio,
               l.origin_channel as canal, l.first_message as mensagem, l.created_at as quando
          from leads l left join companies c on c.id = l.company_id
         where l.organization_id = %s
         order by l.created_at desc limit 8
        """,
        (org_id,),
    ).fetchall()

    mensagens = conn.execute(
        """
        select coalesce(nullif(c.nome_fantasia, ''), c.razao_social) as empresa, m.channel as canal,
               m.body as texto, m.status, coalesce(m.sent_at, m.created_at) as quando
          from outreach_messages m
          join contacts ct on ct.id = m.contact_id
          left join companies c on c.id = ct.company_id
         where m.organization_id = %s and m.direction = 'outbound' and m.status in ('sent', 'dry_run', 'failed')
         order by coalesce(m.sent_at, m.created_at) desc limit 6
        """,
        (org_id,),
    ).fetchall()

    j = settings.envio.janela
    return {
        "organizacao": org["display_name"],
        "atualizado": now.isoformat(),
        "simulacao": settings.envio.dry_run,
        "janela": {"aberta": outreach.in_window(settings, now, tz), "dias": j.dias,
                   "inicio": j.inicio.strftime("%H:%M"), "fim": j.fim.strftime("%H:%M")},
        "limites": settings.envio.limite_diario,
        "canais": {
            "whatsapp": {True: "conectado", False: "desconectado", None: "sem_configuracao"}[whatsapp],
            "email": "configurado" if settings.smtp_host and settings.smtp_user else "sem_configuracao",
        },
        "receita": receita_status(settings.data_dir),
        "funil": funil,
        "leads": [dict(r) for r in leads],
        "mensagens": [dict(r) for r in mensagens],
    }
