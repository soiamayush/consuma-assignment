"""Fixture source: reads pre-baked JSON from disk instead of hitting the network.

Used when USE_FIXTURES=true or when a live scrape fails and you want a
deterministic demo run. The fixture JSON matches Shopify's products shape,
so the same parser is reused.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from ..config import get_settings
from .base import BaseSource, FetchContext, RawBlogPost, RawProduct
from .shopify_products import ShopifyProductsSource

logger = logging.getLogger(__name__)


class FixtureProductsSource(BaseSource):
    kind = "fixture_products"

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        path = Path(self.config.get("path") or self.url)
        if not path.is_absolute():
            path = get_settings().fixtures_dir / path
        if not path.exists():
            logger.warning("fixture products file missing: %s", path)
            return []
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        # Reuse Shopify parser — fixtures use the same shape.
        parser = ShopifyProductsSource(url=f"https://{self.config.get('store','demo.example.com')}")
        return [parser._parse(p) for p in data.get("products", [])]


class FixtureBlogSource(BaseSource):
    kind = "fixture_blog"

    def fetch_products(self, ctx: FetchContext) -> Iterable[RawProduct]:
        return []

    def fetch_blog_posts(self, ctx: FetchContext) -> Iterable[RawBlogPost]:
        from datetime import datetime

        path = Path(self.config.get("path") or self.url)
        if not path.is_absolute():
            path = get_settings().fixtures_dir / path
        if not path.exists():
            logger.warning("fixture blog file missing: %s", path)
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        out: list[RawBlogPost] = []
        for e in data.get("entries", []):
            pub = e.get("published_at")
            dt = None
            if pub:
                try:
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except Exception:
                    dt = None
            out.append(
                RawBlogPost(
                    external_id=str(e.get("id") or e.get("url")),
                    url=e["url"],
                    title=e["title"],
                    summary=e.get("summary"),
                    published_at=dt,
                )
            )
        return out
