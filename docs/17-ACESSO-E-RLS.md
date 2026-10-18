# 17 — Acesso e RLS: como aplicar a correção do C-01

Correção do achado C-01 (`00`), ampliado na issue #10: as quatro tabelas de
negócio (`financial_entries`, `pricing_products`, `sales_channels`,
`commercial_expenses`) estavam abertas ao papel `anon`. Com a URL e a chave
pública do bundle, qualquer pessoa conseguia ler, alterar e apagar tudo.

## O que a correção faz

- **Banco** (`supabase/migrations/20261018003000_c01_tenancy_rls.sql`): cria
  `organizations` e `memberships` conforme `02 §4.1` e a função
  `app.current_org_ids()` conforme `07 §2`. Adiciona `organization_id` às
  quatro tabelas, coloca os dados existentes na organização **Keystone**,
  remove todas as políticas antigas (`anon` e `authenticated` com
  `USING (true)`) e aplica o padrão de tenancy de `07 §2`. `anon` perde
  inclusive os grants de tabela.
- **App:** tela de login (`/login`), rotas protegidas e checagem de vínculo.
  Conta criada sem vínculo vê "Sua conta ainda não tem acesso", em vez de
  telas vazias.

Ter conta **não** dá acesso. O cadastro do Supabase Auth é aberto; o que libera
os dados é um vínculo ativo em `memberships`. Por isso trocar `anon` por
`authenticated` não bastaria.

Os inserts do app não informam `organization_id`: a coluna tem como padrão
`app.default_org_id()`, que devolve a organização de quem está logado. Quando
houver mais de uma organização por pessoa, o app passa a escolher
explicitamente (FASE 2).

## Como aplicar

O projeto `hlvkkziiaeyqyenekdck` é gerenciado pela Lovable (`15`), então a
migration não é aplicada só por estar no repositório. A ordem importa, porque
entre o passo 1 e o passo 4 ninguém acessa os dados:

1. **Aplicar a migration.** No SQL editor do projeto, seja pelo painel da
   Lovable (Cloud → Database) ou pelo do Supabase, cole o conteúdo de
   `supabase/migrations/20261018003000_c01_tenancy_rls.sql` e rode. Ela roda
   numa transação só: se der erro, nada muda.
2. **Publicar o app** com esta versão (merge na `main`).
3. **Criar a conta** em `/login` → "Criar conta". Se o projeto exige
   confirmação de e-mail, clique no link antes de seguir.
4. **Dar o primeiro vínculo** no mesmo SQL editor, trocando o e-mail:

   ```sql
   insert into public.memberships (organization_id, user_id, role)
   select o.id, u.id, 'owner'
     from public.organizations o, auth.users u
    where o.slug = 'keystone'
      and u.email = 'seu-email@exemplo.com';
   ```

5. Entrar de novo no app. Os dados antigos estão lá.

Para liberar outra pessoa, ela cria a conta e você repete o passo 4 com o
e-mail dela e o papel adequado (`admin`, `operator`, `analyst` ou `viewer`;
ver `07 §2`). Para tirar o acesso:
`update public.memberships set status = 'suspended' where user_id = (select id from auth.users where email = '...');`

## Como verificar

Depois do passo 1, a chave pública sozinha não pode devolver nada. Este
comando deve responder `401` ou `403`, ou uma lista vazia, nunca dados:

```bash
curl "$VITE_SUPABASE_URL/rest/v1/financial_entries?select=id&limit=1" \
  -H "apikey: $VITE_SUPABASE_PUBLISHABLE_KEY"
```

No painel do Supabase, **Advisors → Security** não deve listar nenhuma das
quatro tabelas.

## Testes

`supabase/tests/run.sh` aplica todas as migrations num Postgres local
descartável, com um esqueleto mínimo do Supabase (`stub_supabase.sql`), e roda
`rls_c01.sql`. São sete casos: backfill; `anon` sem leitura nem escrita;
membro lê e escreve; membro de outra organização não vê, não altera nem apaga;
ninguém move linha para outra organização; conta sem vínculo não acessa nada;
ninguém cria o próprio vínculo.

```bash
supabase/tests/run.sh                       # Postgres local, usuário com createdb
supabase/tests/run.sh postgresql://u:s@host:5432/postgres
```

## Fora do escopo

- Tela de administração de membros: por enquanto, vínculos são concedidos
  pelo SQL editor.
- Recuperação de senha pelo app: o fluxo de redefinição do Supabase funciona
  pelo painel, mas a tela ainda não existe.
- `profiles`, `audit_log` e o restante da FASE 2 (`09`).
