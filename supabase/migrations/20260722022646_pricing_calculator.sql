-- Pricing Calculator module: product catalog, sales channels, commercial expenses

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Product catalog with all cost variables used for pricing
CREATE TABLE public.pricing_products (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  sku TEXT,
  nome TEXT NOT NULL,
  categoria TEXT,
  unidade TEXT DEFAULT 'un',
  custo_materia_prima NUMERIC NOT NULL DEFAULT 0,
  custo_embalagem NUMERIC NOT NULL DEFAULT 0,
  mao_de_obra_direta NUMERIC NOT NULL DEFAULT 0,
  custos_indiretos NUMERIC NOT NULL DEFAULT 0,
  outros_custos_variaveis NUMERIC NOT NULL DEFAULT 0,
  custo_variavel_unitario NUMERIC GENERATED ALWAYS AS (
    custo_materia_prima + custo_embalagem + mao_de_obra_direta + custos_indiretos + outros_custos_variaveis
  ) STORED,
  preco_atual NUMERIC,
  margem_desejada_pct NUMERIC NOT NULL DEFAULT 30,
  volume_mensal_estimado NUMERIC NOT NULL DEFAULT 0,
  ativo BOOLEAN NOT NULL DEFAULT true,
  import_batch_id UUID,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_pricing_products_updated_at
  BEFORE UPDATE ON public.pricing_products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.pricing_products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anon can read pricing products" ON public.pricing_products FOR SELECT TO anon USING (true);
CREATE POLICY "Anon can insert pricing products" ON public.pricing_products FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Anon can update pricing products" ON public.pricing_products FOR UPDATE TO anon USING (true);
CREATE POLICY "Anon can delete pricing products" ON public.pricing_products FOR DELETE TO anon USING (true);
CREATE POLICY "Auth can read pricing products" ON public.pricing_products FOR SELECT TO authenticated USING (true);
CREATE POLICY "Auth can insert pricing products" ON public.pricing_products FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Auth can update pricing products" ON public.pricing_products FOR UPDATE TO authenticated USING (true);
CREATE POLICY "Auth can delete pricing products" ON public.pricing_products FOR DELETE TO authenticated USING (true);

CREATE INDEX idx_pricing_products_sku ON public.pricing_products(sku);
CREATE INDEX idx_pricing_products_categoria ON public.pricing_products(categoria);
CREATE INDEX idx_pricing_products_ativo ON public.pricing_products(ativo);
CREATE INDEX idx_pricing_products_batch ON public.pricing_products(import_batch_id);

-- Sales channels, each with its own variable cost structure (commission, fees, taxes, freight, marketing)
CREATE TABLE public.sales_channels (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  nome TEXT NOT NULL UNIQUE,
  comissao_pct NUMERIC NOT NULL DEFAULT 0,
  taxa_pagamento_pct NUMERIC NOT NULL DEFAULT 0,
  impostos_pct NUMERIC NOT NULL DEFAULT 0,
  frete_pct NUMERIC NOT NULL DEFAULT 0,
  marketing_pct NUMERIC NOT NULL DEFAULT 0,
  margem_desejada_pct NUMERIC,
  ativo BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_sales_channels_updated_at
  BEFORE UPDATE ON public.sales_channels
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.sales_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anon can read sales channels" ON public.sales_channels FOR SELECT TO anon USING (true);
CREATE POLICY "Anon can insert sales channels" ON public.sales_channels FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Anon can update sales channels" ON public.sales_channels FOR UPDATE TO anon USING (true);
CREATE POLICY "Anon can delete sales channels" ON public.sales_channels FOR DELETE TO anon USING (true);
CREATE POLICY "Auth can read sales channels" ON public.sales_channels FOR SELECT TO authenticated USING (true);
CREATE POLICY "Auth can insert sales channels" ON public.sales_channels FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Auth can update sales channels" ON public.sales_channels FOR UPDATE TO authenticated USING (true);
CREATE POLICY "Auth can delete sales channels" ON public.sales_channels FOR DELETE TO authenticated USING (true);

-- Commercial / operating expenses, used to allocate fixed costs and compute the break-even point
CREATE TABLE public.commercial_expenses (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  descricao TEXT NOT NULL,
  categoria TEXT,
  valor_mensal NUMERIC NOT NULL DEFAULT 0,
  tipo TEXT NOT NULL DEFAULT 'fixo' CHECK (tipo IN ('fixo', 'variavel')),
  competencia TEXT,
  import_batch_id UUID,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.commercial_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anon can read commercial expenses" ON public.commercial_expenses FOR SELECT TO anon USING (true);
CREATE POLICY "Anon can insert commercial expenses" ON public.commercial_expenses FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Anon can update commercial expenses" ON public.commercial_expenses FOR UPDATE TO anon USING (true);
CREATE POLICY "Anon can delete commercial expenses" ON public.commercial_expenses FOR DELETE TO anon USING (true);
CREATE POLICY "Auth can read commercial expenses" ON public.commercial_expenses FOR SELECT TO authenticated USING (true);
CREATE POLICY "Auth can insert commercial expenses" ON public.commercial_expenses FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Auth can update commercial expenses" ON public.commercial_expenses FOR UPDATE TO authenticated USING (true);
CREATE POLICY "Auth can delete commercial expenses" ON public.commercial_expenses FOR DELETE TO authenticated USING (true);

CREATE INDEX idx_commercial_expenses_tipo ON public.commercial_expenses(tipo);
CREATE INDEX idx_commercial_expenses_competencia ON public.commercial_expenses(competencia);
CREATE INDEX idx_commercial_expenses_batch ON public.commercial_expenses(import_batch_id);

-- Seed common Brazilian sales channels with typical cost structures (editable afterwards)
INSERT INTO public.sales_channels (nome, comissao_pct, taxa_pagamento_pct, impostos_pct, frete_pct, marketing_pct, margem_desejada_pct) VALUES
  ('Loja Física', 0, 2.5, 8, 0, 2, 30),
  ('E-commerce Próprio', 0, 3.5, 8, 6, 8, 25),
  ('Marketplace', 16, 3.5, 8, 6, 2, 20),
  ('Atacado / Distribuidor', 0, 1.5, 8, 3, 0, 15),
  ('Televendas', 3, 2.5, 8, 4, 3, 22);
