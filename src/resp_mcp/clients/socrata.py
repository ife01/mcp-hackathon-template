"""Hardened async Socrata client for CDC data.cdc.gov.

Design constraints (from build plan §1.1):
- Domain allowlist enforced before every outbound request.
- SoQL $where clauses built only from pre-validated values — never raw user strings.
- Async httpx with exponential backoff + jitter on 429, 5xx, timeouts (3 retries).
- In-memory TTL cache with per-key asyncio.Lock (single-flight) so concurrent
  wxO requests don't stampede an uncached Socrata query.
- Hard row cap: 50,000 rows maximum per logical query (via $offset pagination).
- Typed exceptions: SecurityError, UpstreamUnavailable, UpstreamBadRequest,
  UpstreamRateLimited.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from resp_mcp.config import settings

logger = logging.getLogger(__name__)

# Hard caps
_MAX_ROWS: int = 50_000
_PAGE_SIZE: int = 5_000
_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 1.0  # seconds
_BACKOFF_MAX: float = 16.0

# ── Typed exceptions ──────────────────────────────────────────────────────────


class SecurityError(RuntimeError):
    """Request blocked by the outbound domain allowlist."""


class UpstreamUnavailable(RuntimeError):
    """Socrata returned 5xx or the connection failed after retries."""


class UpstreamBadRequest(ValueError):
    """Socrata returned 4xx (not 429) — indicates a bad query."""


class UpstreamRateLimited(RuntimeError):
    """Socrata returned 429 and retries were exhausted."""


# ── Cache ─────────────────────────────────────────────────────────────────────

class _CacheEntry:
    __slots__ = ("data", "expires_at")

    def __init__(self, data: Any, ttl: int) -> None:
        self.data = data
        self.expires_at = time.monotonic() + ttl


class _Cache:
    """In-memory TTL cache with per-key asyncio.Lock (single-flight pattern)."""

    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def _get_key_lock(self, key: str) -> asyncio.Lock:
        async with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            self._entries.pop(key, None)
            return None
        return entry.data

    def set(self, key: str, data: Any, ttl: int) -> None:
        self._entries[key] = _CacheEntry(data, ttl)

    async def lock(self, key: str) -> asyncio.Lock:
        return await self._get_key_lock(key)


_cache = _Cache()


# ── Domain allowlist ──────────────────────────────────────────────────────────

def _check_domain(url: str) -> None:
    """Raise SecurityError if the URL host is not in the configured allowlist."""
    host = urlsplit(url).hostname or ""
    if host not in settings.allowed_domains:
        # Never include the full URL in the error — it may contain user input.
        raise SecurityError(
            f"Outbound request blocked: host {host!r} is not in "
            "the allowed domain list."
        )


# ── SoQL quoting helper ───────────────────────────────────────────────────────

def quote_soql_string(value: str) -> str:
    """Escape a string for safe use inside a SoQL single-quoted literal.

    Only call this with values that come from validated enums or reference data
    (jurisdiction codes, pathogen names, etc.) — never with raw user input.
    Escapes single quotes by doubling them, per Socrata SoQL spec.
    """
    return value.replace("'", "''")


def soql_eq(column: str, value: str) -> str:
    """Build a safe ``column='value'`` SoQL equality clause."""
    return f"{column}='{quote_soql_string(value)}'"


def soql_lte(column: str, value: str) -> str:
    """Build a safe ``column<='value'`` SoQL clause (for date bounds)."""
    return f"{column}<='{quote_soql_string(value)}'"


def soql_gte(column: str, value: str) -> str:
    """Build a safe ``column>='value'`` SoQL clause (for date bounds)."""
    return f"{column}>='{quote_soql_string(value)}'"


def soql_and(*clauses: str) -> str:
    """Join multiple SoQL clauses with AND."""
    return " AND ".join(c for c in clauses if c)


# ── HTTP client helpers ───────────────────────────────────────────────────────

def _build_client() -> httpx.AsyncClient:
    token = settings.socrata_app_token
    headers: dict[str, str] = {
        "User-Agent": (
            "respiratory-mcp-server/0.1 (public health situational awareness)"
        ),
        "Accept": "application/json",
    }
    if token:
        headers["X-App-Token"] = token
    return httpx.AsyncClient(
        base_url="https://data.cdc.gov",
        headers=headers,
        follow_redirects=False,
        timeout=settings.http_timeout_seconds,
        trust_env=False,
    )


def _backoff(attempt: int) -> float:
    """Exponential backoff with full jitter: uniform(0, min(cap, base * 2^attempt))."""
    ceiling = min(_BACKOFF_MAX, _BACKOFF_BASE * (2**attempt))
    return random.uniform(0.0, ceiling)


def _should_retry(status: int) -> bool:
    return status == 429 or status >= 500


def _cache_key(dataset_id: str, params: dict[str, Any]) -> str:
    raw = json.dumps({"id": dataset_id, "p": params}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Core query function ───────────────────────────────────────────────────────

async def _fetch_page(
    client: httpx.AsyncClient,
    dataset_id: str,
    params: dict[str, Any],
) -> list[dict]:
    """Fetch a single page from Socrata with retry logic."""
    url = f"https://data.cdc.gov/resource/{dataset_id}.json"
    _check_domain(url)

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.get(f"/resource/{dataset_id}.json", params=params)
            if resp.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    wait = _backoff(attempt)
                    logger.warning(
                        "Socrata rate-limited (429) on %s, retry %d in %.1fs",
                        dataset_id, attempt + 1, wait,
                    )
                    await asyncio.sleep(wait)
                    last_exc = UpstreamRateLimited(
                        f"Socrata rate-limited for dataset {dataset_id!r}. "
                        "Consider adding a SOCRATA_APP_TOKEN to .env."
                    )
                    continue
                raise UpstreamRateLimited(
                    f"Socrata rate-limited for dataset {dataset_id!r} after "
                    f"{_MAX_RETRIES} attempts. Consider adding a SOCRATA_APP_TOKEN."
                )
            if resp.status_code >= 500:
                if attempt < _MAX_RETRIES - 1:
                    wait = _backoff(attempt)
                    logger.warning(
                        "Socrata %d on %s, retry %d in %.1fs",
                        resp.status_code, dataset_id, attempt + 1, wait,
                    )
                    await asyncio.sleep(wait)
                    last_exc = UpstreamUnavailable(
                        f"Socrata returned HTTP {resp.status_code} for dataset "
                        f"{dataset_id!r}."
                    )
                    continue
                raise UpstreamUnavailable(
                    f"Socrata returned HTTP {resp.status_code} for dataset "
                    f"{dataset_id!r} after {_MAX_RETRIES} attempts."
                )
            if resp.status_code >= 400:
                # 4xx (not 429) → bad query, don't retry
                raise UpstreamBadRequest(
                    f"Socrata returned HTTP {resp.status_code} for dataset "
                    f"{dataset_id!r}."
                )
            return resp.json()
        except (UpstreamRateLimited, UpstreamUnavailable, UpstreamBadRequest):
            raise
        except httpx.TimeoutException:
            if attempt < _MAX_RETRIES - 1:
                wait = _backoff(attempt)
                logger.warning(
                    "Socrata timeout on %s, retry %d in %.1fs",
                    dataset_id, attempt + 1, wait,
                )
                await asyncio.sleep(wait)
                last_exc = UpstreamUnavailable(
                    f"Socrata request timed out for dataset {dataset_id!r}."
                )
                continue
            raise UpstreamUnavailable(
                f"Socrata request timed out for dataset {dataset_id!r} after "
                f"{_MAX_RETRIES} attempts."
            ) from None
        except httpx.RequestError as exc:
            raise UpstreamUnavailable(
                f"Socrata connection error for dataset {dataset_id!r}: "
                f"{type(exc).__name__}."
            ) from None

    # Should not reach here, but satisfy type checker
    if last_exc:
        raise last_exc
    raise UpstreamUnavailable(f"Unexpected retry exhaustion for {dataset_id!r}.")


async def query(
    dataset_id: str,
    *,
    select: list[str] | None = None,
    where: str | None = None,
    order: str | None = None,
    limit: int = _PAGE_SIZE,
) -> list[dict]:
    """Query a Socrata dataset with optional SoQL parameters.

    Paginates automatically up to _MAX_ROWS rows total.
    Results are cached in memory for settings.cache_ttl_seconds.

    Args:
        dataset_id: Socrata dataset 4x4 identifier (e.g. "vdzy-6i9v").
        select:     Columns to return. None = all columns.
        where:      SoQL WHERE clause. Build using soql_eq/soql_and helpers only.
        order:      SoQL ORDER BY clause (e.g. "weekendingdate DESC").
        limit:      Rows per page (max _PAGE_SIZE). Total capped at _MAX_ROWS.

    Returns:
        List of row dicts.

    Raises:
        SecurityError: Domain not in allowlist.
        UpstreamUnavailable: 5xx or connection failure after retries.
        UpstreamBadRequest: 4xx (not 429).
        UpstreamRateLimited: 429 after retries.
    """
    base_params: dict[str, Any] = {}
    if select:
        base_params["$select"] = ",".join(select)
    if where:
        base_params["$where"] = where
    if order:
        base_params["$order"] = order

    page_limit = min(limit, _PAGE_SIZE)
    cache_key = _cache_key(dataset_id, {**base_params, "$limit": page_limit})

    # Single-flight: if two coroutines race for the same uncached key, only
    # one fetches; the other waits and reads from cache.
    key_lock = await _cache.lock(cache_key)
    async with key_lock:
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for dataset %s", dataset_id)
            return cached

        rows: list[dict] = []
        offset = 0
        async with _build_client() as client:
            while True:
                params = {**base_params, "$limit": page_limit, "$offset": offset}
                page = await _fetch_page(client, dataset_id, params)
                rows.extend(page)
                if len(page) < page_limit or len(rows) >= _MAX_ROWS:
                    break
                offset += page_limit

        _cache.set(cache_key, rows, settings.cache_ttl_seconds)
        logger.debug(
            "Fetched %d rows from dataset %s (cached for %ds)",
            len(rows), dataset_id, settings.cache_ttl_seconds,
        )
        return rows


async def metadata(dataset_id: str) -> dict:
    """Fetch and cache dataset metadata from /api/views/{id}.json.

    Args:
        dataset_id: Socrata dataset 4x4 identifier.

    Returns:
        Metadata dict (name, description, columns, rowsUpdatedAt, etc.).

    Raises:
        SecurityError: Domain not in allowlist.
        UpstreamUnavailable / UpstreamBadRequest / UpstreamRateLimited.
    """
    url = f"https://data.cdc.gov/api/views/{dataset_id}.json"
    _check_domain(url)

    cache_key = _cache_key(f"meta:{dataset_id}", {})
    key_lock = await _cache.lock(cache_key)
    async with key_lock:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with _build_client() as client:
                    resp = await client.get(f"/api/views/{dataset_id}.json")
                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_backoff(attempt))
                        last_exc = UpstreamRateLimited(
                            f"Rate-limited fetching metadata for {dataset_id!r}."
                        )
                        continue
                    raise UpstreamRateLimited(
                        f"Rate-limited fetching metadata for {dataset_id!r} after "
                        f"{_MAX_RETRIES} attempts."
                    )
                if resp.status_code >= 500:
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(_backoff(attempt))
                        last_exc = UpstreamUnavailable(
                            f"HTTP {resp.status_code} fetching metadata for "
                            f"{dataset_id!r}."
                        )
                        continue
                    raise UpstreamUnavailable(
                        f"HTTP {resp.status_code} fetching metadata for "
                        f"{dataset_id!r} after {_MAX_RETRIES} attempts."
                    )
                if resp.status_code >= 400:
                    raise UpstreamBadRequest(
                        f"HTTP {resp.status_code} fetching metadata for "
                        f"{dataset_id!r}."
                    )
                meta: dict = resp.json()
                _cache.set(cache_key, meta, settings.cache_ttl_seconds)
                return meta
            except (UpstreamRateLimited, UpstreamUnavailable, UpstreamBadRequest):
                raise
            except httpx.TimeoutException:
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_backoff(attempt))
                    last_exc = UpstreamUnavailable(
                        f"Timeout fetching metadata for {dataset_id!r}."
                    )
                    continue
                raise UpstreamUnavailable(
                    f"Timeout fetching metadata for {dataset_id!r} after "
                    f"{_MAX_RETRIES} attempts."
                ) from None
            except httpx.RequestError as exc:
                raise UpstreamUnavailable(
                    f"Connection error fetching metadata for {dataset_id!r}: "
                    f"{type(exc).__name__}."
                ) from None

        if last_exc:
            raise last_exc
        raise UpstreamUnavailable(
            f"Unexpected retry exhaustion for metadata {dataset_id!r}."
        )
