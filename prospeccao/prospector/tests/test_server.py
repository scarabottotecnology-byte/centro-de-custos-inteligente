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

        assert client.post("/webhooks/evolution", json={}).status_code == 401
        ignored = client.post("/webhooks/evolution?token=segredo", json={"event": "connection.update"})
        assert ignored.json() == {"classificacao": None}

        page = client.get(f"/saida/{contact['optout_token']}")
        assert page.status_code == 200 and "Confirmar descadastro" in page.text
        assert client.post(f"/saida/{contact['optout_token']}").status_code == 200

    conn.rollback()
    assert db.is_suppressed(conn, ctx.org_id, "email", "contato@boavista.com.br")
