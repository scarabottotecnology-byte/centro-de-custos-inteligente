import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export function useFinancialData() {
  return useQuery({
    queryKey: ["financial-entries"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("financial_entries")
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });
}
