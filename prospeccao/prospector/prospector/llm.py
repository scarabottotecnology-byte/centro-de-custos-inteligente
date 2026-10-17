"""Chamadas ao Claude: pesquisa da empresa (A6) e classificação de resposta (A8).

Opcional. Sem ANTHROPIC_API_KEY o sistema usa só os templates e a
classificação por palavras-chave — prospecta do mesmo jeito, só menos
personalizado.

Regra de aterramento (docs/05): o modelo só recebe os campos que o banco tem e
é instruído a não afirmar nada fora deles. `grounded_on` grava quais campos
foram usados.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

RESEARCH_SYSTEM = """Você é analista comercial de uma empresa de controladoria e BPO financeiro que vende para pequenas e médias empresas brasileiras.
Recebe os dados públicos de uma empresa (Receita Federal e Google Maps) e a oferta do vendedor.
Escreva em português do Brasil, tom direto e cordial, sem jargão.
Use SOMENTE os fatos presentes nos dados. Não invente faturamento, número de funcionários, notícias, clientes ou dores específicas que os dados não mostrem; quando inferir uma dor, trate como hipótese ("empresas desse porte costumam...").
A frase de abertura deve ter no máximo 25 palavras, citar algo concreto dos dados (segmento, cidade, tempo de mercado, avaliações) e não pode prometer resultado."""

CLASSIFY_SYSTEM = """Classifique a resposta de um prospect a uma mensagem de prospecção B2B (português do Brasil).
- interested: quer conversar, pede proposta, preço, horário ou reunião
- question: faz pergunta sem recusar
- not_interested: recusa educada, já tem fornecedor, não é o momento
- optout: pede para não receber mais mensagens, reclama, diz que é engano ou ameaça denunciar
- other: resposta automática, saudação vazia, sem relação"""


class Research(BaseModel):
    summary: str = Field(description="2 a 3 frases sobre a empresa, só com fatos dos dados")
    likely_pain: str = Field(description="hipótese de dor financeira/gerencial, marcada como hipótese")
    suggested_approach: str = Field(description="como abordar em uma frase")
    opening_line: str = Field(description="frase de abertura personalizada, até 25 palavras")
    grounded_on: list[str] = Field(description="nomes dos campos dos dados usados")


class Classification(BaseModel):
    label: Literal["interested", "question", "not_interested", "optout", "other"]
    reason: str


class Claude:
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.Anthropic()

    def _parse(self, system: str, user: str, schema: type[BaseModel], max_tokens: int):
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": "low"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            log.warning("modelo recusou a solicitação (%s)", getattr(response.stop_details, "category", None))
            return None
        return response.parsed_output

    def research(self, facts: dict, offer: str) -> Research | None:
        user = (f"OFERTA DO VENDEDOR:\n{offer}\n\n"
                f"DADOS DA EMPRESA (JSON):\n{json.dumps(facts, ensure_ascii=False, default=str)}")
        return self._parse(RESEARCH_SYSTEM, user, Research, 2000)

    def classify(self, our_message: str | None, reply: str) -> Classification | None:
        user = f"NOSSA MENSAGEM:\n{our_message or '(não disponível)'}\n\nRESPOSTA DO PROSPECT:\n{reply}"
        return self._parse(CLASSIFY_SYSTEM, user, Classification, 1000)


def build(model: str, enabled: bool) -> Claude | None:
    return Claude(model) if enabled else None
