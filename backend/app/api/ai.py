"""Per-view AI commentary endpoint.

POST /api/ai/explain — body: {view, payload, question?, nonce?}
GET  /api/ai/views   — list of supported view ids (for debugging)

The frontend uses one shared ``<AIExplainCard />`` component to call this from
the Dashboard, Compare, Competitor and Product pages. The cache lives in the
service module so identical payloads only hit Gemini once.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.ai_explain import VIEW_PROMPTS, explain, supported_views

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ExplainRequest(BaseModel):
    view: str = Field(..., description="One of /api/ai/views")
    payload: dict[str, Any] = Field(default_factory=dict)
    question: Optional[str] = Field(None, description="Optional follow-up question about this view.")
    nonce: Optional[str] = Field(None, description="Pass any value to bypass the server-side cache.")


class ExplainResponse(BaseModel):
    view: str
    text: str
    model: Optional[str] = None
    cached: bool = False


@router.get("/views")
def list_views() -> dict[str, Any]:
    return {
        "views": [
            {"id": v, "role": VIEW_PROMPTS[v].role}
            for v in supported_views()
        ]
    }


@router.post("/explain", response_model=ExplainResponse)
def explain_view(req: ExplainRequest) -> ExplainResponse:
    if req.view not in VIEW_PROMPTS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown view '{req.view}'. Use one of: {supported_views()}",
        )
    result = explain(
        req.view,
        req.payload,
        question=req.question,
        nonce=req.nonce,
    )
    return ExplainResponse(**result)
