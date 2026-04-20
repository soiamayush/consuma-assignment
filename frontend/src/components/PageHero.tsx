import type { ReactNode } from "react";
import clsx from "clsx";

type Theme = "rose" | "gold" | "plum" | "sage" | "ink" | "sky";

type Props = {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  badge?: ReactNode;
  theme?: Theme;
  imageUrl?: string;
  children?: ReactNode;
  className?: string;
};

const THEME_STYLES: Record<
  Theme,
  { overlay: string; ring: string; glow: string; accent: string }
> = {
  rose: {
    overlay:
      "from-blush-100/85 via-cream-50/80 to-white/75",
    ring: "ring-blush-200/60",
    glow: "bg-gradient-to-br from-blush-300/50 via-cream-200/40 to-white/0",
    accent: "text-blush-700",
  },
  gold: {
    overlay:
      "from-accent-100/85 via-cream-50/80 to-white/75",
    ring: "ring-accent-200/60",
    glow: "bg-gradient-to-br from-accent-300/50 via-blush-100/40 to-white/0",
    accent: "text-accent-600",
  },
  plum: {
    overlay:
      "from-plum-100/85 via-blush-50/80 to-white/75",
    ring: "ring-plum-200/60",
    glow: "bg-gradient-to-br from-plum-300/50 via-blush-100/40 to-white/0",
    accent: "text-plum-700",
  },
  sage: {
    overlay:
      "from-emerald-50/90 via-cream-50/80 to-white/75",
    ring: "ring-emerald-200/60",
    glow: "bg-gradient-to-br from-emerald-200/40 via-cream-100/40 to-white/0",
    accent: "text-emerald-700",
  },
  ink: {
    overlay:
      "from-ink-100/85 via-cream-50/80 to-white/75",
    ring: "ring-ink-200/60",
    glow: "bg-gradient-to-br from-ink-300/40 via-plum-100/40 to-white/0",
    accent: "text-ink-800",
  },
  sky: {
    overlay:
      "from-sky-50/90 via-cream-50/80 to-white/75",
    ring: "ring-sky-200/60",
    glow: "bg-gradient-to-br from-sky-200/40 via-cream-100/40 to-white/0",
    accent: "text-sky-700",
  },
};

const DEFAULT_IMAGES: Record<Theme, string> = {
  rose: "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=2000&q=80",
  gold: "https://images.unsplash.com/photo-1571875257727-256c39da42af?auto=format&fit=crop&w=2000&q=80",
  plum: "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=2000&q=80",
  sage: "https://images.unsplash.com/photo-1610397962076-02407a169a98?auto=format&fit=crop&w=2000&q=80",
  ink: "https://images.unsplash.com/photo-1526045478516-99145907023c?auto=format&fit=crop&w=2000&q=80",
  sky: "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=2000&q=80",
};

export function PageHero({
  eyebrow,
  title,
  subtitle,
  actions,
  badge,
  theme = "rose",
  imageUrl,
  children,
  className,
}: Props) {
  const t = THEME_STYLES[theme];
  const img = imageUrl ?? DEFAULT_IMAGES[theme];

  return (
    <section
      className={clsx(
        "hero-surface ring-1 animate-fade-up",
        t.ring,
        className,
      )}
    >
      <div
        aria-hidden
        className="absolute inset-0 bg-cover bg-center opacity-[0.55]"
        style={{
          backgroundImage: `url('${img}')`,
        }}
      />
      <div
        aria-hidden
        className={clsx(
          "absolute inset-0 bg-gradient-to-br",
          t.overlay,
        )}
      />
      <div
        aria-hidden
        className={clsx(
          "absolute -top-24 -right-16 h-64 w-64 rounded-full blur-3xl opacity-70",
          t.glow,
        )}
      />
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(17,24,39,0.07) 1px, transparent 0)",
          backgroundSize: "22px 22px",
          maskImage:
            "linear-gradient(to bottom, rgba(0,0,0,0.55), rgba(0,0,0,0))",
        }}
      />

      <div className="relative z-10 px-6 md:px-10 py-8 md:py-12">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div className="max-w-3xl">
            {eyebrow && (
              <div
                className={clsx(
                  "text-[11px] font-semibold uppercase tracking-[0.18em] mb-3",
                  t.accent,
                )}
              >
                {eyebrow}
              </div>
            )}
            <h1 className="font-display text-[2rem] md:text-[2.6rem] leading-[1.05] font-semibold text-ink-900">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-3 text-ink-600 text-sm md:text-[15px] leading-relaxed max-w-2xl">
                {subtitle}
              </p>
            )}
            {badge && <div className="mt-4">{badge}</div>}
          </div>
          {actions && (
            <div className="flex items-center gap-2 flex-wrap shrink-0">
              {actions}
            </div>
          )}
        </div>
        {children && <div className="mt-6">{children}</div>}
      </div>
    </section>
  );
}
