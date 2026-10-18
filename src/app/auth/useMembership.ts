import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/app/auth/AuthProvider";

/**
 * Vínculos ativos da pessoa logada.
 *
 * Ter conta não dá acesso: o cadastro do Supabase Auth é aberto, então quem
 * libera os dados é o vínculo em `memberships`. Sem vínculo, a RLS esconde
 * tudo e as telas pareceriam vazias; esta consulta permite dizer o motivo.
 */
export function useMembership() {
  const { session } = useAuth();
  const userId = session?.user.id;

  return useQuery({
    queryKey: ["memberships", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      const { data, error } = await supabase
        .from("memberships")
        .select("organization_id, role, organizations(display_name)")
        .eq("user_id", userId!)
        .eq("status", "active");
      if (error) throw error;
      return data;
    },
  });
}
