import { useMemo, useState } from "react";
import { useFinancialData } from "@/hooks/useFinancialData";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function Entries() {
  const { data: entries = [], isLoading } = useFinancialData();
  const [search, setSearch] = useState("");
  const [filterGrupo, setFilterGrupo] = useState("all");

  const grupos = useMemo(() => [...new Set(entries.map((e) => e.grupo).filter(Boolean))], [entries]);

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filterGrupo !== "all" && e.grupo !== filterGrupo) return false;
      if (search) {
        const s = search.toLowerCase();
        return (
          e.fornecedor?.toLowerCase().includes(s) ||
          e.razao_social?.toLowerCase().includes(s) ||
          e.historico?.toLowerCase().includes(s) ||
          e.cca?.toLowerCase().includes(s) ||
          e.ccs?.toLowerCase().includes(s)
        );
      }
      return true;
    });
  }, [entries, search, filterGrupo]);

  const fmt = (v: number | null) =>
    v != null ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v) : "—";

  if (isLoading) return <div className="text-muted-foreground p-8">Carregando...</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Lançamentos</h1>
      <div className="flex flex-wrap gap-3">
        <Input placeholder="Buscar fornecedor, razão social..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
        <Select value={filterGrupo} onValueChange={setFilterGrupo}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Grupo" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos Grupos</SelectItem>
            {grupos.map((g) => <SelectItem key={g} value={g!}>{g}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground self-center">{filtered.length} registros</span>
      </div>

      <div className="rounded-lg border overflow-auto max-h-[70vh]">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>CCA</TableHead>
              <TableHead>CCS</TableHead>
              <TableHead>Grupo</TableHead>
              <TableHead>Filial</TableHead>
              <TableHead>Fornecedor</TableHead>
              <TableHead>Competência</TableHead>
              <TableHead className="text-right">Previsto</TableHead>
              <TableHead className="text-right">Pago</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.slice(0, 200).map((e) => (
              <TableRow key={e.id}>
                <TableCell className="text-xs">{e.cca || "—"}</TableCell>
                <TableCell className="text-xs">{e.ccs || "—"}</TableCell>
                <TableCell className="text-xs">{e.grupo || "—"}</TableCell>
                <TableCell className="text-xs">{e.filial || "—"}</TableCell>
                <TableCell className="text-xs">{e.fornecedor || e.razao_social || "—"}</TableCell>
                <TableCell className="text-xs">{e.competencia || "—"}</TableCell>
                <TableCell className="text-xs text-right">{fmt(e.valor_previsto)}</TableCell>
                <TableCell className="text-xs text-right">{fmt(e.valor_pago)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
