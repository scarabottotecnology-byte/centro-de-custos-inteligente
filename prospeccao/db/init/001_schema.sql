-- Prospecção autônoma — esquema do subdomínio Demand + Outreach.
--
-- Segue o contrato de docs/02-MODELO-DE-DADOS.md (§4.5 e §4.6): mesmos nomes de
-- tabela, organization_id NOT NULL em tudo, enums para estado de máquina,
-- timestamptz sempre. Quando o Growth OS ganhar o Supabase próprio, estas
-- tabelas migram sem renomear nada.
--
-- Desvios deliberados do contrato estão marcados com "DESVIO:".
-- Idempotente: pode rodar mais de uma vez.

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

do $$ begin
  create type verification_status as enum ('verified','unverified','unknown');
exception when duplicate_object then null; end $$;

do $$ begin
  create type prospect_stage as enum
    ('discovered','researched','prioritized','contacted','engaged','converted','disqualified');
exception when duplicate_object then null; end $$;

do $$ begin
  create type outreach_channel as enum ('email','whatsapp','linkedin');
exception when duplicate_object then null; end $$;

do $$ begin
  create type contact_state as enum
    ('pending','active','replied','stopped','completed','bounced','suppressed');
exception when duplicate_object then null; end $$;

do $$ begin
  create type approval_mode as enum ('autonomous','approval_required');
exception when duplicate_object then null; end $$;

-- ── Platform (mínimo necessário) ────────────────────────────────────────────

create table if not exists organizations (
  id            uuid primary key default gen_random_uuid(),
  slug          text not null unique,
  legal_name    text not null,
  display_name  text not null,
  cnpj          text,
  timezone      text not null default 'America/Sao_Paulo',
  created_at    timestamptz not null default now()
);

create table if not exists audit_log (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  actor_type      text not null default 'system',
  action          text not null,
  subject_type    text not null,
  subject_id      uuid,
  after           jsonb,
  at              timestamptz not null default now()
);
create index if not exists audit_log_org_at on audit_log (organization_id, at desc);

-- ── Demand ──────────────────────────────────────────────────────────────────

create table if not exists companies (
  id                   uuid primary key default gen_random_uuid(),
  organization_id      uuid not null references organizations(id) on delete cascade,
  cnpj                 text,          -- 14 posições, alfanumérico desde jul/2026
  razao_social         text not null,
  nome_fantasia        text,
  cnae_principal       text,
  cnae_secundarios     text[],
  situacao_cadastral   text,
  data_abertura        date,
  porte                text,          -- MICRO | EPP | DEMAIS | NAO_INFORMADO
  capital_social       numeric(18,2),
  natureza_juridica    text,
  municipio            text,
  uf                   char(2),
  cep                  text,
  logradouro           text,
  bairro               text,
  matriz_filial        text,
  qtd_estabelecimentos int,
  -- DESVIO: colunas abaixo não estão no contrato e vêm das fontes novas (ADR-014).
  cnae_descricao       text,
  opcao_simples        boolean,
  opcao_mei            boolean,
  website              text,
  linkedin_url         text,
  google_place_id      text,
  google_rating        numeric(3,2),
  google_reviews       int,
  google_category      text,
  maps_checked_at      timestamptz,
  source               text not null, -- receita_federal_open_data | google_maps | manual
  source_url           text,
  source_updated_at    timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (organization_id, cnpj)
);
create index if not exists companies_org_uf_cnae on companies (organization_id, uf, cnae_principal);
create index if not exists companies_maps_pending on companies (organization_id) where maps_checked_at is null;

-- Quadro societário público (Receita). Base para o "decisor" da abordagem.
-- DESVIO: tabela nova; o contrato não modela sócios.
create table if not exists company_partners (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  company_id      uuid not null references companies(id) on delete cascade,
  nome            text not null,
  qualificacao    text,           -- código da Receita (49 = sócio-administrador)
  data_entrada    date,
  faixa_etaria    text,
  source          text not null default 'receita_federal_open_data',
  unique (company_id, nome)
);

