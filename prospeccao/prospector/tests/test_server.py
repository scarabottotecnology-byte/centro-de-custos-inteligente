from fastapi.testclient import TestClient

from prospector import db, pipeline, receita, scoring
from prospector.server import create_app


def test_api(conn, settings, receita_dir):
    ctx = pipeline.Context.open(settings, conn)
    receita.store(conn, ctx.org_id, receita.select(receita_dir, settings.icp.filtros), settings.receita_share_token)
    scoring.discover(conn, ctx.org_id, ctx.icp_id)
    contact = conn.execute("select * from contacts where email = 'contato@boavista.com.br'").fetchone()

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"ok": True}

        assert client.post("/run/funil").status_code == 401
        assert client.post("/run/funil", headers={"Authorization": "Bearer errado"}).status_code == 401
        funil = client.post("/run/funil", headers={"Authorization": "Bearer segredo"}).json()
        assert funil["empresas"] == 3
        assert client.post("/run/nada", headers={"Authorization": "Bearer segredo"}).status_code == 404

        assert "Sextante" in client.get("/painel").text
        assert client.get("/painel/dados").status_code == 401
        dados = client.get("/painel/dados", headers={"Authorization": "Bearer segredo"}).json()
        assert dados["funil"]["empresas"] == 3 and dados["funil"]["simuladas_hoje"] == 0
        assert dados["simulacao"] is True
        assert dados["canais"] == {"whatsapp": "sem_configuracao", "email": "sem_configuracao"}
        assert dados["receita"] == {"estado": "carregando", "mes": "2026-09"}  # a pasta do receita_dir
        assert dados["leads"] == [] and dados["mensagens"] == []

        assert client.post("/webhooks/evolution", json={}).status_code == 401
        ignored = client.post("/webhooks/evolution?token=segredo", json={"event": "connection.update"})
        assert ignored.json() == {"classificacao": None}

        page = client.get(f"/saida/{contact['optout_token']}")
        assert page.status_code == 200 and "Confirmar descadastro" in page.text
        assert client.post(f"/saida/{contact['optout_token']}").status_code == 200

    conn.rollback()
    assert db.is_suppressed(conn, ctx.org_id, "email", "contato@boavista.com.br")


_webhooks_criados: list[str] = []


class _FakeEvolution:
    conectado = False

    def __init__(self, *args, **kwargs):
        pass

    def is_connected(self):
        return self.conectado

    def create_instance(self, webhook_url):
        _webhooks_criados.append(webhook_url)
        return {}

    def connect(self):
        return {"base64": "data:image/png;base64,QUJD", "pairingCode": None}


def test_painel_whatsapp(conn, settings, monkeypatch):
    from prospector import server

    monkeypatch.setattr(server, "EvolutionClient", _FakeEvolution)
    auth = {"Authorization": "Bearer segredo"}
    with TestClient(create_app(settings)) as client:
        assert client.post("/painel/whatsapp").status_code == 401
        assert client.post("/painel/whatsapp", headers=auth).json() == {"estado": "sem_configuracao"}

        settings.evolution_apikey = "chave"
        r = client.post("/painel/whatsapp", headers=auth).json()
        assert r == {"estado": "desconectado", "qr": "data:image/png;base64,QUJD", "codigo": None}
        assert _webhooks_criados[-1].endswith("/webhooks/evolution?token=segredo")

        _FakeEvolution.conectado = True
        assert client.post("/painel/whatsapp", headers=auth).json() == {"estado": "conectado"}
        assert client.get("/painel/dados", headers=auth).json()["canais"]["whatsapp"] == "conectado"
