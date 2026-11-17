"""
Card 2: binding posts the premium to the Finance Ledger straight away, the
policy shows the ledger reference, and a ledger outage never breaks a bind.
"""
import datetime

import pytest

from modern import api
from systems import finance

RISK = {"product": "CL", "trade_code": "CONS", "postcode": "LS117MK", "turnover": 650000, "employees": 9}
DOWN_MESSAGE = "Finance Ledger not reachable: the premium will go in the overnight file."


@pytest.fixture(autouse=True)
def fresh_ledger():
    """Each fresh Heron copy reuses the next transaction number, so restore the ledger after each test."""
    postings, by_ref = list(finance.STATE["postings"]), dict(finance.STATE["by_ref"])
    yield
    finance.STATE["postings"][:] = postings
    finance.STATE["by_ref"].clear()
    finance.STATE["by_ref"].update(by_ref)


@pytest.fixture
def ledger(client, monkeypatch):
    """Route the API's ledger call to the real Finance Ledger app."""
    def post(posting):
        r = client.post("/api/systems/finance/postings", json=posting)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(api, "_post_to_ledger", post)


def bind_new_quote(client, lab_date):
    body = {"risk": {**RISK, "claims_count_3y": 0}, "broker_code": "B003",
            "inception_date": (lab_date + datetime.timedelta(days=14)).isoformat(),
            "insured": {"name": "Hollin Mill Bakery Ltd", "address": "4 Mill Yard", "town": "Leeds"}}
    q = client.post("/api/v1/quotes", json=body)
    assert q.status_code == 201, q.text
    ref = q.json()["policy"]["policy_ref"]
    b = client.post(f"/api/v1/quotes/{ref}/bind", json={"user": "CLERK1"})
    assert b.status_code == 200, b.text
    return b.json()


def ledger_rows(client, transaction_ref):
    r = client.get("/api/systems/finance/ledger", params={"transaction_ref": transaction_ref})
    assert r.status_code == 200
    return r.json()


def test_bind_posts_matching_premium_to_ledger(client, heron_db, lab_date, ledger):
    bound = bind_new_quote(client, lab_date)
    trn, policy = bound["transaction"], bound["policy"]
    assert bound["finance"]["posted"] is True
    assert bound["finance"]["posting_ref"].startswith("GL-")
    rows = ledger_rows(client, trn["transaction_ref"])
    assert len(rows) == 1
    p = rows[0]
    assert p["posting_ref"] == bound["finance"]["posting_ref"]
    assert p["policy_ref"] == policy["policy_ref"]
    assert p["policy_term"] == trn["term"]
    assert p["broker_account"] == policy["broker"]["account"]
    assert p["transaction_type"] == trn["type"] == "NB"
    assert p["effective_date"] == trn["effective_date"]
    assert p["gross_premium"] == trn["gross_premium"]
    assert p["ipt"] == trn["ipt"]
    assert p["commission"] == trn["commission"]


def test_policy_shows_ledger_reference(client, heron_db, lab_date, ledger):
    bound = bind_new_quote(client, lab_date)
    ref, trn_ref = bound["policy"]["policy_ref"], bound["transaction"]["transaction_ref"]
    assert bound["transaction"]["finance_ref"] == bound["finance"]["posting_ref"]
    policy = client.get(f"/api/v1/policies/{ref}").json()
    [t] = [t for t in policy["transactions"] if t["transaction_ref"] == trn_ref]
    assert t["finance_ref"] == bound["finance"]["posting_ref"]


def test_repeat_post_does_not_double_count(client, heron_db, lab_date, ledger):
    bound = bind_new_quote(client, lab_date)
    again = api._send_to_finance(bound["transaction"], bound["policy"])
    assert again["posted"] is True
    assert again["duplicate"] is True
    assert again["posting_ref"] == bound["finance"]["posting_ref"]
    assert len(ledger_rows(client, bound["transaction"]["transaction_ref"])) == 1


def test_bind_succeeds_when_ledger_down(client, heron_db, lab_date):
    # conftest.py points ESTATE_BASE_URL at a closed port, so the real HTTP call fails.
    bound = bind_new_quote(client, lab_date)
    assert bound["policy"]["status"] == "L"
    assert bound["transaction"]["transaction_ref"].startswith("HERON-")
    assert bound["finance"] == {"posted": False, "posting_ref": None, "duplicate": False, "message": DOWN_MESSAGE}
    assert bound["transaction"]["finance_ref"] is None
    assert ledger_rows(client, bound["transaction"]["transaction_ref"]) == []
