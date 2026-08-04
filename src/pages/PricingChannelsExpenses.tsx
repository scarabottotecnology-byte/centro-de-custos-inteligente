import { useCallback, useState } from "react";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Upload, Loader2, CheckCircle, Store, Receipt } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import {
  useSalesChannels, useCommercialExpenses,
  useUpsertChannel, useDeleteChannel, useUpsertExpense, useDeleteExpense,
} from "@/hooks/usePricingData";
import { channelVariablePct, fmtBRL, fmtPct, totalFixedExpenses } from "@/lib/pricing";
import { EXPENSE_FIELDS, EXPENSE_HINTS, autoMapImportFields, type ImportFieldMapping } from "@/lib/pricing-import";
import { getErrorMessage } from "@/lib/utils";
import type { TablesInsert } from "@/integrations/supabase/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useQueryClient } from "@tanstack/react-query";

const emptyChannel = {
  id: undefined as string | undefined,
  nome: "",
  comissao_pct: 0,
  taxa_pagamento_pct: 0,
  impostos_pct: 8,
  frete_pct: 0,
  marketing_pct: 0,
  margem_desejada_pct: 25,
  ativo: true,
};

const emptyExpense = {
  id: undefined as string | undefined,
  descricao: "",
  categoria: "",
  valor_mensal: 0,
  tipo: "fixo",
  competencia: "",
};

