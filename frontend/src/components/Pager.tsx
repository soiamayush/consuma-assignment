import { ChevronLeft, ChevronRight } from "lucide-react";

type Props = {
  total: number;
  offset: number;
  limit: number;
  onOffset: (next: number) => void;
  onLimit?: (next: number) => void;
  pageSizes?: number[];
  loading?: boolean;
  /** Optional label for the records being paged (defaults to "items"). */
  label?: string;
};

/**
 * Lightweight server-driven pager. Trusts a `total` from `X-Total-Count`.
 * Hides itself if there is nothing to page through.
 */
export function Pager({
  total,
  offset,
  limit,
  onOffset,
  onLimit,
  pageSizes = [25, 50, 100],
  loading,
  label = "items",
}: Props) {
  const safeLimit = Math.max(1, limit);
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + safeLimit, total);
  const canPrev = offset > 0;
  const canNext = end < total;

  if (total === 0 && !loading) {
    return null;
  }

  return (
    <div className="flex items-center justify-between gap-3 text-xs text-ink-600 mt-3 flex-wrap">
      <div>
        Showing <span className="tabular-nums font-medium">{start.toLocaleString()}</span>–
        <span className="tabular-nums font-medium">{end.toLocaleString()}</span> of{" "}
        <span className="tabular-nums font-medium">{total.toLocaleString()}</span> {label}
        {loading && <span className="ml-2 text-ink-400">refreshing…</span>}
      </div>
      <div className="flex items-center gap-2">
        {onLimit && (
          <select
            className="text-xs border border-ink-200 rounded-md px-2 py-1 bg-white"
            value={safeLimit}
            onChange={(e) => {
              onLimit(Number(e.target.value));
              onOffset(0);
            }}
          >
            {pageSizes.map((s) => (
              <option key={s} value={s}>
                {s} / page
              </option>
            ))}
          </select>
        )}
        <button
          className="btn btn-ghost text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={() => onOffset(Math.max(0, offset - safeLimit))}
          disabled={!canPrev || loading}
          aria-label="Previous page"
        >
          <ChevronLeft size={14} /> Prev
        </button>
        <button
          className="btn btn-ghost text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={() => onOffset(offset + safeLimit)}
          disabled={!canNext || loading}
          aria-label="Next page"
        >
          Next <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
