"""Offline by default: an unmocked HTTP request is a test failure."""

import os

import pytest
import respx


@pytest.fixture(autouse=True)
def offline_http(request, monkeypatch):
    # A user's configured gateway must not change the synthetic test provider.
    # Gateway-specific tests explicitly select their own mocked adapter.
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    if request.node.get_closest_marker("live"):
        if os.environ.get("RUN_LIVE") != "1":
            pytest.skip("Set RUN_LIVE=1 to allow live CDC smoke checks")
        yield
    else:
        with respx.mock(assert_all_mocked=True, assert_all_called=False):
            yield
