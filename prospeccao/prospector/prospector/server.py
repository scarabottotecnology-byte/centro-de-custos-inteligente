"""API HTTP: webhook do WhatsApp, link de descadastro, gatilhos para o n8n e o painel."""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

import httpx
import psycopg
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from . import config, inbound, painel, pipeline
from .providers import EvolutionClient

log = logging.getLogger(__name__)

_PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;color:#1f2933}}
button{{font:inherit;padding:.6rem 1.2rem;border:0;border-radius:.375rem;background:#2f8f88;color:#fff;cursor:pointer}}</style>
</head><body><h1>{title}</h1><p>{text}</p>{extra}</body></html>"""


def _conn(settings: config.Settings) -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def create_app(settings: config.Settings | None = None) -> FastAPI:
    settings = settings or config.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with _conn(settings) as conn:
            ctx = pipeline.Context.open(settings, conn)
            app.state.org_id = ctx.org_id
        yield

    app = FastAPI(title="Sextante", lifespan=lifespan)

    def _auth(authorization: str | None, token: str | None = None) -> None:
        given = token or (authorization or "").removeprefix("Bearer ").strip()
        if not settings.api_token or not hmac.compare_digest(given, settings.api_token):
            raise HTTPException(status_code=401, detail="token inválido")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/webhooks/evolution")
    async def evolution_webhook(request: Request, token: str | None = None) -> dict:
        _auth(None, token)
        payload = await request.json()

        def work():
            with _conn(settings) as conn:
                ctx = pipeline.Context.open(settings, conn)
                return inbound.handle_evolution(conn, ctx.org_id, ctx.claude, payload, notify=ctx.notify_owner)

        label = await run_in_threadpool(work)
        return {"classificacao": label}

    @app.get("/saida/{token}", response_class=HTMLResponse)
    def optout_page(token: str) -> str:
        return _PAGE.format(
            title="Não receber mais mensagens",
            text="Confirme e não enviaremos mais nenhuma mensagem para este contato.",
            extra=f'<form method="post" action="/saida/{token}"><button>Confirmar descadastro</button></form>',
        )

    @app.post("/saida/{token}", response_class=HTMLResponse)
    def optout(token: str) -> str:
        # Também atende o POST de um clique do cabeçalho List-Unsubscribe (RFC 8058).
        with _conn(settings) as conn:
            inbound.optout_by_token(conn, token)
        return _PAGE.format(title="Pronto", text="Você não receberá mais mensagens nossas.", extra="")

    # A página não traz dado nenhum: os números vêm de /painel/dados, que pede o
    # token. Assim o painel continua fechado mesmo com a porta exposta na internet.
    @app.get("/painel", response_class=HTMLResponse)
    def painel_page() -> str:
        return painel.HTML.read_text(encoding="utf-8")

    def _evolution() -> EvolutionClient | None:
        if not settings.evolution_apikey:
            return None
        return EvolutionClient(settings.evolution_url, settings.evolution_apikey,
                               settings.evolution_instance, timeout=5)

    @app.get("/painel/dados")
    def painel_dados(authorization: str | None = Header(default=None)) -> dict:
        _auth(authorization)
        evo = _evolution()
        whatsapp = evo.is_connected() if evo else None
        with _conn(settings) as conn:
            return painel.snapshot(conn, settings, app.state.org_id, whatsapp)

    # Pareamento do chip pelo próprio painel. No servidor o manager da Evolution
    # não fica exposto; aqui o QR só sai para quem tem o token.
    @app.post("/painel/whatsapp")
    def painel_whatsapp(authorization: str | None = Header(default=None)) -> dict:
        _auth(authorization)
        evo = _evolution()
        if evo is None:
            return {"estado": "sem_configuracao"}
        if evo.is_connected():
            return {"estado": "conectado"}
        try:
            evo.create_instance(pipeline.whatsapp_webhook(settings))
        except httpx.HTTPError:
            pass  # a instância já existe; a Evolution responde com erro e segue
        try:
            qr = evo.connect()
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="WhatsApp ainda está ligando") from None
        imagem = qr.get("base64") or None
        if imagem and not imagem.startswith("data:"):
            imagem = "data:image/png;base64," + imagem
        return {"estado": "desconectado", "qr": imagem, "codigo": qr.get("pairingCode")}

    @app.post("/run/{etapa}")
    async def run(etapa: str, authorization: str | None = Header(default=None)) -> dict:
        _auth(authorization)
        if etapa not in pipeline.STEPS and etapa != "ciclo":
            raise HTTPException(status_code=404, detail="etapa desconhecida")

        def work():
            with _conn(settings) as conn:
                ctx = pipeline.Context.open(settings, conn)
                return pipeline.cycle(ctx) if etapa == "ciclo" else pipeline.run_step(ctx, etapa)

        return await run_in_threadpool(work)

    return app
