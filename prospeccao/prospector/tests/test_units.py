from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from prospector import cnpj, inbound, maps, messages, outreach, phones, receita, scoring


class TestCnpj:
    def test_numerico(self):
        assert cnpj.is_valid("11.222.333/0001-81")
        assert not cnpj.is_valid("11.222.333/0001-82")
        assert not cnpj.is_valid("00.000.000/0000-00")

    def test_alfanumerico_exemplo_oficial_da_receita(self):
        assert cnpj.is_valid("12.ABC.345/01DE-35")
        assert cnpj.check_digits("12ABC34501DE") == "35"
        assert not cnpj.is_valid("12.ABC.345/01DE-36")

    def test_dv_nao_aceita_letra(self):
        assert not cnpj.is_valid("12ABC34501DEA5")

    def test_compose_e_format(self):
        assert cnpj.compose("12ABC345", "01DE", "35") == "12ABC34501DE35"
        assert cnpj.format("11222333000181") == "11.222.333/0001-81"


class TestPhones:
    @pytest.mark.parametrize("raw,expected,mobile", [
        ("+55 (41) 99988-7766", "5541999887766", True),
        ("041 3333-4444", "554133334444", False),
        ("(41) 9988-7766", "5541999887766", True),     # celular sem o nono dígito
        ("41999887766", "5541999887766", True),
    ])
    def test_parse(self, raw, expected, mobile):
        p = phones.parse(raw)
        assert p and p.e164 == expected and p.is_mobile is mobile

    @pytest.mark.parametrize("raw", ["", "123", "(20) 3333-4444", "(41) 1111-1111", "(41) 89988-7766"])
    def test_invalidos(self, raw):
        assert phones.parse(raw) is None

    def test_normalize_colunas_da_receita(self):
        assert phones.normalize(" 041", "33334444").e164 == "554133334444"
        assert phones.normalize("", "") is None


class TestScoring:
    def test_normaliza_pelo_peso_disponivel(self, settings):
        icp = settings.icp
        company = {"porte": "DEMAIS", "capital_social": 1_000_000, "data_abertura": date(2015, 1, 1),
                   "cnae_principal": "4639701"}
        value, coverage, breakdown = scoring.score(company, {"mobile": True}, icp, today=date(2026, 10, 1))
        # presença digital não avaliada: sai do denominador, não vira zero
        assert breakdown["presenca_digital"]["nota"] is None
        assert value == 100
        assert coverage == pytest.approx(0.9)

    def test_criterio_sem_dado_nao_penaliza_mas_reduz_cobertura(self, settings):
        company = {"porte": "NAO_INFORMADO", "capital_social": 0, "cnae_principal": "4639701"}
        value, coverage, breakdown = scoring.score(company, {}, settings.icp, today=date(2026, 10, 1))
        assert breakdown["porte"]["nota"] is None and breakdown["capital_social"]["nota"] is None
        assert coverage < scoring.MIN_COVERAGE
        assert value == round(100 * 20 / 30)  # segmento 1.0 (peso 20) + contato 0 (peso 10)

    def test_segmento_prefixo_mais_longo(self, settings):
        icp = settings.icp.model_copy(update={"segmentos": {"4": 0.2, "46": 0.5, "4639": 1.0}})
        _, _, b = scoring.score({"cnae_principal": "4639701"}, {}, icp)
        assert b["segmento"]["nota"] == 1.0


class TestMessages:
    def test_render_sem_ia_nao_deixa_buraco(self, settings):
        company = {"nome_fantasia": "DISTRIBUIDORA BOA VISTA", "municipio": "SAO JOSE DOS PINHAIS", "uf": "PR",
                   "cnae_descricao": "Comércio atacadista de produtos alimentícios em geral",
                   "data_abertura": date(2015, 3, 10)}
        values = messages.variables(company, {"full_name": "Maria Aparecida Souza"}, None,
                                    {"nome": "Jefferson", "empresa": "Keystone"}, "https://x/saida/abc",
                                    today=date(2026, 10, 1))
        text = messages.render(settings.campanhas["whatsapp"].passos[0].texto, values)
        assert text.startswith("Olá, Maria, tudo bem? Aqui é o Jefferson, da Keystone.")
        assert "Distribuidora Boa Vista" in text
        assert "\n\n" not in text and "  " not in text
        assert values["cidade"] == "Sao Jose dos Pinhais"
        assert values["anos"] == "11"

    def test_nome_sem_sufixo_societario(self):
        assert messages.company_name({"razao_social": "ALFA NUMERICA COMERCIO LTDA"}) == "Alfa Numerica Comercio"

    def test_variavel_desconhecida_vira_vazio(self):
        assert messages.render("Oi {nao_existe}!", {}) == "Oi !"


class TestClassificacao:
    @pytest.mark.parametrize("reply,label", [
        ("SAIR", "optout"),
        ("por favor me remova da lista", "optout"),
        ("número errado", "optout"),
        ("Não quero, obrigado", "not_interested"),
        ("já temos contador e controller", "not_interested"),
        ("Sim, pode me ligar amanhã", "interested"),
        ("Quanto custa?", "interested"),
        ("Vocês atendem fora de Curitiba?", "question"),
        ("Somos do Simples, faz diferença?", "question"),   # "simples" não pode casar com "sim"
        ("bom dia", "other"),
    ])
    def test_palavras_chave(self, reply, label):
        assert inbound.classify_keywords(reply) == label

    def test_optout_ignora_modelo(self):
        class Bomba:
            def classify(self, *a):
                raise AssertionError("não deveria chamar o modelo")
        assert inbound.classify(Bomba(), "msg", "pare de mandar mensagem") == ("optout", "palavras-chave")

    def test_strip_quoted(self):
        body = "Tenho interesse.\n\nEm seg., 12 de out. de 2026 Jefferson escreveu:\n> mensagem antiga"
        assert inbound.strip_quoted(body) == "Tenho interesse."


