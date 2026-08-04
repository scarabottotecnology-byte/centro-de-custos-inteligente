import { useMemo, useState } from "react";
import { useFinancialData } from "@/hooks/useFinancialData";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from "recharts";
import { DollarSign, TrendingUp, TrendingDown, FileText } from "lucide-react";

const COLORS = [
  "hsl(220, 70%, 50%)", "hsl(160, 60%, 45%)", "hsl(35, 90%, 55%)",
  "hsl(280, 60%, 55%)", "hsl(0, 72%, 51%)", "hsl(190, 70%, 45%)",
  "hsl(50, 80%, 50%)", "hsl(320, 60%, 50%)",
];

export default function Dashboard() {
  const { data: entries = [], isLoading } = useFinancialData();
  const [filterFilial, setFilterFilial] = useState<string>("all");
  const [filterBU, setFilterBU] = useState<string>("all");
  const [filterCompetencia, setFilterCompetencia] = useState<string>("all");

  const filiais = useMemo(() => [...new Set(entries.map((e) => e.filial).filter(Boolean))], [entries]);
  const bus = useMemo(() => [...new Set(entries.map((e) => e.bu).filter(Boolean))], [entries]);
  const competencias = useMemo(() => [...new Set(entries.map((e) => e.competencia).filter(Boolean))], [entries]);

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filterFilial !== "all" && e.filial !== filterFilial) return false;
      if (filterBU !== "all" && e.bu !== filterBU) return false;
      if (filterCompetencia !== "all" && e.competencia !== filterCompetencia) return false;
      return true;
    });
  }, [entries, filterFilial, filterBU, filterCompetencia]);

  const kpis = useMemo(() => {
    const totalPrevisto = filtered.reduce((s, e) => s + (e.valor_previsto || 0), 0);
    const totalPago = filtered.reduce((s, e) => s + (e.valor_pago || 0), 0);
    const totalNegativo = filtered.reduce((s, e) => s + Math.abs(e.valor_negativo || 0), 0);
    // Use valor_pago if available, otherwise fall back to valor_negativo
    const effectivePago = totalPago || totalNegativo;
    const effectivePrevisto = totalPrevisto || totalNegativo;
    return { totalPrevisto: effectivePrevisto, totalPago: effectivePago, diferenca: effectivePrevisto - effectivePago, count: filtered.length };
  }, [filtered]);

  const barData = useMemo(() => {
    const map = new Map<string, { previsto: number; pago: number }>();
    filtered.forEach((e) => {
      const cc = e.cca || e.ccs || e.cod_cc || "Sem CC";
      const cur = map.get(cc) || { previsto: 0, pago: 0 };
      cur.previsto += e.valor_previsto || Math.abs(e.valor_negativo || 0);
      cur.pago += e.valor_pago || Math.abs(e.valor_negativo || 0);
      map.set(cc, cur);
    });
    return Array.from(map, ([name, v]) => ({ name, ...v })).sort((a, b) => b.pago - a.pago).slice(0, 15);
  }, [filtered]);

  const pieData = useMemo(() => {
    const map = new Map<string, number>();
    filtered.forEach((e) => {
      const g = e.grupo || "Sem Grupo";
      map.set(g, (map.get(g) || 0) + Math.abs(e.valor_pago || e.valor_negativo || 0));
    });
    return Array.from(map, ([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 8);
  }, [filtered]);

  const lineData = useMemo(() => {
    const map = new Map<string, { previsto: number; pago: number }>();
    filtered.forEach((e) => {
      const comp = e.competencia || e.mes || "N/A";
      const cur = map.get(comp) || { previsto: 0, pago: 0 };
      cur.previsto += e.valor_previsto || Math.abs(e.valor_negativo || 0);
      cur.pago += e.valor_pago || Math.abs(e.valor_negativo || 0);
      map.set(comp, cur);
    });
    return Array.from(map, ([name, v]) => ({ name, ...v }));
  }, [filtered]);

  const fmt = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">Carregando...</div>;
  }

  if (entries.length === 0) {
    return (
      <div className="max-w-3xl mx-auto space-y-8 py-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">Fechamento demora dias? Orçamento só no Excel?</h1>
          <p className="text-muted-foreground">Importe sua base financeira e tenha centro de custo, fornecedor e resultado num só lugar — sem depender de planilha solta.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          {[
            "Fechamento gerencial demora dias",
            "Custos sem critério de rateio",
            "Cada área enxerga um número diferente",
            "Falta visibilidade por centro de custo e fornecedor",
          ].map((item) => (
            <div key={item} className="rounded-lg border border-border bg-card px-4 py-3 text-muted-foreground">
              {item}
            </div>
          ))}
        </div>
        <div className="flex flex-col items-center justify-center gap-4 pt-4">
          <FileText className="h-12 w-12 text-muted-foreground" />
          <a href="/import" className="text-primary underline font-medium">Importar planilha</a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        <Select value={filterFilial} onValueChange={setFilterFilial}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Filial" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas Filiais</SelectItem>
            {filiais.map((f) => <SelectItem key={f} value={f!}>{f}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filterBU} onValueChange={setFilterBU}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="B.U." /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas B.U.</SelectItem>
            {bus.map((b) => <SelectItem key={b} value={b!}>{b}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filterCompetencia} onValueChange={setFilterCompetencia}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Competência" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas Competências</SelectItem>
            {competencias.map((c) => <SelectItem key={c} value={c!}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Previsto</CardTitle>
            <TrendingUp className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmt(kpis.totalPrevisto)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Pago</CardTitle>
            <DollarSign className="h-4 w-4 text-accent" />
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmt(kpis.totalPago)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Diferença</CardTitle>
            <TrendingDown className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmt(kpis.diferenca)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Lançamentos</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{kpis.count.toLocaleString("pt-BR")}</p></CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-base">Pago vs Previsto por Centro de Custos</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Legend />
                <Bar dataKey="previsto" name="Previsto" fill="hsl(220, 70%, 50%)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="pago" name="Pago" fill="hsl(160, 60%, 45%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Distribuição por Grupo</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: number) => fmt(v)} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader><CardTitle className="text-base">Evolução por Competência</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Legend />
                <Line type="monotone" dataKey="previsto" name="Previsto" stroke="hsl(220, 70%, 50%)" strokeWidth={2} />
                <Line type="monotone" dataKey="pago" name="Pago" stroke="hsl(160, 60%, 45%)" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
