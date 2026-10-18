-- C-01 (issue #10): fecha o acesso anônimo às tabelas de negócio.
--
-- Até aqui, financial_entries, pricing_products, sales_channels e
-- commercial_expenses tinham políticas `TO anon USING (true)`. Como a URL e a
-- publishable key estão no bundle, qualquer pessoa conseguia ler, alterar e
-- apagar tudo com um curl. Trocar `anon` por `authenticated` não basta: o
-- cadastro do Supabase Auth é aberto, então "autenticado" seria qualquer um
-- que criasse conta.
--
-- O acesso passa a depender de vínculo ativo com uma organização, no modelo
-- de docs/07 §2 e com as tabelas de docs/02 §4.1. Os dados existentes vão
-- para a organização Keystone.
--
-- Segue a ordem obrigatória de docs/07 §2: tabelas e função, organização,
-- coluna nullable, backfill, NOT NULL e só então troca das políticas. A
-- migration roda numa transação só; se qualquer passo falhar, nada muda.
--
-- Depois de aplicar, ninguém acessa nada até ganhar um vínculo. O primeiro
-- precisa ser criado à mão, pelo SQL editor (ver docs/17-ACESSO-E-RLS.md).

create schema if not exists app;
grant usage on schema app to authenticated;

create type public.org_role as enum ('owner', 'admin', 'operator', 'analyst', 'viewer');
create type public.membership_status as enum ('invited', 'active', 'suspended');

create table public.organizations (
  id            uuid primary key default gen_random_uuid(),
  slug          text not null unique,
  legal_name    text not null,
  display_name  text not null,
  cnpj          text,
  timezone      text not null default 'America/Sao_Paulo',
  locale        text not null default 'pt-BR',
  plan          text not null default 'internal',
  status        text not null default 'active',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);

create table public.memberships (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id         uuid not null references auth.users(id) on delete cascade,
  role            public.org_role not null default 'viewer',
  status          public.membership_status not null default 'active',
  invited_by      uuid references auth.users(id),
  created_at      timestamptz not null default now(),
  unique (organization_id, user_id)
);
create index memberships_active_user_idx on public.memberships (user_id) where status = 'active';

-- SECURITY DEFINER porque as políticas de memberships consultam memberships:
-- sem isso, recursão infinita. search_path fixo contra sequestro de schema.
create or replace function app.current_org_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public, app
as $$
  select organization_id
    from public.memberships
   where user_id = auth.uid()
     and status = 'active'
$$;

-- Organização usada quando o insert não informa organization_id. O frontend
-- ainda não escolhe organização (há uma só), então os inserts atuais
-- continuam funcionando sem mudança. Sem vínculo, devolve null e o insert
-- é recusado (pela RLS ou pelo NOT NULL), que é o comportamento certo.
create or replace function app.default_org_id()
returns uuid
language sql
stable
security definer
set search_path = public, app
as $$
  select organization_id
    from public.memberships
   where user_id = auth.uid()
     and status = 'active'
   order by created_at
   limit 1
$$;

revoke all on function app.current_org_ids() from public;
revoke all on function app.default_org_id() from public;
grant execute on function app.current_org_ids() to authenticated;
grant execute on function app.default_org_id() to authenticated;

-- Sem FORCE aqui, de propósito: o dono (postgres, no SQL editor) precisa
-- conceder o primeiro vínculo, e não há política de INSERT. As tabelas de
-- negócio recebem FORCE no fim, depois do backfill.
alter table public.organizations enable row level security;
alter table public.memberships enable row level security;

-- Leitura apenas. Criar organização e conceder vínculo fica no SQL editor
-- até existir tela de administração de membros.
create policy org_select on public.organizations for select to authenticated
  using (id in (select app.current_org_ids()));

create policy membership_select on public.memberships for select to authenticated
  using (user_id = auth.uid() or organization_id in (select app.current_org_ids()));

revoke all on public.organizations from anon;
revoke all on public.memberships from anon;
grant select on public.organizations to authenticated;
grant select on public.memberships to authenticated;

insert into public.organizations (slug, legal_name, display_name)
values ('keystone', 'Keystone Controladoria', 'Keystone');

do $$
declare
  t text;
  keystone uuid := (select id from public.organizations where slug = 'keystone');
begin
  foreach t in array array['financial_entries', 'pricing_products', 'sales_channels', 'commercial_expenses'] loop
    execute format('alter table public.%I add column organization_id uuid references public.organizations(id) on delete cascade', t);
    execute format('update public.%I set organization_id = %L', t, keystone);
    execute format('alter table public.%I alter column organization_id set not null', t);
    execute format('alter table public.%I alter column organization_id set default app.default_org_id()', t);
    execute format('create index %I on public.%I (organization_id)', t || '_organization_id_idx', t);
  end loop;
end $$;

drop policy "Anon can read financial entries" on public.financial_entries;
drop policy "Anon can insert financial entries" on public.financial_entries;
drop policy "Anon can delete financial entries" on public.financial_entries;
drop policy "Auth can read financial entries" on public.financial_entries;
drop policy "Auth can insert financial entries" on public.financial_entries;
drop policy "Auth can delete financial entries" on public.financial_entries;

drop policy "Anon can read pricing products" on public.pricing_products;
drop policy "Anon can insert pricing products" on public.pricing_products;
drop policy "Anon can update pricing products" on public.pricing_products;
drop policy "Anon can delete pricing products" on public.pricing_products;
drop policy "Auth can read pricing products" on public.pricing_products;
drop policy "Auth can insert pricing products" on public.pricing_products;
drop policy "Auth can update pricing products" on public.pricing_products;
drop policy "Auth can delete pricing products" on public.pricing_products;

drop policy "Anon can read sales channels" on public.sales_channels;
drop policy "Anon can insert sales channels" on public.sales_channels;
drop policy "Anon can update sales channels" on public.sales_channels;
drop policy "Anon can delete sales channels" on public.sales_channels;
drop policy "Auth can read sales channels" on public.sales_channels;
drop policy "Auth can insert sales channels" on public.sales_channels;
drop policy "Auth can update sales channels" on public.sales_channels;
drop policy "Auth can delete sales channels" on public.sales_channels;

drop policy "Anon can read commercial expenses" on public.commercial_expenses;
drop policy "Anon can insert commercial expenses" on public.commercial_expenses;
drop policy "Anon can update commercial expenses" on public.commercial_expenses;
drop policy "Anon can delete commercial expenses" on public.commercial_expenses;
drop policy "Auth can read commercial expenses" on public.commercial_expenses;
drop policy "Auth can insert commercial expenses" on public.commercial_expenses;
drop policy "Auth can update commercial expenses" on public.commercial_expenses;
drop policy "Auth can delete commercial expenses" on public.commercial_expenses;

-- Padrão de docs/07 §2. UPDATE com USING e WITH CHECK: só com USING, um
-- membro poderia mover uma linha para outra organização.
do $$
declare
  t text;
begin
  foreach t in array array['financial_entries', 'pricing_products', 'sales_channels', 'commercial_expenses'] loop
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on public.%I from anon', t);
    execute format(
      'create policy tenant_select on public.%I for select to authenticated
         using (organization_id in (select app.current_org_ids()))', t);
    execute format(
      'create policy tenant_insert on public.%I for insert to authenticated
         with check (organization_id in (select app.current_org_ids()))', t);
    execute format(
      'create policy tenant_update on public.%I for update to authenticated
         using (organization_id in (select app.current_org_ids()))
         with check (organization_id in (select app.current_org_ids()))', t);
    execute format(
      'create policy tenant_delete on public.%I for delete to authenticated
         using (organization_id in (select app.current_org_ids()))', t);
  end loop;
end $$;
