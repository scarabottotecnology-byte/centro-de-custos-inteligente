"""Ciclo completo contra um Postgres real (TEST_DATABASE_URL), com provedores falsos."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from prospector import db, inbound, maps, outreach, pipeline, receita, scoring, verify
from prospector.providers import SendResult

TZ = ZoneInfo("America/Sao_Paulo")
# No futuro em relação a now(): o enfileiramento usa o relógio do banco.
WEDNESDAY_10AM = datetime(2030, 10, 16, 10, 0, tzinfo=TZ)


class FakeWhatsApp:
    def __init__(self, with_whatsapp: set[str]):
        self.with_whatsapp = with_whatsapp
        self.sent: list[tuple[str, str]] = []

    def check_numbers(self, numbers):
        return {n: f"{n}@s.whatsapp.net" for n in numbers if n in self.with_whatsapp}

    def send_text(self, number, text, typing_ms=0):
        self.sent.append((number, text))
        return SendResult(provider_message_id=f"wa-{len(self.sent)}")


class FakeEmail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, unsubscribe_url):
        self.sent.append((to, subject, body, unsubscribe_url))
        return SendResult(provider_message_id=f"<m{len(self.sent)}@x>")


class FakeReacher:
    def __init__(self, answers):
        self.answers = answers

    def check(self, email):
        return self.answers.get(email, "unknown")


class FakeGmaps:
    def __init__(self, csv_by_job):
        self.csv_by_job = csv_by_job
        self.jobs = {}

    def create_job(self, name, lines, *, email, max_time):
        job_id = f"job{len(self.jobs)}"
        self.jobs[job_id] = lines
        return job_id

    def status(self, job_id):
        return "ok"

    def results(self, job_id):
        ids = [line.split("#!#")[1] for line in self.jobs[job_id]]
        return self.csv_by_job(ids)


@pytest.fixture
def ctx(conn, settings, receita_dir, monkeypatch):
    monkeypatch.setattr(receita, "SHARED_EMAIL_MIN", 2)
    c = pipeline.Context.open(settings, conn)
    sel = receita.select(receita_dir, settings.icp.filtros)
    receita.store(conn, c.org_id, sel, settings.receita_share_token)
    scoring.discover(conn, c.org_id, c.icp_id)
    return c


def _company(conn, cnpj):
    return conn.execute("select * from companies where cnpj = %s", (cnpj,)).fetchone()


def test_carga_grava_empresa_contato_e_socios(ctx, conn):
    boa = _company(conn, "11222333000181")
    assert boa["porte"] == "DEMAIS" and boa["municipio"] == "CURITIBA" and boa["opcao_simples"] is False
    assert boa["cnae_descricao"].startswith("Comércio atacadista")
    contact = conn.execute("select * from contacts where company_id = %s", (boa["id"],)).fetchone()
    assert contact["full_name"] == "Maria Aparecida Souza" and contact["role_title"] == "Sócio-administrador"
    assert contact["phone"] == "5541999887766" and contact["phone_is_mobile"]
    assert contact["email"] == "contato@boavista.com.br" and not contact["email_shared"]

    alfa = _company(conn, "12ABC34501DE35")
    assert alfa["razao_social"] == "ALFA NUMERICA COMERCIO LTDA"
    shared = conn.execute("select email_shared from contacts where company_id = %s", (alfa["id"],)).fetchone()
    assert shared["email_shared"]  # mesmo e-mail na Metalúrgica Sul
    parceiros = conn.execute("select * from v_contadores_parceiros").fetchall()
    assert [(p["email"], p["empresas_atendidas"]) for p in parceiros] == [("fiscal@contabilx.com.br", 2)]


def test_recarga_e_idempotente(ctx, conn, settings, receita_dir):
    before = conn.execute("select count(*) as n from contacts").fetchone()["n"]
    sel = receita.select(receita_dir, settings.icp.filtros)
    receita.store(conn, ctx.org_id, sel, settings.receita_share_token)
    assert conn.execute("select count(*) as n from contacts").fetchone()["n"] == before
    assert conn.execute("select count(*) as n from companies").fetchone()["n"] == 3


def test_ciclo_completo(ctx, conn, settings):
    settings.envio.dry_run = False
    org = ctx.org_id

    # Google Maps: acha a Boa Vista (site + avaliações + e-mail do site); a Alfa não aparece.
    boa = _company(conn, "11222333000181")

    def csv_for(ids):
        rows = ["input_id,title,website,phone,review_count,review_rating,emails,complete_address,place_id,category,link"]
        rows.append(f'{boa["id"]},Distribuidora Boa Vista,https://boavista.com.br,(41) 3030-4040,58,4.6,'
                    f'"comercial@boavista.com.br, contato@boavista.com.br","{{""postal_code"": ""80010-000""}}",'
                    f'ChIJ123,Distribuidora,https://maps.google.com/?cid=1')
        rows.append(f'{boa["id"]},Outra Empresa Qualquer,,,,,,,,,')
        return "\n".join(rows)

    gm = FakeGmaps(csv_for)
    assert maps.submit(conn, org, settings, gm) == 1
    assert maps.collect(conn, org, gm)["empresas_casadas"] == 1
    boa = _company(conn, "11222333000181")
    assert boa["website"] == "https://boavista.com.br" and boa["google_reviews"] == 58
    emails = {r["email"] for r in conn.execute("select email from contacts where company_id = %s and email is not null",
                                               (boa["id"],))}
    assert emails == {"contato@boavista.com.br", "comercial@boavista.com.br"}  # sem duplicar o da Receita

    stats = scoring.run(conn, org, ctx.icp_id, settings.icp)
    assert stats["priorizados"] >= 1
    prospect = conn.execute("select * from prospects where company_id = %s", (boa["id"],)).fetchone()
    assert prospect["stage"] == "prioritized" and prospect["priority"] >= settings.icp.limiar_priorizacao
    n_scores = conn.execute("select count(*) as n from prospect_scores").fetchone()["n"]
    scoring.run(conn, org, ctx.icp_id, settings.icp)
    assert conn.execute("select count(*) as n from prospect_scores").fetchone()["n"] == n_scores  # nada mudou

    wa = FakeWhatsApp({"5541999887766"})
    verify.whatsapp(conn, org, wa)
    verify.emails(conn, org, settings, FakeReacher({"contato@boavista.com.br": "safe",
                                                    "comercial@boavista.com.br": "invalid"}))
    statuses = {r["email"]: r["email_status"] for r in conn.execute(
        "select email, email_status from contacts where email is not null and company_id = %s", (boa["id"],))}
    assert statuses == {"contato@boavista.com.br": "verified", "comercial@boavista.com.br": "unverified"}

    enq = outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    assert enq["whatsapp"] >= 1

    em = FakeEmail()
    senders = outreach.Senders(whatsapp=wa, email=em)
    sleeps = []
    result = outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=sleeps.append)
    assert result["enviadas"] >= 1
    number, text = wa.sent[0]
    assert number == "5541999887766" and text.startswith("Olá, Maria")

    # Reprocessar no mesmo minuto não manda de novo.
    again = outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=sleeps.append)
    assert again["enviadas"] == 0 and len(wa.sent) == result["enviadas"]

    cc = conn.execute("select cc.* from campaign_contacts cc join contacts ct on ct.id = cc.contact_id "
                      "where ct.phone = '5541999887766'").fetchone()
    assert cc["current_step"] == 1
    assert cc["next_send_at"] == WEDNESDAY_10AM + timedelta(days=3)
    assert conn.execute("select stage from prospects where id = %s", (prospect["id"],)).fetchone()["stage"] == "contacted"

    # Três dias depois cai no sábado: nada sai. O segundo passo vai na segunda.
    saturday = WEDNESDAY_10AM + timedelta(days=3)
    assert outreach.send_due(conn, org, settings, senders, now=saturday, sleep=sleeps.append)["enviadas"] == 0
    outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM + timedelta(days=5), sleep=sleeps.append)
    assert any("Só retomando" in t for _, t in wa.sent)

    # Resposta com interesse pelo webhook do Evolution: para a sequência, cria lead e avisa o dono.
    alerts = []
    payload = {"event": "messages.upsert", "instance": "prospeccao",
               "data": {"key": {"remoteJid": "5541999887766@s.whatsapp.net", "fromMe": False, "id": "IN1"},
                        "message": {"conversation": "Oi! Tenho interesse, pode me ligar amanhã?"}}}
    assert inbound.handle_evolution(conn, org, None, payload, notify=alerts.append) == "interested"
    assert inbound.handle_evolution(conn, org, None, payload, notify=alerts.append) == "interested"  # repetido
    assert len(alerts) == 1 and "Distribuidora Boa Vista" in alerts[0]
    assert conn.execute("select count(*) as n from leads").fetchone()["n"] == 1
    assert conn.execute("select state from campaign_contacts where id = %s", (cc["id"],)).fetchone()["state"] == "replied"
    assert conn.execute("select stage from prospects where id = %s", (prospect["id"],)).fetchone()["stage"] == "engaged"

    sent_before = len(wa.sent)
    outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM + timedelta(days=12), sleep=sleeps.append)
    assert len(wa.sent) == sent_before  # quem respondeu não recebe o passo 3


def test_simulacao_nao_envia_e_libera_depois(ctx, conn, settings):
    org = ctx.org_id
    boa = _company(conn, "11222333000181")
    conn.execute("update contacts set phone_status = 'verified' where company_id = %s and phone is not null", (boa["id"],))
    conn.execute("update prospects set stage = 'prioritized', priority = 90 where company_id = %s", (boa["id"],))
    conn.commit()
    outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    wa = FakeWhatsApp(set())
    senders = outreach.Senders(whatsapp=wa)

    settings.envio.dry_run = True
    assert outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=lambda s: None)["simuladas"] == 1
    assert wa.sent == []
    preview = conn.execute("select status, body from outreach_messages").fetchone()
    assert preview["status"] == "dry_run" and "Maria" in preview["body"]

    settings.envio.dry_run = False
    assert outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=lambda s: None)["enviadas"] == 1
    assert len(wa.sent) == 1
    assert conn.execute("select count(*) as n from outreach_messages").fetchone()["n"] == 1


def test_fora_da_janela_e_limite_diario(ctx, conn, settings):
    org = ctx.org_id
    settings.envio.dry_run = False
    conn.execute("update contacts set phone_status = 'verified' where phone is not null")
    conn.execute("update prospects set stage = 'prioritized', priority = 90")
    conn.commit()
    outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    wa = FakeWhatsApp(set())
    senders = outreach.Senders(whatsapp=wa)
    saturday = datetime(2030, 10, 19, 10, 0, tzinfo=TZ)
    assert outreach.send_due(conn, org, settings, senders, now=saturday, sleep=lambda s: None)["enviadas"] == 0
    settings.envio.limite_diario["whatsapp"] = 1
    assert outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=lambda s: None)["enviadas"] == 1
    assert outreach.send_due(conn, org, settings, senders, now=WEDNESDAY_10AM, sleep=lambda s: None)["enviadas"] == 0


def test_descadastro_bloqueia_para_sempre(ctx, conn, settings):
    org = ctx.org_id
    settings.envio.dry_run = False
    boa = _company(conn, "11222333000181")
    conn.execute("update contacts set phone_status = 'verified' where company_id = %s", (boa["id"],))
    conn.execute("update prospects set stage = 'prioritized', priority = 90 where company_id = %s", (boa["id"],))
    conn.commit()
    outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    contact = conn.execute("select * from contacts where company_id = %s", (boa["id"],)).fetchone()

    assert inbound.optout_by_token(conn, contact["optout_token"])
    assert db.is_suppressed(conn, org, "whatsapp", "5541999887766")
    assert db.is_suppressed(conn, org, "email", "CONTATO@boavista.com.br")  # hash ignora caixa
    raw = conn.execute("select value_hash from suppression_list").fetchall()
    assert all("@" not in r["value_hash"] and "5541" not in r["value_hash"] for r in raw)

    # Mesmo que alguém reative a campanha na mão, o envio checa a lista antes.
    conn.execute("update campaign_contacts set state = 'active', next_send_at = now() - interval '1 minute'")
    conn.commit()
    wa = FakeWhatsApp(set())
    result = outreach.send_due(conn, org, settings, outreach.Senders(whatsapp=wa), now=WEDNESDAY_10AM,
                               sleep=lambda s: None)
    assert wa.sent == [] and result["suprimidas"] == 1


def test_resposta_sair_pelo_whatsapp(ctx, conn):
    boa = _company(conn, "11222333000181")
    conn.execute("update contacts set whatsapp_jid = '5541999887766@s.whatsapp.net' where company_id = %s", (boa["id"],))
    conn.commit()
    payload = {"event": "MESSAGES_UPSERT",
               "data": {"key": {"remoteJid": "123@lid", "remoteJidAlt": "5541999887766@s.whatsapp.net",
                                "fromMe": False, "id": "IN2"},
                        "message": {"extendedTextMessage": {"text": "SAIR"}}}}
    assert inbound.handle_evolution(conn, ctx.org_id, None, payload) == "optout"
    assert db.is_suppressed(conn, ctx.org_id, "whatsapp", "5541999887766")
    stage = conn.execute("select stage from prospects where company_id = %s", (boa["id"],)).fetchone()["stage"]
    assert stage == "disqualified"


def test_dois_processos_nao_enviam_juntos(ctx, conn, settings):
    import psycopg

    org = ctx.org_id
    settings.envio.dry_run = False
    conn.execute("update contacts set phone_status = 'verified' where phone is not null")
    conn.execute("update prospects set stage = 'prioritized', priority = 90")
    conn.commit()
    outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    wa = FakeWhatsApp(set())
    with psycopg.connect(settings.database_url) as other:
        other.execute("select pg_advisory_lock(hashtext(%s))", (f"prospector:send:{org}",))
        busy = outreach.send_due(conn, org, settings, outreach.Senders(whatsapp=wa), now=WEDNESDAY_10AM,
                                 sleep=lambda s: None)
        assert busy["enviadas"] == 0 and wa.sent == []
    done = outreach.send_due(conn, org, settings, outreach.Senders(whatsapp=wa), now=WEDNESDAY_10AM,
                             sleep=lambda s: None)
    assert done["enviadas"] >= 1


def test_maps_vazio_tenta_de_novo_e_desiste(ctx, conn, settings):
    org = ctx.org_id
    gm = FakeGmaps(lambda ids: "")  # Google bloqueou: CSV sem linhas
    for attempt in range(maps.MAX_ATTEMPTS):
        assert maps.submit(conn, org, settings, gm) == 1, attempt
        assert maps.collect(conn, org, gm)["jobs_vazios"] == 1
    assert maps.submit(conn, org, settings, gm) == 0
    unchecked = conn.execute("select count(*) as n from companies where maps_checked_at is null").fetchone()["n"]
    assert unchecked == 0


def test_lote_para_quando_a_janela_fecha(ctx, conn, settings, monkeypatch):
    org = ctx.org_id
    settings.envio.dry_run = False
    conn.execute("update contacts set phone_status = 'verified' where phone is not null")
    conn.execute("update prospects set stage = 'prioritized', priority = 90")
    conn.commit()
    outreach.enqueue(conn, org, settings, ctx.campaign_ids)
    times = iter([WEDNESDAY_10AM.replace(hour=17, minute=29)] * 3 + [WEDNESDAY_10AM.replace(hour=17, minute=33)] * 10)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(times)

    monkeypatch.setattr(outreach, "datetime", Clock)
    wa = FakeWhatsApp(set())
    result = outreach.send_due(conn, org, settings, outreach.Senders(whatsapp=wa), sleep=lambda s: None)
    assert result["enviadas"] == 1 and len(wa.sent) == 1
