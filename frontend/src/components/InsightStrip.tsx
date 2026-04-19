import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Info, Lightbulb, ShieldCheck, Sparkles } from "lucide-react";
import type { InsightCard } from "../api";

const TONE: Record<string, { card: string; chip: string; icon: JSX.Element }> = {
  info: {
    card: "border-sky-200 bg-sky-50/60",
    chip: "bg-sky-100 text-sky-800",
    icon: <Info size={14} />,
  },
  success: {
    card: "border-emerald-200 bg-emerald-50/60",
    chip: "bg-emerald-100 text-emerald-800",
    icon: <ShieldCheck size={14} />,
  },
  warning: {
    card: "border-amber-300 bg-amber-50/70",
    chip: "bg-amber-100 text-amber-900",
    icon: <Lightbulb size={14} />,
  },
  danger: {
    card: "border-rose-300 bg-rose-50/60",
    chip: "bg-rose-100 text-rose-800",
    icon: <AlertTriangle size={14} />,
  },
};

type Props = {
  insights: InsightCard[];
  loading?: boolean;
  title?: string;
  subtitle?: string;
};

export function InsightStrip({ insights, loading, title = "Auto insights", subtitle }: Props) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Sparkles size={16} className="text-amber-600" />
            {title}
          </h2>
          {subtitle && <p className="text-xs text-ink-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {loading && <p className="text-xs text-ink-500">Crunching the catalog…</p>}
      {!loading && insights.length === 0 && (
        <p className="text-xs text-ink-500">No findings yet — run an ingestion.</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {insights.map((c) => {
          const tone = TONE[c.severity] ?? TONE.info;
          return (
            <div key={c.id} className={`card border ${tone.card} p-3 space-y-2 flex flex-col`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide">
                  <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 ${tone.chip}`}>
                    {tone.icon}
                    {c.severity}
                  </span>
                  {c.brand_name && (
                    <span className="text-ink-500 normal-case font-normal">
                      {c.brand_name}
                    </span>
                  )}
                </div>
                {c.metric && (
                  <span className="text-[11px] font-mono text-ink-700 bg-white/60 rounded px-1.5 py-0.5 border border-ink-200">
                    {c.metric}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-sm leading-snug">{c.headline}</h3>
              <p className="text-xs text-ink-700 leading-snug">{c.detail}</p>
              <div className="mt-auto pt-1">
                {c.href && (
                  <Link
                    to={c.href}
                    className="text-xs text-ink-700 hover:text-ink-900 inline-flex items-center gap-1"
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
