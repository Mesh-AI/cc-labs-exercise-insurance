"""
Card 3: every priced quote shows underwriting's technical price and the gap,
flags more than 8% below, and never changes Heron's price or decision.
"""
import pytest

from modern import api

SHOP = {"product": "CP", "trade_code": "RETL", "construction": 1, "sum_insured_buildings": 250000,
        "sum_insured_contents": 60000, "sum_insured_bi": 0, "voluntary_excess": 250, "claims_count_3y": 0}
MANCHESTER, SHEFFIELD = "M43KV", "S12KV"
DOWN_MESSAGE = "Underwriting Workbench not reachable: no technical price check."


@pytest.fixture
def workbench(client, monkeypatch):
    """Route the API's Workbench call to the real Underwriting Workbench app."""
    def post(body):
        r = client.post("/api/systems/underwriting/assessments", json=body)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(api, "_post_assessment", post)


def price(client, postcode):
    r = client.post("/api/v1/quotes/price", json={"risk": {**SHOP, "postcode": postcode}})
    assert r.status_code == 200, r.text
    return r.json()


def test_manchester_shop_flagged_below_technical(client, workbench):
    t = price(client, MANCHESTER)["technical"]
    assert t["available"] is True
    assert t["technical_premium"] == 405.92
    assert t["quoted_premium"] == 362.43
    assert t["deviation_pct"] == -10.7
    assert t["below_threshold"] is True


def test_sheffield_shop_not_flagged(client, workbench):
    t = price(client, SHEFFIELD)["technical"]
    assert t["available"] is True
    assert t["deviation_pct"] == 0.0
    assert t["below_threshold"] is False


@pytest.mark.parametrize("deviation, flagged", [(-8.0, False), (-8.1, True), (5.0, False)])
def test_threshold_is_more_than_8_pct_below(client, monkeypatch, deviation, flagged):
    monkeypatch.setattr(api, "_post_assessment",
                        lambda body: {"technical_premium": 100.0, "deviation_from_technical_pct": deviation})
    t = price(client, MANCHESTER)["technical"]
    assert t["deviation_pct"] == deviation
    assert t["below_threshold"] is flagged


def test_heron_price_and_decision_unchanged(client, monkeypatch, workbench):
    up = price(client, MANCHESTER)
    assert up["technical"]["below_threshold"] is True  # the Workbench itself would refer this

    def down(body):
        raise OSError("Workbench down")

    monkeypatch.setattr(api, "_post_assessment", down)
    without = price(client, MANCHESTER)
    assert up["price"] == without["price"]
    assert up["price"]["gross_premium"] == 362.43
    assert up["decision"] == without["decision"] == "accept"
    assert up["decision_reasons"] == []


def test_workbench_down_still_prices(client):
    # conftest.py points ESTATE_BASE_URL at a closed port, so the real HTTP call fails.
    result = price(client, MANCHESTER)
    assert result["price"]["gross_premium"] == 362.43
    assert result["technical"]["available"] is False
    assert result["technical"]["message"] == DOWN_MESSAGE
    assert result["technical"]["below_threshold"] is False
