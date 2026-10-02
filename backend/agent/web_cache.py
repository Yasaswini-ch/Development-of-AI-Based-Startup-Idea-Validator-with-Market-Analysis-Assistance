"""A small shared cache for public web lookups, so the same search, page
extract, App Store query or company lookup is paid for once instead of on every
run.

This is separate from the 30-minute whole-report cache in main.py, which only
helps when the *same idea* is submitted again. These lookups repeat across
different ideas (two freelancer-tool ideas search the same queries and name the
same rivals) and across re-runs after a failure, and they are what costs Tavily
credits and seconds. Cached here:

  search      Tavily and DuckDuckGo result lists by query      12 hours
  extract     Tavily full-page text by URL                      7 days
  app_store   App Store search results by query                24 hours
  enrichment  Product Hunt / iTunes / Wikidata facts by name   30 days

Only successful, non-empty results are stored, so a failed or empty lookup is
retried next time instead of being remembered. Rows hold public web content and
the search wording derived from an idea, never user accounts. Expired rows are
deleted as new ones are written. Set WEB_CACHE=0 to bypass it entirely. Every
function here fails open: any database problem behaves like a cache miss.
"""

import hashlib
import logging
import os
import time

from sqlalchemy import delete, select

from .db import get_engine, web_cache_table

logger = logging.getLogger(__name__)

TTL_SECONDS = {
    "search": 12 * 60 * 60,
    "extract": 7 * 24 * 60 * 60,
    "app_store": 24 * 60 * 60,
    "enrichment": 30 * 24 * 60 * 60,
}


def enabled() -> bool:
    return os.environ.get("WEB_CACHE", "1") != "0"


def _key(kind: str, raw: str) -> str:
    return f"{kind}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def get(kind: str, raw_key: str):
    """The cached value, or None on a miss, an expired row or any error."""
    if not enabled() or kind not in TTL_SECONDS:
        return None
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                select(web_cache_table.c.data, web_cache_table.c.cached_at).where(
                    web_cache_table.c.cache_key == _key(kind, raw_key)
                )
            ).first()
    except Exception:
        logger.warning("web cache read failed; treating as a miss", exc_info=True)
        return None
    if row is None or time.time() - row.cached_at > TTL_SECONDS[kind]:
        return None
    return row.data


def put(kind: str, raw_key: str, value) -> None:
    """Store a non-empty value. Never raises."""
    if not enabled() or kind not in TTL_SECONDS or not value:
        return
    now = time.time()
    key = _key(kind, raw_key)
    try:
        with get_engine().begin() as conn:
            conn.execute(delete(web_cache_table).where(web_cache_table.c.cache_key == key))
            conn.execute(web_cache_table.insert().values(cache_key=key, kind=kind, data=value, cached_at=now))
            for expired_kind, ttl in TTL_SECONDS.items():
                conn.execute(
                    delete(web_cache_table).where(
                        (web_cache_table.c.kind == expired_kind) & (web_cache_table.c.cached_at < now - ttl)
                    )
                )
    except Exception:
        logger.warning("web cache write failed; continuing without caching", exc_info=True)


def clear() -> None:
    """Empty the cache. Used by tests."""
    try:
        with get_engine().begin() as conn:
            conn.execute(delete(web_cache_table))
    except Exception:
        logger.warning("web cache clear failed", exc_info=True)
