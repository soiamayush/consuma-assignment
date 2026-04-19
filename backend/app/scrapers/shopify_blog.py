"""Shopify blog (Atom feed) source.

Most Shopify stores expose Atom feeds at paths like `/blogs/<handle>.atom`.
We parse Atom with the stdlib (no feedparser dependency) for simpler installs.
"""

from __future__ import annotations

import html
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterable

from dateutil import parser as date_parser

from .base import BaseSource, FetchContext, RawBlogPost, http_get_text

logger = logging.getLogger(__name__)


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_atom_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date_parser.parse(raw)
    except (ValueError, TypeError):
        return None


def _parse_atom_entries(xml_text: str) -> list[RawBlogPost]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("atom xml parse error: %s", exc)
        return []
    out: list[RawBlogPost] = []
    for child in root:
        if _local_tag(child.tag) != "entry":
            continue
        eid: str | None = None
        title: str | None = None
        link_href: str | None = None
        summary: str | None = None
        published: datetime | None = None
        updated: datetime | None = None

        for el in child:
            ln = _local_tag(el.tag)
            text = (el.text or "").strip() if el.text else None
            if ln == "id" and text:
                eid = text
            elif ln == "title":
                # type="html" feeds store escaped markup in text
                title = html.unescape(text) if text else None
            elif ln == "link":
                href = el.attrib.get("href")
                if not href:
                    continue
                rel = el.attrib.get("rel", "")
                if rel == "alternate":
                    link_href = href
                elif link_href is None:
                    link_href = href
            elif ln == "summary" and text:
                summary = html.unescape(text)
            elif ln == "content" and summary is None and text:
                summary = html.unescape(text)
            elif ln == "published" and text:
                published = _parse_atom_datetime(text)
            elif ln == "updated" and text:
                updated = _parse_atom_datetime(text)

        if not eid:
            continue
        pub = published or updated
        if summary and len(summary) > 600:
            summary = summary[:600] + "…"
        out.append(
            RawBlogPost(
                external_id=str(eid),
                url=link_href or "",
                title=title or "(untitled)",
                summary=summary,
                published_at=pub,
            )
        )
    return out


class ShopifyBlogAtomSource(BaseSource):
    kind = "shopify_blog_atom"

    def fetch_products(self, ctx: FetchContext) -> Iterable:
        return []

    def fetch_blog_posts(self, ctx: FetchContext) -> Iterable[RawBlogPost]:
        logger.info("blog atom fetch url=%s", self.url)
        text = http_get_text(self.url, ctx)
        for post in _parse_atom_entries(text):
            if not post.url:
                post = RawBlogPost(
                    external_id=post.external_id,
                    url=self.url,
                    title=post.title,
                    summary=post.summary,
                    published_at=post.published_at,
                )
            yield post
