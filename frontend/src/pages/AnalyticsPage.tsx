import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Pager } from "../components/Pager";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { formatPrice } from "../formatPrice";
import { PriceBandLadder } from "../components/PriceBandLadder";
import { InsightStrip } from "../components/InsightStrip";
import { AIExplainCard } from "../components/AIExplainCard";
import { PageHero } from "../components/PageHero";

const ANCHOR_COLOR = "#bf3f5c";
const PEER_COLOR = "#4b5563";

export function AnalyticsPage() {
  const [windowDays, setWindowDays] = useState(14);
  const [launchLimit, setLaunchLimit] = useState(25);
  const [launchOffset, setLaunchOffset] = useState(0);
  const q = useQuery({
    queryKey: ["analytics", windowDays],
    queryFn: () => api.analyticsOverview(windowDays),
  });
  const insightsQ = useQuery({
    queryKey: ["insights", windowDays],
    queryFn: () => api.insights(windowDays),
  });
  const data = q.data;

  useEffect(() => {
    setLaunchOffset(0);
  }, [windowDays, launchLimit]);

  const launches = data?.recent_launches_30d ?? [];
  const launchPage = useMemo(
    () => launches.slice(launchOffset, launchOffset + launchLimit),
    [launches, launchOffset, launchLimit]
  );

  const ladderRows =
    data?.price_landscape.map((r) => ({
      slug: r.slug,
      name: r.name,
      is_anchor: r.is_anchor,
      min_price: r.p25_listed_price ?? null,
      max_price: r.p75_listed_price ?? null,
      p25: r.p25_listed_price ?? null,
      median: r.median_listed_price ?? null,
      p75: r.p75_listed_price ?? null,
      currency: r.currency,
    })) ?? [];
  const anchorMedianForLadder =
    data?.price_landscape.find((r) => r.is_anchor)?.median_listed_price ?? null;
  const ladderFallbackCurrency =
    data?.price_landscape.find((r) => r.currency && r.currency !== "mixed")?.currency ?? "INR";

  const signalChartData =
    data?.signals_by_brand.map((r) => ({
      label: r.is_anchor ? `${r.name} ★` : r.name,
      signals: r.signals,
      is_anchor: r.is_anchor,
    })) ?? [];

  const activesChartData =
    data?.top_actives_in_catalog.slice(0, 10).map((r) => ({
      active: r.active.replace(/_/g, " "),
      hits: r.product_hits,
    })) ?? [];

  const analyticsAiPayload = useMemo(() => {
    if (!data) return null;
    return {
      window_days: windowDays,
      anchor: { slug: data.anchor_slug, name: data.anchor_name },
      price_landscape: data.price_landscape.map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        product_count: r.product_count,
        median: r.median_listed_price,
        p25: r.p25_listed_price ?? null,
        p75: r.p75_listed_price ?? null,
      })),
      signals_by_brand: data.signals_by_brand.map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        signals: r.signals,
      })),
      discount_landscape: (data.discount_landscape ?? []).map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        discount_share_pct: r.discount_share_pct,
        median_discount_pct: r.median_discount_pct,
      })),
      stock_pressure: (data.stock_pressure ?? []).map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        net_pressure: r.net_pressure,
        out_of_stock: r.out_of_stock,
        back_in_stock: r.back_in_stock,
      })),
      launches_per_week: (data.launches_per_week ?? []).map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        total: r.total,
      })),
      top_price_moves: (data.top_price_moves ?? []).slice(0, 8).map((m) => ({
        brand: m.brand_name,
        title: m.title,
        kind: m.kind,
        pct_change: m.pct_change,
      })),
      anchor_whitespace: (data.anchor_whitespace ?? []).slice(0, 6),
      top_actives: (data.top_actives_in_catalog ?? []).slice(0, 8).map((r) => ({
        active: r.active,
        hits: r.product_hits,
      })),
    };
  }, [data, windowDays]);

  return (
    <div className="space-y-8">
      <PageHero
        eyebrow="Differentiation"
        theme="gold"
        title={
          <>
            Where you <span className="gradient-text">stand</span> on the
            shelf
          </>
        }
        subtitle={
          <>
            A cross-brand read on price bands, discount intensity, launch
            cadence, stock pressure and hero ingredients. Spot where peers are
            crowding and where you have room to own a theme.
          </>
        }
        actions={
          <div className="flex items-center gap-1 p-1 rounded-full bg-white/70 border border-white/70 shadow-sm">
            {[7, 14, 30].map((d) => (
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
        insights={insightsQ.data?.insights ?? []}
        loading={insightsQ.isLoading}
        title="Top findings"
        subtitle={`Plain-English read of the last ${windowDays} days — click any card to drill in.`}
      />

      {analyticsAiPayload && (
        <AIExplainCard
          view="analytics_overview"
          payload={analyticsAiPayload}
          title="AI analytics memo"
          subtitle={`Cross-chart read for the last ${windowDays} days (Gemini, grounded in the numbers on this page).`}
        />
      )}

      {q.isLoading && (
        <p className="text-sm text-ink-500">Gathering the numbers…</p>
      )}
      {q.isError && (
        <p className="text-sm text-rose-600">
          We couldn't load analytics right now. Please try again in a moment.
        </p>
      )}

      {data && (
        <>
          <div className="card p-5">
            <h2 className="font-display text-xl font-semibold mb-2 text-ink-900">
              Executive read
            </h2>
            <p className="text-sm text-ink-700 leading-relaxed">
              {data.narrative}
            </p>
            {data.anchor_name && (
              <p className="text-xs text-ink-500 mt-2">
                Your brand: <strong>{data.anchor_name}</strong>
              </p>
            )}
          </div>

          {data.data_quality_notes && data.data_quality_notes.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-2 text-ink-900">
                Data quality notes
              </h3>
              <ul className="text-sm text-ink-600 list-disc pl-5 space-y-1">
                {data.data_quality_notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Price band by brand
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Box spans p25 → p75; dot marks the median. The dashed rose line
                is your median — anyone to the left is cheaper than you, right
                is pricier. Want to slice by category? Open{" "}
                <Link
                  to="/compare"
                  className="underline font-medium text-ink-700 hover:text-blush-700"
                >
                  Compare
                </Link>
                .
              </p>
              <PriceBandLadder
                rows={ladderRows}
                anchorReference={anchorMedianForLadder}
                fallbackCurrency={ladderFallbackCurrency}
              />
            </div>

            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Signals in window — velocity
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Price moves, launches, stock flips, and editorial announcements.
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={signalChartData} margin={{ bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" angle={-25} textAnchor="end" height={70} tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="signals" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                      {signalChartData.map((_, i) => (
                        <Cell key={i} fill={signalChartData[i]?.is_anchor ? ANCHOR_COLOR : PEER_COLOR} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {data.discount_landscape && data.discount_landscape.length > 0 && (
            <div className="grid md:grid-cols-2 gap-6">
              <div className="card p-5">
                <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                  Discount intensity by brand
                </h3>
                <p className="text-xs text-ink-500 mb-3">
                  Share of catalog visibly on sale (MSRP higher than live price).
                </p>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.discount_landscape.map((r) => ({
                        label: r.is_anchor ? `${r.name} ★` : r.name,
                        share: r.discount_share_pct,
                        is_anchor: r.is_anchor,
                      }))}
                      margin={{ bottom: 40 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="label"
                        angle={-25}
                        textAnchor="end"
                        height={70}
                        tick={{ fontSize: 10 }}
                      />
                      <YAxis tick={{ fontSize: 11 }} unit="%" />
                      <Tooltip formatter={(v: number) => [`${v}%`, "on sale"]} />
                      <Bar dataKey="share" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                        {data.discount_landscape.map((r, i) => (
                          <Cell key={i} fill={r.is_anchor ? ANCHOR_COLOR : PEER_COLOR} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 overflow-x-auto text-xs">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-ink-500 border-b border-ink-200">
                        <th className="py-1 pr-2">Brand</th>
                        <th className="py-1 pr-2">SKUs on sale</th>
                        <th className="py-1 pr-2">Share</th>
                        <th className="py-1 pr-2">Median % off</th>
                        <th className="py-1">Max % off</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.discount_landscape.map((r) => (
                        <tr key={r.slug} className="border-b border-ink-100">
                          <td className="py-1 pr-2 font-medium">
                            {r.is_anchor ? `${r.name} ★` : r.name}
                          </td>
                          <td className="py-1 pr-2 tabular-nums">
                            {r.discounted_skus} / {r.priceable_skus}
                          </td>
                          <td className="py-1 pr-2 tabular-nums">{r.discount_share_pct}%</td>
                          <td className="py-1 pr-2 tabular-nums">
                            {r.median_discount_pct ? `${r.median_discount_pct}%` : "—"}
                          </td>
                          <td className="py-1 tabular-nums">
                            {r.max_discount_pct ? `${r.max_discount_pct}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="card p-5">
                <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                  Stock pressure — last {data.window_days} days
                </h3>
                <p className="text-xs text-ink-500 mb-3">
                  Out-of-stock vs. back-in-stock flips. Net positive means a
                  brand is selling through faster than it restocks.
                </p>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={(data.stock_pressure ?? []).map((r) => ({
                        label: r.is_anchor ? `${r.name} ★` : r.name,
                        out: r.out_of_stock,
                        back: r.back_in_stock,
                        is_anchor: r.is_anchor,
                      }))}
                      margin={{ bottom: 40 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="label"
                        angle={-25}
                        textAnchor="end"
                        height={70}
                        tick={{ fontSize: 10 }}
                      />
                      <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="out" name="Sold out" fill="#dc2626" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                      <Bar dataKey="back" name="Back in stock" fill="#059669" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {data.launches_per_week && data.launches_per_week.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Launch cadence — new SKUs per week, last 12 weeks
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Each line is a brand. A rising slope is portfolio expansion; a
                flat line near zero means a quiet roadmap.
              </p>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={(data.launches_per_week[0]?.weeks ?? []).map((wk, idx) => {
                      const row: Record<string, number | string> = { week: wk.replace(/^\d{4}-/, "") };
                      for (const series of data.launches_per_week ?? []) {
                        row[series.slug] = series.counts[idx] ?? 0;
                      }
                      return row;
                    })}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip />
                    {data.launches_per_week.map((s) => (
                      <Line
                        key={s.slug}
                        type="monotone"
                        dataKey={s.slug}
                        name={s.is_anchor ? `${s.name} ★` : s.name}
                        stroke={s.is_anchor ? ANCHOR_COLOR : "#6b7280"}
                        strokeWidth={s.is_anchor ? 2.5 : 1.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-600">
                {data.launches_per_week.map((s) => (
                  <span key={s.slug} className="chip">
                    {s.is_anchor ? `${s.name} ★` : s.name} · {s.total}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.catalog_size_weekly && data.catalog_size_weekly.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Catalog size by week — last 12 weeks
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Active SKUs counted at week-end. Steepest slope wins the
                portfolio-expansion race.
              </p>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={(data.catalog_size_weekly[0]?.weeks ?? []).map((wk, idx) => {
                      const row: Record<string, number | string> = { week: wk.replace(/^\d{4}-/, "") };
                      for (const series of data.catalog_size_weekly ?? []) {
                        row[series.slug] = series.counts[idx] ?? 0;
                      }
                      return row;
                    })}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                    <Tooltip />
                    {data.catalog_size_weekly.map((s) => (
                      <Line
                        key={s.slug}
                        type="monotone"
                        dataKey={s.slug}
                        name={s.is_anchor ? `${s.name} ★` : s.name}
                        stroke={s.is_anchor ? ANCHOR_COLOR : "#6b7280"}
                        strokeWidth={s.is_anchor ? 2.5 : 1.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-600">
                {data.catalog_size_weekly.map((s) => (
                  <span key={s.slug} className="chip">
                    {s.is_anchor ? `${s.name} ★` : s.name} · now {s.current}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.anchor_whitespace && data.anchor_whitespace.length > 0 && (
            <div className="rounded-2xl border border-blush-200 bg-gradient-to-br from-blush-50/70 to-cream-50/70 backdrop-blur-md p-5 shadow-glass">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                White-space opportunities — ingredients 3+ peers ship that{" "}
                {data.anchor_name ?? "you"} don't
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Concrete portfolio gaps worth considering for the next launch
                slate.
              </p>
              <ul className="text-sm space-y-1">
                {data.anchor_whitespace.map((r) => (
                  <li key={r.active} className="flex justify-between border-b border-amber-200/60 py-1">
                    <span className="font-medium">{r.active.replace(/_/g, " ")}</span>
                    <span className="text-ink-600 text-xs tabular-nums">
                      {r.peer_count} peers · {r.peer_sku_hits} peer SKUs ·{" "}
                      <span className="text-ink-500">{r.peer_slugs.join(", ")}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.top_price_moves && data.top_price_moves.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Top price moves — last {data.window_days} days
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                Biggest absolute percent swings. Drops in green, increases in
                rose. Click a row to open the SKU.
              </p>
              <div className="overflow-x-auto text-sm">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="text-left text-xs text-ink-500 border-b border-ink-200">
                      <th className="py-2 pr-3">Brand</th>
                      <th className="py-2 pr-3">Product</th>
                      <th className="py-2 pr-3">Old → New</th>
                      <th className="py-2">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_price_moves.map((m) => (
                      <tr key={m.signal_id} className="border-b border-ink-100 hover:bg-white/60">
                        <td className="py-2 pr-3 text-ink-600">{m.brand_name ?? m.brand_slug}</td>
                        <td className="py-2 pr-3">
                          {m.product_id != null ? (
                            <Link to={`/products/${m.product_id}`} className="hover:underline">
                              {m.title}
                            </Link>
                          ) : (
                            m.title
                          )}
                        </td>
                        <td className="py-2 pr-3 tabular-nums text-xs">
                          {formatPrice(m.old_price, m.currency)} → {formatPrice(m.new_price, m.currency)}
                        </td>
                        <td
                          className={`py-2 tabular-nums font-semibold ${
                            m.kind === "PRICE_DROP" ? "text-emerald-700" : "text-rose-700"
                          }`}
                        >
                          {m.pct_change > 0 ? "+" : ""}
                          {m.pct_change}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold mb-2 text-ink-900">
              Price distribution — latest snapshot per SKU
            </h3>
            <p className="text-xs text-ink-500 mb-3">
              p25 / p75 use positive prices only (free samples excluded).
            </p>
            <div className="overflow-x-auto text-sm">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-left text-xs text-ink-500 border-b border-ink-200">
                    <th className="py-2 pr-3">Brand</th>
                    <th className="py-2 pr-3">Currency</th>
                    <th className="py-2 pr-3">p25</th>
                    <th className="py-2 pr-3">Median</th>
                    <th className="py-2">p75</th>
                  </tr>
                </thead>
                <tbody>
                  {data.price_landscape.map((r) => (
                    <tr key={r.slug} className="border-b border-ink-100">
                      <td className="py-2 pr-3 font-medium">
                        {r.is_anchor ? `${r.name} ★` : r.name}
                      </td>
                      <td className="py-2 pr-3 text-ink-600">{r.currency ?? "—"}</td>
                      <td className="py-2 pr-3 tabular-nums">
                        {r.p25_listed_price != null ? r.p25_listed_price.toFixed(2) : "—"}
                      </td>
                      <td className="py-2 pr-3 tabular-nums">
                        {r.median_listed_price != null ? r.median_listed_price.toFixed(2) : "—"}
                      </td>
                      <td className="py-2 tabular-nums">
                        {r.p75_listed_price != null ? r.p75_listed_price.toFixed(2) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {data.active_cross_brand && data.active_cross_brand.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
                Cross-brand ingredient overlap
              </h3>
              <p className="text-xs text-ink-500 mb-3">
                How many brands mention the same hero ingredient in product
                titles or tags — a quick read on crowded vs. white-space
                themes.
              </p>
              <div className="overflow-x-auto text-sm">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="text-left text-xs text-ink-500 border-b border-ink-200">
                      <th className="py-2 pr-3">Active</th>
                      <th className="py-2 pr-3">Brands</th>
                      <th className="py-2 pr-3">SKU hits</th>
                      <th className="py-2">Brand slugs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.active_cross_brand.slice(0, 15).map((row) => (
                      <tr key={row.active} className="border-b border-ink-100">
                        <td className="py-2 pr-3 font-medium">{row.active.replace(/_/g, " ")}</td>
                        <td className="py-2 pr-3 tabular-nums">{row.brands_with_hits}</td>
                        <td className="py-2 pr-3 tabular-nums">{row.product_hits}</td>
                        <td className="py-2 text-ink-600">{row.brand_slugs.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold mb-1 text-ink-900">
              Hero ingredients in catalog copy
            </h3>
            <p className="text-xs text-ink-500 mb-3">
              A scan of product titles and tags — the shape of your portfolio's
              ingredient story vs. peers.
            </p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={activesChartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="active" type="category" width={110} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="hits" fill="#0b0b0c" radius={[0, 4, 4, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold mb-2 text-ink-900">
              Ingredients by brand
            </h3>
            <div className="overflow-x-auto text-sm">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-left text-xs text-ink-500 border-b border-ink-200">
                    <th className="py-2 pr-4">Brand</th>
                    <th className="py-2">Top actives (count)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.actives_by_brand).map(([slug, counts]) => {
                    const top = Object.entries(counts)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 8)
                      .map(([k, v]) => `${k.replace(/_/g, " ")} (${v})`)
                      .join(" · ");
                    return (
                      <tr key={slug} className="border-b border-ink-100">
                        <td className="py-2 pr-4 font-medium">
                          <Link to={`/competitors/${slug}`} className="hover:underline">
                            {slug}
                          </Link>
                        </td>
                        <td className="py-2 text-ink-600">{top || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="font-display text-base font-semibold mb-2 text-ink-900">
              Recent catalog launches — last 30 days
            </h3>
            <ul className="text-sm space-y-1.5">
              {launches.length === 0 && (
                <li className="text-ink-500">
                  No new SKUs in this window. Tap{" "}
                  <span className="font-semibold text-ink-900">
                    Refresh data
                  </span>{" "}
                  at the top to pull the latest.
                </li>
              )}
              {launchPage.map((r, i) => (
                <li
                  key={`${r.brand_slug}-${launchOffset + i}`}
                  className="flex gap-2"
                >
                  <span className="text-ink-500 font-medium shrink-0">
                    {r.brand_name}
                  </span>
                  <span className="text-ink-300">·</span>
                  <span className="text-ink-800">{r.title}</span>
                </li>
              ))}
            </ul>
            <Pager
              total={launches.length}
              offset={launchOffset}
              limit={launchLimit}
              onOffset={setLaunchOffset}
              onLimit={setLaunchLimit}
              pageSizes={[25, 50, 100]}
              label="launches"
            />
          </div>
        </>
      )}
    </div>
  );
}
