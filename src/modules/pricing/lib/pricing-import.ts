export type ImportFieldMapping = Record<string, string>; // db_field -> spreadsheet_column

export interface ImportFieldDef {
  key: string;
  label: string;
  type?: "number" | "text";
}

export const PRODUCT_FIELDS: ImportFieldDef[] = [
  { key: "sku", label: "SKU / Código" },
  { key: "nome", label: "Nome do Produto" },
  { key: "categoria", label: "Categoria" },
  { key: "unidade", label: "Unidade" },
  { key: "custo_materia_prima", label: "Matéria-Prima", type: "number" },
  { key: "custo_embalagem", label: "Embalagem", type: "number" },
  { key: "mao_de_obra_direta", label: "Mão de Obra Direta", type: "number" },
  { key: "custos_indiretos", label: "Custos Indiretos (CIF)", type: "number" },
  { key: "outros_custos_variaveis", label: "Outros Custos Variáveis", type: "number" },
  { key: "preco_atual", label: "Preço de Venda Atual", type: "number" },
  { key: "margem_desejada_pct", label: "Margem Desejada (%)", type: "number" },
  { key: "volume_mensal_estimado", label: "Volume Mensal Estimado", type: "number" },
];

export const PRODUCT_HINTS: Record<string, string[]> = {
  sku: ["sku", "código", "codigo", "cod produto"],
  nome: ["nome", "produto", "descrição", "descricao"],
  categoria: ["categoria", "família", "familia", "linha"],
  unidade: ["unidade", "un", "un.", "unidade de medida"],
  custo_materia_prima: ["matéria-prima", "materia prima", "mp", "matéria prima"],
  custo_embalagem: ["embalagem"],
  mao_de_obra_direta: ["mão de obra", "mao de obra", "mod"],
  custos_indiretos: ["custos indiretos", "cif", "indireto"],
  outros_custos_variaveis: ["outros custos", "custo variável", "custo variavel"],
  preco_atual: ["preço atual", "preco atual", "preço de venda", "preco de venda", "preço", "preco"],
  margem_desejada_pct: ["margem desejada", "margem alvo", "margem"],
  volume_mensal_estimado: ["volume", "quantidade mensal", "vendas mensais", "volume mensal"],
};

export const EXPENSE_FIELDS: ImportFieldDef[] = [
  { key: "descricao", label: "Descrição" },
  { key: "categoria", label: "Categoria" },
  { key: "valor_mensal", label: "Valor Mensal", type: "number" },
  { key: "tipo", label: "Tipo (fixo/variavel)" },
  { key: "competencia", label: "Competência" },
];

export const EXPENSE_HINTS: Record<string, string[]> = {
  descricao: ["descrição", "descricao", "despesa", "item"],
  categoria: ["categoria", "grupo"],
  valor_mensal: ["valor mensal", "valor", "custo mensal"],
  tipo: ["tipo", "fixo/variável", "fixo variavel"],
  competencia: ["competência", "competencia", "mês", "mes"],
};

export function autoMapImportFields(spreadsheetColumns: string[], hints: Record<string, string[]>): ImportFieldMapping {
  const mapping: ImportFieldMapping = {};
  const normalized = spreadsheetColumns.map((c) => c.toLowerCase().trim());

  for (const [dbField, fieldHints] of Object.entries(hints)) {
    const idx = normalized.findIndex((col) => fieldHints.some((hint) => col === hint || col.includes(hint)));
    if (idx !== -1) mapping[dbField] = spreadsheetColumns[idx];
  }
  return mapping;
}
