"""Gemini-backed chat assistant for the competitor watch data.

Architecture
------------
For each chat turn we hand Gemini:

1. **System instructions** that lock the role to "competitive intelligence
   analyst for the anchor brand" and force grounding in the supplied JSON.
2. **A landscape brief** (see ``data_brief.build_brief``) — the *whole* picture
   in JSON. ~10–25 KB; trivial for Gemini 2.5 Flash.
3. **The recent chat history** (last N turns from settings).
4. **The new user message**.

Optional tool calls are exposed for deeper drilldowns the model decides it
needs (compare a category, search for SKUs by keyword), but the brief is
enough for almost every realistic question on this dataset, so most turns
finish in one round-trip.

We stream the response so the UI feels instant.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from ..api.compare import compare as compare_endpoint
from ..config import get_settings
from ..models import Competitor, Product, ProductSnapshot
from .data_brief import build_brief

logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTIONS = """You are the in-house competitive intelligence analyst for a beauty brand.
The user is an employee of the ANCHOR brand (e.g. sales, marketing, or product).
You will be given a JSON brief of the entire competitive landscape (anchor + peers,
price bands, discounts, stock pressure, white-space gaps, recent signals,
launches, catalog growth, top social mentions, category index).

How to answer
- Ground EVERY number in the supplied JSON. Never invent prices, percentages,
  SKU titles, or brand names.
- Prefer concrete numbers and brand names over vague claims. When you say
  "Brand X is cheaper", quote the median or specific SKU price.
- When the user asks "where should I focus" / "what should we do" — give 3-5
  prioritised, numbered actions with the supporting metric in parentheses.
- If the question is about a specific category (e.g. "serum", "sunscreen"),
  use the `categories` block + `sku_samples_per_brand` and call out per-brand
  SKU counts and price band. If the data is missing, say so plainly and ask
  whether to drill in via tools.
- Use compact markdown: bold brand names, short bullet lists, currency symbols
  inline (₹ for INR). No headings deeper than h3. No huge tables.
- If a question is outside the data (e.g. macro trends, consumer reviews you
  weren't given), say so honestly and suggest where in the app to look.
- Always finish every sentence and every numbered or bulleted item. If you
  must save space, shorten the intro — never stop mid-word or mid-sentence.

Tone: confident, direct, business-friendly. Treat the user like a peer at
Monday morning ops review. No filler ("Certainly!", "I'd be happy to…").
"""


# --- Tool functions exposed to Gemini -----------------------------------

def _tool_compare_category(db: Session, *, category: Optional[str] = None, keyword: Optional[str] = None) -> dict[str, Any]:
    """Compare per-brand pricing in a specific product_type or for a keyword."""
    return compare_endpoint(category=category, keyword=keyword, db=db)


def _tool_search_products(db: Session, *, query: str, brand: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    """Title-substring search; returns a small ranked SKU list with prices."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Product)
        .options(selectinload(Product.competitor))
        .where(Product.is_active.is_(True), Product.title.ilike(f"%{query}%"))
        .limit(max(1, min(limit, 25)))
    )
    if brand:
        stmt = stmt.join(Competitor).where(Competitor.slug == brand)
    rows: list[dict[str, Any]] = []
    for p in db.scalars(stmt):
        snap = db.scalar(
            select(ProductSnapshot)
            .where(ProductSnapshot.product_id == p.id)
            .order_by(ProductSnapshot.captured_at.desc())
            .limit(1)
        )
        rows.append(
            {
                "id": p.id,
                "brand": p.competitor.slug,
                "title": p.title,
                "type": p.product_type,
                "url": p.url,
                "price": float(snap.price_min) if snap and snap.price_min else None,
                "currency": snap.currency if snap else None,
            }
        )
    return {"query": query, "brand": brand, "results": rows, "count": len(rows)}


# Tool dispatch — keep names + arg names stable, the model is told these.
_TOOLS = {
    "compare_category": _tool_compare_category,
    "search_products": _tool_search_products,
}


# Gemini function-call schemas. Compact, no extras.
_TOOL_DECLARATIONS = [
    {
        "name": "compare_category",
        "description": (
            "Get per-brand price band (p25/median/p75), discount share, anchor delta, "
            "and the cheapest/most-expensive SKUs for a product_type or keyword. "
            "Use when the user asks about a specific shelf (e.g. 'serums', "
            "'vitamin c'), or wants the deep cross-brand comparison."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Exact product_type to filter on (e.g. 'Serum'). Optional."},
                "keyword": {"type": "string", "description": "Substring on title/tags (e.g. 'vitamin c'). Optional."},
            },
        },
    },
    {
        "name": "search_products",
        "description": "Find specific SKUs by title substring across all brands or a single brand.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Title keyword(s)."},
                "brand": {"type": "string", "description": "Optional brand slug (e.g. 'minimalist')."},
                "limit": {"type": "integer", "description": "Max rows (default 10, cap 25)."},
            },
            "required": ["query"],
        },
    },
]


