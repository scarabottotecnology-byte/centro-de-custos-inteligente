import csv
import io
import os
import zipfile
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from prospector import config, db

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = ROOT / "prospeccao.example.yaml"


def write_zip(path: Path, rows: list[list[str]]) -> None:
    """Grava no formato da Receita: latin-1, ';', tudo entre aspas, sem cabeçalho."""
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL, lineterminator="\n").writerows(rows)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(path.stem.upper() + ".CSV", buf.getvalue().encode("latin-1"))


def estab(basico, ordem, dv, *, fantasia="", situacao="02", inicio="20150310", cnae="4639701",
          uf="PR", municipio="7535", ddd1="41", tel1="999887766", email="", matriz="1", cep="80010000"):
    return [basico, ordem, dv, matriz, fantasia, situacao, "20150310", "00", "", "", inicio, cnae,
            "4691500,4637199", "RUA", "XV DE NOVEMBRO", "100", "SALA 2", "CENTRO", cep, uf, municipio,
            ddd1, tel1, "", "", "", "", email, "", ""]


@pytest.fixture
def receita_dir(tmp_path: Path) -> Path:
    """Mês fictício com sete estabelecimentos; três passam no ICP de exemplo."""
    folder = tmp_path / "receita" / "2026-09"
    folder.mkdir(parents=True)
    write_zip(folder / "Municipios.zip", [["7535", "CURITIBA"], ["7537", "LONDRINA"]])
    write_zip(folder / "Cnaes.zip", [["4639701", "Comércio atacadista de produtos alimentícios em geral"],
                                     ["8630503", "Atividade médica ambulatorial"]])
    write_zip(folder / "Estabelecimentos0.zip", [
        # 1. passa: atacadista em Curitiba, celular, e-mail próprio
        estab("11222333", "0001", "81", fantasia="DISTRIBUIDORA BOA VISTA", email="contato@boavista.com.br"),
        # 2. passa: CNPJ alfanumérico, fixo, e-mail do contador
        estab("12ABC345", "01DE", "35", fantasia="", cnae="4639701", ddd1="41", tel1="33334444",
              email="fiscal@contabilx.com.br"),
        # 3. baixada
        estab("33444555", "0001", "81", situacao="08"),
        # 4. outra cidade
        estab("44555666", "0001", "81", municipio="7537"),
        # 5. aberta há menos de 2 anos
        estab("55666777", "0001", "81", inicio="20260101"),
        # 6. MEI (excluído no Simples)
        estab("66777888", "0001", "81", email="fiscal@contabilx.com.br"),
        # 7. passa: outro cliente do mesmo escritório contábil
        estab("77888999", "0001", "81", fantasia="METALURGICA SUL", cnae="2539001", ddd1="", tel1="",
              email="FISCAL@contabilx.com.br"),
    ])
    write_zip(folder / "Empresas0.zip", [
        ["11222333", "DISTRIBUIDORA BOA VISTA LTDA", "2062", "49", "1500000,00", "05", ""],
        ["12ABC345", "ALFA NUMERICA COMERCIO LTDA", "2062", "49", "250000,00", "03", ""],
        ["33444555", "BAIXADA LTDA", "2062", "49", "100000,00", "05", ""],
        ["66777888", "MEI DA SILVA", "2135", "50", "60000,00", "03", ""],
        ["77888999", "METALURGICA SUL LTDA", "2062", "49", "80000,00", "05", ""],
    ])
    write_zip(folder / "Simples.zip", [
        ["11222333", "N", "", "", "N", "", ""],
        ["12ABC345", "S", "20200101", "", "N", "", ""],
        ["66777888", "S", "20200101", "", "S", "20200101", ""],
    ])
    write_zip(folder / "Socios0.zip", [
        ["11222333", "2", "MARIA APARECIDA SOUZA", "***123456**", "49", "20150310", "", "", "", "", "5"],
        ["11222333", "2", "JOAO PEREIRA", "***654321**", "22", "20150310", "", "", "", "", "6"],
        ["12ABC345", "1", "HOLDING XYZ LTDA", "99888777000100", "22", "20200101", "", "", "", "", "0"],
    ])
    (folder / ".completo").write_text("ok")
    return folder


@pytest.fixture
def settings(tmp_path, monkeypatch) -> config.Settings:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = config.load(EXAMPLE_CONFIG)
    s.data_dir = tmp_path
    s.database_url = os.environ.get("TEST_DATABASE_URL", "")
    s.public_url = "https://prospeccao.exemplo.com.br"
    s.api_token = "segredo"
    return s


@pytest.fixture
def conn(settings):
    url = settings.database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL não definida")
    with psycopg.connect(url, row_factory=dict_row) as c:
        c.execute("drop schema public cascade; create schema public;")
        c.commit()
        db.apply_schema(c)
        yield c
