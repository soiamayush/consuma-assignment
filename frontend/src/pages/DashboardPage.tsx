import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, TrendingDown, TrendingUp, Sparkles, Newspaper } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import { StatCard } from "../components/StatCard";
import { SignalCard } from "../components/SignalCard";
import { InsightStrip } from "../components/InsightStrip";
import { AIExplainCard } from "../components/AIExplainCard";

export function DashboardPage() {
  const [windowDays, setWindowDays] = useState(14);

  const summary = useQuery({
    queryKey: ["dashboard", windowDays],
    queryFn: () => api.dashboard(windowDays),
  });
  const topSignals = useQuery({
    queryKey: ["signals", "top", windowDays],
    queryFn: () => api.signals({ sort: "importance", limit: 8, window_days: windowDays }),
  });
  const peers = useQuery({
    queryKey: ["competitors", "peers"],
    queryFn: () => api.competitors(false),
  });
  const anchor = useQuery({
    queryKey: ["competitors", "anchor"],
    queryFn: api.anchorBrand,
    retry: false,
  });
  const insights = useQuery({
    queryKey: ["insights", windowDays],
    queryFn: () => api.insights(windowDays),
  });

  const s = summary.data;

  const aiPayload = useMemo(() => {
    if (!s) return null;
    return {
      window_days: windowDays,
      anchor: anchor.data ? { slug: anchor.data.slug, name: anchor.data.name } : null,
      totals: {
        total_signals: s.total_signals,
        new_launches: s.new_products,
        price_drops: s.price_drops,
        price_increases: s.price_increases,
        announcements: s.blog_posts,
      },
      by_competitor: (s.by_competitor ?? []).slice(0, 12).map((c) => ({
        slug: c.slug,
        name: c.name,
        signals: c.signal_count,
      })),
      top_themes: (s.top_themes ?? []).slice(0, 10),
      top_signals: (topSignals.data ?? []).slice(0, 10).map((sig) => ({
        kind: sig.kind,
        brand: sig.competitor_name,
        title: sig.title,
        importance: Number(sig.importance.toFixed(2)),
        themes: sig.themes,
      })),
    };
  }, [s, windowDays, anchor.data, topSignals.data]);

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">What changed recently</h1>
          <p className="text-ink-500 mt-1 text-sm max-w-2xl">
            Ranked signals from the last {windowDays} days · sorted by importance.
            <span className="block mt-1 text-ink-400">
              <strong className="font-medium text-ink-600">Minimalist</strong> (beminimalist.co) is the anchor
              brand; INKEY List, COSRX, and Dot &amp; Key are peers for price, launches, and ingredient mix.
              See the{" "}
              <Link to="/analytics" className="font-semibold text-ink-800 underline">
                Analytics
              </Link>{" "}
              page for cross-brand charts.
            </span>
          </p>
        </div>
        <div className="flex items-center gap-1 text-sm">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`btn ${
                windowDays === d ? "bg-ink-900 text-white" : "btn-ghost"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <InsightStrip
        insights={insights.data?.insights ?? []}
        loading={insights.isLoading}
        title="What's worth your attention"
        subtitle={`Auto-generated findings from the last ${windowDays} days of catalog + signals.`}
      />

      {aiPayload && (
        <AIExplainCard
          view="dashboard_summary"
          payload={aiPayload}
          title="AI executive read"
          subtitle={`Gemini-written analyst memo over the last ${windowDays} days. Ask follow-ups below.`}
        />
      )}

      {/* stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Total signals" value={s?.total_signals ?? "—"} accent />
        <StatCard
          label="New launches"
          value={s?.new_products ?? "—"}
          sub={
            <span className="inline-flex items-center gap-1">
              <Sparkles size={12} /> product_launch
            </span>
          }
        />
        <StatCard
          label="Price drops"
          value={s?.price_drops ?? "—"}
          sub={
            <span className="inline-flex items-center gap-1 text-emerald-600">
              <TrendingDown size={12} /> price_drop
            </span>
          }
        />
        <StatCard
          label="Price increases"
          value={s?.price_increases ?? "—"}
          sub={
            <span className="inline-flex items-center gap-1 text-amber-600">
              <TrendingUp size={12} /> price_increase
            </span>
          }
        />
        <StatCard
          label="Announcements"
          value={s?.blog_posts ?? "—"}
          sub={
            <span className="inline-flex items-center gap-1 text-sky-600">
              <Newspaper size={12} /> blog_post
            </span>
          }
        />
      </div>

      {/* main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Top signals</h2>
            <Link to="/feed" className="text-sm text-ink-600 hover:text-ink-900 inline-flex items-center gap-1">
              Full feed <ArrowRight size={14} />
            </Link>
          </div>
          {topSignals.isLoading && <div className="text-ink-500 text-sm">Loading signals…</div>}
          {topSignals.data?.length === 0 && (
            <div className="card p-6 text-sm text-ink-600">
              No signals yet. Click <span className="font-semibold">Run ingestion</span> above to populate data.
            </div>
          )}
          <div className="space-y-2">
            {topSignals.data?.map((sig) => (
              <SignalCard key={sig.id} signal={sig} />
            ))}
          </div>
        </div>

        <aside className="space-y-6">
          <div className="card p-4">
            <h3 className="font-semibold mb-3">Your brand</h3>
            {anchor.data ? (
              <Link
                to={`/competitors/${anchor.data.slug}`}
                className="block text-sm hover:bg-ink-100 p-2 -mx-2 rounded-md border border-amber-200 bg-accent-50"
              >
                <div className="font-medium text-ink-900 flex items-center gap-2">
                  {anchor.data.name}
                  <span className="chip-accent text-[10px] uppercase tracking-wide">Anchor</span>
                </div>
                <div className="text-xs text-ink-500 mt-0.5">
                  {anchor.data.product_count} products · {anchor.data.signal_count} signals
                </div>
              </Link>
            ) : (
              <p className="text-xs text-ink-500">No anchor configured.</p>
            )}
            <h3 className="font-semibold mb-3 mt-5">Peer brands</h3>
            <p className="text-xs text-ink-500 mb-2">
              Everyone in <code className="text-[11px]">/api/competitors</code> is a peer (Minimalist is
              separate at <code className="text-[11px]">/api/competitors/anchor</code>).
            </p>
            <ul className="space-y-2">
              {peers.data?.map((c) => (
                <li key={c.id}>
                  <Link
                    to={`/competitors/${c.slug}`}
                    className="flex items-center justify-between gap-2 text-sm hover:bg-ink-100 p-2 -mx-2 rounded-md"
                  >
                    <div>
                      <div className="font-medium text-ink-900">{c.name}</div>
                      <div className="text-xs text-ink-500">
                        {c.product_count} products · {c.signal_count} signals
                      </div>
                    </div>
                    <div className="text-xs font-mono text-ink-400">
                      w {c.brand_weight.toFixed(1)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-4">
            <h3 className="font-semibold mb-3">Top themes</h3>
            {s?.top_themes?.length ? (
              <div className="flex flex-wrap gap-1.5">
                {s.top_themes.map((t) => (
                  <span key={t.theme} className="chip">
                    {t.theme} <span className="text-ink-400 font-mono ml-1">{t.count}</span>
                  </span>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-500">No themes yet.</div>
            )}
          </div>

          <div className="card p-4">
            <h3 className="font-semibold mb-3">Signal volume by brand</h3>
            <ul className="space-y-2">
              {s?.by_competitor?.map((c) => {
                const max = Math.max(1, ...(s.by_competitor.map((x) => x.signal_count) ?? [1]));
                const pct = (c.signal_count / max) * 100;
                return (
                  <li key={c.slug} className="text-sm">
                    <div className="flex justify-between">
                      <Link to={`/competitors/${c.slug}`} className="hover:underline">
                        {c.name}
                      </Link>
                      <span className="tabular-nums text-ink-500">{c.signal_count}</span>
                    </div>
                    <div className="h-1 bg-ink-100 rounded-full mt-1 overflow-hidden">
                      <div className="h-full bg-ink-700" style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
