import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PricingCalculator from "@/modules/pricing/pages/PricingCalculator";
import PricingChannelsExpenses from "@/modules/pricing/pages/PricingChannelsExpenses";
import PricingProducts from "@/modules/pricing/pages/PricingProducts";

vi.mock("@/integrations/supabase/client", () => ({ supabase: {} }));

type FakeQuery = {
  data: unknown[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: ReturnType<typeof vi.fn>;
};

const ok = (data: unknown[] = []): FakeQuery => ({
  data, isLoading: false, isError: false, error: null, refetch: vi.fn(),
});
// O cliente Supabase rejeita com objeto simples, não com Error.
const failing = (message: string): FakeQuery => ({
  data: undefined, isLoading: false, isError: true, error: { message, code: "42501" }, refetch: vi.fn(),
});

const state = vi.hoisted(() => ({
  products: null as unknown,
  channels: null as unknown,
  expenses: null as unknown,
}));

vi.mock("@/modules/pricing/hooks/usePricingData", () => {
  const mutation = () => ({ mutateAsync: vi.fn(), isPending: false });
  return {
    usePricingProducts: () => state.products,
    useSalesChannels: () => state.channels,
    useCommercialExpenses: () => state.expenses,
    useUpsertProduct: mutation,
    useDeleteProduct: mutation,
    useUpsertChannel: mutation,
    useDeleteChannel: mutation,
    useUpsertExpense: mutation,
    useDeleteExpense: mutation,
  };
});

function renderPage(page: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  state.products = ok();
  state.channels = ok();
  state.expenses = ok();
});

describe("páginas de precificação", () => {
  it("calculadora mostra o erro em vez de ficar carregando, e tenta de novo só a consulta que falhou", () => {
    const channels = failing("permission denied for table sales_channels");
    state.channels = channels;
    renderPage(<PricingCalculator />);

    expect(screen.getByRole("alert")).toHaveTextContent("permission denied for table sales_channels");
    expect(screen.queryByText(/Carregando/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(channels.refetch).toHaveBeenCalledOnce();
    expect((state.products as FakeQuery).refetch).not.toHaveBeenCalled();
  });

  it("calculadora sem produto mostra o estado vazio com link para o cadastro", () => {
    renderPage(<PricingCalculator />);
    expect(screen.getByRole("link", { name: "Cadastrar produtos" })).toHaveAttribute("href", "/pricing/products");
  });

  it("catálogo mostra o erro da consulta de produtos", () => {
    state.products = failing("Failed to fetch");
    renderPage(<PricingProducts />);
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to fetch");
    expect(screen.getByRole("button", { name: /Novo Produto/ })).toBeInTheDocument();
  });

  it("canais mostra o erro da consulta de canais", () => {
    state.channels = failing("Failed to fetch");
    renderPage(<PricingChannelsExpenses />);
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to fetch");
  });
});
