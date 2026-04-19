import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Pager } from "../components/Pager";
import { distanceFromApiUtc, formatInIst, parseApiUtc } from "../time";

export function RunsPage() {
  const [limit, setLimit] = useState(30);
  const [offset, setOffset] = useState(0);
  const runs = useQuery({
    queryKey: ["runs", limit, offset],
    queryFn: () => api.runsPaged(limit, offset),
    refetchInterval: 5000,
    placeholderData: keepPreviousData,
  });
  const items = runs.data?.items ?? [];
  const total = runs.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ingestion runs</h1>
        <p className="text-ink-500 text-sm mt-1">
          Observability for each scrape run · polled every 5s.
        </p>
      </div>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-xs text-ink-500 bg-ink-50">
            <tr>
              <th className="p-3 text-left">
                Started <span className="font-normal text-ink-400">(IST)</span>
              </th>
              <th className="p-3 text-left">
                Finished <span className="font-normal text-ink-400">(IST)</span>
              </th>
              <th className="p-3 text-left">Source</th>
              <th className="p-3 text-right">Seen</th>
              <th className="p-3 text-right">New</th>
              <th className="p-3 text-right">Changed</th>
              <th className="p-3 text-right">Signals</th>
              <th className="p-3 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-t border-ink-100">
                <td className="p-3">
                  <div className="font-medium tabular-nums">
                    {formatInIst(r.started_at, "d MMM yyyy, hh:mm:ss a")}
                  </div>
                  <div className="text-xs text-ink-500 mt-0.5" title={parseApiUtc(r.started_at).toISOString()}>
                    {distanceFromApiUtc(r.started_at)}
                  </div>
                </td>
                <td className="p-3 text-ink-600">
                  {r.finished_at ? (
                    <span className="tabular-nums">
                      {formatInIst(r.finished_at, "d MMM yyyy, hh:mm:ss a")}
                    </span>
                  ) : (
                    <span className="text-amber-600">running…</span>
                  )}
                </td>
                <td className="p-3 font-mono text-xs">#{r.source_id}</td>
                <td className="p-3 text-right tabular-nums">{r.items_seen}</td>
                <td className="p-3 text-right tabular-nums text-emerald-700">
                  {r.items_new || "—"}
                </td>
                <td className="p-3 text-right tabular-nums">{r.items_changed || "—"}</td>
                <td className="p-3 text-right tabular-nums font-semibold">
                  {r.signals_created || "—"}
                </td>
                <td className="p-3">
                  <span
                    className={
                      r.status === "ok"
                        ? "chip bg-emerald-50 text-emerald-700 border-emerald-200"
                        : r.status === "error"
                        ? "chip bg-rose-50 text-rose-700 border-rose-200"
                        : "chip"
                    }
                  >
                    {r.status}
                  </span>
                  {r.error && (
                    <div className="text-xs text-rose-600 mt-1 line-clamp-1">{r.error}</div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        total={total}
        offset={offset}
        limit={limit}
        onOffset={setOffset}
        onLimit={setLimit}
        pageSizes={[30, 60, 120]}
        loading={runs.isFetching}
        label="runs"
      />
    </div>
  );
}
