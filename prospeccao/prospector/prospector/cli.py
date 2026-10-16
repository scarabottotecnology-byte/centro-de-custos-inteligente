"""Linha de comando: `prospector <comando>`."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import time
from datetime import datetime

import uvicorn

from . import config, db, outreach, pipeline

log = logging.getLogger("prospector")


def _print(result) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_init(settings, args) -> None:
    with db.connect(settings) as conn:
        db.apply_schema(conn)
        ctx = pipeline.Context.open(settings, conn)
        _print({"organizacao": ctx.org_id, "icp": ctx.icp_id, "campanhas": ctx.campaign_ids})


def cmd_step(settings, args) -> None:
    with db.connect(settings) as conn:
        ctx = pipeline.Context.open(settings, conn)
        if args.comando == "receita-carregar" and args.pasta:
            _print(pipeline.receita_carregar(ctx, args.pasta))
        else:
            _print(pipeline.run_step(ctx, args.comando))


def cmd_ciclo(settings, args) -> None:
    with db.connect(settings) as conn:
        _print(pipeline.cycle(pipeline.Context.open(settings, conn)))


def cmd_aprovar(settings, args) -> None:
    with db.connect(settings) as conn:
        ctx = pipeline.Context.open(settings, conn)
        _print({"aprovados": outreach.approve_all(conn, ctx.org_id)})


def cmd_whatsapp(settings, args) -> None:
    with db.connect(settings) as conn:
        ctx = pipeline.Context.open(settings, conn)
        if not ctx.evolution:
            raise SystemExit("EVOLUTION_APIKEY não configurada")
        hook = f"{settings.webhook_base_url.rstrip('/')}/webhooks/evolution?token={settings.api_token}"
        try:
            ctx.evolution.create_instance(hook)
        except Exception as exc:  # noqa: BLE001 - instância já existente devolve erro e segue
            log.info("instância não criada (provavelmente já existe): %s", exc)
        qr = ctx.evolution.connect()
        out = settings.data_dir / "whatsapp-qr.png"
        if qr.get("base64"):
            out.write_bytes(base64.b64decode(qr["base64"].split(",", 1)[-1]))
            print(f"QR code salvo em {out}. Abra no computador e leia com o WhatsApp do chip de prospecção.")
        if qr.get("pairingCode"):
            print(f"Ou use o código de pareamento: {qr['pairingCode']}")
        if not qr.get("base64") and not qr.get("pairingCode"):
            _print(qr)


def _monthly_receita(ctx: pipeline.Context) -> None:
    """Uma vez por mês, depois do dia 10, baixa e recarrega a base da Receita."""
    month = datetime.now().strftime("%Y-%m")
    folder = ctx.settings.data_dir / "receita" / month
    if datetime.now().day < 10 or (folder / ".carregado").exists():
        return
    try:
        downloaded = pipeline.receita_baixar(ctx)["pasta"]
        result = pipeline.receita_carregar(ctx, downloaded)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ".carregado").write_text(json.dumps(result, default=str))
    except Exception:  # noqa: BLE001
        log.exception("atualização mensal da Receita falhou; tenta de novo no próximo ciclo")


def cmd_daemon(settings, args) -> None:
    last_full = 0.0
    while True:
        started = time.monotonic()
        try:
            with db.connect(settings) as conn:
                ctx = pipeline.Context.open(settings, conn)
                if args.receita_mensal:
                    _monthly_receita(ctx)
                if started - last_full >= args.ciclo_minutos * 60 or last_full == 0:
                    pipeline.cycle(ctx)
                    last_full = started
                else:
                    for name in ("maps", "caixa", "enviar"):
                        try:
                            pipeline.run_step(ctx, name)
                        except Exception:  # noqa: BLE001
                            log.exception("etapa %s falhou", name)
        except Exception:  # noqa: BLE001 - banco fora do ar não derruba o daemon
            log.exception("ciclo falhou")
        time.sleep(max(5, args.intervalo_minutos * 60 - (time.monotonic() - started)))


def cmd_servidor(settings, args) -> None:
    from .server import create_app

    uvicorn.run(create_app(settings), host="0.0.0.0", port=args.porta)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="prospector", description="Prospecção B2B autônoma")
    parser.add_argument("--config", help="caminho do prospeccao.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("init", help="cria o esquema e sincroniza ICP e campanhas").set_defaults(fn=cmd_init)
    for name, text in [
        ("receita-baixar", "baixa o mês mais recente dos Dados Abertos do CNPJ"),
        ("receita-carregar", "aplica o ICP sobre os arquivos e grava as empresas"),
        ("pontuar", "calcula o ICP Score e prioriza"),
        ("maps", "envia/coleta buscas no Google Maps"),
        ("verificar", "verifica e-mails (Reacher) e WhatsApp (Evolution)"),
        ("pesquisar", "pesquisa e frase de abertura com o Claude"),
        ("enfileirar", "coloca priorizados nas campanhas"),
        ("enviar", "envia o que está vencido, respeitando janela e limites"),
        ("caixa", "lê respostas de e-mail por IMAP"),
        ("funil", "mostra os números do funil"),
    ]:
        p = sub.add_parser(name, help=text)
        if name == "receita-carregar":
            p.add_argument("--pasta", help="pasta com os .zip (padrão: último download completo)")
        p.set_defaults(fn=cmd_step)
    sub.add_parser("ciclo", help="roda o ciclo diário inteiro uma vez").set_defaults(fn=cmd_ciclo)
    sub.add_parser("aprovar", help="libera os contatos pendentes (modo approval_required)").set_defaults(fn=cmd_aprovar)
    sub.add_parser("whatsapp-conectar", help="cria a instância e gera o QR code").set_defaults(fn=cmd_whatsapp)
    d = sub.add_parser("daemon", help="roda sozinho, em loop")
    d.add_argument("--intervalo-minutos", type=float, default=10)
    d.add_argument("--ciclo-minutos", type=float, default=120)
    d.add_argument("--receita-mensal", action="store_true")
    d.set_defaults(fn=cmd_daemon)
    s = sub.add_parser("servidor", help="API de webhooks e descadastro")
    s.add_argument("--porta", type=int, default=8000)
    s.set_defaults(fn=cmd_servidor)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args.fn(config.load(args.config), args)


if __name__ == "__main__":
    main()
