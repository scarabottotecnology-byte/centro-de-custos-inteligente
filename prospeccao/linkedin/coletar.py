"""Lê perfis do LinkedIn e separa empresários e C-level numa planilha.

Usa a biblioteca joeyism/linkedin_scraper (v3, Playwright) com a sua sessão.
Ela não faz busca de pessoas: você fornece os links dos perfis, um por linha,
em perfis.txt (o filtrar_conexoes.py já gera esse arquivo a partir das suas
conexões; também dá para colar links de uma busca feita à mão no LinkedIn).

Para cada perfil grava nome, cargo e empresa atuais, local e o e-mail se ele
estiver visível em "Informações de contato" (costuma aparecer só para conexões).

Ritmo: uma pausa aleatória de 20 a 45 s entre perfis e no máximo 40 perfis por
execução. O LinkedIn restringe contas que leem perfis em massa; não aumente
esses números. Se o LinkedIn pedir verificação ou limitar, o script para e
guarda o que já coletou. Rodar de novo continua de onde parou.

Uso:
    python coletar.py                 # lê perfis.txt
    python coletar.py --limite 20     # menos perfis nesta execução
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import random
import sys
from pathlib import Path

from linkedin_scraper import (
    AuthenticationError,
    BrowserManager,
    PersonScraper,
    ProfileNotFoundError,
    RateLimitError,
)

from decisores import classifica

AQUI = Path(__file__).resolve().parent
SESSAO = AQUI / "sessao_linkedin.json"
SAIDA = AQUI / "saida" / "perfis_linkedin.csv"
CAMPOS = ["nome", "cargo", "empresa", "perfil_decisor", "email", "local", "linkedin_url", "fonte"]
PAUSA_MIN, PAUSA_MAX = 20, 45
LIMITE_PADRAO = 40


def _normaliza_url(url: str) -> str:
    return url.strip().split("?")[0].rstrip("/") + "/"


def ja_coletados() -> set[str]:
    if not SAIDA.exists():
        return set()
    with open(SAIDA, newline="", encoding="utf-8") as f:
        return {_normaliza_url(l["linkedin_url"]) for l in csv.DictReader(f)}


def grava(linha: dict) -> None:
    SAIDA.parent.mkdir(exist_ok=True)
    novo = not SAIDA.exists()
    with open(SAIDA, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerow(linha)


async def coletar(urls: list[str], limite: int) -> int:
    feitos = 0
    async with BrowserManager(headless=False) as browser:
        await browser.load_session(str(SESSAO))
        scraper = PersonScraper(browser.page)
        for url in urls[:limite]:
            try:
                p = await scraper.scrape(url)
            except ProfileNotFoundError:
                print(f"  perfil privado ou inexistente: {url}")
                continue
            except (RateLimitError, AuthenticationError) as e:
                print(f"\nO LinkedIn limitou ou pediu login de novo ({type(e).__name__}). "
                      "Parando aqui; espere algumas horas antes de rodar de novo.")
                break
            email = next((c.value for c in p.contacts if c.type == "email"), "")
            grava({
                "nome": p.name or "",
                "cargo": p.job_title or "",
                "empresa": p.company or "",
                "perfil_decisor": classifica(p.job_title) or "",
                "email": email,
                "local": p.location or "",
                "linkedin_url": url,
                "fonte": "perfil",
            })
            feitos += 1
            print(f"  {feitos}. {p.name} | {p.job_title} | {p.company}" + (" | e-mail" if email else ""))
            await asyncio.sleep(random.uniform(PAUSA_MIN, PAUSA_MAX))
    return feitos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfis", default=str(AQUI / "perfis.txt"), help="arquivo com um link de perfil por linha")
    ap.add_argument("--limite", type=int, default=LIMITE_PADRAO, help=f"máximo de perfis nesta execução (padrão {LIMITE_PADRAO})")
    args = ap.parse_args()

    if not SESSAO.exists():
        print("Falta a sessão. Rode antes: python criar_sessao.py")
        return 1
    caminho = Path(args.perfis)
    if not caminho.exists():
        print(f"Não achei {caminho}. Coloque um link de perfil por linha.")
        return 1

    feitos = ja_coletados()
    urls = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if "linkedin.com/in/" in linha and _normaliza_url(linha) not in feitos:
            urls.append(_normaliza_url(linha))
    if not urls:
        print("Nada novo para coletar.")
        return 0

    print(f"{len(urls)} perfis na fila; coletando até {min(len(urls), args.limite)} agora.")
    n = asyncio.run(coletar(urls, min(args.limite, LIMITE_PADRAO)))
    print(f"\n{n} perfis gravados em {SAIDA}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
