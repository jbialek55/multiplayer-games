"""Shared fixtures for backend tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mp.config import Settings
from mp.main import create_app


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def client() -> TestClient:
    with _client(Settings()) as c:
        yield c


@pytest.fixture
def small_client() -> TestClient:
    """Tiny message limit, for oversized-message tests."""
    with _client(Settings(max_message_bytes=200)) as c:
        yield c


@pytest.fixture
def rate_client() -> TestClient:
    """Tiny rate budget (capacity 2) for rate-limit tests."""
    with _client(Settings(rate_limit_capacity=2, rate_limit_refill_per_sec=0.0)) as c:
        yield c


@pytest.fixture
def grace_client() -> TestClient:
    """Long reconnect window, for rejoin-before-forfeit tests."""
    with _client(Settings(reconnect_grace_seconds=30.0)) as c:
        yield c


@pytest.fixture
def forfeit_client() -> TestClient:
    """Tiny reconnect window, for forfeit-after-timeout tests."""
    with _client(Settings(reconnect_grace_seconds=0.1)) as c:
        yield c


@pytest.fixture
def persist_client() -> TestClient:
    """Persistence enabled on an in-memory SQLite database."""
    with _client(Settings(db_path=":memory:")) as c:
        yield c
