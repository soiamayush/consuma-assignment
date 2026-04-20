import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  Eye,
  ExternalLink,
  Globe2,
  Headphones,
  MessageSquare,
  Newspaper,
  ThumbsUp,
  Youtube,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type SocialMention } from "../api";
import { Pager } from "../components/Pager";
import { AIExplainCard } from "../components/AIExplainCard";
import { PageHero } from "../components/PageHero";

const PLATFORMS = [
  { id: "", label: "All channels" },
  { id: "youtube", label: "YouTube" },
  { id: "news", label: "Google News" },
  { id: "news_bing", label: "Bing News" },
  { id: "podcast", label: "Podcasts" },
];

const SORT_OPTIONS = [
  { id: "recent", label: "Most recent" },
  { id: "views", label: "Most viewed" },
  { id: "score", label: "Top engagement" },
];

const PLATFORM_LABEL: Record<string, string> = {
  youtube: "YouTube",
  news: "Google News",
  news_bing: "Bing News",
  podcast: "Podcasts",
};

function platformIcon(platform: string) {
  if (platform === "youtube")
    return <Youtube size={14} className="text-rose-600" />;
  if (platform === "news")
    return <Newspaper size={14} className="text-sky-600" />;
  if (platform === "news_bing")
    return <Globe2 size={14} className="text-indigo-600" />;
  if (platform === "podcast")
    return <Headphones size={14} className="text-violet-600" />;
  return null;
}

function compactNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function MentionCard({ m }: { m: SocialMention }) {
  return (
    <a
      href={m.url}
      target="_blank"
      rel="noreferrer"
      className="card p-3 flex gap-3 hover:shadow-lift hover:-translate-y-[1px] transition-all group"
    >
      {m.thumbnail_url ? (
        <img
          src={m.thumbnail_url}
          alt=""
          className="w-32 h-20 object-cover rounded-lg bg-ink-100 shrink-0"
          loading="lazy"
        />
      ) : (
        <div className="w-32 h-20 rounded-lg bg-gradient-to-br from-blush-50 to-cream-50 border border-white/60 shrink-0 grid place-items-center text-ink-400">
          {platformIcon(m.platform)}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[11px] text-ink-500 uppercase tracking-[0.12em]">
          {platformIcon(m.platform)}
          <span className="font-semibold">
            {PLATFORM_LABEL[m.platform] ?? m.platform}
          </span>
          <span className="text-ink-300">·</span>
          <span className="text-ink-700 normal-case tracking-normal font-medium">
            {m.competitor_name}
          </span>
          {m.published_at && (
            <>
              <span className="text-ink-300">·</span>
              <span className="text-ink-500 normal-case tracking-normal">
                {formatDistanceToNow(new Date(m.published_at), {
                  addSuffix: true,
                })}
              </span>
            </>
          )}
        </div>
        <div className="font-medium text-sm mt-1 line-clamp-2 group-hover:text-blush-700 transition inline-flex items-start gap-1">
          {m.title}
          <ExternalLink
            size={12}
            className="opacity-0 group-hover:opacity-60 mt-1 shrink-0"
          />
        </div>
        {m.author && (
          <div className="text-xs text-ink-600 mt-1">
            by <span className="font-medium">{m.author}</span>
            {m.author_handle && m.author_handle !== m.author && (
              <span className="text-ink-400"> · {m.author_handle}</span>
            )}
          </div>
        )}
        <div className="flex items-center gap-3 mt-1.5 text-xs text-ink-500 tabular-nums">
          {m.metric_views != null && (
            <span className="inline-flex items-center gap-1">
              <Eye size={12} /> {compactNumber(m.metric_views)}
            </span>
          )}
          {m.metric_score != null && (
            <span className="inline-flex items-center gap-1">
              <ThumbsUp size={12} /> {compactNumber(m.metric_score)}
            </span>
          )}
          {m.metric_comments != null && (
            <span className="inline-flex items-center gap-1">
              <MessageSquare size={12} /> {compactNumber(m.metric_comments)}
            </span>
          )}
        </div>
      </div>
    </a>
  );
}

export function BuzzPage() {
  const [competitor, setCompetitor] = useState("");
  const [platform, setPlatform] = useState("");
  const [sort, setSort] = useState<"recent" | "views" | "score">("recent");
  const [windowDays, setWindowDays] = useState(90);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [creatorPlatform, setCreatorPlatform] = useState<
    "youtube" | "news" | "news_bing" | "podcast"
  >("youtube");

  useEffect(() => {
    setOffset(0);
  }, [competitor, platform, sort, windowDays, limit]);

  const competitors = useQuery({
    queryKey: ["competitors", "all"],
    queryFn: () => api.competitors(true),
  });

  const summary = useQuery({
    queryKey: ["social-summary", windowDays],
    queryFn: () => api.socialSummary(windowDays),
  });

  const mentions = useQuery({
    queryKey: ["social", competitor, platform, sort, windowDays, limit, offset],
    queryFn: () =>
      api.socialMentionsPaged({
        competitor,
        platform,
        sort,
        window_days: windowDays,
        limit,
        offset,
      }),
    placeholderData: keepPreviousData,
  });

  const creators = useQuery({
    queryKey: ["top-creators", competitor, creatorPlatform, windowDays],
    queryFn: () =>
      api.topCreators({
        competitor,
        platform: creatorPlatform,
        window_days: windowDays,
        limit: 15,
      }),
  });

  const items = mentions.data?.items ?? [];
  const total = mentions.data?.total ?? 0;
  const summaryRows = summary.data?.by_brand ?? [];

  const buzzAiPayload = useMemo(() => {
    if (!summary.data) return null;
    const volumeByBrand = summary.data.by_brand.map((r) => ({
      slug: r.slug,
      name: r.name,
      is_anchor: r.is_anchor,
      total: r.total,
      views: r.views,
      youtube: r.platforms.youtube?.mentions ?? 0,
      news: r.platforms.news?.mentions ?? 0,
      news_bing: r.platforms.news_bing?.mentions ?? 0,
      podcast: r.platforms.podcast?.mentions ?? 0,
    }));
    return {
      window_days: windowDays,
      filters: {
        competitor: competitor || null,
        platform: platform || null,
        sort,
      },
      volume_by_brand: volumeByBrand,
      sample_mentions: items.slice(0, 15).map((m) => ({
        platform: m.platform,
        brand: m.competitor_name,
        title: m.title,
        views: m.metric_views,
      })),
      top_creators: (creators.data ?? []).slice(0, 10).map((c) => ({
        author: c.author,
        platform: c.platform,
        competitor: c.competitor_name,
        mentions: c.mention_count,
        views: c.total_views,
      })),
    };
  }, [
    summary.data,
    windowDays,
    competitor,
    platform,
    sort,
    items,
    creators.data,
  ]);

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow="Earned media"
        theme="rose"
        title={
          <>
            Who's actually <span className="gradient-text">talking</span> about
            each brand
          </>
        }
        subtitle={
          <>
            Listening across YouTube, Google News, Bing News and podcasts — so
            you can see which channels and creators repeat per brand, and where
            to place the next collab.
          </>
        }
        actions={
          <div className="flex items-center gap-1 p-1 rounded-full bg-white/70 border border-white/70 shadow-sm">
            {[30, 90, 180, 365].map((d) => (
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

      <div className="card p-5 overflow-x-auto">
        <h2 className="font-display text-lg font-semibold mb-3 text-ink-900">
          Mention volume — last {windowDays} days
        </h2>
        {summaryRows.length === 0 && (
          <p className="text-sm text-ink-500">
            No mentions in this window yet. Tap{" "}
            <span className="font-semibold text-ink-900">Refresh data</span> at
            the top to pull the latest.
          </p>
        )}
        {summaryRows.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-[11px] text-ink-500 border-b border-ink-200 uppercase tracking-[0.12em]">
              <tr>
                <th className="py-2 pr-3 text-left">Brand</th>
                <th className="py-2 pr-3 text-right">YouTube</th>
                <th className="py-2 pr-3 text-right">Google News</th>
                <th className="py-2 pr-3 text-right">Bing</th>
                <th className="py-2 pr-3 text-right">Podcast</th>
                <th className="py-2 pr-3 text-right">Total</th>
                <th className="py-2 text-right">YouTube views</th>
              </tr>
            </thead>
            <tbody>
              {summaryRows.map((r) => (
                <tr
                  key={r.slug}
                  className="border-b border-ink-100 hover:bg-white/60"
                >
                  <td className="py-2.5 pr-3 font-medium">
                    {r.is_anchor ? (
                      <span className="inline-flex items-center gap-1.5">
                        {r.name}
                        <span className="chip-accent">You</span>
                      </span>
                    ) : (
                      r.name
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {r.platforms.youtube?.mentions ?? 0}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {r.platforms.news?.mentions ?? 0}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {r.platforms.news_bing?.mentions ?? 0}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    {r.platforms.podcast?.mentions ?? 0}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums font-semibold text-ink-900">
                    {r.total}
                  </td>
                  <td className="py-2.5 text-right tabular-nums text-ink-600">
                    {compactNumber(r.platforms.youtube?.views ?? null)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {buzzAiPayload && (
        <AIExplainCard
          view="social_buzz"
          payload={buzzAiPayload}
          title="Buzz read"
          subtitle={`A listening summary for the last ${windowDays} days — volume, channels, and creators worth a second look.`}
        />
      )}

      <div className="card p-5">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h2 className="font-display text-lg font-semibold text-ink-900">
            Top{" "}
            {creatorPlatform === "youtube"
              ? "YouTube channels"
              : creatorPlatform === "podcast"
                ? "podcast shows"
                : creatorPlatform === "news_bing"
                  ? "Bing news outlets"
                  : "Google News outlets"}{" "}
            {competitor ? `for ${competitor}` : "across all brands"}
          </h2>
          <div className="flex items-center gap-1 text-xs flex-wrap">
            {(["youtube", "news", "news_bing", "podcast"] as const).map(
              (p) => (
                <button
                  key={p}
                  onClick={() => setCreatorPlatform(p)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                    creatorPlatform === p
                      ? "bg-ink-900 text-white shadow-sm"
                      : "bg-white/60 text-ink-600 hover:text-ink-900 border border-ink-200"
                  }`}
                >
                  {PLATFORM_LABEL[p]}
                </button>
              ),
            )}
          </div>
        </div>
        {creators.isLoading && (
          <p className="text-xs text-ink-500">Loading…</p>
        )}
        {!creators.isLoading && (creators.data?.length ?? 0) === 0 && (
          <p className="text-xs text-ink-500">
            No data for this channel / brand yet.
          </p>
        )}
        <ul className="divide-y divide-ink-100">
          {creators.data?.map((c, i) => (
            <li
              key={`${c.competitor_slug}-${c.author}-${i}`}
              className="py-2.5 flex items-center gap-3"
            >
              <span className="text-ink-400 text-xs w-6 tabular-nums">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm truncate">
                  {c.author_url ? (
                    <a
                      href={c.author_url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-blush-700 inline-flex items-center gap-1"
                    >
                      {c.author} <ExternalLink size={11} />
                    </a>
                  ) : (
                    c.author
                  )}
                </div>
                <div className="text-xs text-ink-500">
                  {c.competitor_name} ·{" "}
                  {c.author_handle ?? PLATFORM_LABEL[c.platform] ?? c.platform}
                </div>
              </div>
              <div className="text-xs tabular-nums text-ink-700 text-right shrink-0">
                <div>{c.mention_count} mentions</div>
                {(c.total_views ?? 0) > 0 && (
                  <div className="text-ink-500">
                    {compactNumber(c.total_views)} views
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-3 flex flex-wrap gap-2 items-center">
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
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          {PLATFORMS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        <select
          className="text-sm border border-ink-200 rounded-full px-3 py-1.5 bg-white/80"
          value={sort}
          onChange={(e) => setSort(e.target.value as any)}
        >
          {SORT_OPTIONS.map((s) => (
            <option key={s.id} value={s.id}>
              Sort: {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2.5">
        {mentions.isLoading && (
          <p className="text-sm text-ink-500">Loading…</p>
        )}
        {!mentions.isLoading && items.length === 0 && (
          <div className="card p-6 text-sm text-ink-600">
            No mentions match these filters. Try widening the window or picking
            a different channel.
          </div>
        )}
        {items.map((m) => (
          <MentionCard key={m.id} m={m} />
        ))}
      </div>

      <Pager
        total={total}
        offset={offset}
        limit={limit}
        onOffset={setOffset}
        onLimit={setLimit}
        loading={mentions.isFetching}
        label="mentions"
      />
    </div>
  );
}
