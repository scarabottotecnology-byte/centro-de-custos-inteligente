"""Separa empresários e C-level da exportação de conexões do LinkedIn.

O LinkedIn entrega as conexões num Connections.csv (Configurações > Privacidade
de dados > Obter uma cópia dos seus dados > Conexões). Esse arquivo já traz
nome, empresa, cargo, link do perfil e, quando a pessoa permite, o e-mail.
Não acessa o LinkedIn: só lê o arquivo, então não há risco para a conta.

Uso:
    python filtrar_conexoes.py Connections.csv

Gera:
    saida/decisores_conexoes.csv  os decisores, com ou sem e-mail
    perfis.txt                    links dos decisores sem e-mail, para o coletar.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from decisores import classifica

AQUI = Path(__file__).resolve().parent
CAMPOS = ["nome", "cargo", "empresa", "perfil_decisor", "email", "linkedin_url", "fonte"]


def le_conexoes(caminho: Path) -> list[dict]:
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    # O arquivo abre com algumas linhas de aviso antes do cabeçalho de verdade.
    inicio = next((i for i, l in enumerate(linhas) if l.startswith("First Name")), None)
    if inicio is None:
        raise SystemExit(f"{caminho}: não achei o cabeçalho 'First Name'. É o Connections.csv do LinkedIn?")
    return list(csv.DictReader(linhas[inicio:]))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    conexoes = le_conexoes(Path(argv[1]))
    decisores = []
    for c in conexoes:
        perfil = classifica(c.get("Position"))
        if not perfil:
            continue
        decisores.append({
            "nome": f"{c.get('First Name', '')} {c.get('Last Name', '')}".strip(),
            "cargo": c.get("Position", ""),
            "empresa": c.get("Company", ""),
            "perfil_decisor": perfil,
            "email": c.get("Email Address", ""),
            "linkedin_url": c.get("URL", ""),
            "fonte": "conexoes",
        })

    saida = AQUI / "saida"
    saida.mkdir(exist_ok=True)
    with open(saida / "decisores_conexoes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(decisores)

    sem_email = [d["linkedin_url"] for d in decisores if not d["email"] and d["linkedin_url"]]
    (AQUI / "perfis.txt").write_text("\n".join(sem_email) + ("\n" if sem_email else ""), encoding="utf-8")

    com_email = len(decisores) - len(sem_email)
    print(f"{len(conexoes)} conexões lidas, {len(decisores)} decisores "
          f"({com_email} com e-mail, {len(sem_email)} sem).")
    print(f"Planilha: {saida / 'decisores_conexoes.csv'}")
    if sem_email:
        print(f"Links sem e-mail em {AQUI / 'perfis.txt'} (rode o coletar.py para tentar o e-mail do perfil).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
