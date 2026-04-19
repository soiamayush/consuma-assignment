import { NavLink, Link } from "react-router-dom";
import { Activity, LayoutDashboard, Rss, RefreshCw, BarChart3, Megaphone, Scale, Sparkles } from "lucide-react";
import clsx from "clsx";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

type Props = { children: React.ReactNode };

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/compare", label: "Compare", icon: Scale },
  { to: "/ask", label: "Ask AI", icon: Sparkles },
  { to: "/feed", label: "Signal feed", icon: Rss },
  { to: "/buzz", label: "Buzz", icon: Megaphone },
  { to: "/runs", label: "Ingestion runs", icon: Activity },
];

export function AppShell({ children }: Props) {
  const qc = useQueryClient();
  const runMut = useMutation({
    mutationFn: () => api.triggerRun(undefined, false),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries(), 2500);
    },
  });
  const runErr =
    runMut.error instanceof Error ? runMut.error.message : runMut.error ? String(runMut.error) : null;

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-ink-200 bg-white/80 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-3 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <div className="h-7 w-7 rounded-md bg-ink-900 text-white grid place-items-center text-xs font-bold">
              CW
            </div>
            <span>Competitor Watch</span>
            <span className="text-ink-400 font-normal text-sm hidden sm:inline">
              · Minimalist vs skincare peers
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    "btn",
                    isActive ? "bg-ink-900 text-white" : "text-ink-700 hover:bg-ink-100"
                  )
                }
              >
                <Icon size={16} />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
            <div className="flex flex-col items-end gap-1">
              <button
                className="btn-primary"
                onClick={() => runMut.mutate()}
                disabled={runMut.isPending}
                title="Trigger an ingestion run across all enabled sources (runs in the API unless RQ is enabled)"
              >
                <RefreshCw size={16} className={runMut.isPending ? "animate-spin" : ""} />
                <span className="hidden sm:inline">
                  {runMut.isPending ? "Running…" : "Run ingestion"}
                </span>
              </button>
              {runErr && (
                <p className="text-[11px] text-rose-600 max-w-xs text-right leading-snug" title={runErr}>
                  {runErr}
                </p>
              )}
            </div>
          </nav>
        </div>
      </header>
      <main className="flex-1 mx-auto max-w-7xl w-full px-6 py-8">{children}</main>
      <footer className="py-6 text-center text-xs text-ink-400">
        Competitor Watch · Take-home prototype
      </footer>
    </div>
  );
}
