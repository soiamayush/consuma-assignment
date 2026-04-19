import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bot, Loader2, RotateCcw, Send, Sparkles, User as UserIcon } from "lucide-react";
import { api, streamChat } from "../api";
import { Markdown } from "../components/Markdown";

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

  const health = useQuery({ queryKey: ["chat-health"], queryFn: api.chatHealth });
  const suggested = useQuery({ queryKey: ["chat-suggested"], queryFn: api.chatSuggested });

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
    const newTurns: Turn[] = [...turns, { role: "user", text }, { role: "assistant", text: "" }];
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
            updated[updated.length - 1] = { ...last, text: last.text + chunk };
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
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Sparkles size={20} className="text-amber-600" /> Ask the analyst
          </h1>
          <p className="text-ink-500 text-sm mt-1 max-w-2xl">
            A live competitive-intel chat for the {health.data?.model ? <code>{health.data.model}</code> : "anchor"} brand.
            Grounded in the same data the rest of the app shows — no made-up prices, no hallucinated peers.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="text-ink-500">Window:</label>
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`btn ${windowDays === d ? "bg-ink-900 text-white" : "btn-ghost"}`}
            >
              {d}d
            </button>
          ))}
          <button
            onClick={reset}
            className="btn btn-ghost"
            title="Clear this conversation"
            disabled={busy && !!abortRef.current}
          >
            <RotateCcw size={14} /> Reset
          </button>
        </div>
      </div>

      {health.data && !health.data.configured && (
        <div className="card p-4 border-amber-300 bg-amber-50/60 text-sm">
          <div className="font-semibold mb-1">Gemini isn't configured yet</div>
          <p className="text-ink-700">
            {health.data.hint ??
              "Add GEMINI_API_KEY to backend/.env and restart the backend."}
          </p>
          <p className="text-ink-600 mt-2 text-xs">
            The data brief and tools are ready; the chat will work the moment the key is loaded.
          </p>
        </div>
      )}

      <div
        ref={scrollRef}
        className="card p-4 h-[60vh] overflow-y-auto space-y-4 bg-ink-50/40"
      >
        {isEmpty && (
          <div className="text-center text-ink-500 text-sm py-12 space-y-3">
            <p>
              Try one of these to get started:
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {(suggested.data?.questions ?? []).map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  disabled={busy || !health.data?.configured}
                  className="chip text-left max-w-[320px] hover:bg-ink-200 disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <Bubble key={i} turn={t} streaming={busy && i === turns.length - 1 && t.role === "assistant"} />
        ))}
        {error && (
          <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-md p-2">
            {error}
          </div>
        )}
      </div>

      <form
        className="flex gap-2"
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
              : "Add GEMINI_API_KEY to backend/.env to start chatting…"
          }
          className="flex-1 text-sm border border-ink-200 rounded-md px-3 py-2 bg-white resize-none focus:outline-none focus:border-ink-500"
          disabled={busy || !health.data?.configured}
        />
        <button
          type="submit"
          className="btn-primary self-stretch flex items-center gap-2"
          disabled={busy || !draft.trim() || !health.data?.configured}
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          {busy ? "Thinking" : "Send"}
        </button>
      </form>

      <p className="text-[11px] text-ink-400 text-center">
        Conversation is stored in your browser only. Reset clears local history but does not affect the database.
      </p>
    </div>
  );
}

function Bubble({ turn, streaming }: { turn: Turn; streaming?: boolean }) {
  const isUser = turn.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-ink-900 text-white grid place-items-center shrink-0">
          <Bot size={16} />
        </div>
      )}
      <div
        className={`rounded-2xl px-4 py-2.5 max-w-[78%] shadow-sm ${
          isUser
            ? "bg-ink-900 text-white"
            : "bg-white border border-ink-200 text-ink-900"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{turn.text}</p>
        ) : (
          <>
            {turn.text ? (
              <Markdown text={turn.text} />
            ) : streaming ? (
              <span className="inline-flex items-center gap-2 text-sm text-ink-500">
                <Loader2 size={14} className="animate-spin" /> reading the landscape…
              </span>
            ) : null}
            {streaming && turn.text && (
              <span className="inline-block w-1.5 h-4 bg-ink-700 ml-0.5 align-middle animate-pulse" />
            )}
          </>
        )}
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-amber-500 text-white grid place-items-center shrink-0">
          <UserIcon size={16} />
        </div>
      )}
    </div>
  );
}
