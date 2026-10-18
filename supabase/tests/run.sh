#!/usr/bin/env bash
# Aplica as migrations num Postgres local descartável e roda os testes de RLS.
# Uso: supabase/tests/run.sh [url-de-um-postgres-de-teste]
# A base "rls_test" é apagada e recriada a cada execução.
set -euo pipefail
cd "$(dirname "$0")/../.."
ADMIN_URL="${1:-postgresql:///postgres}"
TEST_URL="${ADMIN_URL%/*}/rls_test"
psql="psql -v ON_ERROR_STOP=1 -q -X"

$psql "$ADMIN_URL" -c "drop database if exists rls_test" -c "create database rls_test"
$psql "$TEST_URL" -f supabase/tests/stub_supabase.sql

migrations=(supabase/migrations/*.sql)
last="${migrations[-1]}"
for m in "${migrations[@]}"; do
  if [[ "$m" == "$last" ]]; then
    # Dados de antes da migration, para testar o backfill.
    $psql "$TEST_URL" <<'SQL'
insert into public.financial_entries (fornecedor, valor_pago) values ('Fornecedor A', 100), ('Fornecedor B', 200);
insert into public.pricing_products (nome, custo_materia_prima) values ('Produto antigo', 10);
insert into public.sales_channels (nome) values ('Loja');
insert into public.commercial_expenses (descricao, valor_mensal) values ('Aluguel', 5000);
SQL
  fi
  $psql "$TEST_URL" --single-transaction -f "$m"
done

$psql "$TEST_URL" -f supabase/tests/rls_c01.sql
