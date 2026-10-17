# 16 — Prospecção autônoma

**Status:** implementado em `prospeccao/`, testado com Postgres real e com as
APIs reais do gosom, Reacher e Evolution. Falta rodar com internet aberta
(download da Receita, Google Maps e pareamento do WhatsApp).
**Decisão:** ADR-014.

---

## O que faz

Um robô que, sozinho e todo dia útil:

1. **Descobre** empresas na base aberta do CNPJ da Receita Federal, só as que
   batem com o ICP (UF, município, CNAE, porte, capital social, idade, sem MEI).
2. **Enriquece** os prospects mais promissores no Google Maps: site, telefone
   comercial, nota, número de avaliações e e-mails publicados no site.
3. **Pontua** cada empresa (ICP Score 0–100, normalizado pelo peso que tinha
   dado para avaliar) e prioriza.
4. **Verifica** os canais: domínio do e-mail pelo DNS (ou Reacher, se houver
   porta 25), número no próprio WhatsApp.
5. **Pesquisa** a empresa com o Claude e escreve uma frase de abertura
   (opcional, só com fatos do banco).
6. **Aborda** por WhatsApp ou e-mail, em cadência de 3 passos, dentro da janela
   de horário e do limite diário.
7. **Lê as respostas**, para a sequência de quem respondeu, descadastra quem
   pediu e **avisa o Jefferson no WhatsApp** na hora que um lead demonstra
   interesse.

## Peças

| Peça | Projeto | Licença | Papel |
|---|---|---|---|
| Base de empresas | Dados Abertos CNPJ (Receita) | dado público | Discovery |
| ETL | `prospector` (próprio) | — | Carga filtrada pelo ICP |
| Google Maps | gosom/google-maps-scraper | MIT | Enriquecimento |
| Verificação de e-mail | DNS (dnspython); opcional: reacherhq/check-if-email-exists | ISC; AGPL-3.0 (serviço separado) | Antes do envio |
| WhatsApp | EvolutionAPI/evolution-api v2.3.7 | Apache-2.0 + aviso de uso | Envio e respostas |
| Orquestração | `worker` do prospector, ou n8n | — / Sustainable Use | Agenda |
| IA (opcional) | Claude (`claude-opus-5-5`) | API paga | Pesquisa A6 e classificação A8 |

## Como encaixa no Growth OS

O esquema (`prospeccao/db/init/001_schema.sql`) usa os nomes do contrato de
`02-MODELO-DE-DADOS.md` §4.5 e §4.6 — `companies`, `contacts`, `prospects`,
`prospect_scores`, `campaigns`, `campaign_steps`, `campaign_contacts`,
`outreach_messages`, `suppression_list`, `leads` — com `organization_id` em
tudo. Quando o Supabase `keystone-growth-os` receber a FASE 2, as tabelas
migram sem renomear. Desvios do contrato estão marcados com `DESVIO:` no SQL:

- `contacts`: unicidade por empresa, não por organização (o e-mail do contador
  aparece em centenas de empresas).
- `companies`: colunas do Google Maps, `cnae_descricao`, `opcao_simples`.
- `company_partners`: tabela nova para o quadro societário (nome do decisor).
- `campaign_steps.body`: template inline, sem `message_templates`.

Mapeamento para os workflows de `04-WORKFLOWS-N8N.md`:

| Workflow | Etapa do prospector |
|---|---|
| WF-006 Prospect Scoring | `pontuar` |
| WF-009 WhatsApp Outreach | `enviar` (canal whatsapp) |
| WF-011 Lead Qualification | webhook `/webhooks/evolution` + `caixa` |
| WF-012 Company Discovery | `receita-baixar` + `receita-carregar` |

## Garantias testadas

`prospeccao/prospector/tests/` — 61 testes, incluindo o ciclo completo contra
Postgres:

- CNPJ alfanumérico validado pelo exemplo oficial da Receita.
- Recarga mensal da Receita não duplica contato nem perde status de verificação.
- O mesmo passo nunca é enviado duas vezes, mesmo reprocessando, e dois
  processos não enviam ao mesmo tempo (lock no Postgres).
- Fim de semana e fora do horário não envia; limite diário é respeitado; um
  lote que alcança o fim da janela para no meio.
- Job do Google Maps que volta vazio (bloqueio) é tentado de novo até 3 vezes.
- Quem responde sai da sequência; "SAIR" bloqueia para sempre, por regra (não
  por modelo), e a lista guarda só hash.
- Simulação grava a prévia sem enviar e libera o envio real depois, sem
  duplicar.
- Webhook repetido do WhatsApp não cria lead nem aviso em dobro.

## Custo zero (17/10/2026)

A pedido do Jefferson, a stack roda sem gasto no próprio PC Windows
(`prospeccao/WINDOWS.md`): Docker Desktop, Gmail dedicado com senha de app,
Tailscale Funnel para o link de descadastro e sem chave da Anthropic.

O Reacher saiu do padrão (`--profile reacher`): precisa da porta 25 de saída,
bloqueada na internet residencial brasileira e nas nuvens gratuitas, e a imagem
só existe para amd64. No lugar, `verify.emails_mx` consulta o DNS do domínio:
sem servidor de e-mail, o contato vira `unverified`; com servidor, segue
`unknown` com `email_checked_at` e pode entrar em campanha — o bounce é
suprimido pela leitura da caixa. Antes de cada lote, o DNS precisa confirmar
`gmail.com`; se não confirmar (internet caiu, DNS filtrado), nada é marcado.

As portas publicadas passaram a abrir só em `127.0.0.1`.

## Pendências

1. Rodar com internet aberta (este ambiente bloqueia
   `arquivos.receitafederal.gov.br`, Google e WhatsApp).
2. Chip dedicado para o WhatsApp de prospecção.
3. Revisar os textos da campanha em `prospeccao.yaml` e o ICP da região.
4. Migrar as tabelas para o Supabase `keystone-growth-os` na FASE 2.
