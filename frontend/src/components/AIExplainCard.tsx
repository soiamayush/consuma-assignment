import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Send, Sparkles } from "lucide-react";
import { api } from "../api";
import { Markdown } from "./Markdown";

type Props = {
  /** Backend view id, e.g. "dashboard_summary", "compare_scope". */
  view: string;
  /** Compact JSON payload — only the data shown on screen for this view. */
  payload: Record<string, unknown>;
  /** Card title shown in the header (e.g. "AI executive read"). */
  title: string;
  /** Optional one-line subtitle under the title. */
  subtitle?: string;
  /** Set true for opt-in cards (don't auto-call Gemini until clicked). */
  manualTrigger?: boolean;
  /** Show the "Ask a follow-up about this view" input. Default true. */
  allowFollowUp?: boolean;
  /** Visual height for the body. Default 'auto'. */
  className?: string;
};

/**
 * Reusable AI commentary card.
 *
 * Auto-generates analyst commentary on mount (unless ``manualTrigger``), refetches
 * when the payload meaningfully changes, and lets the user ask one-shot follow-up
 * questions scoped to the same view payload.
 */
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
      className={`card border border-violet-200 bg-gradient-to-br from-violet-50/70 to-white p-4 space-y-3 ${
        className ?? ""
      }`}
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Sparkles size={14} className="text-violet-600" />
            {title}
            {model && (
              <span className="text-[10px] font-normal uppercase tracking-wide text-violet-700/80 bg-white/70 border border-violet-200 rounded px-1.5 py-0.5">
                {model}
                {cached ? " · cached" : ""}
              </span>
            )}
          </h3>
          {subtitle && <p className="text-xs text-ink-500 mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {manualTrigger && !text && !isFresh && (
            <button
              type="button"
              onClick={() => mutation.mutate({})}
              className="text-xs px-2.5 py-1 rounded-md bg-violet-600 text-white hover:bg-violet-700 inline-flex items-center gap-1.5"
            >
              <Sparkles size={12} /> Generate
            </button>
          )}
          {(text || error) && (
            <button
              type="button"
              onClick={handleRegen}
              disabled={isFresh}
              className="text-xs px-2 py-1 rounded-md border border-ink-200 text-ink-700 hover:bg-white inline-flex items-center gap-1.5 disabled:opacity-60"
              title="Regenerate (bypasses cache)"
            >
              {isFresh ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Regenerate
            </button>
          )}
        </div>
      </header>

      <div className="min-h-[2.5rem]">
        {isFresh && !text && (
          <p className="text-xs text-ink-500 inline-flex items-center gap-2">
            <Loader2 size={12} className="animate-spin" />
            Asking the analyst…
          </p>
        )}
        {!isFresh && !text && !error && !manualTrigger && (
          <p className="text-xs text-ink-500">No commentary yet.</p>
        )}
        {error && (
          <p className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded px-2 py-1.5">
            {error}
          </p>
        )}
        {text && <Markdown text={text} />}
      </div>

      {allowFollowUp && (text || error) && (
        <div className="pt-2 border-t border-violet-100">
          <label className="text-[11px] text-ink-500 block mb-1">
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
              placeholder="e.g. Which peer should we benchmark first?"
              className="flex-1 text-sm px-2.5 py-1.5 rounded-md border border-ink-200 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300"
              disabled={isFresh}
            />
            <button
              type="button"
              onClick={handleAsk}
              disabled={isFresh || !followUp.trim()}
              className="text-xs px-2.5 py-1.5 rounded-md bg-ink-900 text-white hover:bg-ink-800 inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {isFresh ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
              Ask
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
