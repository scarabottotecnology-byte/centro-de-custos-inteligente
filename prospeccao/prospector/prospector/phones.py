"""Normalização de telefones brasileiros para E.164 sem '+' (55 + DDD + número)."""

import re
from dataclasses import dataclass

_VALID_DDD = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68,
    69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95,
    96, 97, 98, 99,
}


@dataclass(frozen=True)
class Phone:
    e164: str          # 5541999998888
    is_mobile: bool


def normalize(ddd: str | None, number: str | None) -> Phone | None:
    """Combina DDD e número como vêm separados na base da Receita."""
    d = re.sub(r"\D", "", ddd or "").lstrip("0")
    n = re.sub(r"\D", "", number or "")
    if not n:
        return None
    return parse(d + n) if d else parse(n)


def parse(raw: str | None) -> Phone | None:
    """Aceita '+55 (41) 99999-8888', '041 3333-4444', '41999998888' etc."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    digits = digits.lstrip("0")
    if len(digits) not in (10, 11):
        return None
    ddd, local = int(digits[:2]), digits[2:]
    if ddd not in _VALID_DDD:
        return None
    # Celular de 8 dígitos (anterior a 2016): falta o nono dígito.
    if len(local) == 8 and local[0] in "6789":
        local = "9" + local
    if len(local) == 9 and local[0] != "9":
        return None
    if len(local) == 8 and local[0] not in "2345":
        return None
    if len(set(local)) == 1:
        return None
    return Phone(e164=f"55{ddd}{local}", is_mobile=len(local) == 9)
