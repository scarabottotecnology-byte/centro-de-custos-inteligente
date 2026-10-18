import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/app/auth/AuthProvider";
import { useMembership } from "@/app/auth/useMembership";
import { QueryState } from "@/components/shared/QueryState";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";

function FullScreen({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}

/**
 * Libera as telas só para quem está logado e tem vínculo ativo.
 *
 * Sem sessão, manda para /login guardando o destino. Com sessão e sem vínculo,
 * explica que falta liberação em vez de mostrar telas vazias.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, isLoading } = useAuth();
  const location = useLocation();
  const membership = useMembership();

  if (isLoading) {
    return (
      <FullScreen>
        <span className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Verificando sessão…
        </span>
      </FullScreen>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (membership.isLoading || membership.isError || membership.data?.length === 0) {
    return (
      <FullScreen>
        <QueryState
          isLoading={membership.isLoading}
          isError={membership.isError}
          error={membership.error}
          isEmpty={membership.data?.length === 0}
          onRetry={() => membership.refetch()}
          emptyTitle="Sua conta ainda não tem acesso"
          emptyDescription={`A conta ${session.user.email ?? ""} foi criada, mas ainda não está vinculada a nenhuma organização. Peça a liberação a quem administra o sistema e entre de novo depois.`}
          emptyAction={
            <Button variant="outline" size="sm" onClick={() => supabase.auth.signOut()}>
              Sair
            </Button>
          }
        >
          {null}
        </QueryState>
      </FullScreen>
    );
  }

  return <>{children}</>;
}
