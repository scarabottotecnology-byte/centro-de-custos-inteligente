"""Classifica um cargo do LinkedIn como empresário, C-level ou nenhum dos dois.

Quem decide a contratação da Keystone é o dono ou a diretoria. O cargo do
LinkedIn é texto livre, em português ou inglês, então a regra é por palavra:
"Sócio-diretor", "CEO & Founder", "Diretora Financeira" e "Owner" contam;
"Assistente de diretoria" e "Analista financeiro" não.
"""

from __future__ import annotations

import re
import unicodedata

EMPRESARIO = "empresario"
C_LEVEL = "c-level"

# Cargos de quem é dono do negócio.
_EMPRESARIO = re.compile(
    r"\b(socio|socia|fundador|fundadora|cofundador|cofundadora|co-fundador|co-fundadora|"
    r"founder|co-founder|cofounder|proprietario|proprietaria|owner|dono|dona|"
    r"empresario|empresaria)\b"
)
# Diretoria executiva.
_C_LEVEL = re.compile(
    r"\b(ceo|cfo|coo|cto|cmo|cio|cro|chief|presidente|president|"
    r"diretor|diretora|director|managing director|head de financas|head of finance)\b"
)
# Palavras que, junto com as de cima, indicam alguém que não decide.
_EXCLUI = re.compile(r"\b(assistente|assistant|secretaria|secretario|estagiario|estagiaria|intern|analista)\b")


def _normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return sem_acento.lower()


def classifica(cargo: str | None) -> str | None:
    """Devolve EMPRESARIO, C_LEVEL ou None para o cargo informado."""
    t = _normaliza(cargo or "")
    if not t or _EXCLUI.search(t):
        return None
    if _EMPRESARIO.search(t):
        return EMPRESARIO
    if _C_LEVEL.search(t):
        return C_LEVEL
    return None
