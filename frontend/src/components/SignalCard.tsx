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

const KIND_META: Record<
  string,
  { label: string; icon: LucideIcon; color: string; ring: string; iconBg: string }
> = {
  PRODUCT_LAUNCH: {
    label: "New launch",
    icon: PackagePlus,
    color: "text-emerald-700",
    ring: "ring-emerald-100",
    iconBg: "bg-gradient-to-br from-emerald-100 to-emerald-50",
  },
  PRODUCT_REMOVED: {
    label: "Removed",
    icon: PackageMinus,
    color: "text-rose-600",
    ring: "ring-rose-100",
    iconBg: "bg-gradient-to-br from-rose-100 to-rose-50",
  },
  PRICE_DROP: {
    label: "Price drop",
    icon: ArrowDown,
    color: "text-emerald-700",
    ring: "ring-emerald-100",
    iconBg: "bg-gradient-to-br from-emerald-100 to-emerald-50",
  },
  PRICE_INCREASE: {
    label: "Price up",
    icon: ArrowUp,
    color: "text-accent-600",
    ring: "ring-accent-200/60",
    iconBg: "bg-gradient-to-br from-accent-100 to-accent-50",
  },
  OUT_OF_STOCK: {
    label: "Sold out",
    icon: PackageX,
    color: "text-rose-700",
    ring: "ring-rose-100",
    iconBg: "bg-gradient-to-br from-rose-100 to-rose-50",
  },
  BACK_IN_STOCK: {
    label: "Back in stock",
    icon: PackageCheck,
    color: "text-emerald-700",
    ring: "ring-emerald-100",
    iconBg: "bg-gradient-to-br from-emerald-100 to-emerald-50",
  },
  BLOG_POST: {
    label: "Announcement",
    icon: Newspaper,
    color: "text-sky-700",
    ring: "ring-sky-100",
    iconBg: "bg-gradient-to-br from-sky-100 to-sky-50",
  },
  CATALOG_SURGE: {
    label: "Catalog surge",
    icon: Sparkles,
    color: "text-plum-700",
    ring: "ring-plum-200/70",
    iconBg: "bg-gradient-to-br from-plum-100 to-blush-50",
  },
};

const KIND_LABELS: Record<string, string> = {
  PRODUCT_LAUNCH: "New launch",
  PRODUCT_REMOVED: "Removed",
  PRICE_DROP: "Price drop",
  PRICE_INCREASE: "Price up",
  OUT_OF_STOCK: "Sold out",
  BACK_IN_STOCK: "Back in stock",
  BLOG_POST: "Announcement",
  CATALOG_SURGE: "Catalog surge",
};

function humaniseTheme(t: string): string {
  return t
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function ImportanceBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2 shrink-0">
      <div className="h-1.5 w-24 rounded-full bg-ink-100 overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full transition-all",
            pct >= 70
              ? "bg-gradient-to-r from-blush-500 to-accent-500"
              : pct >= 40
                ? "bg-gradient-to-r from-ink-700 to-plum-600"
                : "bg-ink-400",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-semibold tabular-nums text-ink-600 w-7 text-right">
        {pct}
      </span>
    </div>
  );
}

export function SignalCard({ signal }: { signal: Signal }) {
  const meta = KIND_META[signal.kind] ?? {
    label: KIND_LABELS[signal.kind] ?? humaniseTheme(signal.kind),
    icon: Info,
    color: "text-ink-500",
    ring: "ring-ink-100",
    iconBg: "bg-ink-50",
  };
  const Icon = meta.icon;
  const when = formatDistanceToNow(new Date(signal.created_at), {
    addSuffix: true,
  });
  const breakdown = signal.delta?.score_breakdown ?? {};

  const linkTo =
    signal.entity_type === "product" && signal.entity_id
      ? `/products/${signal.entity_id}`
      : signal.competitor_slug
        ? `/competitors/${signal.competitor_slug}`
        : undefined;

  const Body = (
    <div className="card p-4 flex gap-4 hover:shadow-lift hover:-translate-y-[1px] transition-all">
      <div
        className={clsx(
          "h-11 w-11 shrink-0 rounded-xl ring-1 grid place-items-center",
          meta.iconBg,
          meta.ring,
          meta.color,
        )}
      >
        <Icon size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] text-ink-500 flex-wrap uppercase tracking-[0.12em]">
              <span className={clsx("font-semibold", meta.color)}>
                {meta.label}
              </span>
              <span className="text-ink-300">·</span>
              <span className="font-medium text-ink-700 normal-case tracking-normal">
                {signal.competitor_name}
              </span>
              <span className="text-ink-300">·</span>
              <span
                className="text-ink-500 normal-case tracking-normal"
                title={new Date(signal.created_at).toLocaleString()}
              >
                {when}
              </span>
            </div>
            <h3 className="mt-1.5 font-semibold text-ink-900 truncate">
              {signal.title}
            </h3>
            {signal.description && (
              <p className="mt-1 text-sm text-ink-600 line-clamp-2">
                {signal.description}
              </p>
            )}
          </div>
          <ImportanceBar value={signal.importance} />
        </div>
        <div className="mt-3 flex items-center gap-1.5 flex-wrap">
          {signal.themes.map((t) => (
            <span key={t} className="chip">
              {humaniseTheme(t)}
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
          <details className="mt-3 text-xs text-ink-500">
            <summary className="cursor-pointer hover:text-ink-700 select-none">
              Why this score?
            </summary>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-5 gap-2 font-mono bg-ink-50/70 rounded-lg px-3 py-2">
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
