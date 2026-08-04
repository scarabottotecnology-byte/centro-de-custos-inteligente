import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot, Legend,
} from "recharts";
import { Calculator, TrendingUp, Target, Scale, Crown, Package } from "lucide-react";
import { usePricingProducts, useSalesChannels, useCommercialExpenses } from "@/hooks/usePricingData";
import {
  allocateFixedExpenses, breakEven, channelVariablePct, custoVariavelUnitario,
  fmtBRL, fmtPct, simulateMargins, suggestedPrice, totalFixedExpenses,
} from "@/lib/pricing";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function PricingCalculator() {
  const { data: products = [], isLoading: loadingProducts } = usePricingProducts();
  const { data: channels = [], isLoading: loadingChannels } = useSalesChannels();
  const { data: expenses = [], isLoading: loadingExpenses } = useCommercialExpenses();

  const activeProducts = useMemo(() => products.filter((p) => p.ativo), [products]);
  const activeChannels = useMemo(() => channels.filter((c) => c.ativo), [channels]);

  const [productId, setProductId] = useState<string>("");
  const [channelId, setChannelId] = useState<string>("");
  const [simulatedPrice, setSimulatedPrice] = useState<number>(0);

  useEffect(() => {
    if (!productId && activeProducts.length > 0) setProductId(activeProducts[0].id);
  }, [activeProducts, productId]);

  useEffect(() => {
    if (!channelId && activeChannels.length > 0) setChannelId(activeChannels[0].id);
  }, [activeChannels, channelId]);

  const product = useMemo(() => products.find((p) => p.id === productId), [products, productId]);
  const channel = useMemo(() => channels.find((c) => c.id === channelId), [channels, channelId]);

  const totalFixo = useMemo(() => totalFixedExpenses(expenses), [expenses]);
  const allocation = useMemo(() => allocateFixedExpenses(activeProducts, totalFixo), [activeProducts, totalFixo]);

  const custoVariavel = product ? custoVariavelUnitario(product) : 0;
  const alloc = product ? allocation.get(product.id) : undefined;
  const custosFixosAlocados = alloc?.custosFixosAlocados || 0;
  const custoFixoUnitario = alloc?.custoFixoUnitario || 0;

  const variavelPct = channel ? channelVariablePct(channel) : 0;
  const margemDesejada = product?.margem_desejada_pct ?? 30;

  const precoSugerido = useMemo(
    () => suggestedPrice(custoVariavel, variavelPct, margemDesejada),
    [custoVariavel, variavelPct, margemDesejada]
  );

  // Reset simulated price whenever product/channel changes, seeded from the suggested or current price
  useEffect(() => {
    if (!product) return;
    const seed = precoSugerido ?? product.preco_atual ?? custoVariavel * 1.5;
    setSimulatedPrice(Number(seed.toFixed(2)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, channelId]);

  const simulation = useMemo(
    () => simulateMargins({ precoSimulado: simulatedPrice, custoVariavelUnitario: custoVariavel, variavelPct, custoFixoUnitarioAlocado: custoFixoUnitario }),
    [simulatedPrice, custoVariavel, variavelPct, custoFixoUnitario]
  );

  const be = useMemo(
    () => breakEven(custosFixosAlocados, simulation.margemContribuicaoUnit, simulatedPrice),
    [custosFixosAlocados, simulation.margemContribuicaoUnit, simulatedPrice]
  );

  // Suggested price per channel, ranked to find the ideal one
  const channelSuggestions = useMemo(() => {
    if (!product) return [];
    return activeChannels
      .map((c) => {
        const pct = channelVariablePct(c);
        const targetMargin = c.margem_desejada_pct ?? margemDesejada;
        const price = suggestedPrice(custoVariavel, pct, targetMargin);
        const sim = price != null
          ? simulateMargins({ precoSimulado: price, custoVariavelUnitario: custoVariavel, variavelPct: pct, custoFixoUnitarioAlocado: custoFixoUnitario })
          : null;
        return { channel: c, variavelPct: pct, precoSugerido: price, sim };
      })
      .sort((a, b) => (b.sim?.margemLiquidaPct ?? -Infinity) - (a.sim?.margemLiquidaPct ?? -Infinity));
  }, [activeChannels, product, custoVariavel, custoFixoUnitario, margemDesejada]);

  const bestChannelId = channelSuggestions[0]?.channel.id;

  // Break-even chart data: revenue vs total cost as a function of volume
  const chartData = useMemo(() => {
    if (!be.pontoEquilibrioUnidades || simulatedPrice <= 0) return [];
    const maxUnits = Math.max(be.pontoEquilibrioUnidades * 2, product?.volume_mensal_estimado || 0, 10);
    const steps = 10;
    const stepSize = maxUnits / steps;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const units = Math.round(stepSize * i);
      const receita = units * simulatedPrice;
      const custoTotal = custosFixosAlocados + units * (custoVariavel + simulatedPrice * (variavelPct / 100));
      return { units, receita, custoTotal };
    });
  }, [be.pontoEquilibrioUnidades, simulatedPrice, custosFixosAlocados, custoVariavel, variavelPct, product]);

  const isLoading = loadingProducts || loadingChannels || loadingExpenses;

  if (isLoading) {
    return <div className="text-muted-foreground p-8">Carregando...</div>;
  }

  if (activeProducts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Package className="h-16 w-16 text-muted-foreground" />
        <p className="text-muted-foreground text-lg">Sem produto cadastrado, não tem como simular preço.</p>
        <a href="/pricing/products" className="text-primary underline">Cadastrar produtos</a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Calculator className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Calculadora de Precificação</h1>
          <p className="text-sm text-muted-foreground">Descubra a margem líquida real e o ponto de equilíbrio antes de vender no prejuízo — não depois.</p>
        </div>
      </div>

      {/* Selectors */}
      <div className="flex flex-wrap gap-3">
        <Select value={productId} onValueChange={setProductId}>
          <SelectTrigger className="w-[260px]"><SelectValue placeholder="Produto" /></SelectTrigger>
          <SelectContent>
            {activeProducts.map((p) => <SelectItem key={p.id} value={p.id}>{p.nome}{p.sku ? ` (${p.sku})` : ""}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={channelId} onValueChange={setChannelId}>
          <SelectTrigger className="w-[220px]"><SelectValue placeholder="Canal de Venda" /></SelectTrigger>
          <SelectContent>
            {activeChannels.map((c) => <SelectItem key={c.id} value={c.id}>{c.nome}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {product && (
        <>
          {/* Cost breakdown */}
          <Card>
            <CardHeader><CardTitle className="text-base">Estrutura de Custo — {product.nome}</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-sm">
              <div><p className="text-muted-foreground">Matéria-Prima</p><p className="font-medium">{fmtBRL(product.custo_materia_prima)}</p></div>
              <div><p className="text-muted-foreground">Embalagem</p><p className="font-medium">{fmtBRL(product.custo_embalagem)}</p></div>
              <div><p className="text-muted-foreground">Mão de Obra</p><p className="font-medium">{fmtBRL(product.mao_de_obra_direta)}</p></div>
              <div><p className="text-muted-foreground">Custos Indiretos</p><p className="font-medium">{fmtBRL(product.custos_indiretos)}</p></div>
              <div><p className="text-muted-foreground">Outros Variáveis</p><p className="font-medium">{fmtBRL(product.outros_custos_variaveis)}</p></div>
              <div><p className="text-muted-foreground">Custo Fixo Rateado</p><p className="font-medium">{fmtBRL(custoFixoUnitario)}</p></div>
              <div className="col-span-2 sm:col-span-3 lg:col-span-6 border-t pt-3 flex flex-wrap gap-6">
                <div><p className="text-muted-foreground">Custo Variável Unitário</p><p className="text-lg font-bold">{fmtBRL(custoVariavel)}</p></div>
                <div><p className="text-muted-foreground">Custo Total Unitário (var. + fixo rateado)</p><p className="text-lg font-bold">{fmtBRL(custoVariavel + custoFixoUnitario)}</p></div>
                <div><p className="text-muted-foreground">Despesas Variáveis do Canal ({channel?.nome})</p><p className="text-lg font-bold">{fmtPct(variavelPct)}</p></div>
              </div>
            </CardContent>
          </Card>

          {/* KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Preço Sugerido</CardTitle>
                <Target className="h-4 w-4 text-primary" />
              </CardHeader>
              <CardContent><p className="text-2xl font-bold">{precoSugerido != null ? fmtBRL(precoSugerido) : "—"}</p></CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Margem de Contribuição</CardTitle>
                <TrendingUp className="h-4 w-4 text-accent" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{fmtPct(simulation.margemContribuicaoPct)}</p>
                <p className="text-xs text-muted-foreground">{fmtBRL(simulation.margemContribuicaoUnit)} / unidade</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Margem Líquida</CardTitle>
                <Scale className="h-4 w-4 text-chart-3" />
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold ${simulation.margemLiquidaPct < 0 ? "text-destructive" : ""}`}>{fmtPct(simulation.margemLiquidaPct)}</p>
                <p className="text-xs text-muted-foreground">{fmtBRL(simulation.lucroLiquidoUnit)} / unidade</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Ponto de Equilíbrio</CardTitle>
                <Calculator className="h-4 w-4 text-chart-4" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{be.pontoEquilibrioUnidades != null ? `${Math.ceil(be.pontoEquilibrioUnidades)} un` : "—"}</p>
                <p className="text-xs text-muted-foreground">{be.pontoEquilibrioValor != null ? fmtBRL(be.pontoEquilibrioValor) : "sem margem positiva"}</p>
              </CardContent>
            </Card>
          </div>

          {/* Margin Simulator */}
          <Card>
            <CardHeader><CardTitle className="text-base">Simulador de Margens — Preço de Venda Simulado</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center gap-4">
                <Slider
                  value={[simulatedPrice]}
                  min={0}
                  max={Math.max(custoVariavel * 4, (precoSugerido || custoVariavel) * 2.5, 10)}
                  step={0.5}
                  onValueChange={([v]) => setSimulatedPrice(v)}
                  className="flex-1"
                />
                <div className="relative w-36">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">R$</span>
                  <Input
                    type="number"
                    value={simulatedPrice}
                    onChange={(e) => setSimulatedPrice(Number(e.target.value))}
                    className="pl-9"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div><p className="text-muted-foreground">Despesas Variáveis do Canal</p><p className="font-medium">{fmtBRL(simulation.despesasVariaveisValor)}</p></div>
                <div><p className="text-muted-foreground">Margem de Contribuição</p><p className="font-medium">{fmtPct(simulation.margemContribuicaoPct)} ({fmtBRL(simulation.margemContribuicaoUnit)})</p></div>
                <div><p className="text-muted-foreground">Lucro Líquido / Unidade</p><p className={`font-medium ${simulation.lucroLiquidoUnit < 0 ? "text-destructive" : ""}`}>{fmtBRL(simulation.lucroLiquidoUnit)}</p></div>
                <div><p className="text-muted-foreground">Margem Líquida</p><p className={`font-medium ${simulation.margemLiquidaPct < 0 ? "text-destructive" : ""}`}>{fmtPct(simulation.margemLiquidaPct)}</p></div>
              </div>

              {chartData.length > 0 && (
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="units" tick={{ fontSize: 11 }} label={{ value: "Unidades vendidas / mês", position: "insideBottom", offset: -5, fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip formatter={(v: number) => fmtBRL(v)} labelFormatter={(l) => `${l} unidades`} />
                      <Legend />
                      <Line type="monotone" dataKey="receita" name="Receita Total" stroke="hsl(160, 60%, 45%)" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="custoTotal" name="Custo Total" stroke="hsl(0, 72%, 51%)" strokeWidth={2} dot={false} />
                      {be.pontoEquilibrioUnidades != null && be.pontoEquilibrioValor != null && (
                        <ReferenceDot
                          x={Math.round(be.pontoEquilibrioUnidades)}
                          y={be.pontoEquilibrioValor}
                          r={6}
                          fill="hsl(220, 70%, 50%)"
                          stroke="white"
                          label={{ value: "Ponto de Equilíbrio", position: "top", fontSize: 11 }}
                        />
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Per-channel suggestions */}
          <Card>
            <CardHeader><CardTitle className="text-base">Sugestão de Preço Ideal por Canal de Venda</CardTitle></CardHeader>
            <CardContent>
              <div className="rounded-lg border overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Canal</TableHead>
                      <TableHead className="text-right">Custo Variável do Canal</TableHead>
                      <TableHead className="text-right">Preço Sugerido</TableHead>
                      <TableHead className="text-right">Margem de Contribuição</TableHead>
                      <TableHead className="text-right">Margem Líquida</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {channelSuggestions.map(({ channel: c, variavelPct: pct, precoSugerido: price, sim }) => (
                      <TableRow key={c.id} className={c.id === channelId ? "bg-muted/40" : ""}>
                        <TableCell className="text-sm font-medium flex items-center gap-2">
                          {c.nome}
                          {c.id === bestChannelId && (
                            <Badge className="bg-accent text-accent-foreground gap-1"><Crown className="h-3 w-3" />Ideal</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-right">{fmtPct(pct)}</TableCell>
                        <TableCell className="text-xs text-right font-medium">{price != null ? fmtBRL(price) : "inviável"}</TableCell>
                        <TableCell className="text-xs text-right">{sim ? fmtPct(sim.margemContribuicaoPct) : "—"}</TableCell>
                        <TableCell className={`text-xs text-right ${sim && sim.margemLiquidaPct < 0 ? "text-destructive" : ""}`}>{sim ? fmtPct(sim.margemLiquidaPct) : "—"}</TableCell>
                        <TableCell className="text-right">
                          <button
                            className="text-xs text-primary underline"
                            onClick={() => { setChannelId(c.id); if (price != null) setSimulatedPrice(Number(price.toFixed(2))); }}
                          >
                            Simular
                          </button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
