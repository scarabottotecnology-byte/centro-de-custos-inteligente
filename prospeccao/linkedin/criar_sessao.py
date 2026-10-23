"""Abre o LinkedIn para você entrar uma vez e guarda a sessão em sessao_linkedin.json.

O coletar.py reaproveita essa sessão; não guardamos a sua senha em lugar nenhum.
O arquivo dá acesso à sua conta: não compartilhe nem suba para o GitHub (já está
no .gitignore).

Uso:
    python criar_sessao.py
"""

import asyncio

from linkedin_scraper import BrowserManager, wait_for_manual_login

SESSAO = "sessao_linkedin.json"


async def main() -> None:
    async with BrowserManager(headless=False) as browser:
        await browser.page.goto("https://www.linkedin.com/login")
        print("Entre no LinkedIn na janela que abriu (você tem 5 minutos).")
        print("Faça a verificação em duas etapas, se pedir, e espere o feed carregar.")
        await wait_for_manual_login(browser.page, timeout=300_000)
        await browser.save_session(SESSAO)
        print(f"Sessão salva em {SESSAO}.")


if __name__ == "__main__":
    asyncio.run(main())
