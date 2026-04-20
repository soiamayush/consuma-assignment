import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  TrendingDown,
  TrendingUp,
  Sparkles,
  Newspaper,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import { StatCard } from "../components/StatCard";
import { SignalCard } from "../components/SignalCard";
import { InsightStrip } from "../components/InsightStrip";
import { AIExplainCard } from "../components/AIExplainCard";
import { PageHero } from "../components/PageHero";

const WINDOWS = [7, 14, 30, 90];

export function DashboardPage() {
  const [windowDays, setWindowDays] = useState(14);

  const summary = useQuery({
    queryKey: ["dashboard", windowDays],
    queryFn: () => api.dashboard(windowDays),
  });
  const topSignals = useQuery({
    queryKey: ["signals", "top", windowDays],
    queryFn: () =>
      api.signals({ sort: "importance", limit: 8, window_days: windowDays }),
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
      anchor: anchor.data
        ? { slug: anchor.data.slug, name: anchor.data.name }
        : null,
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

  const anchorName = anchor.data?.name ?? "your brand";

  return (
    <div className="space-y-8">
      <PageHero
        eyebrow="Daily briefing"
        theme="rose"
        title={
          <>
            The state of <span className="gradient-text">{anchorName}</span>
            <span className="text-ink-500 font-light"> & the shelf</span>
          </>
        }
        subtitle={
          <>
            A curated look at what moved in the last {windowDays} days — new
            launches, pricing swings, editorial chatter, and white-space you can
            own. Sorted by importance, never by noise.
          </>
        }
        actions={
          <div className="flex items-center gap-1 p-1 rounded-full bg-white/70 border border-white/70 shadow-sm">
            {WINDOWS.map((d) => (
              <button
                key={d}
                onClick={() => setWindowDays(d)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                  windowDays === d
                    ? "bg-ink-900 text-white shadow-sm"
                    : "text-ink-600 hover:text-ink-900"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        }
      />

      <InsightStrip
        insights={insights.data?.insights ?? []}
        loading={insights.isLoading}
        title="What's worth your attention"
        subtitle={`Auto-generated findings across catalog, pricing, and buzz over the last ${windowDays} days.`}
      />

      {aiPayload && (
        <AIExplainCard
          view="dashboard_summary"
          payload={aiPayload}
          title="Executive read"
          subtitle={`An analyst memo on the last ${windowDays} days. Ask a follow-up below.`}
        />
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard
          label="Total signals"
          value={s?.total_signals ?? "—"}
          accent
        />
        <StatCard
          label="New launches"
          value={s?.new_products ?? "—"}
          tone="sage"
          sub={
            <span className="inline-flex items-center gap-1">
              <Sparkles size={12} /> fresh drops
            </span>
          }
        />
        <StatCard
          label="Price drops"
          value={s?.price_drops ?? "—"}
          tone="sage"
          sub={
            <span className="inline-flex items-center gap-1 text-emerald-700">
              <TrendingDown size={12} /> cheaper
            </span>
          }
        />
        <StatCard
          label="Price increases"
          value={s?.price_increases ?? "—"}
          tone="gold"
          sub={
            <span className="inline-flex items-center gap-1 text-accent-600">
              <TrendingUp size={12} /> pricier
            </span>
          }
        />
        <StatCard
          label="Announcements"
          value={s?.blog_posts ?? "—"}
          tone="plum"
          sub={
            <span className="inline-flex items-center gap-1 text-sky-700">
              <Newspaper size={12} /> editorial
            </span>
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-xl md:text-2xl font-semibold text-ink-900">
              Top signals
            </h2>
            <Link
              to="/feed"
              className="text-sm text-ink-600 hover:text-blush-700 inline-flex items-center gap-1 font-medium"
            >
              Full feed <ArrowRight size={14} />
            </Link>
          </div>
          {topSignals.isLoading && (
            <div className="text-ink-500 text-sm">Loading signals…</div>
          )}
          {topSignals.data?.length === 0 && (
            <div className="card p-6 text-sm text-ink-600">
              Nothing noteworthy yet. Tap{" "}
              <span className="font-semibold text-ink-900">Refresh data</span>{" "}
              at the top to fetch the latest.
            </div>
          )}
          <div className="space-y-3">
            {topSignals.data?.map((sig) => (
              <SignalCard key={sig.id} signal={sig} />
            ))}
          </div>
        </div>

        <aside className="space-y-5">
          <div className="card p-5">
            <div className="text-[11px] uppercase tracking-[0.16em] text-ink-500 font-semibold">
              Your brand
            </div>
            {anchor.data ? (
              <Link
                to={`/competitors/${anchor.data.slug}`}
                className="mt-3 block rounded-xl p-4 border border-blush-200 bg-gradient-to-br from-blush-50 to-accent-50 hover:shadow-lift transition"
              >
                <div className="font-display text-xl font-semibold text-ink-900 flex items-center gap-2 flex-wrap">
                  {anchor.data.name}
                  <span className="chip-accent">Anchor</span>
                </div>
                <div className="text-xs text-ink-600 mt-1.5 tabular-nums">
                  <span className="font-semibold text-ink-800">
                    {anchor.data.product_count}
                  </span>{" "}
                  products ·{" "}
                  <span className="font-semibold text-ink-800">
                    {anchor.data.signal_count}
                  </span>{" "}
                  signals
                </div>
              </Link>
            ) : (
              <p className="text-xs text-ink-500 mt-3">
                No anchor brand configured yet.
              </p>
            )}

            <div className="mt-6">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ink-500 font-semibold">
                Peer set
              </div>
              <p className="text-xs text-ink-500 mt-1 mb-3">
                Brands you're tracking on the same shelf.
              </p>
              <ul className="space-y-1.5">
                {peers.data?.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/competitors/${c.slug}`}
                      className="flex items-center justify-between gap-2 text-sm hover:bg-white p-2 -mx-2 rounded-lg transition"
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-ink-900 truncate">
                          {c.name}
                        </div>
                        <div className="text-xs text-ink-500 tabular-nums">
                          {c.product_count} products · {c.signal_count} signals
                        </div>
                      </div>
                      <div className="text-[11px] font-mono text-ink-400 shrink-0">
                        w {c.brand_weight.toFixed(1)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold text-ink-900 mb-3">
              Top themes
            </h3>
            {s?.top_themes?.length ? (
              <div className="flex flex-wrap gap-1.5">
                {s.top_themes.map((t) => (
                  <span key={t.theme} className="chip">
                    {t.theme.replace(/_/g, " ")}{" "}
                    <span className="text-ink-400 font-mono ml-1">
                      {t.count}
                    </span>
                  </span>
                ))}
              </div>
            ) : (
              <div className="text-sm text-ink-500">
                Themes will appear here once signals roll in.
              </div>
            )}
          </div>

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold text-ink-900 mb-3">
              Signal volume by brand
            </h3>
            <ul className="space-y-2.5">
              {s?.by_competitor?.map((c) => {
                const max = Math.max(
                  1,
                  ...(s.by_competitor.map((x) => x.signal_count) ?? [1]),
                );
                const pct = (c.signal_count / max) * 100;
                return (
                  <li key={c.slug} className="text-sm">
                    <div className="flex justify-between">
                      <Link
                        to={`/competitors/${c.slug}`}
                        className="hover:text-blush-700 font-medium"
                      >
                        {c.name}
                      </Link>
                      <span className="tabular-nums text-ink-500">
                        {c.signal_count}
                      </span>
                    </div>
                    <div className="h-1.5 bg-ink-100 rounded-full mt-1.5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-plum-500 to-blush-500"
                        style={{ width: `${pct}%` }}
                      />
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
