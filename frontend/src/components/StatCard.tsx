import clsx from "clsx";

type Props = {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  accent?: boolean;
};

export function StatCard({ label, value, sub, accent }: Props) {
  return (
    <div
      className={clsx(
        "card p-4",
        accent && "border-amber-200 bg-accent-50"
      )}
    >
      <div className="text-xs uppercase tracking-wide text-ink-500 font-medium">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink-900 tabular-nums">{value}</div>
      {sub && <div className="text-xs text-ink-500 mt-1">{sub}</div>}
    </div>
  );
}
