import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

interface AuthState {
  session: Session | null;
  /** Verdadeiro até o Supabase dizer se há sessão salva. */
  isLoading: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

/**
 * Sessão do Supabase Auth para o app inteiro.
 *
 * Sem sessão, as políticas de RLS não devolvem nada (C-01): toda consulta
 * depende de quem está logado. Por isso o cache do react-query é descartado
 * quando a pessoa sai ou troca de conta: senão os dados da conta anterior
 * continuariam na tela.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ session: null, isLoading: true });
  const userId = useRef<string | undefined>(undefined);

  useEffect(() => {
    const apply = (session: Session | null) => {
      if (userId.current !== session?.user.id) queryClient.clear();
      userId.current = session?.user.id;
      setState({ session, isLoading: false });
    };

    // O listener vem antes do getSession para não perder um evento que
    // chegue entre os dois.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => apply(session));
    supabase.auth.getSession().then(({ data: { session } }) => apply(session));

    return () => data.subscription.unsubscribe();
  }, [queryClient]);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
