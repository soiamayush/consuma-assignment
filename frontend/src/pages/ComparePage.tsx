import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowDownNarrowWide, ArrowUpNarrowWide, ExternalLink, Search, X } from "lucide-react";
import { api, type CompareBrandRow, type CompareSku } from "../api";
import { formatPrice } from "../formatPrice";
import { PriceBandLadder } from "../components/PriceBandLadder";
import { AIExplainCard } from "../components/AIExplainCard";

function SkuCard({ sku, currency }: { sku: CompareSku; currency: string | null }) {
  const cur = sku.currency || currency || "INR";
  const onSale = sku.compare_at_min != null && sku.price_min != null && sku.compare_at_min > sku.price_min;
  return (
    <a
      href={sku.url ?? "#"}
      target="_blank"
      rel="noreferrer"
      className="block border border-ink-200 rounded-lg overflow-hidden hover:border-ink-400 hover:shadow-sm transition bg-white w-40 shrink-0"
    >
      <div className="aspect-square bg-ink-100 overflow-hidden">
        {sku.image_url ? (
          <img src={sku.image_url} alt={sku.title} className="w-full h-full object-cover" />
        ) : null}
      </div>
      <div className="p-2 space-y-1">
        <div className="text-[11px] line-clamp-2 leading-snug min-h-[28px]">{sku.title}</div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-sm font-semibold tabular-nums">
            {formatPrice(sku.price_min, cur)}
          </span>
          {onSale && (
            <span className="text-[10px] line-through text-ink-400 tabular-nums">
              {formatPrice(sku.compare_at_min!, cur)}
            </span>
          )}
        </div>
      </div>
    </a>
  );
}

