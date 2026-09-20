import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { TablesInsert, TablesUpdate } from "@/integrations/supabase/types";

export function usePricingProducts() {
  return useQuery({
    queryKey: ["pricing-products"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("pricing_products")
        .select("*")
        .order("nome", { ascending: true });
      if (error) throw error;
      return data;
    },
  });
}

export function useSalesChannels() {
  return useQuery({
    queryKey: ["sales-channels"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("sales_channels")
        .select("*")
        .order("nome", { ascending: true });
      if (error) throw error;
      return data;
    },
  });
}

export function useCommercialExpenses() {
  return useQuery({
    queryKey: ["commercial-expenses"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("commercial_expenses")
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });
}

export function useUpsertProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (product: TablesInsert<"pricing_products"> & { id?: string }) => {
      if (product.id) {
        const { id, ...rest } = product;
        const { error } = await supabase.from("pricing_products").update(rest as TablesUpdate<"pricing_products">).eq("id", id);
        if (error) throw error;
      } else {
        const { error } = await supabase.from("pricing_products").insert(product);
        if (error) throw error;
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pricing-products"] }),
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("pricing_products").delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pricing-products"] }),
  });
}

export function useUpsertChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (channel: TablesInsert<"sales_channels"> & { id?: string }) => {
      if (channel.id) {
        const { id, ...rest } = channel;
        const { error } = await supabase.from("sales_channels").update(rest as TablesUpdate<"sales_channels">).eq("id", id);
        if (error) throw error;
      } else {
        const { error } = await supabase.from("sales_channels").insert(channel);
        if (error) throw error;
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sales-channels"] }),
  });
}

export function useDeleteChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("sales_channels").delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sales-channels"] }),
  });
}

export function useUpsertExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (expense: TablesInsert<"commercial_expenses"> & { id?: string }) => {
      if (expense.id) {
        const { id, ...rest } = expense;
        const { error } = await supabase.from("commercial_expenses").update(rest as TablesUpdate<"commercial_expenses">).eq("id", id);
        if (error) throw error;
      } else {
        const { error } = await supabase.from("commercial_expenses").insert(expense);
        if (error) throw error;
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["commercial-expenses"] }),
  });
}

export function useDeleteExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("commercial_expenses").delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["commercial-expenses"] }),
  });
}
