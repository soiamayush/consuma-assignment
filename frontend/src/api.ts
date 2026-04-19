// API client — thin wrapper over fetch with typed responses.
// Dev: empty VITE_API_URL uses "/api" so Vite's proxy forwards to the FastAPI backend.
// Prod / alternate: set VITE_API_URL=http://localhost:8000 (no trailing slash).
const envBase = import.meta.env.VITE_API_URL as string | undefined;
const BASE =
  envBase && envBase.trim() !== ""
    ? `${envBase.replace(/\/$/, "")}/api`
    : "/api";

export type Competitor = {
  id: number;
  slug: string;
  name: string;
  website: string;
  description: string | null;
  logo_url: string | null;
  brand_weight: number;
  /** Your brand to benchmark peers against */
  is_anchor: boolean;
  product_count: number;
  blog_count: number;
  signal_count: number;
  last_ingested_at: string | null;
};

export type AnalyticsOverview = {
  window_days: number;
  anchor_slug: string | null;
  anchor_name: string | null;
  narrative: string;
  price_landscape: {
    slug: string;
    name: string;
    is_anchor: boolean;
    product_count: number;
    median_listed_price: number | null;
    mean_listed_price: number | null;
    p25_listed_price?: number | null;
    p75_listed_price?: number | null;
    currency: string | null;
  }[];
  top_actives_in_catalog: { active: string; product_hits: number }[];
  actives_by_brand: Record<string, Record<string, number>>;
  signals_by_brand: { slug: string; name: string; is_anchor: boolean; signals: number }[];
  recent_launches_30d: { brand_slug: string; brand_name: string; title: string; first_seen_at: string }[];
  active_cross_brand?: {
    active: string;
    brands_with_hits: number;
    brand_slugs: string[];
    product_hits: number;
  }[];
  data_quality_notes?: string[];
  discount_landscape?: {
    slug: string;
    name: string;
    is_anchor: boolean;
    priceable_skus: number;
    discounted_skus: number;
    discount_share_pct: number;
    median_discount_pct: number;
    max_discount_pct: number;
  }[];
  stock_pressure?: {
    slug: string;
    name: string;
    is_anchor: boolean;
    out_of_stock: number;
    back_in_stock: number;
    net_pressure: number;
  }[];
  launches_per_week?: {
    slug: string;
    name: string;
    is_anchor: boolean;
    weeks: string[];
    counts: number[];
    total: number;
  }[];
  anchor_whitespace?: {
    active: string;
    peer_count: number;
    peer_slugs: string[];
    peer_sku_hits: number;
  }[];
  catalog_size_weekly?: {
    slug: string;
    name: string;
    is_anchor: boolean;
    weeks: string[];
    counts: number[];
    current: number;
  }[];
  top_price_moves?: {
    signal_id: number;
    kind: "PRICE_DROP" | "PRICE_INCREASE";
    brand_slug: string | null;
    brand_name: string | null;
    title: string;
    product_id: number | null;
    old_price: number;
    new_price: number;
    pct_change: number;
    currency: string | null;
    created_at: string;
  }[];
};

export type Signal = {
  id: number;
  competitor_id: number;
  competitor_name: string | null;
  competitor_slug: string | null;
  kind: string;
  entity_type: string;
  entity_id: number | null;
  title: string;
  description: string | null;
  delta: Record<string, any>;
  themes: string[];
  importance: number;
  created_at: string;
};

export type ProductSnapshot = {
  captured_at: string;
  price_min: number | null;
  price_max: number | null;
  compare_at_min?: number | null;
  compare_at_max?: number | null;
  currency: string | null;
  available: boolean;
  variants_count: number;
};

export type Product = {
  id: number;
  competitor_id: number;
  competitor_name: string | null;
  competitor_slug: string | null;
  external_id: string;
  handle: string | null;
  title: string;
  product_type: string | null;
  url: string | null;
  image_url: string | null;
  tags: string[];
  first_seen_at: string;
  last_seen_at: string;
  is_active: boolean;
  latest_price_min: number | null;
  latest_price_max: number | null;
  currency: string | null;
  snapshots?: ProductSnapshot[];
};

export type BlogPost = {
  id: number;
  competitor_id: number;
  competitor_name: string | null;
  title: string;
  url: string;
  summary: string | null;
  published_at: string | null;
  first_seen_at: string;
};

