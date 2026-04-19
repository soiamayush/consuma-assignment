import { formatDistanceToNow } from "date-fns";
import {
  ArrowDown,
  ArrowUp,
  PackagePlus,
  PackageMinus,
  PackageX,
  PackageCheck,
  Newspaper,
  Sparkles,
  Info,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";
import { Link } from "react-router-dom";
import type { Signal } from "../api";

const KIND_META: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  PRODUCT_LAUNCH: { label: "New launch", icon: PackagePlus, color: "text-emerald-600" },
  PRODUCT_REMOVED: { label: "Removed", icon: PackageMinus, color: "text-rose-500" },
  PRICE_DROP: { label: "Price drop", icon: ArrowDown, color: "text-emerald-600" },
  PRICE_INCREASE: { label: "Price up", icon: ArrowUp, color: "text-amber-600" },
  OUT_OF_STOCK: { label: "Sold out", icon: PackageX, color: "text-rose-600" },
  BACK_IN_STOCK: { label: "Back in stock", icon: PackageCheck, color: "text-emerald-600" },
  BLOG_POST: { label: "Announcement", icon: Newspaper, color: "text-sky-600" },
  CATALOG_SURGE: { label: "Catalog surge", icon: Sparkles, color: "text-purple-600" },
};

function ImportanceBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2 shrink-0">
      <div className="h-1.5 w-20 rounded-full bg-ink-200 overflow-hidden">
        <div
          className={clsx(
            "h-full",
            pct >= 70 ? "bg-accent-500" : pct >= 40 ? "bg-ink-700" : "bg-ink-400"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono tabular-nums text-ink-500 w-8 text-right">{pct}</span>
    </div>
  );
}

export function SignalCard({ signal }: { signal: Signal }) {
  const meta = KIND_META[signal.kind] ?? {
    label: signal.kind,
    icon: Info,
    color: "text-ink-500",
  };
  const Icon = meta.icon;
  const when = formatDistanceToNow(new Date(signal.created_at), { addSuffix: true });
  const breakdown = signal.delta?.score_breakdown ?? {};

  const linkTo =
    signal.entity_type === "product" && signal.entity_id
      ? `/products/${signal.entity_id}`
      : signal.competitor_slug
      ? `/competitors/${signal.competitor_slug}`
      : undefined;

  const Body = (
    <div className="card p-4 flex gap-4 hover:border-ink-300 transition-colors">
      <div className={clsx("mt-1 shrink-0", meta.color)}>
        <Icon size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-ink-500 flex-wrap">
              <span className={clsx("font-semibold", meta.color)}>{meta.label}</span>
              <span>·</span>
              <span className="font-medium text-ink-700">{signal.competitor_name}</span>
              <span>·</span>
              <span title={new Date(signal.created_at).toLocaleString()}>{when}</span>
            </div>
            <h3 className="mt-1 font-medium text-ink-900 truncate">{signal.title}</h3>
            {signal.description && (
              <p className="mt-1 text-sm text-ink-600 line-clamp-2">{signal.description}</p>
            )}
          </div>
          <ImportanceBar value={signal.importance} />
        </div>
        <div className="mt-2 flex items-center gap-1.5 flex-wrap">
          {signal.themes.map((t) => (
            <span key={t} className="chip">
              {t}
            </span>
          ))}
          {signal.kind === "PRICE_DROP" && signal.delta.pct_change != null && (
            <span className="chip-accent">
              {(signal.delta.pct_change * 100).toFixed(1)}%
            </span>
          )}
          {signal.kind === "PRICE_INCREASE" && signal.delta.pct_change != null && (
            <span className="chip-accent">
              +{(signal.delta.pct_change * 100).toFixed(1)}%
            </span>
          )}
        </div>
        {breakdown.final !== undefined && (
          <details className="mt-2 text-xs text-ink-500">
            <summary className="cursor-pointer hover:text-ink-700">Why this score?</summary>
            <div className="mt-1 grid grid-cols-2 md:grid-cols-5 gap-2 font-mono">
              <span>base: {breakdown.base}</span>
              <span>magnitude: {breakdown.magnitude}</span>
              <span>recency: {breakdown.recency}</span>
              <span>brand: {breakdown.brand_weight}</span>
              <span>themes: +{breakdown.theme_boost}</span>
            </div>
          </details>
        )}
      </div>
    </div>
  );

  return linkTo ? (
    <Link to={linkTo} className="block">
      {Body}
    </Link>
  ) : (
    Body
  );
}
