import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Info,
  Lightbulb,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { InsightCard } from "../api";

const TONE: Record<
  string,
  { card: string; chip: string; icon: JSX.Element }
> = {
  info: {
    card: "border-sky-200/80 bg-gradient-to-br from-sky-50/90 to-white/70",
    chip: "bg-sky-100/80 text-sky-800",
    icon: <Info size={14} />,
  },
  success: {
    card: "border-emerald-200/80 bg-gradient-to-br from-emerald-50/90 to-white/70",
    chip: "bg-emerald-100/80 text-emerald-800",
    icon: <ShieldCheck size={14} />,
  },
  warning: {
    card: "border-accent-200 bg-gradient-to-br from-accent-50/90 to-white/70",
    chip: "bg-accent-100 text-accent-700",
    icon: <Lightbulb size={14} />,
  },
  danger: {
    card: "border-blush-300/80 bg-gradient-to-br from-blush-50/90 to-white/70",
    chip: "bg-blush-100 text-blush-800",
    icon: <AlertTriangle size={14} />,
  },
};

type Props = {
  insights: InsightCard[];
  loading?: boolean;
  title?: string;
  subtitle?: string;
};

export function InsightStrip({
  insights,
  loading,
  title = "What's worth your attention",
  subtitle,
}: Props) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-display text-xl md:text-2xl font-semibold flex items-center gap-2 text-ink-900">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-blush-400 to-accent-400 text-white shadow-sm">
              <Sparkles size={14} />
            </span>
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-ink-500 mt-1 ml-10">{subtitle}</p>
          )}
        </div>
      </div>
      {loading && (
        <p className="text-xs text-ink-500 ml-10">Reading the landscape…</p>
      )}
      {!loading && insights.length === 0 && (
        <p className="text-xs text-ink-500 ml-10">
          No standout findings yet — check back after the next refresh.
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {insights.map((c) => {
          const tone = TONE[c.severity] ?? TONE.info;
          return (
            <div
              key={c.id}
              className={`rounded-2xl border backdrop-blur-md p-4 space-y-2 flex flex-col shadow-glass ${tone.card}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em]">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${tone.chip}`}
                  >
                    {tone.icon}
                    {c.severity}
                  </span>
                  {c.brand_name && (
                    <span className="text-ink-500 normal-case font-normal tracking-normal">
                      {c.brand_name}
                    </span>
                  )}
                </div>
                {c.metric && (
                  <span className="text-[11px] font-mono text-ink-700 bg-white/70 rounded px-1.5 py-0.5 border border-ink-200">
                    {c.metric}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-[15px] leading-snug text-ink-900">
                {c.headline}
              </h3>
              <p className="text-xs text-ink-700 leading-relaxed">{c.detail}</p>
              <div className="mt-auto pt-2">
                {c.href && (
                  <Link
                    to={c.href}
                    className="text-xs font-medium text-ink-700 hover:text-blush-700 inline-flex items-center gap-1"
                  >
                    Investigate <ArrowRight size={12} />
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
