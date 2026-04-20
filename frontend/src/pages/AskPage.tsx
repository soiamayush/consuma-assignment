import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
  User as UserIcon,
} from "lucide-react";
import { api, streamChat } from "../api";
import { Markdown } from "../components/Markdown";
import { PageHero } from "../components/PageHero";

type Turn = { role: "user" | "assistant"; text: string };

const STORAGE_KEY = "cw-chat-history-v1";

export function AskPage() {
  const [turns, setTurns] = useState<Turn[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw) as Turn[];
    } catch {
      /* ignore */
    }
    return [];
  });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [windowDays, setWindowDays] = useState(14);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const health = useQuery({
    queryKey: ["chat-health"],
    queryFn: api.chatHealth,
  });
  const suggested = useQuery({
    queryKey: ["chat-suggested"],
    queryFn: api.chatSuggested,
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(turns));
    } catch {
      /* ignore */
    }
  }, [turns]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns, busy]);

  async function send(message: string) {
    const text = message.trim();
    if (!text || busy) return;
    setError(null);
    setDraft("");
    const newTurns: Turn[] = [
      ...turns,
      { role: "user", text },
      { role: "assistant", text: "" },
    ];
    setTurns(newTurns);
    setBusy(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await streamChat(
        { message: text, history: newTurns.slice(0, -2), window_days: windowDays },
        (chunk) => {
          setTurns((cur) => {
            const last = cur[cur.length - 1];
            if (!last || last.role !== "assistant") return cur;
            const updated = [...cur];
            updated[updated.length - 1] = {
              ...last,
              text: last.text + chunk,
            };
            return updated;
          });
        },
        ctrl.signal,
      );
    } catch (exc: unknown) {
      const msg = exc instanceof Error ? exc.message : "stream failed";
      setError(msg);
      setTurns((cur) => {
        const last = cur[cur.length - 1];
        if (!last || last.role !== "assistant" || last.text) return cur;
        return cur.slice(0, -1);
      });
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function reset() {
    abortRef.current?.abort();
    setTurns([]);
    setDraft("");
    setError(null);
  }

  const isEmpty = turns.length === 0;

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow="Ask the analyst"
        theme="plum"
        title={
          <>
            A private analyst,{" "}
            <span className="gradient-text">on demand</span>.
          </>
        }
        subtitle={
          <>
            Ask anything about your brand, peers, pricing, launches, or editorial
            chatter. Every answer is grounded in the same catalog the rest of
            the app shows — no hallucinations, no made-up prices.
          </>
        }
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 p-1 rounded-full bg-white/70 border border-white/70 shadow-sm">
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => setWindowDays(d)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                    windowDays === d
                      ? "bg-ink-900 text-white shadow-sm"
                      : "text-ink-600 hover:text-ink-900"
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>
            <button onClick={reset} className="btn-ghost text-xs" title="Clear conversation">
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        }
      />

      {health.data && !health.data.configured && (
        <div className="rounded-2xl border border-accent-200 bg-gradient-to-br from-accent-50/90 to-cream-50/70 backdrop-blur-md p-4 text-sm shadow-glass">
          <div className="font-semibold mb-1 flex items-center gap-2">
            <Sparkles size={14} className="text-accent-600" />
            The assistant is resting
          </div>
          <p className="text-ink-700">
            {health.data.hint ??
              "Live chat isn't available right now. Try again in a moment."}
          </p>
          <p className="text-ink-600 mt-2 text-xs">
            Everything else — dashboards, comparisons, buzz — stays fully
            functional while the assistant is offline.
          </p>
        </div>
      )}

      <div
        ref={scrollRef}
        className="card p-4 md:p-6 h-[62vh] overflow-y-auto space-y-4"
      >
        {isEmpty && (
          <div className="text-center text-ink-500 text-sm py-8 space-y-4">
            <div className="mx-auto h-12 w-12 rounded-full bg-gradient-to-br from-plum-500 to-blush-500 text-white grid place-items-center shadow-lift">
              <Sparkles size={20} />
            </div>
            <p className="text-ink-700 text-base font-medium">
              Not sure where to begin? Try one of these.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-2xl mx-auto">
              {(suggested.data?.questions ?? []).map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  disabled={busy || !health.data?.configured}
                  className="text-left text-sm px-3 py-2 rounded-xl border border-ink-200/80 bg-white/80 hover:bg-white hover:border-plum-200 hover:shadow-sm text-ink-700 max-w-[340px] disabled:opacity-50 transition"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <Bubble
            key={i}
            turn={t}
            streaming={
              busy && i === turns.length - 1 && t.role === "assistant"
            }
          />
        ))}
        {error && (
          <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2.5">
            {error}
          </div>
        )}
      </div>

      <form
        className="flex gap-2 items-end"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
          rows={2}
          placeholder={
            health.data?.configured
              ? "Ask anything about your competitive landscape… (Enter to send, Shift+Enter for newline)"
              : "The assistant is resting — try again in a moment…"
          }
          className="flex-1 text-sm border border-ink-200 rounded-2xl px-4 py-3 bg-white/90 backdrop-blur resize-none focus:outline-none focus:border-plum-400 focus:ring-2 focus:ring-plum-200/60 shadow-sm"
          disabled={busy || !health.data?.configured}
        />
        <button
          type="submit"
          className="btn-accent px-4 py-3 rounded-2xl"
          disabled={busy || !draft.trim() || !health.data?.configured}
        >
          {busy ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}
          <span className="hidden sm:inline">
            {busy ? "Thinking" : "Send"}
          </span>
        </button>
      </form>

      <p className="text-[11px] text-ink-400 text-center">
        Conversations are stored only in your browser. Reset clears local
        history without affecting any saved data.
      </p>
    </div>
  );
}

function Bubble({ turn, streaming }: { turn: Turn; streaming?: boolean }) {
  const isUser = turn.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-plum-600 to-blush-500 text-white grid place-items-center shrink-0 shadow-sm">
          <Bot size={16} />
        </div>
      )}
      <div
        className={`rounded-2xl px-4 py-3 max-w-[78%] shadow-sm ${
          isUser
            ? "bg-gradient-to-br from-ink-900 to-plum-800 text-white"
            : "bg-white/90 backdrop-blur border border-white/70 text-ink-900"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {turn.text}
          </p>
        ) : (
          <>
            {turn.text ? (
              <Markdown text={turn.text} />
            ) : streaming ? (
              <span className="inline-flex items-center gap-2 text-sm text-ink-500">
                <Loader2 size={14} className="animate-spin" /> reading the
                landscape…
              </span>
            ) : null}
            {streaming && turn.text && (
              <span className="inline-block w-1.5 h-4 bg-ink-700 ml-0.5 align-middle animate-pulse" />
            )}
          </>
        )}
      </div>
      {isUser && (
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-500 to-blush-500 text-white grid place-items-center shrink-0 shadow-sm">
          <UserIcon size={16} />
        </div>
      )}
    </div>
  );
}
