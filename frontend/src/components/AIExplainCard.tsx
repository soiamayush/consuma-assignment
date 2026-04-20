import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Send, Sparkles } from "lucide-react";
import { api } from "../api";
import { Markdown } from "./Markdown";

type Props = {
  view: string;
  payload: Record<string, unknown>;
  title: string;
  subtitle?: string;
  manualTrigger?: boolean;
  allowFollowUp?: boolean;
  className?: string;
};
export function AIExplainCard({
  view,
  payload,
  title,
  subtitle,
  manualTrigger = false,
  allowFollowUp = true,
  className,
}: Props) {
  const [text, setText] = useState<string>("");
  const [model, setModel] = useState<string | null>(null);
  const [cached, setCached] = useState<boolean>(false);
  const [followUp, setFollowUp] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const lastKeyRef = useRef<string | null>(null);

  const payloadKey = useMemo(() => {
    try {
      return JSON.stringify(payload);
    } catch {
      return String(Math.random());
    }
  }, [payload]);

  const mutation = useMutation({
    mutationFn: (opts: { question?: string; force?: boolean }) =>
      api.aiExplain({
        view,
        payload,
        question: opts.question,
        nonce: opts.force ? `${Date.now()}` : undefined,
      }),
    onSuccess: (res) => {
      setText(res.text);
      setModel(res.model);
      setCached(res.cached);
      setError(null);
    },
    onError: (err: any) => {
      setError(err?.message ?? "Failed to generate commentary.");
    },
  });

  // Auto-fetch on mount and whenever the payload signature changes.
  useEffect(() => {
    if (manualTrigger) return;
    if (lastKeyRef.current === payloadKey) return;
    lastKeyRef.current = payloadKey;
    mutation.mutate({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payloadKey, manualTrigger]);

  const handleAsk = () => {
    const q = followUp.trim();
    if (!q) return;
    mutation.mutate({ question: q, force: true });
    setFollowUp("");
  };

  const handleRegen = () => {
    mutation.mutate({ force: true });
  };

  const isFresh = mutation.isPending;

  return (
    <section
      className={`relative overflow-hidden rounded-2xl border border-plum-200/70 bg-gradient-to-br from-plum-50/80 via-blush-50/60 to-white/80 backdrop-blur-md p-5 space-y-3 shadow-glass ${
        className ?? ""
      }`}
    >
      <div
        aria-hidden
        className="absolute -top-12 -right-10 h-40 w-40 rounded-full bg-gradient-to-br from-plum-200/60 to-blush-200/40 blur-3xl opacity-70"
      />
      <header className="relative flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-semibold text-[15px] flex items-center gap-2 text-ink-900">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-plum-500 to-blush-500 text-white shadow-sm">
              <Sparkles size={12} />
            </span>
            {title}
            {model && (
              <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-plum-700/80 bg-white/70 border border-plum-200 rounded-full px-2 py-0.5">
                {model}
                {cached ? " · cached" : ""}
              </span>
            )}
          </h3>
          {subtitle && (
            <p className="text-xs text-ink-500 mt-1 ml-9">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {manualTrigger && !text && !isFresh && (
            <button
              type="button"
              onClick={() => mutation.mutate({})}
              className="text-xs px-3 py-1.5 rounded-full bg-gradient-to-r from-plum-600 to-blush-600 text-white hover:opacity-95 inline-flex items-center gap-1.5 shadow-sm"
            >
              <Sparkles size={12} /> Generate
            </button>
          )}
          {(text || error) && (
            <button
              type="button"
              onClick={handleRegen}
              disabled={isFresh}
              className="text-xs px-2.5 py-1.5 rounded-full border border-ink-200 bg-white/70 text-ink-700 hover:bg-white inline-flex items-center gap-1.5 disabled:opacity-60"
              title="Regenerate"
            >
              {isFresh ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <RefreshCw size={12} />
              )}
              Regenerate
            </button>
          )}
        </div>
      </header>

      <div className="relative min-h-[2.5rem]">
        {isFresh && !text && (
          <p className="text-xs text-ink-500 inline-flex items-center gap-2">
            <Loader2 size={12} className="animate-spin" />
            Consulting the analyst…
          </p>
        )}
        {!isFresh && !text && !error && !manualTrigger && (
          <p className="text-xs text-ink-500">No commentary yet.</p>
        )}
        {error && (
          <p className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-2.5 py-2">
            {error}
          </p>
        )}
        {text && <Markdown text={text} />}
      </div>

      {allowFollowUp && (text || error) && (
        <div className="relative pt-3 border-t border-plum-100">
          <label className="text-[11px] text-ink-500 block mb-1.5 uppercase tracking-[0.14em] font-medium">
            Ask a follow-up about this view
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAsk();
              }}
              placeholder="Which peer should we benchmark first?"
              className="flex-1 text-sm px-3 py-2 rounded-full border border-ink-200 bg-white/80 focus:outline-none focus:ring-2 focus:ring-plum-300 focus:border-plum-300"
              disabled={isFresh}
            />
            <button
              type="button"
              onClick={handleAsk}
              disabled={isFresh || !followUp.trim()}
              className="text-xs px-3.5 py-2 rounded-full bg-ink-900 text-white hover:bg-ink-800 inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {isFresh ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Send size={12} />
              )}
              Ask
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
