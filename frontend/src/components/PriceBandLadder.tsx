import { formatPrice } from "../formatPrice";

type Row = {
  slug: string;
  name: string;
  is_anchor: boolean;
  min_price: number | null;
  max_price: number | null;
  p25: number | null;
  median: number | null;
  p75: number | null;
  currency: string | null;
};

type Props = {
  rows: Row[];
  /** Optional anchor median price drawn as a vertical reference line across all rows. */
  anchorReference?: number | null;
  /** Optional unified currency to display when row currency is null. */
  fallbackCurrency?: string | null;
  /** Force a maximum X value (otherwise auto from data). */
  maxOverride?: number;
  height?: number;
};

const ANCHOR_COLOR = "#bf3f5c";
const ANCHOR_BAND = "rgba(191, 63, 92, 0.18)";
const PEER_BAND = "rgba(75, 85, 99, 0.16)";
const PEER_COLOR = "#4b5563";

export function PriceBandLadder({
  rows,
  anchorReference,
  fallbackCurrency,
  maxOverride,
  height,
}: Props) {
  const visible = rows.filter((r) => r.median != null);
  if (visible.length === 0) {
    return <p className="text-xs text-ink-500">Not enough priced SKUs in scope to render a ladder.</p>;
  }

  const allMax = Math.max(
    ...visible.map((r) => r.max_price ?? r.p75 ?? r.median ?? 0),
    anchorReference ?? 0,
    1,
  );
  const xMax = maxOverride ?? allMax * 1.05;
  const labelW = 130;
  const valueW = 110;
  const padL = 12;
  const padR = 12;
  const rowH = 30;
  const usableW = 720; // intrinsic; SVG is responsive via width=100%
  const bandLeft = padL + labelW;
  const bandRight = usableW - padR - valueW;
  const bandWidth = bandRight - bandLeft;

  const xOf = (v: number) => bandLeft + (Math.max(0, v) / xMax) * bandWidth;

  const totalH = height ?? rowH * visible.length + 28;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${usableW} ${totalH}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* X axis ticks (rough) */}
        {[0, 0.25, 0.5, 0.75, 1].map((q) => {
          const x = bandLeft + q * bandWidth;
          const v = q * xMax;
          return (
            <g key={q}>
              <line x1={x} x2={x} y1={4} y2={totalH - 18} stroke="#e5e7eb" strokeDasharray="2 4" />
              <text x={x} y={totalH - 4} fontSize="9" textAnchor="middle" fill="#6b7280">
                {Math.round(v)}
              </text>
            </g>
          );
        })}

        {/* Anchor reference */}
        {anchorReference != null && (
          <g>
            <line
              x1={xOf(anchorReference)}
              x2={xOf(anchorReference)}
              y1={4}
              y2={totalH - 18}
              stroke={ANCHOR_COLOR}
              strokeDasharray="4 3"
              strokeWidth={1.5}
            />
            <text
              x={xOf(anchorReference)}
              y={12}
              fontSize="9"
              textAnchor="middle"
              fill={ANCHOR_COLOR}
              fontWeight={600}
            >
              your median
            </text>
          </g>
        )}

        {visible.map((r, i) => {
          const yMid = 18 + i * rowH + rowH / 2;
          const color = r.is_anchor ? ANCHOR_COLOR : PEER_COLOR;
          const band = r.is_anchor ? ANCHOR_BAND : PEER_BAND;
          const minX = xOf(r.min_price ?? r.p25 ?? r.median!);
          const maxX = xOf(r.max_price ?? r.p75 ?? r.median!);
          const p25X = xOf(r.p25 ?? r.median!);
          const p75X = xOf(r.p75 ?? r.median!);
          const medX = xOf(r.median!);
          const cur = r.currency || fallbackCurrency || null;
          return (
            <g key={r.slug}>
              <text
                x={padL}
                y={yMid + 3}
                fontSize="11"
                fill="#111827"
                fontWeight={r.is_anchor ? 700 : 500}
              >
                {r.name}{r.is_anchor ? " ★" : ""}
              </text>
              <line x1={minX} x2={maxX} y1={yMid} y2={yMid} stroke={color} strokeWidth={1} opacity={0.55} />
              <line x1={minX} x2={minX} y1={yMid - 4} y2={yMid + 4} stroke={color} strokeWidth={1} opacity={0.55} />
              <line x1={maxX} x2={maxX} y1={yMid - 4} y2={yMid + 4} stroke={color} strokeWidth={1} opacity={0.55} />
              <rect
                x={p25X}
                y={yMid - 7}
                width={Math.max(2, p75X - p25X)}
                height={14}
                fill={band}
                stroke={color}
                strokeWidth={1}
                rx={2}
              />
              <circle cx={medX} cy={yMid} r={4} fill={color} />
              <text
                x={usableW - padR}
                y={yMid + 3}
                fontSize="10"
                textAnchor="end"
                fill="#374151"
              >
                {formatPrice(r.median!, cur)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