create table if not exists company_signals (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  company_id      uuid not null references companies(id) on delete cascade,
  type            text not null,
  description     text not null,
  evidence_url    text,
  observed_at     timestamptz not null default now(),
  weight          numeric(5,2) not null default 1,
  confidence      numeric(3,2) check (confidence between 0 and 1),
  source          text not null,
  unique (company_id, type)
);

create table if not exists contacts (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references organizations(id) on delete cascade,
  company_id          uuid references companies(id) on delete set null,
  full_name           text,
  role_title          text,
  seniority           text,
  email               text,
  email_status        verification_status not null default 'unknown',
  email_shared        boolean not null default false, -- e-mail repetido em várias empresas (escritório contábil)
  email_checked_at    timestamptz,
  phone               text,           -- E.164 sem '+': 55DDDNUMERO
  phone_status        verification_status not null default 'unknown', -- verified = tem WhatsApp
  phone_is_mobile     boolean,
  whatsapp_jid        text,
  linkedin_url        text,
  source              text not null,
  source_url          text,
  consent_status      text not null default 'none',
  optout_token        text not null default encode(gen_random_bytes(12), 'hex'),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);
-- DESVIO: o contrato tem unique (organization_id, email). Na base da Receita o mesmo
-- e-mail (do contador) aparece em centenas de empresas, então a unicidade é por empresa.
create unique index if not exists contacts_company_email on contacts (company_id, lower(email)) where email is not null;
create unique index if not exists contacts_company_phone on contacts (company_id, phone) where phone is not null;
create unique index if not exists contacts_optout_token on contacts (optout_token);
-- Um contato cadastral por empresa vindo da Receita (alvo do upsert mensal).
create unique index if not exists contacts_company_receita on contacts (company_id)
  where source = 'receita_federal_open_data';

create table if not exists icp_profiles (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  description     text,
  criteria        jsonb not null,
  weights         jsonb not null,
  version         int not null default 1,
  is_active       boolean not null default false,
  created_at      timestamptz not null default now(),
  unique (organization_id, name, version)
);

create table if not exists prospects (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  company_id      uuid not null references companies(id) on delete cascade,
  icp_profile_id  uuid references icp_profiles(id) on delete set null,
  stage           prospect_stage not null default 'discovered',
  priority        int,
  last_touch_at   timestamptz,
  next_action     text,
  next_action_at  timestamptz,
  created_at      timestamptz not null default now(),
  unique (organization_id, company_id)
);
create index if not exists prospects_org_stage on prospects (organization_id, stage, priority desc);

create table if not exists prospect_scores (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  prospect_id     uuid not null references prospects(id) on delete cascade,
  icp_profile_id  uuid not null references icp_profiles(id) on delete cascade,
  score           int not null check (score between 0 and 100),
  coverage        numeric(4,3) not null,  -- fração do peso que tinha dado para avaliar
  breakdown       jsonb not null,
  computed_at     timestamptz not null default now(),
  unique (prospect_id, icp_profile_id, computed_at)
);

create table if not exists company_research (
  id                 uuid primary key default gen_random_uuid(),
  organization_id    uuid not null references organizations(id) on delete cascade,
  company_id         uuid not null references companies(id) on delete cascade,
  summary            text not null,
  likely_pain        text,
  suggested_approach text,
  opening_line       text,
  priority           int,
  grounded_on        jsonb not null default '[]',
  model              text,
  generated_at       timestamptz not null default now()
);

-- ── Outreach ────────────────────────────────────────────────────────────────

create table if not exists campaigns (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name            text not null,
  channel         outreach_channel not null,
  objective       text,
  icp_profile_id  uuid references icp_profiles(id),
  status          text not null default 'active',
  daily_cap       int not null default 30,
  approval_mode   approval_mode not null default 'autonomous',
  created_at      timestamptz not null default now(),
  unique (organization_id, name)
);

create table if not exists campaign_steps (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  campaign_id     uuid not null references campaigns(id) on delete cascade,
  step_index      int not null,
  delay_days      int not null default 0,
  channel         outreach_channel not null,
  subject         text,
  body            text not null,  -- DESVIO: template inline; o contrato usa message_templates
  stop_on_reply   boolean not null default true,
  is_terminal     boolean not null default false,
  unique (campaign_id, step_index)
);

