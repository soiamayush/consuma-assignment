import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownNarrowWide,
  ArrowUpNarrowWide,
  ExternalLink,
  Target,
} from "lucide-react";
import { format } from "date-fns";
import { useMemo } from "react";
import { api, type PeerCard } from "../api";
import { PriceHistoryChart } from "../components/PriceHistoryChart";
import { AIExplainCard } from "../components/AIExplainCard";
import { formatPrice } from "../formatPrice";

function PeerSlot({
  label,
  card,
  selfPrice,
  icon,
  tone,
}: {
  label: string;
  card: PeerCard | null;
  selfPrice: number | null;
  icon: JSX.Element;
  tone: string;
}) {
  if (!card) {
    return (
      <div className={`border border-dashed border-ink-200 rounded-lg p-3 text-xs text-ink-500 ${tone}`}>
        <div className="flex items-center gap-1 font-medium text-ink-700 mb-1">{icon} {label}</div>
        No peer SKU in this slot.
      </div>
    );
  }
  const cur = card.currency || "INR";
  const delta =
    selfPrice && card.price_min ? Math.round(((card.price_min - selfPrice) / selfPrice) * 100) : null;
  return (
    <div className={`border rounded-lg p-3 space-y-2 ${tone}`}>
      <div className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-700">
        {icon} {label}
      </div>
      <div className="flex gap-3">
        <div className="w-20 h-20 shrink-0 bg-ink-100 rounded overflow-hidden">
          {card.image_url ? (
            <img src={card.image_url} alt={card.title} className="w-full h-full object-cover" />
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-ink-500">
            <Link to={`/competitors/${card.brand_slug}`} className="hover:underline">
              {card.brand_name}
            </Link>
            {card.is_anchor ? " ★" : ""}
          </div>
          <Link to={`/products/${card.id}`} className="text-sm font-medium leading-snug hover:underline line-clamp-2 block">
            {card.title}
          </Link>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-sm font-semibold tabular-nums">
              {formatPrice(card.price_min, cur)}
            </span>
            {delta != null && delta !== 0 && (
              <span
                className={`text-[11px] font-semibold ${delta < 0 ? "text-emerald-700" : "text-rose-700"}`}
              >
                {delta > 0 ? "+" : ""}
                {delta}% vs this
              </span>
            )}
          </div>
          {card.url && (
            <a
              href={card.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-ink-500 hover:text-ink-900 mt-1"
            >
              <ExternalLink size={11} /> brand site
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function ProductPage() {
  const { id = "" } = useParams();
  const q = useQuery({ queryKey: ["product", id], queryFn: () => api.product(Number(id)) });
  const peersQ = useQuery({
    queryKey: ["product-peers", id],
    queryFn: () => api.productPeers(Number(id)),
    enabled: !!id,
  });

  const p = q.data;
  const peers = peersQ.data;

  const aiPayload = useMemo(() => {
    if (!p) return null;
    const peerCard = (c: PeerCard | null | undefined) =>
      c
        ? {
            brand: c.brand_name,
            title: c.title,
            price_min: c.price_min,
            currency: c.currency,
            is_anchor: c.is_anchor,
          }
        : null;
    return {
      sku: {
        brand: p.competitor_name,
        is_anchor_brand: peers?.cheapest?.is_anchor || peers?.closest?.is_anchor || false,
        title: p.title,
        product_type: p.product_type,
        price_min: p.latest_price_min,
        price_max: p.latest_price_max,
        currency: p.currency,
        msrp: p.snapshots?.[0]?.compare_at_max ?? null,
      },
      peers: peers
        ? {
            category: peers.category,
            peer_count: peers.peer_count,
            cheapest: peerCard(peers.cheapest),
            closest: peerCard(peers.closest),
            most_expensive: peerCard(peers.most_expensive),
            sample_alternatives: (peers.alternatives ?? []).slice(0, 5).map((a) => ({
              brand: a.brand_name,
              title: a.title,
              price_min: a.price_min,
              currency: a.currency,
            })),
          }
        : null,
    };
  }, [p, peers]);

  if (q.isLoading)
    return <div className="text-sm text-ink-500">Loading the product…</div>;
  if (!p) return <div>Not found.</div>;

  return (
    <div className="space-y-6">
      <div className="text-xs text-ink-500 uppercase tracking-[0.14em] font-semibold">
        {p.competitor_slug ? (
          <Link
            to={`/competitors/${p.competitor_slug}`}
            className="hover:text-blush-700 transition"
          >
            {p.competitor_name}
          </Link>
        ) : (
          <span>{p.competitor_name}</span>
        )}{" "}
        <span className="text-ink-300">·</span>{" "}
        <span className="text-ink-500 normal-case tracking-normal font-normal">
          {p.product_type}
        </span>
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card overflow-hidden">
          <div className="aspect-square bg-gradient-to-br from-cream-100 to-blush-50">
            {p.image_url ? (
              <img
                src={p.image_url}
                alt={p.title}
                className="w-full h-full object-cover"
              />
            ) : null}
          </div>
        </div>
        <div className="space-y-3">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-900">
            {p.title}
          </h1>
          <div className="text-lg font-medium tabular-nums">
            {p.latest_price_min != null ? formatPrice(p.latest_price_min, p.currency) : "—"}
            {p.latest_price_max != null &&
              p.latest_price_max !== p.latest_price_min &&
              p.latest_price_min != null && (
                <span className="text-ink-400">
                  {" "}
                  – {formatPrice(p.latest_price_max, p.currency)}
                </span>
              )}
          </div>
          {p.snapshots?.[0]?.compare_at_max != null &&
            p.snapshots[0].compare_at_max > (p.latest_price_min ?? 0) && (
              <p className="text-sm text-ink-500">
                List / MSRP: {formatPrice(p.snapshots[0].compare_at_max, p.currency ?? "INR")}
              </p>
            )}
          {p.url && (
            <a
              href={p.url}
              target="_blank"
              rel="noreferrer"
              className="btn-ghost inline-flex w-fit"
            >
              View on site <ExternalLink size={14} />
            </a>
          )}
          <div className="flex flex-wrap gap-1">
            {p.tags.map((t) => (
              <span key={t} className="chip">
                {t}
              </span>
            ))}
          </div>
          <div className="text-xs text-ink-500 pt-2">
            First seen {format(new Date(p.first_seen_at), "MMM d, yyyy")} · Last seen{" "}
            {format(new Date(p.last_seen_at), "MMM d, yyyy")}
          </div>
        </div>
      </div>

      {peers && (peers.cheapest || peers.closest || peers.most_expensive) && (
        <div className="card p-5 space-y-3">
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <div>
              <h2 className="font-display text-lg font-semibold text-ink-900">
                Comparable across peers
              </h2>
              <p className="text-xs text-ink-500">
                {peers.category ? (
                  <>
                    Same category: <strong>{peers.category}</strong>
                    {peers.peer_count != null && (
                      <> · {peers.peer_count} peer SKU{peers.peer_count === 1 ? "" : "s"} priced</>
                    )}
                  </>
                ) : (
                  <>Comparing across all peers.</>
                )}
              </p>
            </div>
            <Link
              to={`/compare?category=${encodeURIComponent(peers.category ?? "")}`}
              className="btn btn-ghost text-xs"
            >
              Open in Compare →
            </Link>
          </div>
          <div className="grid md:grid-cols-3 gap-3">
            <PeerSlot
              label="Cheapest peer"
              card={peers.cheapest}
              selfPrice={p.latest_price_min ?? null}
              icon={<ArrowDownNarrowWide size={12} />}
              tone="border-emerald-200 bg-emerald-50/40"
            />
            <PeerSlot
              label="Closest in price"
              card={peers.closest}
              selfPrice={p.latest_price_min ?? null}
              icon={<Target size={12} />}
              tone="border-ink-200 bg-ink-50/40"
            />
            <PeerSlot
              label="Most expensive peer"
              card={peers.most_expensive}
              selfPrice={p.latest_price_min ?? null}
              icon={<ArrowUpNarrowWide size={12} />}
              tone="border-rose-200 bg-rose-50/40"
            />
          </div>
          {peers.alternatives.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-ink-700 hover:text-ink-900">
                More peer SKUs in this category ({peers.alternatives.length})
              </summary>
              <ul className="mt-2 space-y-1 text-xs">
                {peers.alternatives.map((a) => {
                  const cur = a.currency || "INR";
                  return (
                    <li key={a.id} className="flex items-center justify-between gap-3 border-b border-ink-100 py-1">
                      <span className="truncate">
                        <span className="text-ink-500">{a.brand_name}</span> ·{" "}
                        <Link to={`/products/${a.id}`} className="hover:underline">
                          {a.title}
                        </Link>
                      </span>
                      <span className="tabular-nums font-medium">{formatPrice(a.price_min, cur)}</span>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}
        </div>
      )}
      {peers?.note && (
        <div className="card p-3 text-xs text-ink-500">{peers.note}</div>
      )}

      {aiPayload && aiPayload.peers && (
        <AIExplainCard
          view="product_peers"
          payload={aiPayload}
          title="AI peer commentary"
          subtitle="Two-paragraph merchandiser take on how this SKU sits versus peers."
          allowFollowUp={false}
        />
      )}

      <div className="card p-5">
        <h2 className="font-display text-lg font-semibold mb-2 text-ink-900">
          Price history
        </h2>
        <PriceHistoryChart snapshots={p.snapshots ?? []} currency={p.currency} />
      </div>

      <div className="card p-5">
        <h2 className="font-display text-lg font-semibold mb-2 text-ink-900">
          Snapshots
        </h2>
        <table className="w-full text-sm">
          <thead className="text-xs text-ink-500 text-left">
            <tr>
              <th className="py-1">Captured</th>
              <th>Price</th>
              <th>Avail.</th>
              <th>Variants</th>
            </tr>
          </thead>
          <tbody>
            {(p.snapshots ?? []).map((s, i) => (
              <tr key={i} className="border-t border-ink-100">
                <td className="py-1">{format(new Date(s.captured_at), "MMM d, yyyy HH:mm")}</td>
                <td className="tabular-nums">
                  {s.price_min != null ? formatPrice(s.price_min, s.currency ?? p.currency) : "—"}
                  {s.compare_at_max != null && s.compare_at_max > (s.price_min ?? 0) && (
                    <span className="text-ink-500 text-xs block">
                      MSRP {formatPrice(s.compare_at_max, s.currency ?? p.currency)}
                    </span>
                  )}
                </td>
                <td>{s.available ? "yes" : "no"}</td>
                <td className="tabular-nums">{s.variants_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
