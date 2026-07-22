import { useCallback, useMemo, useState } from "react";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { Plus, Upload, Loader2, CheckCircle, Pencil, Trash2, Package } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { usePricingProducts, useUpsertProduct, useDeleteProduct } from "@/hooks/usePricingData";
import { custoVariavelUnitario, fmtBRL, type PricingProduct } from "@/lib/pricing";
import { PRODUCT_FIELDS, PRODUCT_HINTS, autoMapImportFields, type ImportFieldMapping } from "@/lib/pricing-import";
import { getErrorMessage } from "@/lib/utils";
import type { TablesInsert } from "@/integrations/supabase/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useQueryClient } from "@tanstack/react-query";

const emptyForm = {
  id: undefined as string | undefined,
  sku: "",
  nome: "",
  categoria: "",
  unidade: "un",
  custo_materia_prima: 0,
  custo_embalagem: 0,
  mao_de_obra_direta: 0,
  custos_indiretos: 0,
  outros_custos_variaveis: 0,
  preco_atual: 0,
  margem_desejada_pct: 30,
  volume_mensal_estimado: 0,
  ativo: true,
};

export default function PricingProducts() {
  const { data: products = [], isLoading } = usePricingProducts();
  const upsertProduct = useUpsertProduct();
  const deleteProduct = useDeleteProduct();
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  // Import state
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [mapping, setMapping] = useState<ImportFieldMapping>({});
  const [importing, setImporting] = useState(false);
  const [importDone, setImportDone] = useState(false);

  const openNew = () => {
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (p: PricingProduct) => {
    setForm({
      id: p.id,
      sku: p.sku || "",
      nome: p.nome,
      categoria: p.categoria || "",
      unidade: p.unidade || "un",
      custo_materia_prima: p.custo_materia_prima,
      custo_embalagem: p.custo_embalagem,
      mao_de_obra_direta: p.mao_de_obra_direta,
      custos_indiretos: p.custos_indiretos,
      outros_custos_variaveis: p.outros_custos_variaveis,
      preco_atual: p.preco_atual || 0,
      margem_desejada_pct: p.margem_desejada_pct,
      volume_mensal_estimado: p.volume_mensal_estimado,
      ativo: p.ativo,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.nome.trim()) {
      toast.error("Informe o nome do produto");
      return;
    }
    try {
      await upsertProduct.mutateAsync(form);
      toast.success(form.id ? "Produto atualizado" : "Produto cadastrado");
      setDialogOpen(false);
    } catch (err) {
      toast.error("Erro ao salvar: " + getErrorMessage(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteProduct.mutateAsync(id);
      toast.success("Produto removido");
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
      if (json.length === 0) {
        toast.error("Planilha vazia");
        return;
      }
      const cols = Object.keys(json[0]);
      setColumns(cols);
      setRows(json);
      setMapping(autoMapImportFields(cols, PRODUCT_HINTS));
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
    if (!mapping.nome) {
      toast.error("Mapeie ao menos o campo Nome do Produto");
      return;
    }
    setImporting(true);
    const batchId = crypto.randomUUID();
    try {
      const CHUNK = 500;
      for (let i = 0; i < rows.length; i += CHUNK) {
        const chunk = rows.slice(i, i + CHUNK).map((row) => {
          const entry: Record<string, unknown> = { import_batch_id: batchId };
          for (const [dbField, col] of Object.entries(mapping)) {
            const val = row[col];
            const fieldDef = PRODUCT_FIELDS.find((f) => f.key === dbField);
            if (fieldDef?.type === "number") {
              entry[dbField] = val != null ? Number(val) || 0 : 0;
            } else {
              entry[dbField] = val != null ? String(val) : null;
            }
          }
          if (!entry.nome) return null;
          return entry;
        }).filter(Boolean) as unknown as TablesInsert<"pricing_products">[];

        if (chunk.length === 0) continue;
        const { error } = await supabase.from("pricing_products").insert(chunk);
        if (error) throw error;
      }
      toast.success(`${rows.length} produtos importados com sucesso!`);
      setImportDone(true);
      queryClient.invalidateQueries({ queryKey: ["pricing-products"] });
    } catch (err) {
      toast.error("Erro na importação: " + getErrorMessage(err));
    } finally {
      setImporting(false);
    }
  };

  const resetImport = () => {
    setFile(null);
    setColumns([]);
    setRows([]);
    setMapping({});
    setImportDone(false);
  };

  const totalCatalog = useMemo(() => products.length, [products]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo de Produtos</h1>
          <p className="text-sm text-muted-foreground">Cadastre os produtos e suas variáveis de custo para precificação</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openNew}><Plus className="h-4 w-4 mr-2" />Novo Produto</Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{form.id ? "Editar Produto" : "Novo Produto"}</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="col-span-2">
                <Label>Nome do Produto *</Label>
                <Input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />
              </div>
              <div>
                <Label>SKU / Código</Label>
                <Input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
              </div>
              <div>
                <Label>Categoria</Label>
                <Input value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })} />
              </div>
              <div>
                <Label>Unidade</Label>
                <Input value={form.unidade} onChange={(e) => setForm({ ...form, unidade: e.target.value })} />
              </div>
              <div>
                <Label>Volume Mensal Estimado</Label>
                <Input type="number" value={form.volume_mensal_estimado} onChange={(e) => setForm({ ...form, volume_mensal_estimado: Number(e.target.value) })} />
              </div>
              <div className="col-span-2 border-t pt-3 mt-1">
                <p className="text-sm font-medium text-muted-foreground mb-2">Custos Variáveis Unitários</p>
              </div>
              <div>
                <Label>Matéria-Prima (R$)</Label>
                <Input type="number" value={form.custo_materia_prima} onChange={(e) => setForm({ ...form, custo_materia_prima: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Embalagem (R$)</Label>
                <Input type="number" value={form.custo_embalagem} onChange={(e) => setForm({ ...form, custo_embalagem: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Mão de Obra Direta (R$)</Label>
                <Input type="number" value={form.mao_de_obra_direta} onChange={(e) => setForm({ ...form, mao_de_obra_direta: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Custos Indiretos - CIF (R$)</Label>
                <Input type="number" value={form.custos_indiretos} onChange={(e) => setForm({ ...form, custos_indiretos: Number(e.target.value) })} />
              </div>
              <div className="col-span-2">
                <Label>Outros Custos Variáveis (R$)</Label>
                <Input type="number" value={form.outros_custos_variaveis} onChange={(e) => setForm({ ...form, outros_custos_variaveis: Number(e.target.value) })} />
              </div>
              <div className="col-span-2 border-t pt-3 mt-1">
                <p className="text-sm font-medium text-muted-foreground mb-2">Precificação</p>
              </div>
              <div>
                <Label>Preço de Venda Atual (R$)</Label>
                <Input type="number" value={form.preco_atual} onChange={(e) => setForm({ ...form, preco_atual: Number(e.target.value) })} />
              </div>
              <div>
                <Label>Margem Desejada (%)</Label>
                <Input type="number" value={form.margem_desejada_pct} onChange={(e) => setForm({ ...form, margem_desejada_pct: Number(e.target.value) })} />
              </div>
              <div className="col-span-2 flex items-center gap-2 pt-2">
                <Switch checked={form.ativo} onCheckedChange={(v) => setForm({ ...form, ativo: v })} />
                <Label>Produto ativo</Label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button onClick={handleSave} disabled={upsertProduct.isPending}>
                {upsertProduct.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                Salvar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Import */}
      <Card>
        <CardHeader><CardTitle className="text-base">Importar Planilha de Produtos e Custos</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <label className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl p-8 cursor-pointer hover:bg-muted/50 transition-colors">
            <Upload className="h-8 w-8 text-muted-foreground mb-2" />
            <span className="text-sm text-muted-foreground">{file ? file.name : "Clique para selecionar .xlsx ou .csv"}</span>
            <input type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={handleFile} />
          </label>

          {columns.length > 0 && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {PRODUCT_FIELDS.map((field) => (
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
                  {importDone ? "Importado!" : importing ? "Importando..." : `Importar ${rows.length} produtos`}
                </Button>
                {importDone && <Button variant="outline" onClick={resetImport}>Nova importação</Button>}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader><CardTitle className="text-base">Produtos Cadastrados ({totalCatalog})</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-muted-foreground py-8 text-center">Carregando...</div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
              <Package className="h-12 w-12" />
              <p>Nenhum produto cadastrado ainda.</p>
            </div>
          ) : (
            <div className="rounded-lg border overflow-auto max-h-[60vh]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>SKU</TableHead>
                    <TableHead>Produto</TableHead>
                    <TableHead>Categoria</TableHead>
                    <TableHead className="text-right">Custo Variável</TableHead>
                    <TableHead className="text-right">Preço Atual</TableHead>
                    <TableHead className="text-right">Margem Desejada</TableHead>
                    <TableHead className="text-right">Volume/Mês</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((p) => (
                    <TableRow key={p.id} className={!p.ativo ? "opacity-50" : ""}>
                      <TableCell className="text-xs">{p.sku || "—"}</TableCell>
                      <TableCell className="text-sm font-medium">{p.nome}</TableCell>
                      <TableCell className="text-xs">{p.categoria || "—"}</TableCell>
                      <TableCell className="text-xs text-right">{fmtBRL(custoVariavelUnitario(p))}</TableCell>
                      <TableCell className="text-xs text-right">{fmtBRL(p.preco_atual)}</TableCell>
                      <TableCell className="text-xs text-right">{p.margem_desejada_pct}%</TableCell>
                      <TableCell className="text-xs text-right">{p.volume_mensal_estimado}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-1 justify-end">
                          <Button size="icon" variant="ghost" onClick={() => openEdit(p)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button size="icon" variant="ghost"><Trash2 className="h-4 w-4 text-destructive" /></Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Remover produto?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Esta ação removerá "{p.nome}" do catálogo permanentemente.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDelete(p.id)}>Remover</AlertDialogAction>
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
