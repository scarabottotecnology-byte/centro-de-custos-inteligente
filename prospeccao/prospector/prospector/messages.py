"""Montagem das mensagens a partir dos templates do YAML.

Variáveis disponíveis nos textos da campanha:
  {saudacao}     "Olá, Maria" ou "Olá" quando não há nome do decisor
  {primeiro_nome}
  {empresa}      nome fantasia, ou razão social sem o sufixo societário
  {cidade} {uf}
  {segmento}     descrição do CNAE principal, em minúsculas
  {anos}         anos de mercado
  {abertura}     frase personalizada pela IA (vazia sem IA)
  {remetente} {empresa_remetente}
  {link_saida}   link de descadastro (obrigatório no e-mail)
"""

from __future__ import annotations

import re
from datetime import date

_SUFFIX = re.compile(r"\b(LTDA|EIRELI|EPP|ME|S/?A|SLU|SOCIEDADE LIMITADA UNIPESSOAL)\.?$", re.I)
_SMALL = {"de", "da", "do", "dos", "das", "e"}


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return ""


def title(text: str) -> str:
    words = text.lower().split()
    return " ".join(w if i and w in _SMALL else w.capitalize() for i, w in enumerate(words))


def company_name(company: dict) -> str:
    name = company.get("nome_fantasia") or company.get("razao_social") or ""
    name = _SUFFIX.sub("", name.strip()).strip(" -.")
    return title(name) if name.isupper() else name


def first_name(full_name: str | None) -> str:
    if not full_name:
        return ""
    return full_name.split()[0].capitalize()


def variables(company: dict, contact: dict, research: dict | None, remetente: dict,
              optout_url: str, today: date | None = None) -> dict:
    today = today or date.today()
    nome = first_name(contact.get("full_name"))
    anos = ""
    if company.get("data_abertura"):
        anos = str(int((today - company["data_abertura"]).days // 365.25))
    segmento = (company.get("cnae_descricao") or company.get("google_category") or "").lower()
    return {
        "saudacao": f"Olá, {nome}" if nome else "Olá",
        "primeiro_nome": nome,
        "empresa": company_name(company),
        "cidade": title(company.get("municipio") or ""),
        "uf": company.get("uf") or "",
        "segmento": segmento,
        "anos": anos,
        "abertura": (research or {}).get("opening_line") or "",
        "remetente": remetente.get("nome", ""),
        "empresa_remetente": remetente.get("empresa", ""),
        "link_saida": optout_url,
    }


def render(template: str, values: dict) -> str:
    lines = []
    for line in template.splitlines():
        out = line.format_map(_Safe(values))
        # Linha que só existia para uma variável vazia (ex.: {abertura} sem IA) some;
        # linha em branco escrita de propósito no template fica.
        if "{" in line and not out.strip():
            continue
        lines.append(re.sub(r"[ \t]{2,}", " ", out).rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