create table if not exists campaign_contacts (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  campaign_id     uuid not null references campaigns(id) on delete cascade,
  contact_id      uuid not null references contacts(id) on delete cascade,
  prospect_id     uuid references prospects(id) on delete set null,
  state           contact_state not null default 'active',
  current_step    int not null default 0,
  next_send_at    timestamptz,
  stopped_reason  text,
  created_at      timestamptz not null default now(),
  unique (campaign_id, contact_id)
);
create index if not exists campaign_contacts_due on campaign_contacts (state, next_send_at) where state = 'active';

create table if not exists outreach_messages (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references organizations(id) on delete cascade,
  campaign_contact_id uuid references campaign_contacts(id) on delete cascade,
  contact_id          uuid not null references contacts(id) on delete cascade,
  step_index          int,
  channel             outreach_channel not null,
  direction           text not null default 'outbound',
  provider_message_id text,
  subject             text,
  body                text,
  personalization     jsonb,
  status              text not null default 'queued',
  classification      text,      -- inbound: interested | question | not_interested | optout | other
  sent_at             timestamptz,
  replied_at          timestamptz,
  error               text,
  idempotency_key     text not null,
  created_at          timestamptz not null default now(),
  unique (organization_id, idempotency_key)
);
create index if not exists outreach_messages_sent_day on outreach_messages (organization_id, channel, sent_at)
  where direction = 'outbound';

-- Verificada antes de TODO envio. Guarda hash, nunca o valor (docs/02 §4.6).
create table if not exists suppression_list (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  channel         outreach_channel not null,
  value_hash      text not null,
  reason          text not null,
  created_at      timestamptz not null default now(),
  unique (organization_id, channel, value_hash)
);

-- Lead = prospect que respondeu com interesse. Versão enxuta de docs/02 §4.8.
create table if not exists leads (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  company_id      uuid references companies(id) on delete set null,
  contact_id      uuid references contacts(id) on delete set null,
  prospect_id     uuid references prospects(id) on delete set null,
  origin_channel  outreach_channel,
  status          text not null default 'new',
  first_message   text,
  notified_at     timestamptz,
  created_at      timestamptz not null default now(),
  unique (organization_id, contact_id)
);

-- Jobs do Google Maps em andamento (gosom).
create table if not exists enrichment_jobs (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  provider        text not null,
  external_id     text not null,
  company_ids     uuid[] not null,
  status          text not null default 'pending',
  created_at      timestamptz not null default now(),
  finished_at     timestamptz,
  unique (provider, external_id)
);

-- ── Views de leitura ────────────────────────────────────────────────────────

create or replace view v_funil as
select
  o.slug as organizacao,
  (select count(*) from companies c where c.organization_id = o.id)                              as empresas,
  (select count(*) from prospects p where p.organization_id = o.id and p.stage = 'prioritized')  as priorizados,
  (select count(*) from prospects p where p.organization_id = o.id and p.stage = 'contacted')    as contatados,
  (select count(*) from prospects p where p.organization_id = o.id and p.stage = 'engaged')      as responderam,
  (select count(*) from leads l where l.organization_id = o.id)                                  as leads,
  (select count(*) from outreach_messages m where m.organization_id = o.id
     and m.direction = 'outbound' and m.status = 'sent'
     and m.sent_at >= date_trunc('day', now() at time zone o.timezone) at time zone o.timezone) as enviadas_hoje
from organizations o;

-- E-mails repetidos em várias empresas são, quase sempre, do escritório contábil
-- que atende essas empresas. Para uma controladoria, isso é canal de parceria.
create or replace view v_contadores_parceiros as
select
  ct.organization_id,
  lower(ct.email)                         as email,
  split_part(lower(ct.email), '@', 2)     as dominio,
  count(distinct ct.company_id)           as empresas_atendidas,
  array_agg(distinct c.municipio)         as municipios
from contacts ct
join companies c on c.id = ct.company_id
where ct.email_shared
group by ct.organization_id, lower(ct.email);