export type DashboardSummary = {
  window_days: number;
  total_signals: number;
  new_products: number;
  price_drops: number;
  price_increases: number;
  blog_posts: number;
  top_themes: { theme: string; count: number }[];
  by_competitor: { slug: string; name: string; signal_count: number; top_importance: number }[];
};

export type SocialMention = {
  id: number;
  competitor_id: number;
  competitor_name: string | null;
  competitor_slug: string | null;
  platform: "youtube" | "news" | "news_bing" | "podcast" | "instagram" | string;
  external_id: string;
  url: string;
  title: string;
  summary: string | null;
  author: string | null;
  author_handle: string | null;
  author_url: string | null;
  thumbnail_url: string | null;
  metric_views: number | null;
  metric_score: number | null;
  metric_comments: number | null;
  published_at: string | null;
  first_seen_at: string;
};

export type TopCreator = {
  competitor_slug: string;
  competitor_name: string;
  platform: string;
  author: string;
  author_handle: string | null;
  author_url: string | null;
  mention_count: number;
  total_views: number | null;
  total_score: number | null;
  sample_url: string | null;
};

export type SocialSummary = {
  window_days: number;
  by_brand: {
    slug: string;
    name: string;
    is_anchor: boolean;
    total: number;
    views: number;
    platforms: Record<string, { mentions: number; views: number }>;
  }[];
};

export type InsightCard = {
  id: string;
  severity: "info" | "success" | "warning" | "danger" | string;
  headline: string;
  detail: string;
  metric: string | null;
  brand_slug: string | null;
  brand_name: string | null;
  href: string | null;
};

export type InsightsResponse = {
  window_days: number;
  anchor_slug: string | null;
  anchor_name: string | null;
  insights: InsightCard[];
};

export type PeerCard = {
  id: number;
  title: string;
  url: string | null;
  image_url: string | null;
  product_type: string | null;
  brand_slug: string;
  brand_name: string;
  is_anchor: boolean;
  price_min: number | null;
  price_max: number | null;
  compare_at_min: number | null;
  currency: string | null;
};

export type ProductPeers = {
  self: PeerCard;
  category: string | null;
  peer_count?: number;
  cheapest: PeerCard | null;
  closest: PeerCard | null;
  most_expensive: PeerCard | null;
  alternatives: PeerCard[];
  note?: string;
};

export type CompareSku = {
  id: number;
  title: string;
  url: string | null;
  image_url: string | null;
  price_min: number | null;
  price_max: number | null;
  compare_at_min: number | null;
  compare_at_max: number | null;
  currency: string | null;
};

export type CompareBrandRow = {
  slug: string;
  name: string;
  is_anchor: boolean;
  sku_count: number;
  priceable_skus: number;
  currency: string | null;
  min_price: number | null;
  max_price: number | null;
  p25: number | null;
  median: number | null;
  p75: number | null;
  discount_share_pct: number;
  median_discount_pct: number;
  max_discount_pct: number;
  /** Median delta vs anchor median, signed % (positive = pricier than anchor). */
  anchor_delta_pct: number | null;
  cheapest: CompareSku[];
  most_expensive: CompareSku[];
  all_skus: CompareSku[];
};

export type CompareResponse = {
  scope: {
    category: string | null;
    keyword: string | null;
    in_scope_total: number;
    anchor_in_scope: number;
  };
  anchor_slug: string | null;
  anchor_name: string | null;
  anchor_median_price: number | null;
  categories: { category: string; sku_count: number }[];
  keyword_suggestions: { keyword: string; hits: number }[];
  per_brand: CompareBrandRow[];
};

export type IngestionRun = {
  id: number;
  source_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  items_seen: number;
  items_new: number;
  items_changed: number;
  signals_created: number;
  error: string | null;
};

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

/** Paged result: same JSON body as before plus the X-Total-Count header. */
export type Page<T> = { items: T[]; total: number };

async function jPage<T>(path: string, init?: RequestInit): Promise<Page<T>> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${body.slice(0, 200)}`);
  }
  const items = (await res.json()) as T[];
  const totalHeader = res.headers.get("X-Total-Count");
  const total = totalHeader != null ? Number(totalHeader) : items.length;
  return { items, total: Number.isFinite(total) ? total : items.length };
}

/** Anchor brand (Minimalist). Returns null if not configured (404). */
async function fetchAnchorBrand(): Promise<Competitor | null> {
  const res = await fetch(`${BASE}/competitors/anchor`, {
    headers: { "Content-Type": "application/json" },
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${body.slice(0, 200)}`);
  }
  return (await res.json()) as Competitor;
}

