/** Format a numeric catalog price with the right symbol / ISO code. */

export function formatPrice(amount: number | null | undefined, currency: string | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "—";
  const c = (currency || "USD").toUpperCase();
  if (c === "INR") {
    return `₹${amount.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  }
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: c }).format(amount);
  } catch {
    return `${c} ${amount.toFixed(2)}`;
  }
}
