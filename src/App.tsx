import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppLayout } from "@/components/AppLayout";
import Index from "./pages/Index";
import Import from "./pages/Import";
import Entries from "./pages/Entries";
import CostCenters from "./pages/CostCenters";
import PricingCalculator from "./pages/PricingCalculator";
import PricingProducts from "./pages/PricingProducts";
import PricingChannelsExpenses from "./pages/PricingChannelsExpenses";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/import" element={<Import />} />
            <Route path="/entries" element={<Entries />} />
            <Route path="/cost-centers" element={<CostCenters />} />
            <Route path="/pricing/calculator" element={<PricingCalculator />} />
            <Route path="/pricing/products" element={<PricingProducts />} />
            <Route path="/pricing/channels" element={<PricingChannelsExpenses />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
