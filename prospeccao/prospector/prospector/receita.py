"""Carga dos Dados Abertos do CNPJ (Receita Federal).

Download: a Receita publica os arquivos num compartilhamento Nextcloud. Desde
12/10/2026 a listagem é por WebDAV (PROPFIND) com o token do compartilhamento
como usuário — o mesmo caminho que o rictom/cnpj-sqlite e o
caiopizzol/cnpj-data-pipeline usam. O token fica em RECEITA_SHARE_TOKEN porque
a Receita já o trocou antes.

Carga: em vez de importar os ~60 milhões de estabelecimentos, o ETL aplica os
filtros do ICP já na leitura do arquivo e só grava o que interessa. Quatro
passadas, cada uma restrita ao conjunto da anterior:

    Estabelecimentos (UF, município, CNAE, situação, matriz, idade)
      → Empresas (porte, capital social, razão social, natureza jurídica)
      → Simples (opção pelo Simples e MEI)
      → Sócios (nome do decisor)
"""

from __future__ import annotations

import csv
import io
import logging
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator
from xml.etree import ElementTree

import httpx
import psycopg

from . import cnpj as cnpjlib
from . import phones
from .config import Filtros, Settings

log = logging.getLogger(__name__)

BASE = "https://arquivos.receitafederal.gov.br"
SOURCE = "receita_federal_open_data"
DAV_NS = {"d": "DAV:"}

# Layout oficial (dicionário de dados da Receita, cnpj-metadados.pdf).
ESTABELECIMENTO = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial", "nome_fantasia",
    "situacao", "data_situacao", "motivo_situacao", "cidade_exterior", "pais",
    "data_inicio", "cnae_principal", "cnae_secundarios", "tipo_logradouro",
    "logradouro", "numero", "complemento", "bairro", "cep", "uf", "municipio",
    "ddd1", "telefone1", "ddd2", "telefone2", "ddd_fax", "fax", "email",
    "situacao_especial", "data_situacao_especial",
]
EMPRESA = ["cnpj_basico", "razao_social", "natureza_juridica", "qualificacao_responsavel",
           "capital_social", "porte", "ente_federativo"]
SIMPLES = ["cnpj_basico", "opcao_simples", "data_opcao_simples", "data_exclusao_simples",
           "opcao_mei", "data_opcao_mei", "data_exclusao_mei"]
SOCIO = ["cnpj_basico", "identificador", "nome", "documento", "qualificacao", "data_entrada",
         "pais", "representante", "nome_representante", "qualificacao_representante", "faixa_etaria"]

PORTE = {"00": "NAO_INFORMADO", "01": "MICRO", "03": "EPP", "05": "DEMAIS"}
SITUACAO = {1: "NULA", 2: "ATIVA", 3: "SUSPENSA", 4: "INAPTA", 8: "BAIXADA"}
# Ordem de preferência para escolher quem recebe a abordagem.
QUALIFICACAO_DECISOR = ["49", "05", "65", "16", "10", "22"]
QUALIFICACAO_NOME = {
    "49": "Sócio-administrador", "05": "Administrador", "65": "Titular",
    "16": "Presidente", "10": "Diretor", "22": "Sócio",
}
# E-mail repetido em tantas empresas quase sempre é do escritório contábil.
SHARED_EMAIL_MIN = 3

NEEDED = re.compile(r"^(Estabelecimentos\d|Empresas\d|Socios\d|Simples|Municipios|Cnaes)\.zip$", re.I)


# ── Download ────────────────────────────────────────────────────────────────

def _propfind(client: httpx.Client, url: str, token: str) -> list[str]:
    resp = client.request("PROPFIND", url, auth=(token, ""), headers={"Depth": "1"})
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    return [el.text or "" for el in root.findall("d:response/d:href", DAV_NS)]


def latest_month(client: httpx.Client, token: str) -> str:
    hrefs = _propfind(client, f"{BASE}/public.php/webdav/Dados/Cadastros/CNPJ/", token)
    months = sorted(m.group(1) for h in hrefs if (m := re.search(r"(\d{4}-\d{2})/?$", h)))
    if not months:
        raise RuntimeError("Nenhuma pasta AAAA-MM encontrada no compartilhamento da Receita")
    return months[-1]


