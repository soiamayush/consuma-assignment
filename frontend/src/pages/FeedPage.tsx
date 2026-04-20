import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Pager } from "../components/Pager";
import { SignalCard } from "../components/SignalCard";
import { PageHero } from "../components/PageHero";

const KINDS = [
  { k: "", label: "All" },
  { k: "PRODUCT_LAUNCH", label: "Launches" },
  { k: "PRICE_DROP", label: "Price drops" },
  { k: "PRICE_INCREASE", label: "Price up" },
  { k: "OUT_OF_STOCK", label: "Sold out" },
  { k: "BACK_IN_STOCK", label: "Back in stock" },
  { k: "BLOG_POST", label: "Announcements" },
  { k: "CATALOG_SURGE", label: "Catalog surge" },
];

export function FeedPage() {
  const [kind, setKind] = useState("");
  const [competitor, setCompetitor] = useState("");
  const [sort, setSort] = useState<"importance" | "recent">("importance");
  const [windowDays, setWindowDays] = useState(30);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    setOffset(0);
  }, [kind, competitor, sort, windowDays, limit]);

  const competitors = useQuery({
    queryKey: ["competitors", "all"],
    queryFn: () => api.competitors(true),
  });
  const signals = useQuery({
    queryKey: [
      "signals",
      kind,
      competitor,
      sort,
      windowDays,
      limit,
      offset,
    ],
    queryFn: () =>
      api.signalsPaged({
        kind,
        competitor,
        sort,
        window_days: windowDays,
        limit,
        offset,
      }),
    placeholderData: keepPreviousData,
  });
  const items = signals.data?.items ?? [];
  const total = signals.data?.total ?? 0;

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow="Signal feed"
        theme="ink"
        title={
          <>
            Every ripple on the <span className="gradient-text">shelf</span>
          </>
        }
        subtitle={
          <>
            Launches, price moves, stock flips and editorial — filtered by kind,
            brand, or rank. Sorted by importance so the loud stuff comes first.
          </>
        }
      />

      <div className="card p-3 flex flex-wrap gap-2 items-center">
        <div className="flex flex-wrap gap-1">
          {KINDS.map((x) => (
            <button
              key={x.k}
              onClick={() => setKind(x.k)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                kind === x.k
                  ? "bg-ink-900 text-white shadow-sm"
                  : "bg-white/60 text-ink-600 hover:bg-white hover:text-ink-900 border border-ink-200"
              }`}
            >
              {x.label}
            </button>
          ))}
        </div>
        <div className="grow" />
        <select
          className="text-sm border border-ink-200 rounded-full px-3 py-1.5 bg-white/80"
          value={competitor}
          onChange={(e) => setCompetitor(e.target.value)}
        >
          <option value="">All brands</option>
          {competitors.data?.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          className="text-sm border border-ink-200 rounded-full px-3 py-1.5 bg-white/80"
          value={sort}
          onChange={(e) => setSort(e.target.value as any)}
        >
          <option value="importance">Sort: importance</option>
          <option value="recent">Sort: most recent</option>
        </select>
        <select
          className="text-sm border border-ink-200 rounded-full px-3 py-1.5 bg-white/80"
          value={windowDays}
          onChange={(e) => setWindowDays(Number(e.target.value))}
        >
          {[7, 14, 30, 90, 365].map((d) => (
            <option key={d} value={d}>
              Last {d} days
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3">
        {signals.isLoading && (
          <div className="text-sm text-ink-500">Loading the feed…</div>
        )}
        {!signals.isLoading && items.length === 0 && (
          <div className="card p-6 text-sm text-ink-600">
            No signals match these filters. Try a wider window or different
            brand.
          </div>
        )}
        {items.map((s) => (
          <SignalCard key={s.id} signal={s} />
        ))}
      </div>

      <Pager
        total={total}
        offset={offset}
        limit={limit}
        onOffset={setOffset}
        onLimit={setLimit}
        loading={signals.isFetching}
        label="signals"
      />
    </div>
  );
}
