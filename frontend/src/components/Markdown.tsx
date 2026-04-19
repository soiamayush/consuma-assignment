import { Fragment } from "react";

/**
 * Tiny safe markdown renderer for the chat bubble.
 *
 * We intentionally avoid a full parser dependency — Gemini's output for our
 * prompts is constrained: paragraphs, bullet/numbered lists, bold, italic,
 * inline code, and links. This handles those cases and falls back to plain
 * text for anything else.
 */

type InlineToken =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "italic"; value: string }
  | { kind: "code"; value: string }
  | { kind: "link"; value: string; href: string };

function tokenize(line: string): InlineToken[] {
  const out: InlineToken[] = [];
  // Order: links → code → bold → italic → text. We do a single pass with regex.
  const re = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))|(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(_[^_]+_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) {
      out.push({ kind: "text", value: line.slice(last, m.index) });
    }
    if (m[1]) {
      out.push({ kind: "link", value: m[2], href: m[3] });
    } else if (m[4]) {
      out.push({ kind: "code", value: m[4].slice(1, -1) });
    } else if (m[5]) {
      out.push({ kind: "bold", value: m[5].slice(2, -2) });
    } else if (m[6]) {
      out.push({ kind: "italic", value: m[6].slice(1, -1) });
    } else if (m[7]) {
      out.push({ kind: "italic", value: m[7].slice(1, -1) });
    }
    last = m.index + m[0].length;
  }
  if (last < line.length) {
    out.push({ kind: "text", value: line.slice(last) });
  }
  return out;
}

function Inline({ line }: { line: string }) {
  return (
    <>
      {tokenize(line).map((t, i) => {
        if (t.kind === "text") return <Fragment key={i}>{t.value}</Fragment>;
        if (t.kind === "bold") return <strong key={i}>{t.value}</strong>;
        if (t.kind === "italic") return <em key={i}>{t.value}</em>;
        if (t.kind === "code") {
          return (
            <code
              key={i}
              className="bg-ink-100 text-ink-800 rounded px-1 py-0.5 text-[0.85em] font-mono"
            >
              {t.value}
            </code>
          );
        }
        if (t.kind === "link") {
          const internal = t.href.startsWith("/") || t.href.startsWith("#");
          return (
            <a
              key={i}
              href={t.href}
              target={internal ? undefined : "_blank"}
              rel={internal ? undefined : "noreferrer"}
              className="text-ink-900 underline hover:text-ink-700"
            >
              {t.value}
            </a>
          );
        }
        return null;
      })}
    </>
  );
}

export function Markdown({ text }: { text: string }) {
  if (!text) return null;
  // Normalise CRLF and split into blocks (blank line separated).
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {blocks.map((block, bi) => {
        const lines = block.split("\n");
        const isBullet = lines.every((l) => /^\s*[-*]\s+/.test(l));
        const isNumbered = lines.every((l) => /^\s*\d+\.\s+/.test(l));
        if (isBullet) {
          return (
            <ul key={bi} className="list-disc pl-5 space-y-1">
              {lines.map((l, i) => (
                <li key={i}>
                  <Inline line={l.replace(/^\s*[-*]\s+/, "")} />
                </li>
              ))}
            </ul>
          );
        }
        if (isNumbered) {
          return (
            <ol key={bi} className="list-decimal pl-5 space-y-1">
              {lines.map((l, i) => (
                <li key={i}>
                  <Inline line={l.replace(/^\s*\d+\.\s+/, "")} />
                </li>
              ))}
            </ol>
          );
        }
        // Heading shortcuts: ### / ## / #
        if (/^###\s+/.test(lines[0])) {
          return (
            <h3 key={bi} className="font-semibold text-base">
              <Inline line={lines[0].replace(/^###\s+/, "")} />
            </h3>
          );
        }
        if (/^##\s+/.test(lines[0])) {
          return (
            <h2 key={bi} className="font-semibold text-lg">
              <Inline line={lines[0].replace(/^##\s+/, "")} />
            </h2>
          );
        }
        return (
          <p key={bi} className="whitespace-pre-wrap">
            {lines.map((l, i) => (
              <Fragment key={i}>
                <Inline line={l} />
                {i < lines.length - 1 ? <br /> : null}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
