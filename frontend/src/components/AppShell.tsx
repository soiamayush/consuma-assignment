import { NavLink, Link } from "react-router-dom";
import {
  Activity,
  LayoutDashboard,
  Rss,
  RefreshCw,
  BarChart3,
  Megaphone,
  Scale,
  Sparkles,
} from "lucide-react";
import clsx from "clsx";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

type Props = { children: React.ReactNode };

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/compare", label: "Compare", icon: Scale },
  { to: "/ask", label: "Ask AI", icon: Sparkles },
  { to: "/feed", label: "Feed", icon: Rss },
  { to: "/buzz", label: "Buzz", icon: Megaphone },
  { to: "/runs", label: "Runs", icon: Activity },
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
    runMut.error instanceof Error
      ? runMut.error.message
      : runMut.error
        ? String(runMut.error)
        : null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-30 border-b border-white/60 glass">
        <div className="mx-auto max-w-7xl px-4 md:px-6 py-3 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="relative">
              <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-ink-900 via-plum-700 to-blush-600 text-white grid place-items-center shadow-lift group-hover:scale-105 transition">
                <Sparkles size={16} strokeWidth={2.2} />
              </div>
              <div className="absolute -inset-1 rounded-xl bg-gradient-to-br from-blush-400/40 to-accent-300/40 blur-md -z-10 opacity-0 group-hover:opacity-100 transition" />
            </div>
            <div className="leading-tight">
              <div className="font-display text-[17px] font-semibold tracking-tight">
                Atelier
              </div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-ink-500 -mt-0.5 hidden sm:block">
                Beauty intelligence
              </div>
            </div>
          </Link>

          <nav className="flex items-center gap-1 flex-wrap justify-end">
            <div className="hidden md:flex items-center gap-0.5 bg-white/60 border border-white/70 rounded-full p-1 shadow-sm">
              {NAV.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    clsx(
                      "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors",
                      isActive
                        ? "bg-ink-900 text-white shadow-sm"
                        : "text-ink-600 hover:text-ink-900 hover:bg-white",
                    )
                  }
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>

            <div className="md:hidden flex items-center gap-0.5 overflow-x-auto">
              {NAV.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    clsx(
                      "inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap",
                      isActive
                        ? "bg-ink-900 text-white"
                        : "text-ink-600 hover:bg-white",
                    )
                  }
                >
                  <Icon size={13} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>

            <div className="flex flex-col items-end gap-1 ml-2">
              <button
                className="btn-accent text-xs md:text-sm"
                onClick={() => runMut.mutate()}
                disabled={runMut.isPending}
              >
                <RefreshCw
                  size={14}
                  className={runMut.isPending ? "animate-spin" : ""}
                />
                <span>{runMut.isPending ? "Refreshing" : "Refresh data"}</span>
              </button>
              {runErr && (
                <p
                  className="text-[11px] text-rose-600 max-w-xs text-right leading-snug"
                  title={runErr}
                >
                  {runErr}
                </p>
              )}
            </div>
          </nav>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-7xl w-full px-4 md:px-6 py-6 md:py-10 space-y-8">
        {children}
      </main>

      <footer className="mt-8 pb-8">
        <div className="mx-auto max-w-7xl px-6">
          <div className="rounded-2xl border border-white/60 bg-white/60 backdrop-blur-md px-5 py-4 flex items-center justify-between gap-4 flex-wrap text-xs text-ink-500 shadow-glass">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-gradient-to-br from-blush-500 to-accent-500" />
              <span className="font-medium text-ink-700">Atelier</span>
              <span className="text-ink-400">·</span>
              <span>Curated competitive intelligence for beauty brands</span>
            </div>
            <div className="text-ink-400">
              Crafted with care · {new Date().getFullYear()}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
