/**
 * Backend stores naive UTC (see backend `time_utils.utc_now`). JSON often omits
 * a `Z` suffix, so `new Date("2025-04-19T20:18:01")` is interpreted as *local* wall
 * time in browsers — wrong by several hours vs IST/UTC. We normalise to UTC first.
 */
import { formatDistanceToNow } from "date-fns";
import { enIN } from "date-fns/locale";
import { formatInTimeZone } from "date-fns-tz";

export const TZ_IST = "Asia/Kolkata";

/** Parse API datetime string as an absolute UTC instant. */
export function parseApiUtc(iso: string | null | undefined): Date {
  if (iso == null || String(iso).trim() === "") return new Date(NaN);
  const t = String(iso).trim();
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(t)) return new Date(t);
  const isoLike = t.includes("T") ? t : t.replace(" ", "T");
  return new Date(`${isoLike}Z`);
}

/** Format instant in India Standard Time (en-IN style). */
export function formatInIst(iso: string | null | undefined, pattern: string): string {
  const d = parseApiUtc(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return formatInTimeZone(d, TZ_IST, pattern, { locale: enIN });
}

/** Relative time from now, based on correctly parsed API UTC. */
export function distanceFromApiUtc(iso: string | null | undefined): string {
  const d = parseApiUtc(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return formatDistanceToNow(d, { addSuffix: true, locale: enIN });
}
