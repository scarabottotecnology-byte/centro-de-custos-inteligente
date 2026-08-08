# 11 — Plano de Estrutura no ClickUp (Growth OS)

Especificação da pasta de produto a ser criada no ClickUp. Este documento é o
contrato do que será criado — serve tanto para a criação automatizada quanto para
criação manual, se preferir.

> **Escopo.** Esta pasta contém **apenas o projeto do aplicativo**. As 53 fichas
> comerciais existentes (listas GROWTH, GERAL, COMERCIAL — Claude Version, POP)
> não são tocadas: são a operação comercial da consultoria, não o software.
> Portal Crimson e a Controladoria da Oficial Farma são projetos de outra empresa
> e não têm relação alguma com isto.

---

## Destino

| | |
|---|---|
| Workspace | `90133024540` |
| Espaço | **KEYSTONE** — `901313737868` |
| Pasta nova | **GROWTH OS — Produto** |
| Listas | 7 (uma por eixo) |
| Fichas | 24 (uma por fase) |

### Premissa das datas

Início em **segunda-feira, 10/08/2026**, com os prazos derivados das estimativas
em semanas do documento `09-ROADMAP-E-ACEITE.md`. O **Eixo D corre em paralelo ao
Eixo C** (depende apenas da FASE 3), que é o cenário recomendado no roadmap.
As datas são derivadas, não compromisso — ajuste na pasta depois de criada.

---

## Estrutura

### EIXO A — Fundação
*Estrutura técnica, banco, autenticação, multi-tenant e a tela executiva.
Contém a correção da falha crítica de segurança. Nenhum outro eixo pode começar
antes deste terminar.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 1 — Fundação técnica** | 24/08/2026 | 2 sem |
| **FASE 2 — Banco, autenticação e multi-tenant** | 14/09/2026 | 3 sem |
| **FASE 3 — Command Center** | 24/09/2026 | 1,5 sem |

### EIXO B — Conteúdo
*Inteligência de mercado, estratégia editorial e a fábrica de conteúdo com IA.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 4 — Content Strategy + Market Intelligence** | 12/10/2026 | 2,5 sem |
| **FASE 5 — AI Content Factory + Review** | 29/10/2026 | 2,5 sem |

### EIXO C — Publicação e Análise
*Integração com as redes, coleta de métricas e o primeiro loop de aprendizado.
Depende de aprovação de terceiros — ver as fichas de bloqueio na FASE 1.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 6 — LinkedIn** | 16/11/2026 | 2,5 sem |
| **FASE 7 — Meta / Instagram** | 30/11/2026 | 2 sem |
| **FASE 8 — Social Analytics** | 14/12/2026 | 2 sem |
| **FASE 9 — AI Performance Analyst** | 24/12/2026 | 1,5 sem |

### EIXO D — Demanda
*Captura de leads, ICP, descoberta de empresas e inteligência de prospecção.
Corre em paralelo ao Eixo C — depende apenas da FASE 3.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 10 — Lead Engine** | 08/10/2026 | 2 sem |
| **FASE 11 — ICP Engine** | 19/10/2026 | 1,5 sem |
| **FASE 12 — Company Discovery** | 05/11/2026 | 2,5 sem |
| **FASE 13 — Prospect Intelligence** | 19/11/2026 | 2 sem |

### EIXO E — Relacionamento
*Abordagem por e-mail e WhatsApp, qualificação por IA e CRM. É o eixo de maior
risco de conformidade: o primeiro em que o sistema fala com pessoas reais.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 14 — E-mail Outreach** | 14/01/2027 | 3 sem |
| **FASE 15 — WhatsApp** | 01/02/2027 | 2,5 sem |
| **FASE 16 — AI Qualification** | 15/02/2027 | 2 sem |
| **FASE 17 — CRM + Pipeline** | 01/03/2027 | 2 sem |

### EIXO F — Inteligência
*Atribuição de receita, agente estratégico e o ciclo diário automático.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 18 — Attribution** | 15/03/2027 | 2 sem |
| **FASE 19 — AI Growth Strategist** | 29/03/2027 | 2 sem |
| **FASE 20 — Daily Growth Cycle** | 08/04/2027 | 1,5 sem |

### EIXO G — Produção
*Observabilidade, LGPD, testes, hardening e deploy.*

| Ficha | Prazo | Est. |
|---|---|---|
| **FASE 21 — Observabilidade e segurança** | 22/04/2027 | 2 sem |
| **FASE 22 — Testes completos** | 06/05/2027 | 2 sem |
| **FASE 23 — Hardening** | 17/05/2027 | 1,5 sem |
| **FASE 24 — Deploy** | 24/05/2027 | 1 sem |

---

## Conteúdo de cada ficha

Cada uma das 24 fichas recebe, na descrição:

1. **Objetivo** — uma frase sobre o que a fase entrega.
2. **Entregas** — a lista de itens do roadmap.
3. **Critérios de aceite** — os checkboxes de `09-ROADMAP-E-ACEITE.md §3`,
   em formato de checklist markdown, para marcar dentro do card.
4. **Dependência** — qual fase precisa estar concluída antes.
5. **Referência** — o documento de arquitetura correspondente.

A ficha só é fechada quando todos os critérios estiverem marcados — é a
`Definição de COMPLETE` do documento 09 aplicada dentro do ClickUp.

---

## Prioridades

| Prioridade | Fichas | Motivo |
|---|---|---|
| `urgent` | FASE 1, FASE 2 | A FASE 2 corrige o achado C-01, que hoje deixa dados financeiros de clientes expostos a leitura e exclusão anônimas |
| `high` | FASES 3, 6, 7, 14, 15, 21 | Gargalos de caminho crítico ou de conformidade |
| `normal` | demais | — |

---

## Observação sobre bloqueadores externos

Três itens da FASE 1 não são código e têm semanas de espera por terceiros:
o pedido de acesso ao LinkedIn Community Management API, o App Review da Meta
e a verificação de negócio do WhatsApp. Eles entram como critérios de aceite
da FASE 1 justamente para não serem esquecidos — se ficarem para as FASES 6, 7
e 15, travam o roadmap.

---

## Estado da execução

| Data | Evento |
|---|---|
| 08/08/2026 | Estrutura especificada. Criação da pasta bloqueada por rate limit da API do ClickUp (224 min). Nova tentativa agendada. |
