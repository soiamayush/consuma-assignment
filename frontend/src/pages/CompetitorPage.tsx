import { useParams, Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Pager } from "../components/Pager";
import { SignalCard } from "../components/SignalCard";
import { AIExplainCard } from "../components/AIExplainCard";
import { PageHero } from "../components/PageHero";
import { formatPrice } from "../formatPrice";

export function CompetitorPage() {
  const { slug = "" } = useParams();
  const [productLimit, setProductLimit] = useState(24);
  const [productOffset, setProductOffset] = useState(0);
  const [signalLimit, setSignalLimit] = useState(20);
  const [signalOffset, setSignalOffset] = useState(0);

  // New brand → restart paginators.
  useEffect(() => {
    setProductOffset(0);
    setSignalOffset(0);
  }, [slug]);

  const competitor = useQuery({
    queryKey: ["competitor", slug],
    queryFn: () => api.competitor(slug),
  });
  const products = useQuery({
    queryKey: ["products", slug, productLimit, productOffset],
    queryFn: () =>
      api.productsPaged({ competitor: slug, limit: productLimit, offset: productOffset }),
    placeholderData: keepPreviousData,
  });
  const signals = useQuery({
    queryKey: ["signals", slug, signalLimit, signalOffset],
    queryFn: () =>
      api.signalsPaged({
        competitor: slug,
        limit: signalLimit,
        offset: signalOffset,
        window_days: 90,
      }),
    placeholderData: keepPreviousData,
  });
  const blog = useQuery({
    queryKey: ["blog", slug],
    queryFn: () => api.blogPosts(slug),
  });
  const anchor = useQuery({
    queryKey: ["competitors", "anchor"],
    queryFn: api.anchorBrand,
    retry: false,
  });

  const productItems = products.data?.items ?? [];
  const productTotal = products.data?.total ?? 0;
  const signalItems = signals.data?.items ?? [];
  const signalTotal = signals.data?.total ?? 0;

  const c = competitor.data;

  const aiPayload = useMemo(() => {
    if (!c) return null;
    const sampleSkus = productItems.slice(0, 12).map((p) => ({
      title: p.title,
      product_type: p.product_type,
      price_min: p.latest_price_min,
      price_max: p.latest_price_max,
      currency: p.currency,
    }));
    const recentSignals = signalItems.slice(0, 12).map((s) => ({
      kind: s.kind,
      title: s.title,
      importance: Number(s.importance.toFixed(2)),
      themes: s.themes,
    }));
    return {
      brand: {
        slug: c.slug,
        name: c.name,
        is_anchor: c.is_anchor,
        product_count: c.product_count,
        signal_count: c.signal_count,
        blog_count: c.blog_count,
        brand_weight: c.brand_weight,
      },
      anchor: anchor.data
        ? {
            slug: anchor.data.slug,
            name: anchor.data.name,
            product_count: anchor.data.product_count,
            signal_count: anchor.data.signal_count,
          }
        : null,
      recent_signals: recentSignals,
      sample_skus: sampleSkus,
      recent_posts: (blog.data ?? []).slice(0, 5).map((b) => ({ title: b.title })),
    };
  }, [c, productItems, signalItems, anchor.data, blog.data]);

  return (
    <div className="space-y-8">
      <PageHero
        eyebrow={c?.is_anchor ? "Your brand" : "Brand profile"}
        theme={c?.is_anchor ? "rose" : "ink"}
        title={
          c?.name ? (
            <span className="gradient-text">{c.name}</span>
          ) : (
            "…"
          )
        }
        subtitle={c?.description ?? undefined}
        badge={
          c ? (
            <div className="flex flex-wrap items-center gap-3 text-xs text-ink-600">
              <a
                href={c.website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-ink-800 hover:text-blush-700"
              >
                Visit site <ExternalLink size={12} />
              </a>
              <span className="text-ink-300">·</span>
              <span>
                Brand weight{" "}
                <span className="font-semibold text-ink-800">
                  {c.brand_weight.toFixed(2)}
                </span>
              </span>
              {c.last_ingested_at && (
                <>
                  <span className="text-ink-300">·</span>
                  <span>
                    Last refreshed{" "}
                    {formatDistanceToNow(new Date(c.last_ingested_at), {
                      addSuffix: true,
                    })}
                  </span>
                </>
              )}
            </div>
          ) : null
        }
        actions={
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl bg-white/80 backdrop-blur border border-white/60 px-4 py-2.5 shadow-sm">
              <div className="text-[10px] uppercase tracking-[0.14em] text-ink-500 font-semibold">
                Products
              </div>
              <div className="font-display font-semibold text-lg tabular-nums text-ink-900">
                {c?.product_count ?? "—"}
              </div>
            </div>
            <div className="rounded-xl bg-white/80 backdrop-blur border border-white/60 px-4 py-2.5 shadow-sm">
              <div className="text-[10px] uppercase tracking-[0.14em] text-ink-500 font-semibold">
                Signals
              </div>
              <div className="font-display font-semibold text-lg tabular-nums text-ink-900">
                {c?.signal_count ?? "—"}
              </div>
            </div>
            <div className="rounded-xl bg-white/80 backdrop-blur border border-white/60 px-4 py-2.5 shadow-sm">
              <div className="text-[10px] uppercase tracking-[0.14em] text-ink-500 font-semibold">
                Posts
              </div>
              <div className="font-display font-semibold text-lg tabular-nums text-ink-900">
                {c?.blog_count ?? "—"}
              </div>
            </div>
          </div>
        }
      />

      {aiPayload && (
        <AIExplainCard
          view="brand_brief"
          payload={aiPayload}
          title={`Brief · ${c?.name ?? "this brand"}`}
          subtitle={
            c?.is_anchor
              ? "A candid read on where your own portfolio sits right now."
              : "Strengths, weaknesses, recent moves — and what to watch versus your brand."
          }
        />
      )}

      <section>
        <h2 className="font-display text-xl font-semibold mb-3 text-ink-900">
          Recent signals
        </h2>
        <div className="space-y-2">
          {!signals.isLoading && signalItems.length === 0 && (
            <div className="card p-4 text-sm text-ink-500">No signals yet for this brand.</div>
          )}
          {signalItems.map((s) => (
            <SignalCard key={s.id} signal={s} />
          ))}
        </div>
        <Pager
          total={signalTotal}
          offset={signalOffset}
          limit={signalLimit}
          onOffset={setSignalOffset}
          onLimit={setSignalLimit}
          pageSizes={[10, 20, 50]}
          loading={signals.isFetching}
          label="signals"
        />
      </section>

      <section>
        <h2 className="font-display text-xl font-semibold mb-3 text-ink-900">
          Catalog
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {productItems.map((p) => (
            <Link
              key={p.id}
              to={`/products/${p.id}`}
              className="card overflow-hidden hover:shadow-lift hover:-translate-y-[1px] transition-all"
            >
              <div className="aspect-square bg-ink-100 overflow-hidden">
                {p.image_url ? (
                  <img
                    src={p.image_url}
                    alt={p.title}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full grid place-items-center text-ink-300 text-xs">
                    no image
                  </div>
                )}
              </div>
              <div className="p-3">
                <div className="text-xs text-ink-500">{p.product_type}</div>
                <div className="font-medium text-sm line-clamp-2">{p.title}</div>
                <div className="mt-1 text-sm tabular-nums">
                  {formatPrice(p.latest_price_min, p.currency)}
                  {p.latest_price_max != null && p.latest_price_max !== p.latest_price_min && (
                    <span className="text-ink-400">
                      {" – "}
                      {formatPrice(p.latest_price_max, p.currency)}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
        <Pager
          total={productTotal}
          offset={productOffset}
          limit={productLimit}
          onOffset={setProductOffset}
          onLimit={setProductLimit}
          pageSizes={[12, 24, 48, 96]}
          loading={products.isFetching}
          label="products"
        />
      </section>

      {blog.data && blog.data.length > 0 && (
        <section>
          <h2 className="font-display text-xl font-semibold mb-3 text-ink-900">
            Recent posts
          </h2>
          <ul className="space-y-2">
            {blog.data.map((b) => (
              <li key={b.id} className="card p-3">
                <a
                  href={b.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium hover:underline inline-flex items-center gap-1"
                >
                  {b.title} <ExternalLink size={12} />
                </a>
                {b.summary && <p className="text-sm text-ink-600 mt-1 line-clamp-2">{b.summary}</p>}
                <div className="text-xs text-ink-500 mt-1">
                  {b.published_at
                    ? formatDistanceToNow(new Date(b.published_at), { addSuffix: true })
                    : "Date unknown"}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
