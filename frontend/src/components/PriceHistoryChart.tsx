import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { format } from "date-fns";
import type { ProductSnapshot } from "../api";
import { formatPrice } from "../formatPrice";

export function PriceHistoryChart({
  snapshots,
  currency,
}: {
  snapshots: ProductSnapshot[];
  currency?: string | null;
}) {
  if (!snapshots?.length) {
    return <div className="text-sm text-ink-500">No snapshots yet.</div>;
  }
  const cur = currency ?? snapshots[0]?.currency ?? null;
  const data = [...snapshots]
    .sort((a, b) => +new Date(a.captured_at) - +new Date(b.captured_at))
    .map((s) => ({
      t: new Date(s.captured_at).getTime(),
      label: format(new Date(s.captured_at), "MMM d HH:mm"),
      price: s.price_min ?? null,
    }));
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#eef0f2" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} width={48} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
            formatter={(v: number) => [formatPrice(v, cur), "Sale price"]}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#0b0b0c"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
