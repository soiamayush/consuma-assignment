"""Chat assistant endpoint backed by Gemini.

POST /api/chat        — streaming SSE; body: {"message": str, "history": [...], "window_days": int}
GET  /api/chat/health — returns whether GEMINI_API_KEY is configured.

The SSE stream emits ``data: <chunk>\\n\\n`` events. The frontend just appends
each chunk to the in-progress message bubble. A final ``data: [DONE]`` event
signals end-of-stream so the UI can flip "thinking" off.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services.gemini_chat import stream_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = Field(default_factory=list)
    window_days: int = 14


@router.get("/health")
def chat_health() -> dict[str, object]:
    s = get_settings()
    return {
        "configured": bool(s.gemini_api_key),
        "model": s.gemini_model if s.gemini_api_key else None,
        "history_window": s.chat_history_window,
        "hint": (
            None
            if s.gemini_api_key
            else "Add GEMINI_API_KEY to backend/.env (free key at https://aistudio.google.com/app/apikey)."
        ),
    }


@router.get("/suggested")
def suggested_questions() -> dict[str, list[str]]:
    """A small starter set of high-signal questions for the empty-chat state."""
    return {
        "questions": [
            "Where should I focus this week — give me 3 priorities.",
            "In the serum category, who is doing great and why?",
            "Which peers are discounting most aggressively right now?",
            "What's my biggest pricing white-space vs peers?",
            "Which categories are most crowded? Where can I differentiate?",
            "Show the biggest price moves in the last 14 days.",
            "Which peer is launching the fastest in the last 12 weeks?",
            "Who is getting the loudest social buzz and on which platform?",
        ]
    }


def _sse(data: str) -> bytes:
    """Format one SSE event. Newlines inside data must each be prefixed."""
    safe = data.replace("\r\n", "\n")
    payload = "\n".join(f"data: {line}" for line in safe.split("\n"))
    return (payload + "\n\n").encode("utf-8")


@router.post("")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    history = [{"role": t.role, "text": t.text} for t in req.history]

    def gen():
        try:
            # Send a tiny opening event so the client can show the cursor instantly.
            yield _sse(json.dumps({"event": "start"}))
            for chunk in stream_chat(
                db,
                req.message,
                history,
                window_days=req.window_days,
            ):
                if chunk:
                    yield _sse(chunk)
        except Exception as exc:
            logger.exception("chat stream failed")
            yield _sse(f"\n\n_(server error: {exc})_")
        finally:
            yield b"data: [DONE]\n\n"

    headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
