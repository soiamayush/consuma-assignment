"""FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import ai as ai_api
from .api import analytics as analytics_api
from .api import chat as chat_api
from .api import compare as compare_api
from .api import competitors as competitors_api
from .api import ingest as ingest_api
from .api import products as products_api
from .api import signals as signals_api
from .api import social as social_api
from .config import get_settings
from .db import init_db
from .seed import reconcile_database_with_current_seed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reset stale SQLite (e.g. still showing Allbirds after switching to Minimalist seed).
    reconcile_database_with_current_seed()
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="Competitor Watch",
    description="Minimalist (anchor) vs skincare peers — signals + catalog analytics.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(competitors_api.router)
app.include_router(products_api.router)
app.include_router(signals_api.router)
app.include_router(ingest_api.router)
app.include_router(analytics_api.router)
app.include_router(compare_api.router)
app.include_router(social_api.router)
app.include_router(chat_api.router)
app.include_router(ai_api.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
