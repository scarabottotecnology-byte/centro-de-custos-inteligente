# Prospecção autônoma — Keystone

Robô de prospecção B2B 100% open source e auto-hospedado. Acha empresas na base
da Receita Federal, enriquece no Google Maps, pontua pelo seu ICP, verifica os
canais e aborda por WhatsApp e e-mail — sozinho, dentro do horário comercial.
Quando alguém responde com interesse, você recebe um aviso no seu WhatsApp.

Arquitetura e decisões: [`docs/16-PROSPECCAO-AUTONOMA.md`](../docs/16-PROSPECCAO-AUTONOMA.md)
e ADR-014 em [`docs/10`](../docs/10-DECISOES-ARQUITETURAIS-ADR.md).

```
Receita (CNPJ) ─▶ ICP Score ─▶ Google Maps ─▶ checagem DNS / WhatsApp ─▶ Claude (opcional)
                                                                              │
          aviso no seu WhatsApp ◀── lead ◀── resposta ◀── WhatsApp / e-mail ◀─┘
```

## O que você precisa

**Custo zero, no seu computador Windows:** siga o [`WINDOWS.md`](./WINDOWS.md).

| | Grátis | Pago (opcional) |
|---|---|---|
| Onde roda | seu PC com Docker Desktop, ligado em horário comercial | VPS Linux de 4 GB (R$ 40–80/mês), 24 h |
| WhatsApp | um chip que você já tenha parado | chip novo (~R$ 15, uma vez) |
| E-mail | Gmail novo só para prospecção, com senha de app (500/dia) | subdomínio próprio com SPF, DKIM e DMARC |
| Link de descadastro | Tailscale Funnel (`https://seu-pc.xxx.ts.net`) ou só a resposta "SAIR" | domínio com HTTPS |
| Checagem de e-mail | DNS do domínio (padrão) | Reacher, só em servidor com porta 25 liberada |
| IA | sem IA: templates e palavras-chave | chave da Anthropic |

Em qualquer caso: ~30 GB de disco (os arquivos da Receita ocupam ~8 GB e o mês
anterior é apagado depois de cada carga) e **um número de WhatsApp dedicado —
nunca o seu pessoal nem o da empresa.**

## Subir

No Windows, siga o [`WINDOWS.md`](./WINDOWS.md). No Linux ou Mac:

```bash
cd prospeccao
cp .env.example .env                     # preencha as senhas e o SMTP
cp prospeccao.example.yaml prospeccao.yaml   # ajuste ICP, região e textos
docker compose up -d
docker compose run --rm cli init
```

### 1. Carregar as empresas (uma vez; depois o `worker` repete todo mês)

```bash
docker compose run --rm cli receita-baixar      # ~8 GB, pode levar 1 h
docker compose run --rm cli receita-carregar    # aplica o ICP e grava
docker compose run --rm cli pontuar
docker compose run --rm cli funil
```

Quanto mais fechado o filtro em `icp.filtros`, mais rápida a carga. Um estado
inteiro com todos os CNAEs pode passar de um milhão de empresas — comece por
algumas cidades.

### 2. Conectar o WhatsApp

```bash
docker compose run --rm cli whatsapp-conectar
```

Abra o painel do Evolution em `http://localhost:8081/manager`, entre com a URL
`http://localhost:8081` e a `EVOLUTION_APIKEY`, clique em **Conectar** na
instância `prospeccao` e leia o QR com o WhatsApp do chip (Aparelhos conectados
→ Conectar aparelho). O QR expira em segundos, por isso o painel é mais prático.

As portas só abrem para o próprio computador. Num servidor remoto, abra antes
um túnel a partir da sua máquina: `ssh -L 8081:localhost:8081 usuario@servidor`.

### 3. Ensaiar sem enviar

Com `PROSPECTOR_DRY_RUN=true` (padrão), o robô faz tudo menos enviar: as
mensagens ficam no banco com status `dry_run` e aparecem no log.

```bash
docker compose logs -f worker
docker compose exec postgres psql -U prospector -c \
  "select channel, body from outreach_messages where status = 'dry_run' limit 5"
```

