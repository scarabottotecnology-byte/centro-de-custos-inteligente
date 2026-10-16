"""Enriquecimento pelo Google Maps via gosom/google-maps-scraper (API REST local).

Cada empresa vira uma linha de busca "nome cidade UF #!#<company_id>". O gosom
devolve o <company_id> na coluna input_id, o que permite casar resultado com
empresa sem adivinhação. Entre os lugares retornados, aceita-se só o que bate
pelo nome (similaridade) ou pelo CEP — um telefone de outra empresa é pior que
nenhum telefone.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

import httpx
import psycopg

from . import phones
from .config import Settings

log = logging.getLogger(__name__)
SOURCE = "google_maps"
MIN_SIMILARITY = 0.72
# Job sem nenhuma linha quase sempre é bloqueio do Google, não ausência das empresas.
MAX_ATTEMPTS = 3
_STOPWORDS = {"LTDA", "ME", "EPP", "EIRELI", "SA", "S", "A", "DE", "DA", "DO", "DOS", "DAS", "E",
              "COMERCIO", "SERVICOS", "INDUSTRIA", "CIA", "COMPANHIA", "SLU", "SOCIEDADE", "LIMITADA"}


def _tokens(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().upper()
    words = [w for w in re.split(r"[^A-Z0-9]+", s) if w and w not in _STOPWORDS]
    return " ".join(words)


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    if ta in tb or tb in ta:
        return 1.0
    return SequenceMatcher(None, ta, tb).ratio()


def query_for(company: dict) -> str:
    name = company.get("nome_fantasia") or company["razao_social"]
    return f"{name} {company.get('municipio') or ''} {company.get('uf') or ''}".strip()


def _cep(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")[:8]


def best_match(company: dict, places: list[dict]) -> dict | None:
    names = [n for n in (company.get("nome_fantasia"), company.get("razao_social")) if n]
    cep = _cep(company.get("cep"))
    best, best_score = None, 0.0
    for place in places:
        sim = max((similarity(n, place.get("title", "")) for n in names), default=0.0)
        addr = place.get("complete_address") or {}
        if isinstance(addr, str):
            try:
                addr = json.loads(addr) if addr else {}
            except json.JSONDecodeError:
                addr = {}
        same_cep = bool(cep) and _cep(addr.get("postal_code")) == cep
        value = sim + (0.3 if same_cep else 0.0)
        if (sim >= MIN_SIMILARITY or (same_cep and sim >= 0.4)) and value > best_score:
            best, best_score = place, value
    return best


def parse_csv(text: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        grouped.setdefault(row.get("input_id", ""), []).append(row)
    return grouped


class GmapsClient:
    def __init__(self, base_url: str, timeout: float = 30):
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def create_job(self, name: str, lines: list[str], *, email: bool, max_time: int) -> str:
        resp = self.http.post("/api/v1/jobs", json={
            "name": name, "keywords": lines, "lang": "pt", "zoom": 15, "depth": 1,
            "email": email, "max_time": max_time,
        })
        resp.raise_for_status()
        return resp.json()["id"]

    def status(self, job_id: str) -> str:
        resp = self.http.get(f"/api/v1/jobs/{job_id}")
        resp.raise_for_status()
        return resp.json().get("Status", "")

    def results(self, job_id: str) -> str:
        resp = self.http.get(f"/api/v1/jobs/{job_id}/download")
        resp.raise_for_status()
        return resp.text


def submit(conn: psycopg.Connection, org_id: str, settings: Settings, client: GmapsClient) -> int:
    """Cria jobs para os prospects priorizados (ou quase) ainda não enriquecidos."""
    pending = conn.execute(
        """
        select c.id, c.razao_social, c.nome_fantasia, c.municipio, c.uf from companies c
          join prospects p on p.company_id = c.id
         where c.organization_id = %s and c.maps_checked_at is null
           and p.stage in ('discovered','researched','prioritized')
           and not exists (select 1 from enrichment_jobs j
                            where j.status in ('pending','working') and c.id = any(j.company_ids))
           and (select count(*) from enrichment_jobs j
                 where j.status in ('failed','empty') and c.id = any(j.company_ids)) < %s
         order by p.priority desc nulls last
         limit %s
        """,
        (org_id, MAX_ATTEMPTS, settings.enriquecimento.lote * 4),
    ).fetchall()
    created = 0
    lote = settings.enriquecimento.lote
    for i in range(0, len(pending), lote):
        chunk = pending[i:i + lote]
        lines = [f"{query_for(c)} #!#{c['id']}" for c in chunk]
        job_id = client.create_job(f"prospeccao-{org_id[:8]}-{i}", lines,
                                   email=settings.enriquecimento.extrair_emails_do_site,
                                   max_time=settings.enriquecimento.tempo_max_job_segundos)
        conn.execute(
            "insert into enrichment_jobs (organization_id, provider, external_id, company_ids) values (%s,%s,%s,%s)",
            (org_id, "gmaps", job_id, [c["id"] for c in chunk]),
        )
        created += 1
    conn.commit()
    return created


def collect(conn: psycopg.Connection, org_id: str, client: GmapsClient) -> dict[str, int]:
    stats = {"jobs_concluidos": 0, "empresas_casadas": 0, "sem_resultado": 0}
    jobs = conn.execute(
        "select * from enrichment_jobs where organization_id = %s and provider = 'gmaps' "
        "and status in ('pending','working')",
        (org_id,),
    ).fetchall()
    for job in jobs:
        status = client.status(job["external_id"])
        if status in ("pending", "working"):
            conn.execute("update enrichment_jobs set status = %s where id = %s", (status, job["id"]))
            continue
        grouped = parse_csv(client.results(job["external_id"])) if status == "ok" else {}
        if not grouped:
            final = "failed" if status != "ok" else "empty"
            attempts = conn.execute(
                "select count(*) as n from enrichment_jobs where status in ('failed','empty') "
                "and company_ids && %s", (job["company_ids"],),
            ).fetchone()["n"] + 1
            conn.execute("update enrichment_jobs set status = %s, finished_at = now() where id = %s",
                         (final, job["id"]))
            if attempts >= MAX_ATTEMPTS:
                conn.execute("update companies set maps_checked_at = now() where id = any(%s)", (job["company_ids"],))
            log.warning("job %s do Maps voltou sem resultado (%s, tentativa %d)", job["external_id"], final, attempts)
            stats["jobs_vazios"] = stats.get("jobs_vazios", 0) + 1
            continue
        companies = conn.execute("select * from companies where id = any(%s)", (job["company_ids"],)).fetchall()
        for company in companies:
            place = best_match(company, grouped.get(str(company["id"]), []))
            if place:
                apply_place(conn, org_id, company, place)
                stats["empresas_casadas"] += 1
            else:
                stats["sem_resultado"] += 1
            conn.execute("update companies set maps_checked_at = now() where id = %s", (company["id"],))
        conn.execute("update enrichment_jobs set status = %s, finished_at = now() where id = %s",
                     (status, job["id"]))
        stats["jobs_concluidos"] += 1
    conn.commit()
    return stats


def _num(value: str | None, cast=float):
    try:
        return cast(float(value)) if value not in (None, "") else None
    except ValueError:
        return None


def apply_place(conn: psycopg.Connection, org_id: str, company: dict, place: dict) -> None:
    website = (place.get("website") or "").strip() or None
    conn.execute(
        """
        update companies set website = coalesce(website, %s), google_place_id = %s,
               google_rating = %s, google_reviews = %s, google_category = %s, updated_at = now()
         where id = %s
        """,
        (website, place.get("place_id") or None, _num(place.get("review_rating")),
         _num(place.get("review_count"), int), place.get("category") or None, company["id"]),
    )
    link = place.get("link") or None
    phone = phones.parse(place.get("phone"))
    if phone:
        conn.execute(
            """
            insert into contacts (organization_id, company_id, phone, phone_is_mobile, source, source_url)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (company_id, phone) where phone is not null do nothing
            """,
            (org_id, company["id"], phone.e164, phone.is_mobile, SOURCE, link),
        )
    emails = [e.strip().lower() for e in (place.get("emails") or "").split(",") if "@" in e]
    for email in emails[:3]:
        conn.execute(
            """
            insert into contacts (organization_id, company_id, email, source, source_url)
            values (%s, %s, %s, %s, %s)
            on conflict (company_id, lower(email)) where email is not null do nothing
            """,
            (org_id, company["id"], email, "google_maps_website", website or link),
        )
