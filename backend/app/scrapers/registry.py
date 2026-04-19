from __future__ import annotations

from typing import Any

from .base import BaseSource
from .browser import BrowserListingSource
from .fixture import FixtureBlogSource, FixtureProductsSource
from .html_listing import HtmlListingSource
from .mamaearth_sitemap import MamaearthSitemapSource
from .myglamm import MyGlammApiSource
from .bing_news_rss import BingNewsRssSource
from .instagram_graph_hashtag import InstagramGraphHashtagSource
from .itunes_podcast import ItunesPodcastSource
from .news_rss import NewsRssSource
from .shopify_blog import ShopifyBlogAtomSource
from .shopify_products import ShopifyProductsSource
from .youtube_search import YouTubeSearchSource

_REGISTRY: dict[str, type[BaseSource]] = {
    "shopify_products": ShopifyProductsSource,
    "shopify_blog_atom": ShopifyBlogAtomSource,
    "fixture_products": FixtureProductsSource,
    "fixture_blog": FixtureBlogSource,
    "browser_listing": BrowserListingSource,
    "html_listing": HtmlListingSource,
    "myglamm_internal_api": MyGlammApiSource,
    "mamaearth_sitemap": MamaearthSitemapSource,
    "youtube_search": YouTubeSearchSource,
    "news_rss": NewsRssSource,
    "bing_news_rss": BingNewsRssSource,
    "itunes_podcast": ItunesPodcastSource,
    "instagram_graph_hashtag": InstagramGraphHashtagSource,
}


def build_source(kind: str, url: str, config: dict[str, Any] | None = None) -> BaseSource:
    if kind not in _REGISTRY:
        raise ValueError(f"Unknown source kind: {kind}")
    return _REGISTRY[kind](url=url, config=config or {})


def available_kinds() -> list[str]:
    return list(_REGISTRY.keys())
