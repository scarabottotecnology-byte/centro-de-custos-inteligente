

# Dashboard Financeiro - Análise por Centro de Custos

## Visão Geral
Sistema de dashboard financeiro com importação de planilhas Excel, mapeamento de campos e visualizações analíticas por centro de custos. Os dados serão armazenados no Supabase (necessário conectar).

## Arquitetura

### 1. Banco de Dados (Supabase)
Será necessário conectar o Supabase ao projeto. Tabela principal:

```text
financial_entries
├── id (uuid, PK)
├── cca (text)
├── ccs (text)
├── cf (text)
├── grupo (text)
├── filial (text)
├── valor_negativo (numeric)
├── mes (text)
├── competencia (text)
├── bu (text)
├── numero (text)
├── vencimento (date)
├── emissao (date)
├── valor_previsto (numeric)
├── fornecedor (text)
├── pagamento (text)
├── valor_pago (numeric)
├── lancamento (text)
├── historico (text)
├── razao_social (text)
├── cod_cc (text)
├── bu_projeto (text)
├── projeto (text)
├── created_at (timestamptz)
└── import_batch_id (uuid) -- para rastrear importações
```

### 2. Páginas e Componentes

**Layout**: Sidebar com navegação + área principal de conteúdo

**Páginas**:
- `/` — Dashboard principal com KPIs e gráficos
- `/import` — Importação de planilha com mapeamento de colunas
- `/entries` — Tabela de lançamentos com filtros
- `/cost-centers` — Análise detalhada por centro de custos

### 3. Dashboard Principal (`/`)
- **KPI Cards**: Total previsto, Total pago, Diferença, Nº de lançamentos
- **Gráfico de barras**: Valor pago vs previsto por centro de custos (CCA/CCS)
- **Gráfico de pizza**: Distribuição por Grupo
- **Gráfico de linha**: Evolução mensal por competência
- **Filtros globais**: Filial, B.U., Competência, Grupo

### 4. Importação de Planilha (`/import`)
- Upload de arquivo .xlsx/.csv
- Leitura das colunas da planilha usando biblioteca `xlsx` (SheetJS)
- Tela de mapeamento: colunas da planilha ↔ campos do banco
- Preview dos dados antes de confirmar
- Inserção em lote no Supabase

### 5. Análise por Centro de Custos (`/cost-centers`)
- Seletor de centro de custos (CCA, CCS, COD CC)
- Tabela detalhada dos lançamentos filtrados
- Gráficos comparativos entre centros de custos
- Totalizadores por fornecedor dentro do centro de custos

## Dependências Necessárias
- `xlsx` (SheetJS) — leitura de planilhas Excel
- `recharts` — já instalado, para gráficos

## Pré-requisito
Será necessário **conectar o Supabase** ao projeto para criar a tabela e persistir os dados. Enquanto isso não for feito, posso iniciar com armazenamento local (localStorage) para prototipagem rápida.

## Sequência de Implementação
1. Configurar Supabase e criar tabela `financial_entries`
2. Criar layout com sidebar de navegação
3. Implementar página de importação com mapeamento de campos
4. Criar dashboard com KPIs e gráficos (recharts)
5. Criar página de análise por centro de custos
6. Criar página de listagem com filtros e busca

