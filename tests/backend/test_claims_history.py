"""
Card 5: the policy page lists the policy's claims from the Claims Desk and flags
when Heron's keyed count is lower than the Claims Desk's count before the term
started. Heron's figure is never changed.
"""
import pytest

from modern import api

DOWN_MESSAGE = "Claims Desk not reachable: claims history not shown."


@pytest.fixture
def claims_desk(client, monkeypatch):
    """Route the API's Claims Desk calls to the real Claims Desk app."""
    def get(path, params):
        r = client.get("/api/systems/claims" + path, params=params)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(api, "_claims_desk_get", get)


def policy(client, ref):
    r = client.get(f"/api/v1/policies/{ref}")
    assert r.status_code == 200, r.text
    return r.json()


def test_policy_lists_claims_from_claims_desk(client, claims_desk):
    claims = policy(client, "LDL0010245")["claims"]
    assert claims["available"] is True
    assert [c["claim_ref"] for c in claims["claims"]] == ["CLM-2026-000124", "CLM-2026-000112"]
    newest, older = claims["claims"]
    assert newest["loss_date"] == "2026-08-09" and newest["status"] == "open" and newest["outstanding"] == 8645.04
    assert older["loss_date"] == "2026-04-26" and older["status"] == "settled" and older["paid"] == 17590.29
    for c in claims["claims"]:
        assert c["description"] and c["term"] == 2


def test_flags_when_heron_count_is_lower(client, claims_desk):
    p = policy(client, "LDL0010245")
    c = p["claims"]
    assert (c["heron_count"], c["claims_desk_count"]) == (0, 2)
    assert c["compared_as_at"] == "2026-08-23"
    assert c["lower_in_heron"] is True
    assert p["risk"]["claims_count_3y"] == 0  # Heron's figure is untouched


def test_no_flag_when_counts_agree(client, claims_desk):
    c = policy(client, "LDL0010003")["claims"]
    assert c["heron_count"] == c["claims_desk_count"] == 1
    assert c["lower_in_heron"] is False


def test_policy_with_no_claims(client, claims_desk):
    c = policy(client, "LDC0010001")["claims"]
    assert c["available"] is True
    assert c["claims"] == []
    assert c["lower_in_heron"] is False


def test_policy_loads_when_claims_desk_down(client):
    # conftest.py points ESTATE_BASE_URL at a closed port, so the real HTTP calls fail.
    p = policy(client, "LDL0010245")
    assert p["policy_ref"] == "LDL0010245" and p["transactions"]
    assert p["claims"]["available"] is False
    assert p["claims"]["message"] == DOWN_MESSAGE
    assert p["claims"]["lower_in_heron"] is False
