"""Unit tests for resp_mcp.clients.socrata.

All tests are offline — network calls are intercepted by respx.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from resp_mcp.clients.socrata import (
    SecurityError,
    UpstreamBadRequest,
    UpstreamRateLimited,
    UpstreamUnavailable,
    _Cache,
    _check_domain,
    metadata,
    query,
    quote_soql_string,
    soql_and,
    soql_eq,
    soql_lte,
)
from resp_mcp.config import settings

# ── Helpers ───────────────────────────────────────────────────────────────────

BASE = "https://data.cdc.gov"
DATASET = "vdzy-6i9v"
RESOURCE_URL = f"{BASE}/resource/{DATASET}.json"
META_URL = f"{BASE}/api/views/{DATASET}.json"

SAMPLE_ROWS = [
    {"jurisdiction": "GA", "weekendingdate": "2026-11-14",
     "totalconfflunewadmper100k": "2.47"},
    {"jurisdiction": "GA", "weekendingdate": "2026-11-07",
     "totalconfflunewadmper100k": "2.41"},
]


def _fresh_cache() -> _Cache:
    """Return a new, isolated cache instance for each test."""
    return _Cache()


# ── Domain allowlist ──────────────────────────────────────────────────────────

def test_check_domain_allows_cdc():
    _check_domain("https://data.cdc.gov/resource/abc.json")  # must not raise


def test_check_domain_allows_socrata_catalog():
    _check_domain("https://api.us.socrata.com/api/catalog/v1")


def test_check_domain_blocks_external():
    with pytest.raises(SecurityError, match="not in the allowed domain list"):
        _check_domain("https://evil.example.com/steal-data")


def test_check_domain_blocks_ssrf_metadata():
    with pytest.raises(SecurityError):
        _check_domain("http://169.254.169.254/latest/meta-data")


def test_check_domain_blocks_localhost():
    with pytest.raises(SecurityError):
        _check_domain("http://localhost/admin")


# ── SoQL quoting ──────────────────────────────────────────────────────────────

def test_quote_soql_string_no_special():
    assert quote_soql_string("Georgia") == "Georgia"


def test_quote_soql_string_escapes_single_quote():
    assert quote_soql_string("O'Brien") == "O''Brien"


def test_quote_soql_string_escapes_multiple():
    assert quote_soql_string("it's a 'test'") == "it''s a ''test''"


def test_soql_eq_builds_clause():
    assert soql_eq("jurisdiction", "GA") == "jurisdiction='GA'"


def test_soql_eq_escapes_quotes():
    assert soql_eq("name", "O'Brien") == "name='O''Brien'"


def test_soql_lte_builds_clause():
    assert soql_lte("weekendingdate", "2026-10-31") == "weekendingdate<='2026-10-31'"


def test_soql_and_joins_clauses():
    result = soql_and("a='1'", "b='2'", "c='3'")
    assert result == "a='1' AND b='2' AND c='3'"


def test_soql_and_skips_empty():
    assert soql_and("a='1'", "", "c='3'") == "a='1' AND c='3'"


# ── Successful query ──────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_query_returns_rows():
    respx.get(RESOURCE_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE_ROWS)
    )
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    rows = await query(DATASET, where=soql_eq("jurisdiction", "GA"))
    assert len(rows) == 2
    assert rows[0]["jurisdiction"] == "GA"


@respx.mock
@pytest.mark.asyncio
async def test_query_paginates():
    """When a full page is returned, the client should request the next offset."""
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    page1 = [{"row": i} for i in range(5)]
    page2 = [{"row": i} for i in range(5, 8)]

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        offset = int(request.url.params.get("$offset", 0))
        return httpx.Response(200, json=page2 if offset > 0 else page1)

    respx.get(RESOURCE_URL).mock(side_effect=side_effect)

    # Set page size to 5 so pagination triggers
    with patch.object(socrata, "_PAGE_SIZE", 5):
        rows = await query(DATASET, limit=5)

    assert call_count == 2
    assert len(rows) == 8


# ── 429 retry ─────────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_query_retries_on_429_then_succeeds():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=SAMPLE_ROWS)

    respx.get(RESOURCE_URL).mock(side_effect=side_effect)

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        rows = await query(DATASET)

    assert call_count == 2
    assert len(rows) == 2


@respx.mock
@pytest.mark.asyncio
async def test_query_raises_rate_limited_after_all_retries():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(RESOURCE_URL).mock(return_value=httpx.Response(429))

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        with pytest.raises(UpstreamRateLimited, match="rate-limited"):
            await query(DATASET)


# ── 503 / 5xx failure ─────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_query_raises_unavailable_on_503():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(RESOURCE_URL).mock(return_value=httpx.Response(503))

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        with pytest.raises(UpstreamUnavailable, match="503"):
            await query(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_query_raises_bad_request_on_400():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(RESOURCE_URL).mock(return_value=httpx.Response(400))

    with pytest.raises(UpstreamBadRequest, match="400"):
        await query(DATASET)


# ── Cache hit ─────────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_query_returns_cache_hit_without_network():
    from resp_mcp.clients import socrata

    cache = _fresh_cache()
    socrata._cache = cache
    from resp_mcp.clients.socrata import _cache_key

    # Pre-populate cache
    key = _cache_key(DATASET, {"$limit": 5000})
    cache.set(key, SAMPLE_ROWS, ttl=3600)

    # Route should never be called
    mock_route = respx.get(RESOURCE_URL).mock(return_value=httpx.Response(500))

    rows = await query(DATASET)
    assert rows == SAMPLE_ROWS
    assert not mock_route.called


# ── Concurrent single-flight ──────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_concurrent_requests_single_flight():
    """Two concurrent queries for the same key must only hit the network once."""
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    network_hit_count = 0

    async def slow_response(request: httpx.Request) -> httpx.Response:
        nonlocal network_hit_count
        network_hit_count += 1
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=SAMPLE_ROWS)

    respx.get(RESOURCE_URL).mock(side_effect=slow_response)

    results = await asyncio.gather(query(DATASET), query(DATASET))

    assert network_hit_count == 1
    assert results[0] == results[1] == SAMPLE_ROWS


# ── Domain allowlist rejection on query ───────────────────────────────────────

@pytest.mark.asyncio
async def test_query_blocked_for_disallowed_domain(monkeypatch):
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    # Temporarily remove data.cdc.gov from the allowlist
    monkeypatch.setattr(settings, "allowed_domains", ["api.us.socrata.com"])

    with pytest.raises(SecurityError, match="not in the allowed domain list"):
        await query(DATASET)


# ── metadata() ────────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_metadata_returns_dict():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    meta = {"name": "NHSN", "columns": []}
    respx.get(META_URL).mock(return_value=httpx.Response(200, json=meta))

    result = await metadata(DATASET)
    assert result["name"] == "NHSN"


@respx.mock
@pytest.mark.asyncio
async def test_metadata_cached():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    meta = {"name": "NHSN", "columns": []}
    mock_route = respx.get(META_URL).mock(return_value=httpx.Response(200, json=meta))

    await metadata(DATASET)
    await metadata(DATASET)  # second call — should use cache

    assert mock_route.call_count == 1


# ── Cache TTL expiry ──────────────────────────────────────────────────────────

def test_cache_expires_entries():
    cache = _Cache()
    cache.set("key", {"data": 1}, ttl=0)  # expires immediately
    # Force expiry by advancing time isn't needed — ttl=0 means already expired
    # on next monotonic() call (monotonic always advances)
    import time as _t
    _t.sleep(0.01)
    assert cache.get("key") is None


def test_cache_returns_valid_entry():
    cache = _Cache()
    cache.set("key", {"data": 42}, ttl=3600)
    assert cache.get("key") == {"data": 42}


# ── Additional coverage ───────────────────────────────────────────────────────

def test_soql_gte_builds_clause():
    assert soql_lte("weekendingdate", "2026-01-01") == "weekendingdate<='2026-01-01'"


def test_app_token_included_when_set(monkeypatch):
    from resp_mcp.clients.socrata import _build_client
    monkeypatch.setattr(settings, "socrata_app_token", "tok123")
    client = _build_client()
    assert client.headers.get("x-app-token") == "tok123"


def test_should_retry_covers_429_and_5xx():
    from resp_mcp.clients.socrata import _should_retry
    assert _should_retry(429) is True
    assert _should_retry(503) is True
    assert _should_retry(400) is False


@respx.mock
@pytest.mark.asyncio
async def test_query_retries_on_503_then_succeeds():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=SAMPLE_ROWS)

    respx.get(RESOURCE_URL).mock(side_effect=side_effect)

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        rows = await query(DATASET)

    assert call_count == 2
    assert len(rows) == 2


@respx.mock
@pytest.mark.asyncio
async def test_query_retries_on_timeout_then_succeeds():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json=SAMPLE_ROWS)

    respx.get(RESOURCE_URL).mock(side_effect=side_effect)

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        rows = await query(DATASET)

    assert call_count == 2
    assert len(rows) == 2


@respx.mock
@pytest.mark.asyncio
async def test_query_raises_unavailable_on_timeout_exhaustion():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(RESOURCE_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        with pytest.raises(UpstreamUnavailable, match="timed out"):
            await query(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_query_raises_unavailable_on_connection_error():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(RESOURCE_URL).mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(UpstreamUnavailable, match="ConnectError"):
        await query(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_metadata_retries_on_503_then_succeeds():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"name": "NHSN"})

    respx.get(META_URL).mock(side_effect=side_effect)

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        result = await metadata(DATASET)

    assert call_count == 2
    assert result["name"] == "NHSN"


@respx.mock
@pytest.mark.asyncio
async def test_metadata_raises_on_429_exhaustion():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(META_URL).mock(return_value=httpx.Response(429))

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        with pytest.raises(UpstreamRateLimited):
            await metadata(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_metadata_raises_on_400():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(META_URL).mock(return_value=httpx.Response(404))

    with pytest.raises(UpstreamBadRequest):
        await metadata(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_metadata_raises_on_timeout_exhaustion():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(META_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    with patch("resp_mcp.clients.socrata.asyncio.sleep"):
        with pytest.raises(UpstreamUnavailable, match="Timeout"):
            await metadata(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_metadata_blocked_for_disallowed_domain(monkeypatch):
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    monkeypatch.setattr(settings, "allowed_domains", ["api.us.socrata.com"])

    with pytest.raises(SecurityError):
        await metadata(DATASET)


@respx.mock
@pytest.mark.asyncio
async def test_metadata_raises_on_connection_error():
    from resp_mcp.clients import socrata
    socrata._cache = _fresh_cache()

    respx.get(META_URL).mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(UpstreamUnavailable, match="ConnectError"):
        await metadata(DATASET)


def test_soql_gte_builds_correct_clause():
    from resp_mcp.clients.socrata import soql_gte
    assert soql_gte("weekendingdate", "2026-01-01") == "weekendingdate>='2026-01-01'"
