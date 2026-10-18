import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { Navigate, useLocation, type Location } from "react-router-dom";
import { useAuth } from "@/app/auth/AuthProvider";
import { Logo } from "@/components/shared/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { getErrorMessage } from "@/lib/utils";

type Mode = "signin" | "signup";

export default function LoginPage() {
  const { session, isLoading } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: Location } | null)?.from?.pathname ?? "/";

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!isLoading && session) return <Navigate to={from} replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        // Com confirmação de e-mail ligada no projeto, o signUp não abre sessão.
        if (!data.session) {
          setNotice("Conta criada. Confirme pelo link enviado ao seu e-mail e depois entre.");
          setMode("signin");
        }
      }
    } catch (err) {
      setError(
        getErrorMessage(err) === "Invalid login credentials"
          ? "E-mail ou senha incorretos."
          : getErrorMessage(err),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <Logo />
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-2xl font-semibold tracking-[-0.02em]">
            {mode === "signin" ? "Entrar" : "Criar conta"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {mode === "signin"
              ? "Os dados financeiros só aparecem para contas liberadas."
              : "Depois de criar a conta, peça a liberação a quem administra o sistema."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Senha</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              minLength={mode === "signup" ? 8 : undefined}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <p role="alert" className="text-sm text-negative">{error}</p>}
          {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}

          <Button type="submit" disabled={submitting}>
            {submitting && <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />}
            {mode === "signin" ? "Entrar" : "Criar conta"}
          </Button>
        </form>

        <button
          type="button"
          className="self-start text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
          onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null); }}
        >
          {mode === "signin" ? "Ainda não tem conta? Criar conta" : "Já tem conta? Entrar"}
        </button>
      </div>
    </div>
  );
}