Leu, gostou? Mude `PROSPECTOR_DRY_RUN=false` no `.env` e
`docker compose up -d worker api`. As prévias viram envio real, sem duplicar.

## Como ele trabalha sozinho

O serviço `worker` roda em loop:

| Quando | O quê |
|---|---|
| a cada 10 min | coleta resultados do Maps, lê respostas, envia mensagens vencidas |
| a cada 2 h | ciclo completo: Maps → pontuar → verificar → pesquisar → enfileirar → enviar |
| todo mês, a partir do dia 10 | baixa e recarrega a base da Receita |

Envio só acontece em dia útil, das 9h às 17h30 (configurável), até o limite
diário por canal, com intervalo aleatório de 1,5 a 4 min entre mensagens de
WhatsApp.

Prefere orquestrar visualmente? `docker compose --profile n8n up -d` e importe
os workflows de `n8n/` (eles chamam a mesma API). Use o `worker` **ou** o n8n
para o ciclo; os dois juntos não duplicam envio, mas gastam recurso à toa.

## Comandos

```bash
docker compose run --rm cli <comando>
```

| Comando | O que faz |
|---|---|
| `init` | cria o esquema, a organização, o ICP e as campanhas do YAML |
| `receita-baixar` / `receita-carregar` | base da Receita |
| `pontuar` | ICP Score e priorização |
| `maps` | envia e coleta buscas no Google Maps |
| `verificar` | e-mail (DNS, ou Reacher se configurado) e WhatsApp |
| `pesquisar` | pesquisa e frase de abertura com o Claude |
| `enfileirar` | põe os priorizados na campanha do melhor canal |
| `enviar` | envia o que venceu |
| `caixa` | lê respostas e bounces por IMAP |
| `aprovar` | libera contatos pendentes (se `envio.modo: approval_required`) |
| `ciclo` | roda o ciclo inteiro uma vez |
| `funil` | números do funil |

Consultas úteis no banco:

```sql
select * from v_funil;
select * from leads order by created_at desc;
select * from v_contadores_parceiros order by empresas_atendidas desc;  -- escritórios contábeis
```

`v_contadores_parceiros` lista os e-mails que aparecem em várias empresas do
cadastro — quase sempre o escritório contábil delas. Para uma controladoria,
é uma lista de parceiros de indicação.

## Respostas

| Resposta | O que acontece |
|---|---|
| interesse ou pergunta | sequência para, vira `lead`, você recebe aviso no WhatsApp |
| "não tenho interesse" | sequência para, prospect desqualificado |
| "SAIR", "pare", "engano"… | bloqueado para sempre em todos os canais |
| link de descadastro do e-mail | idem |

Com a chave da Anthropic, a classificação usa o Claude; sem ela, palavras-chave.
Pedido de descadastro é decidido sempre por regra, nunca pelo modelo.

## Para não queimar o canal

- **WhatsApp:** comece com 15–20 mensagens/dia num chip novo e suba 5 por
  semana. Banimento derruba o número e todas as conversas.
- **E-mail:** comece com 20–40/dia por caixa. Hard bounce entra na lista de
  supressão sozinho.
- Mantenha o "responda SAIR" da primeira mensagem. Denúncia como spam é o que
  mais derruba número.

## Avisos de licença

- **Evolution API** — este sistema usa a Evolution API (evolution-api.com)
  para o WhatsApp. A licença pede que esse aviso fique visível a quem
  administra o sistema e que o logo e o copyright do painel não sejam
  removidos.
- **Reacher** (opcional, `--profile reacher`) é AGPL-3.0 e roda como serviço
  separado, chamado por HTTP.
- **gosom/google-maps-scraper** é MIT. Raspar o Google Maps viola os termos de
  uso do Google; o risco prático é bloqueio de IP (concorrência baixa por
  padrão; dá para usar proxy). Decisão registrada no ADR-014.

## Desenvolvimento

```bash
cd prospector
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest                                          # testes de unidade
docker run -d --name pg -e POSTGRES_PASSWORD=x -p 5433:5432 postgres:16-alpine
TEST_DATABASE_URL=postgresql://postgres:x@localhost:5433/postgres pytest   # + integração
```