function ChannelsTab() {
  const { data: channels = [], isLoading } = useSalesChannels();
  const upsertChannel = useUpsertChannel();
  const deleteChannel = useDeleteChannel();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyChannel);

  const openNew = () => { setForm(emptyChannel); setOpen(true); };
  const openEdit = (c: typeof emptyChannel & { id: string }) => { setForm(c); setOpen(true); };

  const handleSave = async () => {
    if (!form.nome.trim()) { toast.error("Informe o nome do canal"); return; }
    try {
      await upsertChannel.mutateAsync(form);
      toast.success(form.id ? "Canal atualizado" : "Canal cadastrado");
      setOpen(false);
    } catch (err) {
      toast.error("Erro ao salvar: " + getErrorMessage(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteChannel.mutateAsync(id);
      toast.success("Canal removido");
    } catch (err) {
      toast.error("Erro ao remover: " + getErrorMessage(err));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />Novo Canal</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>{form.id ? "Editar Canal" : "Novo Canal de Venda"}</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="col-span-2">
                <Label>Nome do Canal *</Label>
                <Input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex: Marketplace, Loja Física..." />
              </div>
              <div>
                <Label>Comissão (%)</Label>
                <Input type="number" value={form.comissao_pct} onChange={(e) => setForm({ ...form, comissao_pct: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Taxa de Pagamento (%)</Label>
                <Input type="number" value={form.taxa_pagamento_pct} onChange={(e) => setForm({ ...form, taxa_pagamento_pct: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Impostos sobre Venda (%)</Label>
                <Input type="number" value={form.impostos_pct} onChange={(e) => setForm({ ...form, impostos_pct: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Frete (%)</Label>
                <Input type="number" value={form.frete_pct} onChange={(e) => setForm({ ...form, frete_pct: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Marketing / Ads (%)</Label>
                <Input type="number" value={form.marketing_pct} onChange={(e) => setForm({ ...form, marketing_pct: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Margem Desejada no Canal (%)</Label>
                <Input type="number" value={form.margem_desejada_pct ?? 0} onChange={(e) => setForm({ ...form, margem_desejada_pct: Number(e.target.value) })} />
              </div>
              <div className="col-span-2 flex items-center gap-2 pt-2">
                <Switch checked={form.ativo} onCheckedChange={(v) => setForm({ ...form, ativo: v })} />
                <Label>Canal ativo</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button onClick={handleSave} disabled={upsertChannel.isPending}>
                {upsertChannel.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                Salvar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="text-muted-foreground py-8 text-center">Carregando...</div>
      ) : channels.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
          <Store className="h-12 w-12" />
          <p>Nenhum canal de venda cadastrado.</p>
        </div>
      ) : (
        <div className="rounded-lg border overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Canal</TableHead>
                <TableHead className="text-right">Comissão</TableHead>
                <TableHead className="text-right">Taxa Pag.</TableHead>
                <TableHead className="text-right">Impostos</TableHead>
                <TableHead className="text-right">Frete</TableHead>
                <TableHead className="text-right">Marketing</TableHead>
                <TableHead className="text-right">Total Variável</TableHead>
                <TableHead className="text-right">Margem Alvo</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {channels.map((c) => (
                <TableRow key={c.id} className={!c.ativo ? "opacity-50" : ""}>
                  <TableCell className="text-sm font-medium">{c.nome}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.comissao_pct)}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.taxa_pagamento_pct)}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.impostos_pct)}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.frete_pct)}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.marketing_pct)}</TableCell>
                  <TableCell className="text-xs text-right font-medium">{fmtPct(channelVariablePct(c))}</TableCell>
                  <TableCell className="text-xs text-right">{fmtPct(c.margem_desejada_pct)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex gap-1 justify-end">
                      <Button size="icon" variant="ghost" onClick={() => openEdit({ ...c, margem_desejada_pct: c.margem_desejada_pct ?? 0 })}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="icon" variant="ghost"><Trash2 className="h-4 w-4 text-destructive" /></Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Remover canal?</AlertDialogTitle>
                            <AlertDialogDescription>Esta ação removerá "{c.nome}" permanentemente.</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(c.id)}>Remover</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function ExpensesTab() {
  const { data: expenses = [], isLoading } = useCommercialExpenses();
  const upsertExpense = useUpsertExpense();
  const deleteExpense = useDeleteExpense();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyExpense);

  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [mapping, setMapping] = useState<ImportFieldMapping>({});
  const [importing, setImporting] = useState(false);
  const [importDone, setImportDone] = useState(false);

  const openNew = () => { setForm(emptyExpense); setOpen(true); };
  const openEdit = (e: typeof emptyExpense & { id: string }) => { setForm(e); setOpen(true); };

  const handleSave = async () => {
    if (!form.descricao.trim()) { toast.error("Informe a descrição da despesa"); return; }
    try {
      await upsertExpense.mutateAsync(form);
      toast.success(form.id ? "Despesa atualizada" : "Despesa cadastrada");
      setOpen(false);
    } catch (err) {
      toast.error("Erro ao salvar: " + getErrorMessage(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteExpense.mutateAsync(id);
      toast.success("Despesa removida");
    } catch (err) {
      toast.error("Erro ao remover: " + getErrorMessage(err));
    }
  };

  const handleFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setImportDone(false);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const wb = XLSX.read(evt.target?.result, { type: "binary" });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const json = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws);
      if (json.length === 0) { toast.error("Planilha vazia"); return; }
      const cols = Object.keys(json[0]);
      setColumns(cols);
      setRows(json);
      setMapping(autoMapImportFields(cols, EXPENSE_HINTS));
      toast.success(`${json.length} linhas encontradas`);
    };
    reader.readAsBinaryString(f);
  }, []);

  const updateMapping = (dbField: string, colValue: string) => {
    setMapping((prev) => {
      const next = { ...prev };
      if (colValue === "__none__") delete next[dbField];
      else next[dbField] = colValue;
      return next;
    });
  };

  const handleImport = async () => {
    if (!mapping.descricao || !mapping.valor_mensal) {
      toast.error("Mapeie ao menos Descrição e Valor Mensal");
      return;
    }
    setImporting(true);
    const batchId = crypto.randomUUID();
    try {
      const CHUNK = 500;
      for (let i = 0; i < rows.length; i += CHUNK) {
        const chunk = rows.slice(i, i + CHUNK).map((row) => {
          const entry: Record<string, unknown> = { import_batch_id: batchId, tipo: "fixo" };
          for (const [dbField, col] of Object.entries(mapping)) {
            const val = row[col];
            const fieldDef = EXPENSE_FIELDS.find((f) => f.key === dbField);
            if (fieldDef?.type === "number") entry[dbField] = val != null ? Number(val) || 0 : 0;
            else entry[dbField] = val != null ? String(val) : null;
          }
          if (entry.tipo && !["fixo", "variavel"].includes(String(entry.tipo).toLowerCase())) entry.tipo = "fixo";
          if (!entry.descricao) return null;
          return entry;
        }).filter(Boolean) as unknown as TablesInsert<"commercial_expenses">[];

        if (chunk.length === 0) continue;
        const { error } = await supabase.from("commercial_expenses").insert(chunk);
        if (error) throw error;
      }
      toast.success(`${rows.length} despesas importadas com sucesso!`);
      setImportDone(true);
      queryClient.invalidateQueries({ queryKey: ["commercial-expenses"] });
    } catch (err) {
      toast.error("Erro na importação: " + getErrorMessage(err));
    } finally {
      setImporting(false);
    }
  };

  const resetImport = () => { setFile(null); setColumns([]); setRows([]); setMapping({}); setImportDone(false); };

  const totalFixo = totalFixedExpenses(expenses);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Despesas Fixas / Mês</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">{fmtBRL(totalFixo)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Itens Cadastrados</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">{expenses.length}</p></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Importar Despesas Comerciais</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <label className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl p-8 cursor-pointer hover:bg-muted/50 transition-colors">
            <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            <span className="text-sm text-muted-foreground">{file ? file.name : "Clique para selecionar .xlsx ou .csv"}</span>
            <input type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={handleFile} />
          </label>
          {columns.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {EXPENSE_FIELDS.map((field) => (
                  <div key={field.key} className="flex items-center gap-2">
                    <span className="text-sm w-40 shrink-0 font-medium">{field.label}</span>
                    <Select value={mapping[field.key] || "__none__"} onValueChange={(v) => updateMapping(field.key, v)}>
                      <SelectTrigger className="flex-1"><SelectValue placeholder="Selecione..." /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— Não mapear —</SelectItem>
                        {columns.map((col) => <SelectItem key={col} value={col}>{col}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
              <div className="flex gap-3">
                <Button onClick={handleImport} disabled={importing || importDone}>
                  {importing && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                  {importDone && <CheckCircle className="h-4 w-4 mr-2" />}
                  {importDone ? "Importado!" : importing ? "Importando..." : `Importar ${rows.length} despesas`}
                </Button>
                {importDone && <Button variant="outline" onClick={resetImport}>Nova importação</Button>}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Despesas Comerciais Cadastradas</CardTitle>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openNew}><Plus className="h-4 w-4 mr-2" />Nova Despesa</Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>{form.id ? "Editar Despesa" : "Nova Despesa Comercial"}</DialogTitle></DialogHeader>
              <div className="grid grid-cols-2 gap-4 py-2">
                <div className="col-span-2">
                  <Label>Descrição *</Label>
                  <Input value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
                </div>
                <div>
                  <Label>Categoria</Label>
                  <Input value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })} placeholder="Comercial, Marketing..." />
                </div>
                <div>
                  <Label>Valor Mensal (R$)</Label>
                  <Input type="number" value={form.valor_mensal} onChange={(e) => setForm({ ...form, valor_mensal: Number(e.target.value) })} />
                </div>
                <div>
                  <Label>Tipo</Label>
                  <Select value={form.tipo} onValueChange={(v) => setForm({ ...form, tipo: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixo">Fixo</SelectItem>
                      <SelectItem value="variavel">Variável</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Competência</Label>
                  <Input value={form.competencia} onChange={(e) => setForm({ ...form, competencia: e.target.value })} placeholder="Ex: 07/2026" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
                <Button onClick={handleSave} disabled={upsertExpense.isPending}>
                  {upsertExpense.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                  Salvar
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-muted-foreground py-8 text-center">Carregando...</div>
          ) : expenses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
              <Receipt className="h-12 w-12" />
              <p>Nenhuma despesa cadastrada.</p>
            </div>
          ) : (
            <div className="rounded-lg border overflow-auto max-h-[50vh]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Descrição</TableHead>
                    <TableHead>Categoria</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Competência</TableHead>
                    <TableHead className="text-right">Valor Mensal</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {expenses.map((e) => (
                    <TableRow key={e.id}>
                      <TableCell className="text-sm">{e.descricao}</TableCell>
                      <TableCell className="text-xs">{e.categoria || "—"}</TableCell>
                      <TableCell className="text-xs capitalize">{e.tipo}</TableCell>
                      <TableCell className="text-xs">{e.competencia || "—"}</TableCell>
                      <TableCell className="text-xs text-right">{fmtBRL(e.valor_mensal)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-1 justify-end">
                          <Button size="icon" variant="ghost" onClick={() => openEdit({
                            id: e.id, descricao: e.descricao, categoria: e.categoria || "",
                            valor_mensal: e.valor_mensal, tipo: e.tipo, competencia: e.competencia || "",
                          })}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="icon" variant="ghost"><Trash2 className="h-4 w-4 text-destructive" /></Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Remover despesa?</AlertDialogTitle>
                                <AlertDialogDescription>Esta ação removerá "{e.descricao}" permanentemente.</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDelete(e.id)}>Remover</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function PricingChannelsExpenses() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Canais de Venda & Despesas Comerciais</h1>
        <p className="text-sm text-muted-foreground">Marketplace, loja física e atacado têm custos diferentes — aplicar a mesma margem para todos é deixar dinheiro na mesa.</p>
      </div>
      <Tabs defaultValue="channels">
        <TabsList>
          <TabsTrigger value="channels">Canais de Venda</TabsTrigger>
          <TabsTrigger value="expenses">Despesas Comerciais</TabsTrigger>
        </TabsList>
        <TabsContent value="channels" className="mt-4"><ChannelsTab /></TabsContent>
        <TabsContent value="expenses" className="mt-4"><ExpensesTab /></TabsContent>
      </Tabs>
    </div>
  );
}
