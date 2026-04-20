import clsx from "clsx";

type Props = {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  accent?: boolean;
  tone?: "neutral" | "rose" | "gold" | "plum" | "sage" | "rose-dark";
};

const TONE: Record<string, string> = {
  neutral: "from-white/85 to-white/60 border-white/60",
  rose: "from-blush-50/90 to-white/70 border-blush-100",
  gold: "from-accent-50/90 to-white/70 border-accent-200/80",
  plum: "from-plum-50/90 to-white/70 border-plum-200/70",
  sage: "from-emerald-50/90 to-white/70 border-emerald-200/70",
  "rose-dark": "from-blush-100/90 to-cream-50/70 border-blush-200",
};

export function StatCard({ label, value, sub, accent, tone = "neutral" }: Props) {
  const toneKey = accent ? "rose-dark" : tone;
  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-2xl border p-4 backdrop-blur-md shadow-glass bg-gradient-to-br transition hover:-translate-y-0.5 hover:shadow-lift",
        TONE[toneKey],
      )}
    >
      <div
        aria-hidden
        className="absolute -top-6 -right-6 h-20 w-20 rounded-full bg-gradient-to-br from-white/80 to-transparent opacity-60 blur-xl"
      />
      <div className="relative">
        <div className="text-[11px] uppercase tracking-[0.16em] text-ink-500 font-semibold">
          {label}
        </div>
        <div className="mt-1.5 text-[1.7rem] font-display font-semibold text-ink-900 tabular-nums leading-none">
          {value}
        </div>
        {sub && <div className="text-xs text-ink-500 mt-2">{sub}</div>}
      </div>
    </div>
  );
}