function BrandCard({
  row,
  anchorMedian,
  fallbackCurrency,
}: {
  row: CompareBrandRow;
  anchorMedian: number | null;
  fallbackCurrency: string | null;
}) {
  const cur = row.currency || fallbackCurrency || "INR";
  const delta = row.anchor_delta_pct;
  const showDelta = !row.is_anchor && delta != null;
  const cheaper = showDelta && (delta as number) < 0;

  return (
    <div className={`card p-4 space-y-3 ${row.is_anchor ? "border-amber-300 bg-amber-50/40" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <Link to={`/competitors/${row.slug}`} className="hover:underline">
              {row.name}
            </Link>
            {row.is_anchor && (
              <span className="chip-accent text-[10px] uppercase tracking-wide">Anchor</span>
            )}
          </h3>
          <p className="text-xs text-ink-500 mt-0.5">
            {row.sku_count} SKU{row.sku_count === 1 ? "" : "s"} in scope ·{" "}
            {row.priceable_skus} priced
          </p>
        </div>
        {showDelta && (
          <div
            className={`text-right text-xs font-semibold ${
              cheaper ? "text-emerald-700" : "text-rose-700"
            }`}
            title="Median price vs anchor median"
          >
            <div className="inline-flex items-center gap-1">
              {cheaper ? <ArrowDownNarrowWide size={14} /> : <ArrowUpNarrowWide size={14} />}
              {(delta as number) > 0 ? "+" : ""}
              {delta}% vs anchor
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 text-center gap-2 text-[11px]">
        <div className="rounded-md bg-ink-50 p-2">
          <div className="text-ink-500">p25</div>
          <div className="font-semibold tabular-nums">{formatPrice(row.p25, cur)}</div>
        </div>
        <div className="rounded-md bg-ink-100 p-2">
          <div className="text-ink-500">median</div>
          <div className="font-semibold tabular-nums">{formatPrice(row.median, cur)}</div>
        </div>
        <div className="rounded-md bg-ink-50 p-2">
          <div className="text-ink-500">p75</div>
          <div className="font-semibold tabular-nums">{formatPrice(row.p75, cur)}</div>
        </div>
      </div>

      <div className="text-[11px] text-ink-600 grid grid-cols-2 gap-y-0.5">
        <div>
          Range: <span className="tabular-nums">{formatPrice(row.min_price, cur)}</span> –{" "}
          <span className="tabular-nums">{formatPrice(row.max_price, cur)}</span>
        </div>
        <div>
          On sale:{" "}
          <span className="font-semibold tabular-nums">{row.discount_share_pct}%</span>
          {row.median_discount_pct ? (
            <>
              {" "}
              · median <span className="tabular-nums">{row.median_discount_pct}%</span> off
            </>
          ) : null}
        </div>
      </div>

      {row.cheapest.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold text-ink-600 mb-1">Cheapest in scope</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {row.cheapest.map((s) => (
              <SkuCard key={`c-${s.id}`} sku={s} currency={cur} />
            ))}
          </div>
        </div>
      )}

      {row.most_expensive.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold text-ink-600 mb-1">Most expensive in scope</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {row.most_expensive.map((s) => (
              <SkuCard key={`e-${s.id}`} sku={s} currency={cur} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ComparePage() {
  const [category, setCategory] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [keywordInput, setKeywordInput] = useState("");

  const q = useQuery({
    queryKey: ["compare", category, keyword],
    queryFn: () =>
      api.compare({
        category: category ?? undefined,
        keyword: keyword || undefined,
      }),
  });

  const data = q.data;

  // Sort brands: anchor first, then by SKU count desc within scope.
  const sortedBrands = useMemo(() => {
    if (!data) return [] as CompareBrandRow[];
    return [...data.per_brand].sort((a, b) => {
      if (a.is_anchor !== b.is_anchor) return a.is_anchor ? -1 : 1;
      return b.sku_count - a.sku_count;
    });
  }, [data]);

  const fallbackCurrency =
    data?.per_brand.find((r) => r.currency && r.currency !== "mixed")?.currency ?? "INR";

  const aiPayload = useMemo(() => {
    if (!data || data.scope.in_scope_total === 0) return null;
    return {
      scope: {
        category: data.scope.category,
        keyword: data.scope.keyword,
        in_scope_total: data.scope.in_scope_total,
        anchor_in_scope: data.scope.anchor_in_scope,
      },
      anchor: {
        slug: data.anchor_slug,
        name: data.anchor_name,
        median_price: data.anchor_median_price,
      },
      currency: fallbackCurrency,
      per_brand: sortedBrands.map((r) => ({
        slug: r.slug,
        name: r.name,
        is_anchor: r.is_anchor,
        sku_count: r.sku_count,
        priceable_skus: r.priceable_skus,
        median: r.median,
        p25: r.p25,
        p75: r.p75,
        min_price: r.min_price,
        max_price: r.max_price,
        discount_share_pct: r.discount_share_pct,
        median_discount_pct: r.median_discount_pct,
        anchor_delta_pct: r.anchor_delta_pct,
        cheapest: r.cheapest.slice(0, 2).map((s) => ({
          title: s.title,
          price_min: s.price_min,
          compare_at_min: s.compare_at_min,
        })),
        most_expensive: r.most_expensive.slice(0, 2).map((s) => ({
          title: s.title,
          price_min: s.price_min,
          compare_at_min: s.compare_at_min,
        })),
      })),
    };
  }, [data, sortedBrands, fallbackCurrency]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Compare</h1>
        <p className="text-ink-500 mt-1 text-sm max-w-3xl">
          Pick a category or type a keyword (e.g. <em>vitamin c serum</em>) to compare every brand on
          the same shelf — price band, cheapest / priciest SKUs, discount intensity, and how they sit
          versus your anchor.
        </p>
      </div>

      {/* picker */}
      <div className="card p-4 space-y-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[260px]">
            <label className="block text-xs font-medium text-ink-600 mb-1">Search keyword</label>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setKeyword(keywordInput.trim());
              }}
            >
              <div className="relative flex-1">
                <Search
                  size={14}
                  className="absolute left-2 top-1/2 -translate-y-1/2 text-ink-400 pointer-events-none"
                />
                <input
                  className="w-full text-sm border border-ink-200 rounded-md px-7 py-1.5 bg-white"
                  placeholder="vitamin c serum, sunscreen, retinol…"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                />
                {keywordInput && (
                  <button
                    type="button"
                    onClick={() => {
                      setKeywordInput("");
                      setKeyword("");
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              <button type="submit" className="btn-primary text-xs">
                Compare
              </button>
            </form>
          </div>
          <div className="text-xs text-ink-600">
            <div>
              <span className="font-medium">{data?.scope.in_scope_total ?? 0}</span> SKUs in scope
              {data?.scope.anchor_in_scope ? (
                <> · {data.scope.anchor_in_scope} from anchor</>
              ) : null}
            </div>
            {(category || keyword) && (
              <button
                onClick={() => {
                  setCategory(null);
                  setKeyword("");
                  setKeywordInput("");
                }}
                className="text-rose-700 hover:underline mt-1 inline-flex items-center gap-1"
              >
                <X size={12} /> clear filters
              </button>
            )}
          </div>
        </div>

        <div>
          <div className="text-xs font-medium text-ink-600 mb-1">Categories (product_type)</div>
          <div className="flex flex-wrap gap-1.5">
            <button
              className={`chip ${category == null ? "bg-ink-900 text-white" : ""}`}
              onClick={() => setCategory(null)}
            >
              All
            </button>
            {(data?.categories ?? []).map((c) => (
              <button
                key={c.category}
                onClick={() => setCategory(c.category === category ? null : c.category)}
                className={`chip ${
                  category === c.category ? "bg-ink-900 text-white" : ""
                }`}
                title={`${c.sku_count} SKUs`}
              >
                {c.category}
                <span className={`ml-1 ${category === c.category ? "text-ink-200" : "text-ink-400"} text-[10px]`}>
                  {c.sku_count}
                </span>
              </button>
            ))}
          </div>
        </div>

        {data?.keyword_suggestions && data.keyword_suggestions.length > 0 && !keyword && (
          <div>
            <div className="text-xs font-medium text-ink-600 mb-1">Try a keyword</div>
            <div className="flex flex-wrap gap-1.5">
              {data.keyword_suggestions.slice(0, 16).map((k) => (
                <button
                  key={k.keyword}
                  className="chip"
                  onClick={() => {
                    setKeywordInput(k.keyword);
                    setKeyword(k.keyword);
                  }}
                >
                  {k.keyword}
                  <span className="ml-1 text-ink-400 text-[10px]">{k.hits}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {q.isLoading && <p className="text-sm text-ink-500">Loading comparison…</p>}
      {q.isError && (
        <p className="text-sm text-rose-600">Could not load comparison. Is the API running?</p>
      )}

      {data && data.scope.in_scope_total === 0 && (
        <div className="card p-6 text-sm text-ink-600">
          Nothing in scope for this filter. Try a different category or keyword.
        </div>
      )}

      {data && data.scope.in_scope_total > 0 && (
        <>
          {/* Price band ladder — the centrepiece chart */}
          <div className="card p-4">
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="font-semibold">
                Price ladder
                {category ? ` · ${category}` : ""}
                {keyword ? ` · "${keyword}"` : ""}
              </h2>
              {data.anchor_median_price != null && (
                <span className="text-xs text-ink-500">
                  Anchor median: <strong className="text-amber-700">
                    {formatPrice(data.anchor_median_price, fallbackCurrency)}
                  </strong>
                </span>
              )}
            </div>
            <p className="text-xs text-ink-500 mb-3">
              Box = p25 → p75 of latest listed price. Dot = median. Whiskers = min / max in scope.
              Dashed orange line = anchor median for reference.
            </p>
            <PriceBandLadder
              rows={sortedBrands}
              anchorReference={data.anchor_median_price}
              fallbackCurrency={fallbackCurrency}
            />
          </div>

          {aiPayload && (
            <AIExplainCard
              view="compare_scope"
              payload={aiPayload}
              title="AI strategist memo"
              subtitle={`Pricing & assortment recommendations for ${
                category ? `category "${category}"` : keyword ? `keyword "${keyword}"` : "this scope"
              }.`}
            />
          )}

          {/* Per-brand cards */}
          <div className="grid lg:grid-cols-2 gap-5">
            {sortedBrands.map((row) => (
              <BrandCard
                key={row.slug}
                row={row}
                anchorMedian={data.anchor_median_price}
                fallbackCurrency={fallbackCurrency}
              />
            ))}
          </div>

          {/* Combined ranked SKU table — every priced SKU in scope across all brands */}
          <div className="card p-4">
            <h2 className="font-semibold mb-1">All SKUs in scope, cheapest first</h2>
            <p className="text-xs text-ink-500 mb-3">
              Combined view across every brand — pricing transparency for buyers.
            </p>
            <CombinedSkuTable rows={sortedBrands} fallbackCurrency={fallbackCurrency} />
          </div>
        </>
      )}
    </div>
  );
}

function CombinedSkuTable({
  rows,
  fallbackCurrency,
}: {
  rows: CompareBrandRow[];
  fallbackCurrency: string | null;
}) {
  const [showAll, setShowAll] = useState(false);
  const flat = useMemo(() => {
    const items: { brand: string; brandSlug: string; isAnchor: boolean; sku: CompareSku }[] = [];
    for (const r of rows) {
      for (const s of r.all_skus) {
        items.push({ brand: r.name, brandSlug: r.slug, isAnchor: r.is_anchor, sku: s });
      }
    }
    items.sort(
      (a, b) => (a.sku.price_min ?? Number.POSITIVE_INFINITY) - (b.sku.price_min ?? Number.POSITIVE_INFINITY),
    );
    return items;
  }, [rows]);

  const visible = showAll ? flat : flat.slice(0, 25);

  if (flat.length === 0) return <p className="text-xs text-ink-500">No priced SKUs.</p>;

  return (
    <>
      <div className="overflow-x-auto text-sm">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-xs text-ink-500 border-b border-ink-200">
              <th className="py-2 pr-3">#</th>
              <th className="py-2 pr-3">Brand</th>
              <th className="py-2 pr-3">Product</th>
              <th className="py-2 pr-3">Price</th>
              <th className="py-2 pr-3">MSRP</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => {
              const cur = r.sku.currency || fallbackCurrency;
              const onSale =
                r.sku.compare_at_min != null &&
                r.sku.price_min != null &&
                r.sku.compare_at_min > r.sku.price_min;
              return (
                <tr key={`${r.brandSlug}-${r.sku.id}`} className="border-b border-ink-100 hover:bg-ink-50/50">
                  <td className="py-2 pr-3 text-xs text-ink-400 tabular-nums">{i + 1}</td>
                  <td className="py-2 pr-3">
                    <Link to={`/competitors/${r.brandSlug}`} className="hover:underline">
                      {r.brand}
                      {r.isAnchor ? " ★" : ""}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    <Link to={`/products/${r.sku.id}`} className="hover:underline">
                      {r.sku.title}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 tabular-nums font-medium">
                    {formatPrice(r.sku.price_min, cur)}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-xs text-ink-500">
                    {onSale ? formatPrice(r.sku.compare_at_min!, cur) : "—"}
                  </td>
                  <td className="py-2">
                    {r.sku.url && (
                      <a
                        href={r.sku.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-ink-500 hover:text-ink-900 inline-flex"
                        title="Open on brand site"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {flat.length > 25 && (
        <div className="mt-2 text-xs">
          <button
            onClick={() => setShowAll((s) => !s)}
            className="btn btn-ghost text-xs"
          >
            {showAll ? "Show top 25" : `Show all ${flat.length}`}
          </button>
        </div>
      )}
    </>
  );
}