# --- Streaming generator -------------------------------------------------

def stream_chat(
    db: Session,
    user_message: str,
    history: list[dict[str, str]],
    *,
    window_days: int = 14,
) -> Iterable[str]:
    """Yield text chunks for an SSE stream.

    `history` is a list of {role: 'user'|'model', text: str} most-recent-last.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        yield (
            "Gemini isn't configured yet. Add `GEMINI_API_KEY` to `backend/.env` "
            "(get a free key at https://aistudio.google.com/app/apikey) and restart "
            "the backend. The brief and tools are ready — only the model call needs the key."
        )
        return

    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception as exc:  # pragma: no cover - dep missing
        logger.exception("google-genai import failed")
        yield (
            f"The Gemini SDK isn't installed in this environment ({exc}). "
            "Install with `pip install google-genai` and restart."
        )
        return

    brief = build_brief(db, window_days=window_days)
    brief_json = json.dumps(brief, default=str, ensure_ascii=False)
    # Keep the brief text bounded — Gemini handles 1M tokens but smaller = faster.
    if len(brief_json) > 120_000:
        brief_json = brief_json[:120_000] + "\n…(truncated)"

    client = genai.Client(api_key=settings.gemini_api_key)

    # Build the chat contents: history + new user turn. The brief is sent as a
    # system_instruction so it doesn't leak into chat memory.
    contents: list[Any] = []
    trimmed_history = history[-max(0, settings.chat_history_window) * 2:] if settings.chat_history_window else []
    for turn in trimmed_history:
        role = "user" if turn.get("role") == "user" else "model"
        contents.append(gtypes.Content(role=role, parts=[gtypes.Part.from_text(text=turn.get("text", ""))]))
    contents.append(
        gtypes.Content(role="user", parts=[gtypes.Part.from_text(text=user_message)])
    )

    tool = gtypes.Tool(function_declarations=_TOOL_DECLARATIONS)
    max_out = max(512, min(settings.gemini_max_output_tokens, 65_536))
    config = gtypes.GenerateContentConfig(
        system_instruction=(
            SYSTEM_INSTRUCTIONS
            + "\n\n=== LANDSCAPE BRIEF (JSON) ===\n"
            + brief_json
            + "\n=== END BRIEF ===\n"
        ),
        tools=[tool],
        temperature=0.4,
        max_output_tokens=max_out,
    )

    # We loop: stream → if a tool call comes back, execute it locally and feed
    # the result back as a new turn. Cap to 3 tool rounds per user message.
    for _round in range(3):
        try:
            stream = client.models.generate_content_stream(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            logger.exception("Gemini stream failed")
            yield f"\n\n_(Gemini call failed: {exc})_\n"
            return

        accumulated_text_parts: list[str] = []
        # Same function_call can appear on many stream chunks — keep one per name.
        function_calls_by_name: dict[str, Any] = {}
        for chunk in stream:
            # Pull plain text deltas to the client immediately.
            text = getattr(chunk, "text", None)
            if text:
                accumulated_text_parts.append(text)
                yield text
            # Collect function-call parts (dedupe by name — SDK repeats them per chunk).
            try:
                cands = getattr(chunk, "candidates", None) or []
                for cand in cands:
                    parts = getattr(getattr(cand, "content", None), "parts", None) or []
                    for part in parts:
                        fc = getattr(part, "function_call", None)
                        if fc:
                            name = getattr(fc, "name", "") or "_"
                            function_calls_by_name[name] = fc
            except Exception:
                pass

        function_calls = list(function_calls_by_name.values())
        if not function_calls:
            return  # done

        # Append the model's tool-call turn to context, then execute and add results.
        model_parts = []
        if accumulated_text_parts:
            model_parts.append(gtypes.Part.from_text(text="".join(accumulated_text_parts)))
        for fc in function_calls:
            model_parts.append(gtypes.Part(function_call=fc))
        contents.append(gtypes.Content(role="model", parts=model_parts))

        tool_response_parts = []
        for fc in function_calls:
            name = getattr(fc, "name", "")
            args = getattr(fc, "args", {}) or {}
            yield f"\n\n_(consulting `{name}`…)_\n\n"
            handler = _TOOLS.get(name)
            if not handler:
                result = {"error": f"unknown tool '{name}'"}
            else:
                try:
                    result = handler(db, **dict(args))
                except Exception as exc:
                    logger.exception("tool '%s' failed", name)
                    result = {"error": str(exc)}
            tool_response_parts.append(
                gtypes.Part.from_function_response(name=name, response={"content": result})
            )
        contents.append(gtypes.Content(role="user", parts=tool_response_parts))

    yield "\n\n_(stopped after 3 tool rounds)_"
