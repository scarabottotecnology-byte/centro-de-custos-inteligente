# Keystone Growth OS

Sistema de inteligência comercial e crescimento orientado por IA, da Keystone
Controladoria.

O produto conecta inteligência de mercado, estratégia de conteúdo, publicação,
análise de performance, geração de leads, prospecção, relacionamento,
qualificação e CRM num ciclo único — em que o resultado de cada venda realimenta
as decisões do ciclo seguinte.

O dashboard de **Centro de Custos** existente permanece no produto como o módulo
**Cost Intelligence**.

## Estado atual

| | |
|---|---|
| Fase | **FASE 0 — Discovery e Arquitetura** · concluída |
| Próximo passo | Aprovação do documento de arquitetura, depois `EXECUTE FASE 1` |
| Em produção | Módulo de Centro de Custos (import de planilha, dashboard, lançamentos) |

> ⚠️ **O sistema ainda não está apto a produção.** A auditoria da FASE 0
> identificou que o banco atual permite leitura, escrita e exclusão anônimas
> (achado C-01). A correção está planejada para a FASE 2. Detalhes em
> [`docs/00-AUDITORIA-ESTADO-ATUAL.md`](./docs/00-AUDITORIA-ESTADO-ATUAL.md).

## Documentação

A arquitetura completa está em [`docs/`](./docs/README.md) — visão, stack,
modelo de dados, integrações, workflows, agentes de IA, segurança, LGPD,
observabilidade, testes, roadmap e decisões arquiteturais.

## Stack

React 18 · TypeScript · Vite · Tailwind · shadcn/ui · Supabase (PostgreSQL,
Auth, Storage, Edge Functions) · TanStack Query · n8n · pgvector

## Desenvolvimento

```bash
npm install
npm run dev        # servidor de desenvolvimento
npm run lint       # eslint
npm run test       # vitest
npm run build      # build de produção
```

### Variáveis de ambiente

```
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=
VITE_SUPABASE_PROJECT_ID=
```

Apenas chaves públicas ficam no frontend. Segredos (tokens OAuth, chaves de LLM,
credenciais de provedor) vivem exclusivamente no servidor — ver
[`docs/07-SEGURANCA-LGPD-MULTITENANT.md`](./docs/07-SEGURANCA-LGPD-MULTITENANT.md).