def list_files(client: httpx.Client, token: str, month: str) -> list[str]:
    hrefs = _propfind(client, f"{BASE}/public.php/webdav/Dados/Cadastros/CNPJ/{month}/", token)
    names = [m.group(1) for h in hrefs if (m := re.search(r"/([^/]+\.zip)$", h, re.I))]
    return sorted(n for n in names if NEEDED.match(n))


def download(settings: Settings, month: str | None = None) -> Path:
    token = settings.receita_share_token
    with httpx.Client(timeout=httpx.Timeout(60, read=300), follow_redirects=True) as client:
        month = month or latest_month(client, token)
        target = settings.data_dir / "receita" / month
        target.mkdir(parents=True, exist_ok=True)
        for name in list_files(client, token, month):
            dest = target / name
            url = f"{BASE}/public.php/dav/files/{token}/Dados/Cadastros/CNPJ/{month}/{name}"
            _download_resumable(client, url, dest)
    (target / ".completo").write_text(datetime.now(timezone.utc).isoformat())
    return target


def _download_resumable(client: httpx.Client, url: str, dest: Path) -> None:
    head = client.head(url)
    head.raise_for_status()
    size = int(head.headers.get("content-length", 0))
    have = dest.stat().st_size if dest.exists() else 0
    if size and have == size:
        log.info("já baixado: %s", dest.name)
        return
    headers = {"Range": f"bytes={have}-"} if have else {}
    log.info("baixando %s (%.1f MB)", dest.name, size / 1e6)
    with client.stream("GET", url, headers=headers) as resp:
        resp.raise_for_status()
        mode = "ab" if resp.status_code == 206 else "wb"
        with dest.open(mode) as fh:
            for chunk in resp.iter_bytes(1 << 20):
                fh.write(chunk)


def prune(base: Path, keep: Path) -> int:
    """Apaga os .zip dos meses que não são `keep`. Cada mês são ~8 GB; num PC
    pessoal o disco enche em poucos meses se nada for apagado."""
    freed = 0
    for zip_path in base.glob("*/*.zip"):
        if zip_path.parent.resolve() != keep.resolve():
            freed += zip_path.stat().st_size
            zip_path.unlink()
    return freed


# ── Leitura ─────────────────────────────────────────────────────────────────

def iter_rows(zip_path: Path, columns: list[str]) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                for values in csv.reader(text, delimiter=";", quotechar='"'):
                    if len(values) < len(columns):
                        values = values + [""] * (len(columns) - len(values))
                    yield dict(zip(columns, (v.strip() for v in values), strict=False))  # colunas extras são ignoradas


def _files(folder: Path, prefix: str) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.name.lower().startswith(prefix.lower()) and p.suffix == ".zip")


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().upper()


def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if len(s) != 8 or not s.isdigit() or s == "00000000":
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


