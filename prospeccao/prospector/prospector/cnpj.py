"""CNPJ numérico e alfanumérico (IN RFB 2.229/2024, emitido desde jul/2026).

As 12 primeiras posições aceitam 0-9 e A-Z; os 2 dígitos verificadores
continuam numéricos. O valor de cada caractere é o código ASCII menos 48, então
'0'..'9' valem 0..9 e 'A' vale 17 — o mesmo cálculo de módulo 11 de sempre.
"""

import re

_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_SHAPE = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def clean(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def _dv(chars: str, weights: list[int]) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights, strict=True))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def check_digits(base12: str) -> str:
    first = _dv(base12, _WEIGHTS_1)
    second = _dv(base12 + str(first), _WEIGHTS_2)
    return f"{first}{second}"


def is_valid(value: str) -> bool:
    cnpj = clean(value)
    if not _SHAPE.match(cnpj) or len(set(cnpj)) == 1:
        return False
    return cnpj[12:] == check_digits(cnpj[:12])


def compose(basico: str, ordem: str, dv: str) -> str:
    """Monta o CNPJ a partir das três colunas do arquivo de Estabelecimentos."""
    return clean(basico).rjust(8, "0") + clean(ordem).rjust(4, "0") + clean(dv).rjust(2, "0")


def format(value: str) -> str:  # noqa: A001 - espelha o vocabulário do domínio
    c = clean(value)
    if len(c) != 14:
        return value
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
