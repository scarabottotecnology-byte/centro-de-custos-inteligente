import type { Tables } from "@/integrations/supabase/types";

export type PricingProduct = Tables<"pricing_products">;
export type SalesChannel = Tables<"sales_channels">;
export type CommercialExpense = Tables<"commercial_expenses">;

/** Sum of a sales channel's variable cost drivers, as % of the sale price. */
export function channelVariablePct(channel: Pick<SalesChannel,
  "comissao_pct" | "taxa_pagamento_pct" | "impostos_pct" | "frete_pct" | "marketing_pct">
): number {
  return (
    (channel.comissao_pct || 0) +
    (channel.taxa_pagamento_pct || 0) +
    (channel.impostos_pct || 0) +
    (channel.frete_pct || 0) +
    (channel.marketing_pct || 0)
  );
}

/** Mark-up divisor method: Preço = Custo Variável / [1 - (%despesas variáveis + %margem desejada)]. */
export function suggestedPrice(
  custoVariavelUnitario: number,
  variavelPct: number,
  margemDesejadaPct: number
): number | null {
  const divisor = 1 - (variavelPct + margemDesejadaPct) / 100;
  if (divisor <= 0) return null; // impossible to reach the desired margin with this cost structure
  return custoVariavelUnitario / divisor;
}

export interface MarginSimulationInput {
  precoSimulado: number;
  custoVariavelUnitario: number;
  variavelPct: number; // channel commissions + fees + taxes + freight + marketing, as % of price
  custoFixoUnitarioAlocado: number; // allocated fixed/commercial expense per unit
}

export interface MarginSimulationResult {
  despesasVariaveisValor: number;
  margemContribuicaoUnit: number;
  margemContribuicaoPct: number;
  lucroLiquidoUnit: number;
  margemLiquidaPct: number;
}

/** Core margin simulator: given any sale price, compute contribution margin and net margin. */
export function simulateMargins(input: MarginSimulationInput): MarginSimulationResult {
  const { precoSimulado, custoVariavelUnitario, variavelPct, custoFixoUnitarioAlocado } = input;
  const despesasVariaveisValor = precoSimulado * (variavelPct / 100);
  const margemContribuicaoUnit = precoSimulado - custoVariavelUnitario - despesasVariaveisValor;
  const margemContribuicaoPct = precoSimulado > 0 ? (margemContribuicaoUnit / precoSimulado) * 100 : 0;
  const lucroLiquidoUnit = margemContribuicaoUnit - custoFixoUnitarioAlocado;
  const margemLiquidaPct = precoSimulado > 0 ? (lucroLiquidoUnit / precoSimulado) * 100 : 0;
  return { despesasVariaveisValor, margemContribuicaoUnit, margemContribuicaoPct, margemLiquidaPct, lucroLiquidoUnit };
}

export interface BreakEven {
  pontoEquilibrioUnidades: number | null;
  pontoEquilibrioValor: number | null;
}

/** Ponto de Equilíbrio Contábil = Custos Fixos / Margem de Contribuição (unitária ou %). */
export function breakEven(
  custosFixosAlocados: number,
  margemContribuicaoUnit: number,
  precoSimulado: number
): BreakEven {
  if (margemContribuicaoUnit <= 0) {
    return { pontoEquilibrioUnidades: null, pontoEquilibrioValor: null };
  }
  const pontoEquilibrioUnidades = custosFixosAlocados / margemContribuicaoUnit;
  const pontoEquilibrioValor = pontoEquilibrioUnidades * precoSimulado;
  return { pontoEquilibrioUnidades, pontoEquilibrioValor };
}

export function custoVariavelUnitario(p: Pick<PricingProduct,
  "custo_materia_prima" | "custo_embalagem" | "mao_de_obra_direta" | "custos_indiretos" | "outros_custos_variaveis"
>): number {
  return (
    (p.custo_materia_prima || 0) +
    (p.custo_embalagem || 0) +
    (p.mao_de_obra_direta || 0) +
    (p.custos_indiretos || 0) +
    (p.outros_custos_variaveis || 0)
  );
}

/**
 * Allocates total monthly fixed commercial expenses across products, proportional to each
 * product's estimated monthly revenue (custeio por rateio simples, base receita).
 */
export function allocateFixedExpenses(
  products: PricingProduct[],
  totalFixedExpenses: number
): Map<string, { custosFixosAlocados: number; custoFixoUnitario: number }> {
  const result = new Map<string, { custosFixosAlocados: number; custoFixoUnitario: number }>();
  const withRevenue = products.map((p) => ({
    id: p.id,
    volume: p.volume_mensal_estimado || 0,
    receita: (p.preco_atual || suggestedPrice(custoVariavelUnitario(p), 0, p.margem_desejada_pct || 0) || 0) * (p.volume_mensal_estimado || 0),
  }));
  const totalReceita = withRevenue.reduce((s, p) => s + p.receita, 0);

  for (const p of withRevenue) {
    const share = totalReceita > 0 ? p.receita / totalReceita : products.length > 0 ? 1 / products.length : 0;
    const custosFixosAlocados = share * totalFixedExpenses;
    const custoFixoUnitario = p.volume > 0 ? custosFixosAlocados / p.volume : 0;
    result.set(p.id, { custosFixosAlocados, custoFixoUnitario });
  }
  return result;
}

export function totalFixedExpenses(expenses: CommercialExpense[]): number {
  return expenses.filter((e) => e.tipo === "fixo").reduce((s, e) => s + (e.valor_mensal || 0), 0);
}

export const fmtBRL = (v: number | null | undefined) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  `${(v ?? 0).toFixed(digits)}%`;
