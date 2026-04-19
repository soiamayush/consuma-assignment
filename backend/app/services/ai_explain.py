"""LLM commentary service: turns small JSON payloads into analyst-grade markdown.

Used by ``POST /api/ai/explain`` for per-view AI cards across the UI:

* ``dashboard_summary``  — exec read of recent activity + top movers
* ``compare_scope``      — strategist memo for the chosen category/keyword
* ``brand_brief``        — SWOT-style brief for one competitor
* ``product_peers``      — paragraph contextualising one SKU vs peers
* ``analytics_overview`` — ties price/discount/stock/launch charts into one memo
* ``social_buzz``        — PR/comms read on mention volume + sample clips

Design goals
- **Small payloads**: each view sends only the data shown on screen, not the
  whole landscape. Keeps tokens, latency, and cost low.
- **Tightly scoped prompts**: per-view system text so the model talks like the
  right kind of analyst (commercial, brand, merchandising, etc.).
- **Server-side LRU cache**: same payload hits Gemini once until the data
  changes. The frontend can force-regenerate via ``nonce`` (cache buster).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-view prompt templates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ViewPrompt:
    role: str        # one-line analyst persona for system prompt
    guidance: str    # bullets that tell the model what to produce
    style: str       # output style/format reminders


_BASE_GUARDRAILS = (
    "Hard rules:\n"
    "- Ground EVERY number in the supplied JSON. Never invent prices, percentages, "
    "SKU titles, or brand names.\n"
    "- Use compact markdown: short bullets, **bold brand names**, ₹ for INR. "
    "No headings deeper than h3. No tables.\n"
    "- Always finish your sentences. If space is tight, drop the intro — never "
    "stop mid-word or mid-bullet.\n"
    "- If a key field is missing, say so plainly in one short line and continue.\n"
)


VIEW_PROMPTS: dict[str, ViewPrompt] = {
    "dashboard_summary": ViewPrompt(
        role="You are the on-call competitive intelligence analyst for the anchor brand.",
        guidance=(
            "Write a tight executive read for the morning standup, in this exact order:\n"
            "1. **Headline (1 line)** — the single most important thing that changed.\n"
            "2. **What moved** — 3 bullets, each a brand + concrete metric (price, "
            "launches, OOS, social).\n"
            "3. **Where to act this week** — 2-3 numbered actions tied to the metrics above.\n"
            "Keep total length under ~140 words."
        ),
        style="Confident, peer-to-peer tone. No filler.",
    ),
    "compare_scope": ViewPrompt(
        role="You are the pricing & assortment strategist for the anchor brand.",
        guidance=(
            "Given the per-brand price band, discount intensity and cheapest/priciest "
            "SKUs for the chosen scope, write:\n"
            "1. **Where the anchor sits** — one sentence on price position vs peers.\n"
            "2. **Pressure points** — 2-3 bullets on the most aggressive peers, with "
            "the metric (% on sale, median % off, anchor delta).\n"
            "3. **Recommended moves** — 3 numbered actions: pricing, assortment, or "
            "merchandising. Each must reference the supporting number.\n"
            "Stay under ~160 words."
        ),
        style="Direct, decision-ready. Treat the reader as a category lead.",
    ),
    "brand_brief": ViewPrompt(
        role="You are a brand analyst writing a one-page competitor brief.",
        guidance=(
            "Produce a SWOT-style read of the supplied brand vs the anchor:\n"
            "**Snapshot** (1 line: SKU count, signal velocity, distinctive bet).\n"
            "**Strengths** (2 bullets) · **Weaknesses** (2 bullets).\n"
            "**Recent moves** (2 bullets — quote real prices/SKUs from the data).\n"
            "**Watch list** (2 numbered things the anchor should monitor).\n"
            "Keep it under ~180 words."
        ),
        style="Neutral, evidence-first. Not marketing copy.",
    ),
    "product_peers": ViewPrompt(
        role="You are a merchandiser comparing one SKU against peer alternatives.",
        guidance=(
            "Write **two short paragraphs**, no lists:\n"
            "Para 1 — How this SKU is positioned vs the peer set on price (cheapest / "
            "closest / most expensive). Use real prices from the JSON.\n"
            "Para 2 — One concrete recommendation (e.g. promote, hold, reprice, bundle), "
            "and why, citing the peer evidence.\n"
            "Stay under ~120 words total."
        ),
        style="Conversational analyst tone. No bullets, no headings.",
    ),
    "analytics_overview": ViewPrompt(
        role="You are the category analytics lead summarising a full analytics dashboard.",
        guidance=(
            "The JSON bundles price bands, signal velocity, discount share, optional stock "
            "pressure, launch cadence, and top price moves for the anchor vs peers.\n"
            "Write in this order (keep under ~170 words):\n"
            "1. **Headline** — one line on where the anchor stands vs peers on price/discount.\n"
            "2. **Three bullets** — each a concrete pattern with a number (brand + metric).\n"
            "3. **Risks / opportunities** — 2 numbered items the commercial team should act on.\n"
            "Synthesise only from the structured numbers — do not invent metrics not present in the JSON."
        ),
        style="Crisp, number-forward. Assume the reader skimmed the charts.",
    ),
    "social_buzz": ViewPrompt(
        role="You are a PR and social listening analyst for the anchor skincare brand.",
        guidance=(
            "Given per-brand mention counts by platform plus sample titles and top creators, write:\n"
            "1. **Who is loudest** — 1-2 sentences naming brands and platforms with counts.\n"
            "2. **Narrative themes** — 2 bullets: what topics or formats show up in the samples "
            "(only if evident from titles; otherwise say the sample is thin).\n"
            "3. **Suggested response** — 2 numbered actions (e.g. counter-messaging, creator outreach, "
            "monitor a hashtag). Stay under ~150 words."
        ),
        style="Professional, non-hype. No emojis.",
    ),
    "analytics_section": ViewPrompt(
        role="You are an analyst explaining a single chart/section to a non-technical exec.",
        guidance=(
            "Write **one short paragraph (≤80 words)** explaining what the supplied data "
            "means. Lead with the headline insight, then the supporting number. End with "
            "the implication for the anchor brand. No lists."
        ),
        style="Plain-English, no jargon, no marketing fluff.",
    ),
}


# ---------------------------------------------------------------------------
# Cache key + generation
# ---------------------------------------------------------------------------

def _payload_fingerprint(view: str, payload: dict[str, Any], question: Optional[str]) -> str:
    blob = json.dumps(
        {"v": view, "p": payload, "q": question or ""},
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


# Bounded LRU — module-level dict + simple eviction. We avoid functools.lru_cache
# because we need to invalidate by 'nonce' and store metadata too.
_CACHE: "dict[str, tuple[str, str]]" = {}  # fingerprint -> (text, model)
_CACHE_ORDER: list[str] = []
_CACHE_MAX = 256


def _cache_get(fp: str) -> Optional[tuple[str, str]]:
    return _CACHE.get(fp)


def _cache_put(fp: str, text: str, model: str) -> None:
    _CACHE[fp] = (text, model)
    _CACHE_ORDER.append(fp)
    while len(_CACHE_ORDER) > _CACHE_MAX:
        oldest = _CACHE_ORDER.pop(0)
        _CACHE.pop(oldest, None)


def explain(
    view: str,
    payload: dict[str, Any],
    *,
    question: Optional[str] = None,
    nonce: Optional[str] = None,
) -> dict[str, Any]:
    """Return ``{text, model, cached, view}`` for the requested view + payload.

    ``nonce`` (any non-empty string) bypasses the cache — the frontend uses
    this for the "Regenerate" button.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return {
            "text": (
                "Gemini isn't configured yet. Add `GEMINI_API_KEY` to `backend/.env` "
                "(get a free key at https://aistudio.google.com/app/apikey) and restart "
                "the backend to enable AI commentary."
            ),
            "model": None,
            "cached": False,
            "view": view,
        }

    spec = VIEW_PROMPTS.get(view) or VIEW_PROMPTS["analytics_section"]

    fp = _payload_fingerprint(view, payload, question)
    if not nonce:
        cached = _cache_get(fp)
        if cached is not None:
            text, model = cached
            return {"text": text, "model": model, "cached": True, "view": view}

    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception as exc:  # pragma: no cover - dep missing
        logger.exception("google-genai import failed")
        return {
            "text": f"Gemini SDK unavailable in this environment ({exc}).",
            "model": None,
            "cached": False,
            "view": view,
        }

    payload_json = json.dumps(payload, default=str, ensure_ascii=False)
    if len(payload_json) > 60_000:
        payload_json = payload_json[:60_000] + "\n…(truncated)"

    system_instruction = (
        f"{spec.role}\n\n{spec.guidance}\n\nStyle: {spec.style}\n\n{_BASE_GUARDRAILS}"
    )
    user_prompt_parts = [
        f"=== VIEW: {view} ===",
        "=== DATA (JSON) ===",
        payload_json,
        "=== END DATA ===",
    ]
    if question:
        user_prompt_parts.append(f"User follow-up question: {question}")
    user_prompt = "\n".join(user_prompt_parts)

    client = genai.Client(api_key=settings.gemini_api_key)
    config = gtypes.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.4,
        max_output_tokens=max(512, min(settings.gemini_max_output_tokens, 4096)),
    )

    try:
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[gtypes.Content(role="user", parts=[gtypes.Part.from_text(text=user_prompt)])],
            config=config,
        )
        text = (resp.text or "").strip()
    except Exception as exc:
        logger.exception("Gemini explain call failed (view=%s)", view)
        return {
            "text": f"_(Gemini call failed: {exc})_",
            "model": settings.gemini_model,
            "cached": False,
            "view": view,
        }

    if not text:
        text = "_(Model returned no text — try regenerating or shrinking the input.)_"

    _cache_put(fp, text, settings.gemini_model)
    return {"text": text, "model": settings.gemini_model, "cached": False, "view": view}


@lru_cache(maxsize=1)
def supported_views() -> list[str]:
    return sorted(VIEW_PROMPTS.keys())
