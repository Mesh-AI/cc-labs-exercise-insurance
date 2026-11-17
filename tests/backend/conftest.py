"""
Pytest configuration and fixtures for backend tests.

The lab clock is frozen at the dataset's as-at date (server/data/as_at.json),
so tests give the same answers whenever they run.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add server directory to path
server_path = Path(__file__).parent.parent.parent / "server"
sys.path.insert(0, str(server_path))

from main import app  # noqa: E402
from legacy import heron, herondb  # noqa: E402
from systems.common import today  # noqa: E402

LEGACY_DATA = os.path.join(str(server_path), "data", "legacy")


@pytest.fixture(autouse=True)
def no_live_estate(monkeypatch):
    """
    The new API reaches the downstream systems over HTTP at ESTATE_BASE_URL
    (docs/ARCHITECTURE.md). Nothing listens there during tests, so point it at a
    closed port: the connection is refused at once instead of reaching whatever
    happens to be running on 8001. A test that needs a downstream answer must
    supply one, for example by monkeypatching the fetch to use the `client`
    fixture. A test that doesn't gets the "system is down" path.
    """
    monkeypatch.setenv("ESTATE_BASE_URL", "http://127.0.0.1:9/api/systems")


@pytest.fixture
def client():
    """Test client for the whole backend: new API, Heron screens and the three downstream systems."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def heron_db():
    """
    A fresh copy of the Heron database for one test, with the lab clock set.

    Use this for anything that writes (quotes, binds, adjustments) so tests
    cannot affect each other. Restores the shared database afterwards.
    """
    shared = heron.CN
    heron.USEDB(herondb.OPENDB(LEGACY_DATA))
    heron.SETSYSDT(heron.D2I(today()))
    yield heron
    heron.USEDB(shared)
    heron.SETSYSDT(heron.D2I(today()))


@pytest.fixture
def lab_date():
    """The frozen lab date as a datetime.date."""
    return today()
