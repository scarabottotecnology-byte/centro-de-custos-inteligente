-- Testes de RLS do C-01 (issue #10). Rodar com supabase/tests/run.sh.
-- Cada bloco falha com exceção se a política não se comportar como esperado.

-- Dados de antes da migration já foram inseridos pelo run.sh; aqui só os
-- usuários: membro da Keystone, membro de outra organização e sem vínculo.
insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-00000000000a', 'membro@keystone.test'),
  ('00000000-0000-0000-0000-00000000000b', 'outra@org.test'),
  ('00000000-0000-0000-0000-00000000000c', 'sem-vinculo@qualquer.test');
insert into public.organizations (slug, legal_name, display_name) values ('outra', 'Outra Ltda', 'Outra');
insert into public.memberships (organization_id, user_id, role)
  select id, '00000000-0000-0000-0000-00000000000a', 'owner' from public.organizations where slug = 'keystone';
insert into public.memberships (organization_id, user_id, role)
  select id, '00000000-0000-0000-0000-00000000000b', 'owner' from public.organizations where slug = 'outra';

-- Ids guardados antes de trocar de papel: um membro de fora não enxerga a
-- organização alheia, então não daria para buscá-los depois.
do $$ begin
  perform set_config('test.keystone', (select id::text from public.organizations where slug = 'keystone'), false);
  perform set_config('test.outra', (select id::text from public.organizations where slug = 'outra'), false);
end $$;

create function pg_temp.as_user(uid text) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', uid)::text, true);
  execute 'set local role authenticated';
end $$;

-- 1. Backfill: nenhuma linha antiga ficou sem organização, todas na Keystone.
do $$ begin
  if exists (select 1 from public.financial_entries f join public.organizations o on o.id = f.organization_id where o.slug <> 'keystone')
     or (select count(*) from public.financial_entries) <> 2
     or (select count(*) from public.pricing_products) <> 1 then
    raise exception 'backfill errado';
  end if;
end $$;

-- 2. anon não lê nem escreve nada.
begin;
set local role anon;
do $$
declare t text;
begin
  foreach t in array array['financial_entries', 'pricing_products', 'sales_channels', 'commercial_expenses', 'organizations', 'memberships'] loop
    begin
      execute format('select count(*) from public.%I', t);
      raise exception 'anon leu %', t;
    exception when insufficient_privilege then null;
    end;
  end loop;
  begin
    insert into public.pricing_products (nome) values ('invasor');
    raise exception 'anon inseriu';
  exception when insufficient_privilege then null;
  end;
end $$;
rollback;

-- 3. Membro da Keystone lê os dados antigos e insere sem informar organização.
begin;
select from pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
do $$ begin
  if (select count(*) from public.financial_entries) <> 2 then raise exception 'membro não leu os lançamentos'; end if;
  if (select count(*) from public.pricing_products) <> 1 then raise exception 'membro não leu os produtos'; end if;
  insert into public.pricing_products (nome) values ('novo');
  insert into public.financial_entries (fornecedor) values ('novo');
  update public.sales_channels set comissao_pct = 12;
  if (select comissao_pct from public.sales_channels limit 1) <> 12 then raise exception 'membro não atualizou'; end if;
  if (select count(*) from public.organizations) <> 1 then raise exception 'membro vê organização alheia'; end if;
end $$;
rollback;

-- 4. Membro de outra organização não vê, não altera e não apaga nada da Keystone.
begin;
select from pg_temp.as_user('00000000-0000-0000-0000-00000000000b');
do $$
declare n int;
begin
  if (select count(*) from public.financial_entries) <> 0 then raise exception 'vazou entre organizações'; end if;
  update public.pricing_products set custo_materia_prima = 0;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'alterou dado de outra organização'; end if;
  delete from public.commercial_expenses;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'apagou dado de outra organização'; end if;
  begin
    insert into public.pricing_products (nome, organization_id)
      values ('plantado', current_setting('test.keystone')::uuid);
    raise exception 'inseriu em outra organização';
  exception when insufficient_privilege then null;
  end;
end $$;
rollback;

-- 5. Membro não consegue mover linha própria para outra organização.
begin;
select from pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
do $$ begin
  update public.pricing_products set organization_id = current_setting('test.outra')::uuid;
  raise exception 'moveu linha para outra organização';
exception when insufficient_privilege then null;
end $$;
rollback;

-- 6. Conta criada sem vínculo (cadastro aberto do Supabase) não acessa nada.
begin;
select from pg_temp.as_user('00000000-0000-0000-0000-00000000000c');
do $$ begin
  if (select count(*) from public.financial_entries) + (select count(*) from public.pricing_products)
     + (select count(*) from public.memberships) + (select count(*) from public.organizations) <> 0 then
    raise exception 'conta sem vínculo leu dados';
  end if;
  begin
    insert into public.pricing_products (nome) values ('sem vínculo');
    raise exception 'conta sem vínculo inseriu';
  exception when insufficient_privilege or not_null_violation then null;
  end;
end $$;
rollback;

-- 7. Membro não se dá vínculo em outra organização nem se promove.
begin;
select from pg_temp.as_user('00000000-0000-0000-0000-00000000000c');
do $$ begin
  insert into public.memberships (organization_id, user_id, role)
    values (current_setting('test.keystone')::uuid, '00000000-0000-0000-0000-00000000000c', 'owner');
  raise exception 'criou o próprio vínculo';
exception when insufficient_privilege then null;
end $$;
rollback;

select 'rls_c01: todos os testes passaram' as resultado;
