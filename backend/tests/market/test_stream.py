"""Tests for SSE streaming endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class TestCreateStreamRouter:
    """Router factory tests — no HTTP streaming required."""

    def test_returns_fresh_router_each_call(self):
        """Each call returns a distinct APIRouter, safe to call multiple times."""
        cache = PriceCache()
        r1 = create_stream_router(cache)
        r2 = create_stream_router(cache)
        assert r1 is not r2

    def test_registers_prices_route(self):
        """Router must register a route at /api/stream/prices."""
        cache = PriceCache()
        router = create_stream_router(cache)
        # In Starlette 0.52+, route.path includes the router prefix
        paths = [route.path for route in router.routes]
        assert "/api/stream/prices" in paths

    def test_prices_route_accepts_get(self):
        """The prices route must accept GET requests."""
        cache = PriceCache()
        router = create_stream_router(cache)
        for route in router.routes:
            if route.path == "/api/stream/prices":
                assert "GET" in route.methods
                return
        pytest.fail("/api/stream/prices route not found")


@pytest.mark.asyncio
class TestGenerateEvents:
    """Unit tests for _generate_events using the async generator directly."""

    async def test_yields_retry_directive_first(self):
        """_generate_events must yield retry directive before any data."""
        cache = PriceCache()
        request = MagicMock()
        request.client = None
        request.is_disconnected = AsyncMock(return_value=False)

        gen = _generate_events(cache, request, interval=0.01)
        first = await gen.__anext__()
        assert first == "retry: 1000\n\n"
        await gen.aclose()

    async def test_no_data_event_when_cache_empty(self):
        """No data: event is emitted when the cache has no prices."""
        cache = PriceCache()
        request = MagicMock()
        request.client = None

        disconnect_calls = 0

        async def is_disconnected():
            nonlocal disconnect_calls
            disconnect_calls += 1
            return disconnect_calls >= 3

        request.is_disconnected = is_disconnected

        events = []
        async for chunk in _generate_events(cache, request, interval=0.01):
            events.append(chunk)

        data_events = [e for e in events if e.startswith("data:")]
        assert data_events == []

    async def test_emits_data_event_when_version_changes(self):
        """A data: event is emitted when cache version increments."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        request = MagicMock()
        request.client = None

        disconnect_calls = 0

        async def is_disconnected():
            nonlocal disconnect_calls
            disconnect_calls += 1
            return disconnect_calls >= 4

        request.is_disconnected = is_disconnected

        events = []
        async for chunk in _generate_events(cache, request, interval=0.01):
            events.append(chunk)

        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) >= 1
        payload = json.loads(data_events[0].removeprefix("data:").strip())
        assert "AAPL" in payload

    async def test_no_duplicate_events_when_version_unchanged(self):
        """If cache version doesn't change, only one data event is sent."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        request = MagicMock()
        request.client = None

        call_count = 0

        async def is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count >= 6

        request.is_disconnected = is_disconnected

        events = []
        async for chunk in _generate_events(cache, request, interval=0.01):
            events.append(chunk)

        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) == 1

    async def test_disconnect_stops_generator(self):
        """Generator stops cleanly when client reports disconnect."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        request = MagicMock()
        request.client = None
        request.is_disconnected = AsyncMock(return_value=True)

        events = []
        async for chunk in _generate_events(cache, request, interval=0.01):
            events.append(chunk)

        assert events == ["retry: 1000\n\n"]

    async def test_data_payload_matches_cache_contents(self):
        """The data event payload must match what's in the cache."""
        cache = PriceCache()
        cache.update("MSFT", 420.00)
        cache.update("NVDA", 800.00)

        request = MagicMock()
        request.client = None

        calls = 0

        async def is_disconnected():
            nonlocal calls
            calls += 1
            return calls >= 4

        request.is_disconnected = is_disconnected

        events = []
        async for chunk in _generate_events(cache, request, interval=0.01):
            events.append(chunk)

        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) >= 1
        payload = json.loads(data_events[0].removeprefix("data:").strip())
        assert set(payload.keys()) == {"MSFT", "NVDA"}
        assert payload["MSFT"]["price"] == 420.00
        assert payload["NVDA"]["price"] == 800.00
