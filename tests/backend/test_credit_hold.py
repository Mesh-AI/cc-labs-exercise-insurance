"""
Card 4: warn on the quote screen when the broker has premium on credit hold
(unpaid over 60 days). Advice only: the price, decision and save are unchanged.
"""
import datetime

import pytest

from modern import api

RISK = {"product": "CL", "trade_code": "CONS", "postcode": "LS117MK", "turnover": 420000, "employees": 6,
        "claims_count_3y": 0}
DOWN_MESSAGE = "Finance Ledger not reachable: broker credit status not checked."


@pytest.fixture
def ledger(client, monkeypatch):
    """Route the API's ledger GET to the real Finance Ledger app; the 404 handling stays real."""
    def get(path):
        r = client.get("/api/systems" + path)
        return r.status_code, (r.json() if r.status_code == 200 else None)

    monkeypatch.setattr(api, "_ledger_get", get)


def price(client, broker_code):
    r = client.post("/api/v1/quotes/price", json={"risk": RISK, "broker_code": broker_code})
    assert r.status_code == 200, r.text
    return r.json()


def test_broker_on_credit_hold_is_flagged(client, ledger):
    credit = price(client, "B004")["broker_credit"]
    assert credit == {"checked": True, "on_hold": True, "policies_on_credit_hold": 19,
                      "overdue_amount": 66486.68, "message": None}


def test_broker_in_good_standing_shows_nothing(client, ledger):
    credit = price(client, "B001")["broker_credit"]
    assert credit["checked"] is True
    assert credit["on_hold"] is False
    assert credit["policies_on_credit_hold"] == 0


def test_broker_without_ledger_history_shows_nothing(client, ledger):
    assert client.get("/api/systems/finance/brokers/BRK-B999/statement").status_code == 404
    credit = price(client, "B999")["broker_credit"]
    assert credit["checked"] is True
    assert credit["on_hold"] is False


def test_no_broker_no_check(client, ledger):
    assert price(client, None)["broker_credit"] is None


def test_ledger_down_still_prices(client):
    # conftest.py points ESTATE_BASE_URL at a closed port, so the real HTTP call fails.
    result = price(client, "B004")
    assert result["price"]["gross_premium"] > 0
    assert result["broker_credit"]["checked"] is False
    assert result["broker_credit"]["on_hold"] is False
    assert result["broker_credit"]["message"] == DOWN_MESSAGE


def test_warning_does_not_block_or_change_price(client, heron_db, lab_date, ledger, monkeypatch):
    warned = price(client, "B004")
    assert warned["broker_credit"]["on_hold"] is True

    def down(path):
        raise OSError("Finance Ledger down")

    monkeypatch.setattr(api, "_ledger_get", down)
    unchecked = price(client, "B004")
    assert unchecked["broker_credit"]["checked"] is False
    for key in ("price", "decision", "decision_reasons"):
        assert warned[key] == unchecked[key]
    saved = client.post("/api/v1/quotes", json={
        "risk": RISK, "broker_code": "B004", "inception_date": (lab_date + datetime.timedelta(days=14)).isoformat(),
        "insured": {"name": "Cardle Lane Joinery Ltd", "address": "12 Cardle Lane", "town": "Leeds"}})
    assert saved.status_code == 201, saved.text
