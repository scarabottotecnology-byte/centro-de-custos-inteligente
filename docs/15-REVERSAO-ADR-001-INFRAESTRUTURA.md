# 15 — Reversão do ADR-001: infraestrutura própria para o Growth OS

**Status:** decisão revista em 08/08/2026, a pedido do cliente.
**Substitui:** ADR-001 do documento 10.

---

## O que o ADR-001 dizia

> "Expandir este repositório. O Centro de Custos vira o módulo **Cost
> Intelligence** dentro do Growth OS. Mesma organização, mesmo Supabase, mesmos
> usuários."

## Por que estava errado

A decisão foi tomada sobre uma premissa que eu não verifiquei: a de que o
repositório e o projeto Supabase pertenciam à Keystone e podiam ser
compartilhados. **Nenhuma das duas coisas se confirmou.**

O cliente informou que o Centro de Custos é outro produto, com outra finalidade.
E a verificação subsequente revelou algo que a auditoria da FASE 0 não tinha
alcançado — justamente porque o MCP do Supabase negava permissão, e eu registrei
isso como limitação de sessão em vez de investigar a causa.

---

## O achado: o banco não está sob controle da Keystone

A aplicação aponta para o projeto Supabase `hlvkkziiaeyqyenekdck`.

A organização Supabase da Keystone (`bgrfqtbkcqzkpcdswthx`) contém três
projetos, e **nenhum deles é esse**:

| Projeto | Ref | Estado |
|---|---|---|
| portal-crimson | `dborbtlmcewxcypexdgj` | inativo |
| scarabottotecnology-byte's Project | `imsyshhahmiftwwqhlcl` | ativo |
| Plataforma controladoria | `tbiabzdvssypslkxxuef` | inativo |

`hlvkkziiaeyqyenekdck` é um projeto **provisionado e gerenciado pela Lovable**.
Isso explica retroativamente por que o MCP do Supabase respondia
"You do not have permission to perform this action": o projeto não pertence à
conta da Keystone.

### O que isso significa na prática

- Os lançamentos financeiros de clientes estão num banco administrado por
  terceiro, fora do painel Supabase da Keystone.
- Migração, política de RLS, backup e restauração dependem do intermediário.
- Sair da Lovable exige um plano de migração de dados que ninguém escreveu.
- **A correção do C-01 depende de acesso que hoje não é direto.**

Isto não é acusação à Lovable — é como a plataforma funciona, e é uma
conveniência legítima para prototipar. Mas não é onde deve viver o banco de um
produto comercial com dado de cliente.

---

## Nova decisão

### ADR-013 — Infraestrutura própria e separada para o Growth OS 🔴

**Decisão.** O Keystone Growth OS nasce com repositório próprio, projeto
Supabase próprio na organização da Keystone, e ciclo de deploy próprio. Não
herda nada da infraestrutura do Centro de Custos.

**Razões.**

1. **São produtos diferentes.** O Centro de Custos é ferramenta de
   controladoria; o Growth OS é sistema comercial. Compartilhar banco os
   acopla sem que haja fluxo de dado real entre eles.
2. **O banco atual não é da Keystone.** Construir um produto comercial sobre
   infraestrutura administrada por terceiro é dívida de governança.
3. **Multi-tenant desde o início fica mais limpo.** Sem backfill, sem
   convivência com tabela legada, sem migração de política em base com dados.
   A FASE 2 fica materialmente mais simples.
4. **Custo zero.** Criar projeto novo na organização da Keystone custa R$ 0 por
   mês no plano atual — verificado.

**Consequência.** O trabalho de frontend já entregue (design system, estrutura
de módulos, shell de navegação, seletor de tema, identidade visual) é portável e
migra para o repositório novo. Nada se perde.

---

## O que muda no roadmap

| | Antes | Depois |
|---|---|---|
| Repositório | `centro-de-custos-inteligente` | novo, a criar |
| Supabase | `hlvkkziiaeyqyenekdck` (Lovable) | novo, na org da Keystone |
| FASE 2 | Tenancy + backfill + migração do Cost Intelligence + correção do C-01 | Tenancy em base limpa |
| Módulo Cost Intelligence | Dentro do Growth OS | **Fora** — permanece produto separado |
| Estimativa da FASE 2 | 3 semanas | **2 semanas** |
| Total do roadmap | 52 semanas | **51 semanas** |

A FASE 2 encolhe porque some a parte mais delicada dela: migrar uma tabela com
dados em produção enquanto se troca a política de segurança embaixo.

---

## ⚠️ A consequência que não pode se perder

**O C-01 continua aberto, e agora está órfão.**

O achado crítico da FASE 0 — políticas de RLS concedendo `SELECT`, `INSERT` e
`DELETE` ao papel `anon` sobre `financial_entries` — **é do Centro de Custos, não
do Growth OS**. Ao tirar o Cost Intelligence do escopo, a correção sai junto do
roadmap.

Isso não torna o problema menor. Ele continua exatamente igual:

> Qualquer pessoa que abra a aplicação de custos consegue extrair a URL e a
> chave pública do bundle e, com uma requisição, ler todos os lançamentos
> financeiros dos clientes ou apagar a tabela. Não há soft delete nem backup
> configurado.

**Recomendação:** tratar a correção do C-01 como uma tarefa isolada e urgente no
produto Centro de Custos, independente do Growth OS e antes dele. É trabalho de
poucas horas — remover as políticas `anon`, exigir autenticação — mas depende de
acesso ao projeto Supabase gerenciado pela Lovable.

Enquanto isso não for feito, o risco permanece, e a reorganização de escopo não
o resolve — apenas o move para fora do campo de visão.

---

## Pendências desta decisão

1. **Criar o repositório novo** e migrar o trabalho de frontend já entregue.
2. **Criar o projeto Supabase** na organização da Keystone.
3. **Atualizar as fichas do ClickUp** — as da FASE 2 descrevem a migração do
   Cost Intelligence e a correção do C-01, que saem de escopo.
4. **Abrir a correção do C-01** como tarefa separada, no produto certo.
5. **Confirmar o destino do Centro de Custos:** continua na Lovable, ou também
   migra para infraestrutura própria? É decisão de negócio, não técnica.
