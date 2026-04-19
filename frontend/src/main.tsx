import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { CompetitorPage } from "./pages/CompetitorPage";
import { FeedPage } from "./pages/FeedPage";
import { ProductPage } from "./pages/ProductPage";
import { RunsPage } from "./pages/RunsPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { BuzzPage } from "./pages/BuzzPage";
import { ComparePage } from "./pages/ComparePage";
import { AskPage } from "./pages/AskPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, refetchOnWindowFocus: false },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/ask" element={<AskPage />} />
            <Route path="/feed" element={<FeedPage />} />
            <Route path="/buzz" element={<BuzzPage />} />
            <Route path="/competitors/:slug" element={<CompetitorPage />} />
            <Route path="/products/:id" element={<ProductPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