class TestMaps:
    company = {"id": "c1", "razao_social": "DISTRIBUIDORA BOA VISTA LTDA", "nome_fantasia": "BOA VISTA ALIMENTOS",
               "cep": "80010-000", "municipio": "CURITIBA", "uf": "PR"}

    def test_casa_por_nome(self):
        places = [{"title": "Padaria Central"}, {"title": "Boa Vista Alimentos - Distribuidora"}]
        assert maps.best_match(self.company, places)["title"].startswith("Boa Vista")

    def test_casa_por_cep_com_nome_parecido(self):
        places = [{"title": "BV Distribuidora Boa", "complete_address": '{"postal_code": "80010-000"}'}]
        assert maps.best_match(self.company, places) is not None

    def test_recusa_empresa_errada(self):
        assert maps.best_match(self.company, [{"title": "Oficina do Zé"}]) is None

    def test_query_e_csv(self):
        assert maps.query_for(self.company) == "BOA VISTA ALIMENTOS CURITIBA PR"
        grouped = maps.parse_csv("input_id,title,phone\nc1,A,1\nc1,B,2\nc2,C,3\n")
        assert [r["title"] for r in grouped["c1"]] == ["A", "B"]


class TestReceita:
    def test_select_aplica_icp_em_cada_passada(self, receita_dir, settings):
        sel = receita.select(receita_dir, settings.icp.filtros, today=date(2026, 10, 1))
        assert set(sel.estabelecimentos) == {"11222333000181", "12ABC34501DE35", "77888999000181"}
        assert sel.empresas["11222333"]["porte"] == "DEMAIS"
        assert sel.cnaes["4639701"].startswith("Comércio")       # latin-1 lido corretamente
        assert [s["nome"] for s in sel.socios["11222333"]] == ["MARIA APARECIDA SOUZA", "JOAO PEREIRA"]
        assert "12ABC345" not in sel.socios                       # sócio PJ não entra

    def test_decisor_prefere_socio_administrador(self):
        socios = [{"nome": "B", "qualificacao": "22"}, {"nome": "A", "qualificacao": "49"}]
        assert receita.decisor(socios)["nome"] == "A"

    def test_parsers(self):
        assert receita.parse_date("00000000") is None
        assert receita.parse_date("20150310") == date(2015, 3, 10)
        assert str(receita.parse_money("1500000,00")) == "1500000.00"


def test_janela_de_envio(settings):
    tz = "America/Sao_Paulo"
    assert outreach.in_window(settings, datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo(tz)), tz)      # quarta
    assert not outreach.in_window(settings, datetime(2026, 10, 14, 20, 0, tzinfo=ZoneInfo(tz)), tz)  # noite
    assert not outreach.in_window(settings, datetime(2026, 10, 17, 10, 0, tzinfo=ZoneInfo(tz)), tz)  # sábado


class TestDns:
    def test_mx_presente(self, monkeypatch):
        from prospector import verify
        monkeypatch.setattr(verify.dns.resolver, "resolve", lambda d, r, lifetime: ["mx"])
        assert verify._has_mail_server("boavista.com.br") is True

    def test_sem_mx_usa_registro_a(self, monkeypatch):
        from prospector import verify
        calls = []

        def resolve(domain, record, lifetime):
            calls.append(record)
            if record == "MX":
                raise verify.dns.resolver.NoAnswer()
            return ["1.2.3.4"]

        monkeypatch.setattr(verify.dns.resolver, "resolve", resolve)
        assert verify._has_mail_server("exemplo.com.br") is True and calls == ["MX", "A"]

    def test_dominio_inexistente(self, monkeypatch):
        from prospector import verify

        def resolve(domain, record, lifetime):
            raise verify.dns.resolver.NXDOMAIN()

        monkeypatch.setattr(verify.dns.resolver, "resolve", resolve)
        assert verify._has_mail_server("nao-existe.com.br") is False

    def test_servidor_de_nomes_falhou_vira_none(self, monkeypatch):
        from prospector import verify

        def resolve(domain, record, lifetime):
            raise verify.dns.resolver.NoNameservers()

        monkeypatch.setattr(verify.dns.resolver, "resolve", resolve)
        assert verify._has_mail_server("boavista.com.br") is None

    def test_timeout_vira_none(self, monkeypatch):
        from prospector import verify

        def resolve(domain, record, lifetime):
            raise verify.dns.exception.Timeout()

        monkeypatch.setattr(verify.dns.resolver, "resolve", resolve)
        assert verify._has_mail_server("lento.com.br") is None


def test_prune_apaga_so_meses_antigos(tmp_path):
    for month in ("2026-08", "2026-09"):
        (tmp_path / month).mkdir()
        (tmp_path / month / "Empresas0.zip").write_bytes(b"x" * 10)
        (tmp_path / month / ".carregado").write_text("ok")
    assert receita.prune(tmp_path, keep=tmp_path / "2026-09") == 10
    assert not (tmp_path / "2026-08" / "Empresas0.zip").exists()
    assert (tmp_path / "2026-08" / ".carregado").exists()
    assert (tmp_path / "2026-09" / "Empresas0.zip").exists()
