"""
Card 1: for an existing customer, pricing uses the Claims Desk's claim count,
not the typed one. New customers, and a Claims Desk that is down, use the typed figure.
"""
import datetime

import pytest

from modern import api

VARROWSTONE = "4000218"  # Heron keyed 0 claims; the Claims Desk has 2
RISK = {"product": "CL", "trade_code": "CONS", "postcode": "LS117MK", "turnover": 1800000, "employees": 22}
DOWN_MESSAGE = "Claims Desk not reachable: priced on the typed figure."


@pytest.fixture
def claims_desk(client, monkeypatch):
    """Route the API's Claims Desk call to the real Claims Desk app, and record each call."""
    calls = []

    def fetch(insured_ref):
        calls.append(insured_ref)
        r = client.get("/api/systems/claims/experience", params={"insured_ref": insured_ref})
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(api, "_fetch_claims_experience", fetch)
    return calls


def price(client, typed, insured_ref=None):
    body = {"risk": {**RISK, "claims_count_3y": typed}, "broker_code": "B003", "insured_ref": insured_ref}
    r = client.post("/api/v1/quotes/price", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def claims_factor(result):
    return [f["label"] for f in result["price"]["schedule"]["factors"] if f["label"].startswith("Claims")]


def quote(client, lab_date, typed):
    body = {"risk": {**RISK, "claims_count_3y": typed}, "broker_code": "B003", "insured_ref": VARROWSTONE,
            "inception_date": (lab_date + datetime.timedelta(days=14)).isoformat()}
    r = client.post("/api/v1/quotes", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_existing_customer_priced_on_claims_desk_count(client, claims_desk):
    result = price(client, typed=0, insured_ref=VARROWSTONE)
    assert result["claims_count"]["value"] == 2
    assert result["claims_count"]["source"] == "claims_desk"
    assert claims_factor(result) == ["Claims in last three years: 2"]
    assert result["price"]["gross_premium"] == price(client, typed=2)["price"]["gross_premium"]
    assert claims_desk == [VARROWSTONE]


def test_new_customer_uses_typed_count(client, claims_desk):
    result = price(client, typed=3)
    assert result["claims_count"] == {"value": 3, "source": "typed", "claims_desk_unavailable": False, "message": None}
    assert claims_factor(result) == ["Claims in last three years: 3"]
    assert claims_desk == []


def test_claims_desk_down_falls_back_to_typed(client):
    # conftest.py points ESTATE_BASE_URL at a closed port, so the real HTTP call fails.
    result = price(client, typed=1, insured_ref=VARROWSTONE)
    assert result["claims_count"]["value"] == 1
    assert result["claims_count"]["source"] == "typed"
    assert result["claims_count"]["claims_desk_unavailable"] is True
    assert result["claims_count"]["message"] == DOWN_MESSAGE
    assert claims_factor(result) == ["Claims in last three years: 1"]


def test_saved_quote_carries_claims_desk_count(client, heron_db, lab_date, claims_desk):
    shown = price(client, typed=0, insured_ref=VARROWSTONE)
    saved = quote(client, lab_date, typed=0)
    assert saved["policy"]["risk"]["claims_count_3y"] == 2
    assert saved["claims_count"]["source"] == "claims_desk"
    assert saved["price"]["gross_premium"] == shown["price"]["gross_premium"]


def test_create_quote_when_claims_desk_down(client, heron_db, lab_date):
    saved = quote(client, lab_date, typed=1)
    assert saved["policy"]["risk"]["claims_count_3y"] == 1
    assert saved["claims_count"]["claims_desk_unavailable"] is True
