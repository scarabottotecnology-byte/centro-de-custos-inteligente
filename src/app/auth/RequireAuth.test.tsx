import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/app/auth/AuthProvider";
import LoginPage from "@/app/auth/LoginPage";
import { RequireAuth } from "@/app/auth/RequireAuth";

const mock = vi.hoisted(() => ({
  session: null as unknown,
  memberships: { data: [] as unknown[], error: null as unknown },
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("@/integrations/supabase/client", () => {
  // Encadeamento .select().eq().eq() do PostgREST, resolvendo no fim.
  const query = {
    select: () => query,
    eq: () => query,
    then: (resolve: (v: unknown) => unknown) => resolve(mock.memberships),
  };
  return {
    supabase: {
      auth: {
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe: vi.fn() } } }),
        getSession: () => Promise.resolve({ data: { session: mock.session } }),
        signInWithPassword: mock.signInWithPassword,
        signOut: mock.signOut,
      },
      from: () => query,
    },
  };
});

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<RequireAuth><p>dados financeiros</p></RequireAuth>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const session = { user: { id: "u1", email: "pessoa@empresa.com" } };

beforeEach(() => {
  mock.session = null;
  mock.memberships = { data: [], error: null };
  mock.signInWithPassword.mockReset();
  mock.signOut.mockReset();
});

describe("acesso ao app", () => {
  it("sem sessão, manda para o login e não mostra dados", async () => {
    renderAt("/pricing/calculator");
    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByText("dados financeiros")).not.toBeInTheDocument();
  });

  it("conta sem vínculo vê o aviso de liberação pendente, não telas vazias", async () => {
    mock.session = session;
    renderAt("/");
    expect(await screen.findByText("Sua conta ainda não tem acesso")).toBeInTheDocument();
    expect(screen.getByText(/pessoa@empresa\.com/)).toBeInTheDocument();
    expect(screen.queryByText("dados financeiros")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sair" }));
    expect(mock.signOut).toHaveBeenCalledOnce();
  });

  it("membro ativo vê o app", async () => {
    mock.session = session;
    mock.memberships = { data: [{ organization_id: "o1", role: "owner" }], error: null };
    renderAt("/");
    expect(await screen.findByText("dados financeiros")).toBeInTheDocument();
  });

  it("falha ao consultar o vínculo mostra o erro com nova tentativa", async () => {
    mock.session = session;
    mock.memberships = { data: null as unknown as unknown[], error: { message: "Failed to fetch" } };
    renderAt("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Failed to fetch");
  });

  it("login com senha errada mostra a mensagem em português", async () => {
    mock.signInWithPassword.mockResolvedValue({ error: new Error("Invalid login credentials") });
    renderAt("/login");
    fireEvent.change(await screen.findByLabelText("E-mail"), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "errada" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("E-mail ou senha incorretos."));
    expect(mock.signInWithPassword).toHaveBeenCalledWith({ email: "a@b.com", password: "errada" });
  });
});
