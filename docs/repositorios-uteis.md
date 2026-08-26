# Repositórios úteis — curadoria para o stack e as frentes de trabalho

Levantamento feito varrendo GitHub e a web em agosto/2026, filtrado por dois critérios:
**(1)** encaixa no que já existe aqui (Vite + React + shadcn/ui + Supabase + import XLSX + Recharts)
ou **(2)** encaixa nas frentes recorrentes de FP&A, controladoria, custos, faturamento, folha,
auditoria e BI.

Números de estrelas marcados com ✔ foram conferidos direto na página do repositório;
os demais vêm de comparativos publicados e podem estar defasados.

---

## 1. Aplicável direto no `centro-de-custos-inteligente`

| Repositório | O que é | Por que serve aqui |
|---|---|---|
| [`adazzle/react-data-grid`](https://github.com/adazzle/react-data-grid) — 7,7k ✔ | Data grid React com virtualização, edição de célula, copiar/colar, arrastar-preencher, agrupamento de linhas, colunas congeladas, linhas de resumo, dark mode | A tela `Entries` hoje é uma tabela shadcn. Com milhares de lançamentos ela trava e não dá pra editar em massa. Este grid dá sensação de Excel dentro do app — conferência de classificação de centro de custo linha a linha. Zero dependências externas, React 19+ |
| [`dream-num/univer`](https://github.com/dream-num/univer) — ~16,7k | Planilha completa no navegador (fórmulas, formatação, import/export XLSX). Sucessor do Luckysheet | Caminho para o usuário final conciliar e reclassificar dentro do produto, sem exportar → editar no Excel → reimportar. Elimina o ciclo que hoje gera retrabalho |
| [`exceljs/exceljs`](https://github.com/exceljs/exceljs) — ~15,3k | Escrita de XLSX com formatação real: máscara `R$ #,##0.00`, cores, congelar painel, múltiplas abas, fórmulas | O projeto usa `xlsx` (SheetJS), excelente para **ler**, fraco para **gerar** saída formatada. Para entregar DRE/relatório em Excel com cara de entregável de consultoria, ExcelJS é o certo. Dá pra manter os dois: SheetJS na importação, ExcelJS na exportação |
| [`duckdb/duckdb-wasm`](https://github.com/duckdb/duckdb-wasm) — 2,1k ✔ | DuckDB (OLAP em SQL) rodando em WebAssembly no browser; lê CSV, Parquet, JSON e Arrow | Permite validar e agregar a planilha importada **antes** de gravar no Supabase: totais por centro de custo, duplicidades, saldo que não fecha. Um `GROUP BY` em SQL no cliente resolve o que hoje exigiria round-trip ao banco |
| [`supabase/cli`](https://github.com/supabase/cli) | Migrations versionadas, tipos TypeScript gerados do schema, branches de banco | Hoje existe **uma única migration** em `supabase/migrations/`. Sem disciplina de migration, qualquer mudança de schema vira quebra silenciosa no front |

### Três aplicações imediatas neste repositório

1. **Trocar a tabela de `Entries` por `react-data-grid`** — é a tela que mais escala em volume e a que mais precisa de edição em massa.
2. **Separar leitura de escrita de Excel** — `xlsx` para importar, `exceljs` para exportar relatórios formatados.
3. **Validar antes de gravar** — DuckDB-Wasm (ou validação em Zod, que já está no projeto) na etapa `Import`, com relatório de inconsistências antes do commit no banco.

---

## 2. Dados brasileiros — o que alimenta premissa e cadastro

| Repositório | O que é | Uso concreto |
|---|---|---|
| [`BrasilAPI/BrasilAPI`](https://github.com/BrasilAPI/BrasilAPI) — ~11k ✔ | API pública, sem autenticação: CNPJ, CEP, bancos, feriados nacionais, câmbio, NCM, taxas (SELIC, CDI, IPCA) | Enriquecer cadastro de fornecedor/cliente por CNPJ, validar CEP, puxar indexador para reajuste contratual. Custo zero, sem chave |
| [`wilsonfreitas/python-bcb`](https://github.com/wilsonfreitas/python-bcb) — 125 ✔ | Interface Python para o Banco Central: SGS (séries temporais), PTAX, **Expectativas/Focus**, taxa de juros, IFDATA | Premissa macro em projeção e budget: SELIC, IPCA e a expectativa do Focus entram como cenário. Direto ao ponto para forecast |
| [`GusFurtado/DadosAbertosBrasil`](https://github.com/GusFurtado/DadosAbertosBrasil) — 127 ✔ | Pacote pandas para IBGE, IPEA, Banco Central, Câmara e Senado | IPCA/INPC por região, PIB, população — base para benchmark setorial e reajuste |
| [`rictom/cnpj_api`](https://github.com/rictom/cnpj_api) | API Python sobre a base pública de CNPJ da Receita Federal (consulta por UF, município, CNAE, porte, situação) | Base **local** de CNPJ: enriquecimento em lote de milhares de fornecedores sem estourar rate limit de API pública |
| [`nfephp-org/sped-nfe`](https://github.com/nfephp-org/sped-nfe) | Geração e comunicação de NF-e com as SEFAZ (PHP) | Conciliação faturamento × nota fiscal emitida — a frente de "conciliação de NF" |
| [`IF-TI/APIs-PublicasBrasil`](https://github.com/IF-TI/APIs-PublicasBrasil) | Catálogo de APIs públicas brasileiras | Consulta rápida quando aparecer necessidade de dado externo novo |

---

## 3. Engenharia de dados e BI

| Repositório | O que é | Uso concreto |
|---|---|---|
| [`duckdb/duckdb`](https://github.com/duckdb/duckdb) | Banco analítico em processo; lê XLSX, CSV, Parquet e Postgres direto por SQL | Substitui pandas em boa parte do tratamento de base. Um `SELECT` sobre 12 arquivos de faturamento mensal, sem servidor |
| [`duckdb/dbt-duckdb`](https://github.com/duckdb/dbt-duckdb) | Adapter dbt para DuckDB | Transformações versionadas em Git, com teste: `de-para` de plano de contas e centro de custo viram modelos testáveis em vez de fórmula em planilha |
| [`unionai-oss/pandera`](https://github.com/unionai-oss/pandera) | Validação declarativa de schema de DataFrame | Encaixe direto com o padrão de 17 colunas: colunas obrigatórias, tipos, domínio permitido de centro de custo, natureza contábil. É o auditor de base rodando automático, antes de o número chegar no relatório |
| [`great-expectations/great_expectations`](https://github.com/great-expectations/great_expectations) | Framework de qualidade de dados mais completo (e mais pesado) | Alternativa ao pandera quando precisar de documentação de qualidade para o cliente |
| [`evidence-dev/evidence`](https://github.com/evidence-dev/evidence) | BI como código: SQL + Markdown → dashboard versionado | Relatório mensal recorrente que hoje é refeito à mão. Cada fechamento vira um commit; o histórico fica auditável |
| [`metabase/metabase`](https://github.com/metabase/metabase) | BI self-hosted, sobe em um container | Plugue no Postgres do Supabase e o cliente se serve sozinho — sem você construir tela para cada pergunta nova |
| [`rilldata/rill`](https://github.com/rilldata/rill) | Dashboards em YAML/SQL sobre DuckDB | Exploração rápida de base grande antes de decidir o que virar produto |
| [`apache/superset`](https://github.com/apache/superset) / [`lightdash/lightdash`](https://github.com/lightdash/lightdash) | BI de larga escala / BI nativo em dbt | Alternativas — Superset é o mais trabalhoso de operar |

---

## 4. Modelo contábil de referência

Não para usar como dependência, e sim para **copiar a modelagem** ao evoluir o schema do Supabase.

| Repositório | Por que olhar |
|---|---|
| [`beancount/beancount`](https://github.com/beancount/beancount) | Partidas dobradas em arquivo texto. A modelagem de contas hierárquicas e a garantia de lançamento balanceado são a referência mais limpa que existe |
| [`simonmichael/hledger`](https://github.com/simonmichael/hledger) | Mesma linhagem, compatível com Beancount, ecossistema forte de relatórios |
| [`formancehq/ledger`](https://github.com/formancehq/ledger) | Ledger cloud-native, multi-moeda, multi-ativo, transações n:n — referência de arquitetura para escala |
| [`OCA/l10n-brazil`](https://github.com/OCA/l10n-brazil) | Localização brasileira do Odoo: plano de contas nacional e impostos (ICMS, PIS, COFINS, ISS, IPI, IRPJ, CSLL) modelados de verdade. Referência de domínio fiscal |
| [`Purple-Stock/open-erp`](https://github.com/Purple-Stock/open-erp) | ERP open source brasileiro (alternativa a Bling/Tiny) com financeiro e BI |

---

## 5. Documentos: PDF, extrato, balancete

| Repositório | O que é | Uso concreto |
|---|---|---|
| [`docling-project/docling`](https://github.com/docling-project/docling) | Converte PDF/DOCX em Markdown estruturado com tabelas preservadas (IBM) | Extrato bancário, balancete e relatório de fechamento que chegam em PDF. Melhor resultado em PDF nativo |
| [`datalab-to/marker`](https://github.com/datalab-to/marker) | PDF → Markdown com alta fidelidade de tabela | Quando o Docling perde a estrutura da tabela. Exige GPU e é mais lento |
| [`Unstructured-IO/unstructured`](https://github.com/Unstructured-IO/unstructured) | ETL de documentos complexos para formato estruturado | Volume alto e formatos variados |
| [`genieincodebottle/parsemypdf`](https://github.com/genieincodebottle/parsemypdf) | Comparativo prático de parsers de PDF lado a lado | Escolher o parser certo por tipo de documento sem testar do zero |
| [`opendataloader-project/opendataloader-pdf`](https://github.com/opendataloader-project/opendataloader-pdf) | Parser determinístico com proteção contra prompt injection embutida | Quando o PDF vem de terceiro e o conteúdo vai alimentar uma IA — o único da lista que trata esse risco |

---

## 6. Produtividade e IA

| Repositório | Por que |
|---|---|
| [`anthropics/skills`](https://github.com/anthropics/skills) | Skills oficiais — referência de estrutura para as suas skills financeiras |
| [`hesreallyhim/awesome-claude-code`](https://github.com/hesreallyhim/awesome-claude-code) | Curadoria de comandos, hooks e workflows de Claude Code |
| [`modelcontextprotocol/servers`](https://github.com/modelcontextprotocol/servers) | Servidores MCP oficiais (Postgres, filesystem, Git) |
| [`punkpeye/awesome-mcp-servers`](https://github.com/punkpeye/awesome-mcp-servers) | Catálogo amplo da comunidade MCP |
| [`n8n-io/n8n`](https://github.com/n8n-io/n8n) | Automação self-hosted com nós de IA | Alerta automático de variação orçado × realizado acima de X%, disparo de rotina de fechamento, e-mail para o cliente |
| [`activepieces/activepieces`](https://github.com/activepieces/activepieces) | Alternativa MIT ao n8n |
| [`dream-num/skills`](https://github.com/dream-num/skills) | Skill do Univer: diff, review e rollback estilo Git em planilhas | Rastreabilidade de alteração em planilha — resolve "quem mudou esse número" |

---

## Ordem de ataque sugerida

1. **`react-data-grid` + `exceljs`** — ganho visível no produto, esforço baixo, sem mudança de arquitetura.
2. **`pandera` (ou Zod) na importação** — corta na raiz o problema de base suja chegar no relatório.
3. **`BrasilAPI` + `python-bcb`** — premissa macro e enriquecimento de cadastro, custo zero.
4. **`duckdb` + `dbt-duckdb`** — quando o volume de bases mensais justificar pipeline versionado.
5. **`metabase` ou `evidence`** — quando o cliente começar a pedir corte de dado que não está na tela.