export const api = {
  /** Peers only unless `includeAnchor` is true (e.g. feed filter dropdown). */
  competitors: (includeAnchor = false) =>
    j<Competitor[]>(`/competitors${includeAnchor ? "?include_anchor=true" : ""}`),
  anchorBrand: () => fetchAnchorBrand(),
  competitor: (slug: string) => j<Competitor>(`/competitors/${slug}`),
  signals: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return j<Signal[]>(`/signals${qs ? `?${qs}` : ""}`);
  },
  signalsPaged: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return jPage<Signal>(`/signals${qs ? `?${qs}` : ""}`);
  },
  dashboard: (windowDays = 14) =>
    j<DashboardSummary>(`/dashboard/summary?window_days=${windowDays}`),
  analyticsOverview: (windowDays = 14) =>
    j<AnalyticsOverview>(`/analytics/overview?window_days=${windowDays}`),
  insights: (windowDays = 14) =>
    j<InsightsResponse>(`/analytics/insights?window_days=${windowDays}`),
  products: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return j<Product[]>(`/products${qs ? `?${qs}` : ""}`);
  },
  productsPaged: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return jPage<Product>(`/products${qs ? `?${qs}` : ""}`);
  },
  product: (id: number) => j<Product>(`/products/${id}`),
  productPeers: (id: number) => j<ProductPeers>(`/products/${id}/peers`),
  blogPosts: (competitor?: string) =>
    j<BlogPost[]>(`/blog-posts${competitor ? `?competitor=${competitor}` : ""}`),
  runs: () => j<IngestionRun[]>("/ingest/runs"),
  runsPaged: (limit = 30, offset = 0) =>
    jPage<IngestionRun>(`/ingest/runs?limit=${limit}&offset=${offset}`),
  socialMentionsPaged: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return jPage<SocialMention>(`/social${qs ? `?${qs}` : ""}`);
  },
  topCreators: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return j<TopCreator[]>(`/social/creators${qs ? `?${qs}` : ""}`);
  },
  socialSummary: (windowDays = 90) =>
    j<SocialSummary>(`/social/summary?window_days=${windowDays}`),
  compare: (params: { category?: string; keyword?: string } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return j<CompareResponse>(`/compare${qs ? `?${qs}` : ""}`);
  },
  /** Set `VITE_INGEST_USE_QUEUE=true` only when a Redis RQ worker is running (e.g. docker worker). */
  triggerRun: (slugs?: string[], sync = false) => {
    const useQueue = import.meta.env.VITE_INGEST_USE_QUEUE === "true";
    return j<any>(`/ingest/run?sync=${sync}&use_queue=${useQueue}`, {
      method: "POST",
      body: JSON.stringify({ slugs: slugs ?? null }),
    });
  },
  chatHealth: () =>
    j<{ configured: boolean; model: string | null; history_window: number; hint: string | null }>(
      "/chat/health",
    ),
  chatSuggested: () => j<{ questions: string[] }>("/chat/suggested"),
  /** Per-view AI commentary. `view` ids are defined in backend ai_explain.VIEW_PROMPTS. */
  aiExplain: (body: {
    view: string;
    payload: Record<string, unknown>;
    question?: string;
    nonce?: string;
  }) =>
    j<{ view: string; text: string; model: string | null; cached: boolean }>(`/ai/explain`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

/**
 * Streaming chat helper. Streams Server-Sent Events from POST /api/chat and
 * invokes `onChunk(text)` for each text chunk. Returns the full assembled text
 * once the stream ends. Throws on transport error.
 */
export async function streamChat(
  body: { message: string; history: { role: "user" | "assistant"; text: string }[]; window_days?: number },
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const t = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} – ${t.slice(0, 200)}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let assembled = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE events are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const eventBlock = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const dataLines = eventBlock
        .split("\n")
        .filter((ln) => ln.startsWith("data:"))
        .map((ln) => ln.slice(5).replace(/^ /, ""));
      const data = dataLines.join("\n");
      if (!data) continue;
      if (data === "[DONE]") {
        return assembled;
      }
      // Skip control beacons (e.g. `{"event": "start"}` — Python json.dumps uses a space after `:`).
      try {
        const o = JSON.parse(data) as { event?: string };
        if (o && typeof o === "object" && o.event === "start") continue;
      } catch {
        /* not JSON — stream as normal assistant text */
      }
      assembled += data;
      onChunk(data);
    }
  }
  return assembled;
}