def parse_money(s: str) -> Decimal | None:
    try:
        return Decimal((s or "").replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def _lookup(folder: Path, prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in _files(folder, prefix):
        for row in iter_rows(path, ["codigo", "descricao"]):
            out[row["codigo"]] = row["descricao"]
    return out


@dataclass
class Selection:
    month: str
    estabelecimentos: dict[str, dict] = field(default_factory=dict)  # cnpj -> linha
    empresas: dict[str, dict] = field(default_factory=dict)          # basico -> linha
    simples: dict[str, dict] = field(default_factory=dict)
    socios: dict[str, list[dict]] = field(default_factory=dict)
    municipios: dict[str, str] = field(default_factory=dict)
    cnaes: dict[str, str] = field(default_factory=dict)

    def basicos(self) -> set[str]:
        return {e["cnpj_basico"] for e in self.estabelecimentos.values()}


def select(folder: Path, filtros: Filtros, today: date | None = None) -> Selection:
    """Aplica o ICP sobre os arquivos já baixados e devolve só o que passa."""
    today = today or date.today()
    sel = Selection(month=folder.name)
    sel.municipios = _lookup(folder, "Municipios")
    sel.cnaes = _lookup(folder, "Cnaes")

    allowed_mun: set[str] | None = None
    if filtros.municipios:
        wanted = {norm_name(m) for m in filtros.municipios}
        allowed_mun = {code for code, name in sel.municipios.items() if norm_name(name) in wanted}
        missing = wanted - {norm_name(sel.municipios[c]) for c in allowed_mun}
        if missing:
            log.warning("municípios não encontrados na tabela da Receita: %s", ", ".join(sorted(missing)))
    ufs = set(filtros.ufs)
    prefixes = tuple(filtros.cnae_prefixos)
    min_days = filtros.abertura_min_anos * 365.25

    for path in _files(folder, "Estabelecimentos"):
        log.info("lendo %s", path.name)
        for row in iter_rows(path, ESTABELECIMENTO):
            if not row["situacao"].isdigit() or int(row["situacao"]) != 2:
                continue
            if ufs and row["uf"] not in ufs:
                continue
            if allowed_mun is not None and row["municipio"] not in allowed_mun:
                continue
            if prefixes and not row["cnae_principal"].startswith(prefixes):
                continue
            if filtros.somente_matriz and row["matriz_filial"] != "1":
                continue
            opened = parse_date(row["data_inicio"])
            if min_days and (opened is None or (today - opened).days < min_days):
                continue
            number = cnpjlib.compose(row["cnpj_basico"], row["cnpj_ordem"], row["cnpj_dv"])
            if not cnpjlib.is_valid(number):
                continue
            sel.estabelecimentos[number] = row
    log.info("estabelecimentos no filtro: %d", len(sel.estabelecimentos))

    basicos = sel.basicos()
    portes = set(filtros.portes)
    for path in _files(folder, "Empresas"):
        for row in iter_rows(path, EMPRESA):
            if row["cnpj_basico"] not in basicos:
                continue
            porte = PORTE.get(row["porte"].zfill(2), "NAO_INFORMADO")
            capital = parse_money(row["capital_social"]) or Decimal(0)
            if portes and porte not in portes:
                continue
            if capital < Decimal(str(filtros.capital_social_min)):
                continue
            sel.empresas[row["cnpj_basico"]] = {**row, "porte": porte, "capital_social": capital}

    for path in _files(folder, "Simples"):
        for row in iter_rows(path, SIMPLES):
            if row["cnpj_basico"] in sel.empresas:
                sel.simples[row["cnpj_basico"]] = row

    for number, row in list(sel.estabelecimentos.items()):
        basico = row["cnpj_basico"]
        if basico not in sel.empresas:
            del sel.estabelecimentos[number]
        elif filtros.excluir_mei and sel.simples.get(basico, {}).get("opcao_mei") == "S":
            del sel.estabelecimentos[number]
    log.info("após porte, capital e MEI: %d", len(sel.estabelecimentos))

    keep = sel.basicos()
    for path in _files(folder, "Socios"):
        for row in iter_rows(path, SOCIO):
            if row["cnpj_basico"] in keep and row["identificador"] == "2":  # pessoa física
                sel.socios.setdefault(row["cnpj_basico"], []).append(row)
    return sel


def decisor(socios: Iterable[dict]) -> dict | None:
    ranked = sorted(
        (s for s in socios if s["qualificacao"].zfill(2) in QUALIFICACAO_DECISOR),
        key=lambda s: QUALIFICACAO_DECISOR.index(s["qualificacao"].zfill(2)),
    )
    return ranked[0] if ranked else None


def _best_phone(row: dict) -> phones.Phone | None:
    candidates = [phones.normalize(row["ddd1"], row["telefone1"]),
                  phones.normalize(row["ddd2"], row["telefone2"])]
    candidates = [p for p in candidates if p]
    candidates.sort(key=lambda p: not p.is_mobile)
    return candidates[0] if candidates else None


def _email(raw: str) -> str | None:
    e = (raw or "").strip().lower()
    return e if re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", e) else None


# ── Gravação ────────────────────────────────────────────────────────────────

def store(conn: psycopg.Connection, org_id: str, sel: Selection, token: str) -> int:
    source_url = f"{BASE}/index.php/s/{token}?dir=/Dados/Cadastros/CNPJ/{sel.month}"
    source_at = datetime.strptime(sel.month + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    email_count = Counter(e for r in sel.estabelecimentos.values() if (e := _email(r["email"])))
    per_basico = Counter(r["cnpj_basico"] for r in sel.estabelecimentos.values())

    company_rows, contact_rows, partner_rows = [], [], []
    for number, row in sel.estabelecimentos.items():
        basico = row["cnpj_basico"]
        emp = sel.empresas[basico]
        simp = sel.simples.get(basico, {})
        logradouro = " ".join(x for x in (row["tipo_logradouro"], row["logradouro"], row["numero"],
                                          row["complemento"]) if x)
        company_rows.append((
            org_id, number, emp["razao_social"] or row["nome_fantasia"] or number,
            row["nome_fantasia"] or None, row["cnae_principal"],
            [c for c in row["cnae_secundarios"].split(",") if c] or None,
            sel.cnaes.get(row["cnae_principal"]),
            SITUACAO.get(int(row["situacao"]), row["situacao"]), parse_date(row["data_inicio"]),
            emp["porte"], emp["capital_social"], emp["natureza_juridica"],
            sel.municipios.get(row["municipio"], row["municipio"]), row["uf"], row["cep"] or None,
            logradouro or None, row["bairro"] or None,
            "MATRIZ" if row["matriz_filial"] == "1" else "FILIAL", per_basico[basico],
            simp.get("opcao_simples") == "S" if simp else None,
            simp.get("opcao_mei") == "S" if simp else None,
            SOURCE, source_url, source_at,
        ))
        phone = _best_phone(row)
        email = _email(row["email"])
        boss = decisor(sel.socios.get(basico, []))
        if phone or email:
            contact_rows.append((
                org_id, number,
                boss["nome"].title() if boss else None,
                QUALIFICACAO_NOME.get(boss["qualificacao"].zfill(2)) if boss else None,
                "socio" if boss else None,
                email, bool(email and email_count[email] >= SHARED_EMAIL_MIN),
                phone.e164 if phone else None, phone.is_mobile if phone else None,
                SOURCE, source_url,
            ))
        for s in sel.socios.get(basico, []):
            partner_rows.append((org_id, number, s["nome"].title(), s["qualificacao"].zfill(2),
                                 parse_date(s["data_entrada"]), s["faixa_etaria"] or None))

    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into companies (organization_id, cnpj, razao_social, nome_fantasia, cnae_principal,
              cnae_secundarios, cnae_descricao, situacao_cadastral, data_abertura, porte, capital_social,
              natureza_juridica, municipio, uf, cep, logradouro, bairro, matriz_filial,
              qtd_estabelecimentos, opcao_simples, opcao_mei, source, source_url, source_updated_at)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (organization_id, cnpj) do update set
              razao_social = excluded.razao_social, nome_fantasia = excluded.nome_fantasia,
              cnae_principal = excluded.cnae_principal, cnae_secundarios = excluded.cnae_secundarios,
              cnae_descricao = excluded.cnae_descricao, situacao_cadastral = excluded.situacao_cadastral,
              porte = excluded.porte, capital_social = excluded.capital_social,
              natureza_juridica = excluded.natureza_juridica, municipio = excluded.municipio,
              uf = excluded.uf, cep = excluded.cep, logradouro = excluded.logradouro,
              bairro = excluded.bairro, qtd_estabelecimentos = excluded.qtd_estabelecimentos,
              opcao_simples = excluded.opcao_simples, opcao_mei = excluded.opcao_mei,
              source_url = excluded.source_url, source_updated_at = excluded.source_updated_at,
              updated_at = now()
            """,
            company_rows,
        )
        cur.executemany(
            """
            insert into contacts (organization_id, company_id, full_name, role_title, seniority,
                                  email, email_shared, phone, phone_is_mobile, source, source_url)
            select %s, c.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
              from companies c where c.organization_id = %s and c.cnpj = %s
            on conflict (company_id) where source = 'receita_federal_open_data' do update set
              full_name = excluded.full_name, role_title = excluded.role_title,
              seniority = excluded.seniority, email_shared = excluded.email_shared,
              email = excluded.email,
              email_status = case when contacts.email is distinct from excluded.email
                                  then 'unknown' else contacts.email_status end,
              phone = excluded.phone, phone_is_mobile = excluded.phone_is_mobile,
              phone_status = case when contacts.phone is distinct from excluded.phone
                                  then 'unknown' else contacts.phone_status end,
              updated_at = now()
            """,
            [(r[0], *r[2:], r[0], r[1]) for r in contact_rows],
        )
        cur.executemany(
            """
            insert into company_partners (organization_id, company_id, nome, qualificacao, data_entrada, faixa_etaria)
            select %s, c.id, %s, %s, %s, %s from companies c where c.organization_id = %s and c.cnpj = %s
            on conflict (company_id, nome) do nothing
            """,
            [(r[0], *r[2:], r[0], r[1]) for r in partner_rows],
        )
    conn.commit()
    return len(company_rows)
