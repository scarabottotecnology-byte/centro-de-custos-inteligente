"""ICP Score (WF-006).

Regra de docs/03 §3.5: cada critério só conta se houver dado para avaliá-lo, e
o score é normalizado pelo peso disponível. `coverage` diz quanto do ICP foi de
fato avaliado — um 90 com 40% de cobertura vale menos que um 90 com 95%.
"""

from __future__ import annotations

import math
from datetime import date

import psycopg
from psycopg.types.json import Jsonb

from .config import Icp

PORTE_NOTA = {"DEMAIS": 1.0, "EPP": 0.7, "MICRO": 0.35}
MIN_COVERAGE = 0.5


def _segmento(cnae: str | None, segmentos: dict[str, float]) -> float | None:
    if not segmentos:
        return None
    if not cnae:
        return 0.0
    best = max((p for p in segmentos if cnae.startswith(p)), key=len, default=None)
    return segmentos[best] if best else 0.0


def evaluate(company: dict, contact: dict, icp: Icp, today: date | None = None) -> dict[str, tuple]:
    """Devolve critério -> (nota 0..1 ou None, valor observado, motivo)."""
    today = today or date.today()
    out: dict[str, tuple] = {}

    porte = company.get("porte")
    nota = PORTE_NOTA.get(porte or "")
    out["porte"] = (nota, porte, "porte da Receita" if nota is not None else "porte não informado")

    cap = company.get("capital_social")
    if cap and float(cap) > 0:
        out["capital_social"] = (min(1.0, math.sqrt(float(cap) / icp.capital_social_ideal)), float(cap),
                                 f"capital social vs. ideal de {icp.capital_social_ideal:,.0f}")
    else:
        out["capital_social"] = (None, None, "capital social não declarado")

    opened = company.get("data_abertura")
    if opened:
        anos = (today - opened).days / 365.25
        out["idade"] = (min(1.0, anos / icp.idade_ideal_anos), round(anos, 1), "anos desde a abertura")
    else:
        out["idade"] = (None, None, "data de abertura ausente")

    seg = _segmento(company.get("cnae_principal"), icp.segmentos)
    out["segmento"] = (seg, company.get("cnae_principal"),
                       "CNAE no mapa de segmentos" if seg else "CNAE fora dos segmentos prioritários"
                       if seg == 0 else "segmentos não configurados")

    if company.get("maps_checked_at"):
        nota = 0.0
        if company.get("website"):
            nota += 0.5
        if company.get("google_rating"):
            nota += 0.25
        if (company.get("google_reviews") or 0) >= 10:
            nota += 0.25
        out["presenca_digital"] = (nota, {"site": company.get("website"),
                                          "avaliacoes": company.get("google_reviews")},
                                   "Google Maps e site")
    else:
        out["presenca_digital"] = (None, None, "ainda não enriquecido pelo Google Maps")

    if contact.get("mobile") or contact.get("email_own"):
        nota, motivo = 1.0, "celular ou e-mail próprio"
    elif contact.get("landline"):
        nota, motivo = 0.5, "apenas telefone fixo"
    elif contact.get("email_shared"):
        nota, motivo = 0.2, "apenas e-mail do escritório contábil"
    else:
        nota, motivo = 0.0, "sem canal de contato"
    out["contato_direto"] = (nota, {k: v for k, v in contact.items() if v}, motivo)
    return out


def score(company: dict, contact: dict, icp: Icp, today: date | None = None) -> tuple[int, float, dict]:
    evaluated = evaluate(company, contact, icp, today)
    total_weight = sum(icp.pesos.values()) or 1
    used_weight = 0.0
    points = 0.0
    breakdown = {}
    for key, peso in icp.pesos.items():
        nota, valor, motivo = evaluated.get(key, (None, None, "critério desconhecido"))
        contrib = None
        if nota is not None:
            used_weight += peso
            points += peso * nota
            contrib = round(peso * nota, 2)
        breakdown[key] = {"peso": peso, "nota": None if nota is None else round(nota, 3),
                          "valor": valor, "contribuicao": contrib, "motivo": motivo}
    value = round(100 * points / used_weight) if used_weight else 0
    return value, round(used_weight / total_weight, 3), breakdown


_CONTACT_SUMMARY = """
  select company_id,
         bool_or(phone_is_mobile and phone_status <> 'unverified')               as mobile,
         bool_or(phone is not null and not coalesce(phone_is_mobile, false))     as landline,
         bool_or(email is not null and not email_shared and email_status <> 'unverified') as email_own,
         bool_or(email is not null and email_shared)                             as email_shared
    from contacts where organization_id = %s group by company_id
"""


def discover(conn: psycopg.Connection, org_id: str, icp_id: str) -> int:
    """Toda empresa carregada vira prospect (estágio 'discovered')."""
    cur = conn.execute(
        """
        insert into prospects (organization_id, company_id, icp_profile_id)
        select c.organization_id, c.id, %s from companies c
         where c.organization_id = %s
        on conflict (organization_id, company_id) do nothing
        """,
        (icp_id, org_id),
    )
    conn.commit()
    return cur.rowcount


def run(conn: psycopg.Connection, org_id: str, icp_id: str, icp: Icp) -> dict[str, int]:
    contacts = {r["company_id"]: r for r in conn.execute(_CONTACT_SUMMARY, (org_id,)).fetchall()}
    rows = conn.execute(
        """
        select p.id as prospect_id, p.stage, last.score as last_score, last.breakdown as last_breakdown, c.*
          from prospects p
          join companies c on c.id = p.company_id
          left join lateral (
            select s.score, s.breakdown from prospect_scores s
             where s.prospect_id = p.id and s.icp_profile_id = %s
             order by s.computed_at desc limit 1
          ) last on true
         where p.organization_id = %s and p.stage in ('discovered','researched','prioritized')
        """,
        (icp_id, org_id),
    ).fetchall()
    stats = {"pontuados": 0, "priorizados": 0}
    with conn.cursor() as cur:
        for row in rows:
            contact = dict(contacts.get(row["id"], {}))
            contact.pop("company_id", None)
            value, coverage, breakdown = score(row, contact, icp)
            # Histórico só quando algo mudou; rodar todo dia não deve multiplicar linhas.
            if row["last_score"] != value or row["last_breakdown"] != breakdown:
                cur.execute(
                    "insert into prospect_scores (organization_id, prospect_id, icp_profile_id, score, coverage, breakdown) "
                    "values (%s, %s, %s, %s, %s, %s)",
                    (org_id, row["prospect_id"], icp_id, value, coverage, Jsonb(breakdown)),
                )
            prioritized = value >= icp.limiar_priorizacao and coverage >= MIN_COVERAGE
            stage = "prioritized" if prioritized else ("researched" if row["stage"] == "researched" else "discovered")
            cur.execute("update prospects set priority = %s, stage = %s where id = %s",
                        (value, stage, row["prospect_id"]))
            stats["pontuados"] += 1
            stats["priorizados"] += int(prioritized)
    conn.commit()
    return stats
