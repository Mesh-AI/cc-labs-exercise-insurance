"""
Characterisation tests for Heron's rating and referral rules.

These tests do not say what the rules should be. They pin down what Heron does
today, to the penny, so that anything built on top can prove it gives the same
answer. Every expected value below was produced by running Heron itself.

Three behaviours are pinned that look wrong. They are marked QUIRK. Do not
"fix" them here: changing a price is a business decision for underwriting and
finance, not a refactor. See docs/DOMAIN.md for the full list.
"""
import pytest

# The reference risk: a retail shop in Sheffield (S1, no area loading), standard
# construction, 250 excess, no claims. Premiums are in pence, as Heron holds them.
BASE = dict(prod="CP", trd="RETL", pcode="S12KV", constr=1, sibld=650000, sicont=180000, sibi=250000,
            turnov=0, empcnt=0, volxs=250, clmcnt=0)
BASE_PREMIUM = 137703

LIABILITY = dict(prod="CL", trd="CONS", pcode="LS117MK", constr=1, sibld=0, sicont=0, sibi=0,
                 turnov=1800000, empcnt=22, volxs=0, clmcnt=0)


def rate(heron, **changes):
    return heron.CALCPRM(**dict(BASE, **changes))


class TestPropertyRating:
    """Commercial property: base rates, then trade, area, construction, claims and excess."""

    def test_reference_risk(self, heron_db):
        # 650,000 x 0.95 + 180,000 x 2.40 + 250,000 x 1.60 per mille = 1,449.50, x 0.95 claim free
        assert rate(heron_db) == BASE_PREMIUM

    @pytest.mark.parametrize("trade,expected", [
        ("OFFC", 110162), ("SALN", 123932), ("RETL", 137703), ("WHSE", 158358), ("LMFG", 172128),
        ("FOOD", 179013), ("HOTL", 185898), ("MOTR", 192783), ("REST", 199669), ("CONS", 151473),
        ("WOOD", 261635), ("WSTE", 302946),
    ])
    def test_trade_factor(self, heron_db, trade, expected):
        assert rate(heron_db, trd=trade) == expected

    @pytest.mark.parametrize("postcode,expected", [
        ("HU37OC", 185898), ("YO12MO", 165243), ("CA11KV", 172128), ("DN12KV", 158358),
        ("TS13KV", 151473), ("BD17KV", 159735), ("SE18KV", 156981), ("LS117MK", 145965),
    ])
    def test_two_letter_area_loadings_apply(self, heron_db, postcode, expected):
        assert rate(heron_db, pcode=postcode) == expected

    @pytest.mark.parametrize("postcode", ["L18KV", "M43KV", "E14IO", "B52KM", "G412KV"])
    def test_single_letter_area_loadings_do_not_apply(self, heron_db, postcode):
        """
        QUIRK 1. AREAFC holds loadings for L, M, E, B and G (change CHG0412, 2009),
        but AREFAC looks up the first two characters of the postcode, so 'M4' never
        matches 'M'. Liverpool, Manchester, east London, Birmingham and Glasgow have
        been priced with no area loading ever since. Pinned as it behaves.
        """
        assert heron_db.AREAFC[postcode[0]] > 1.0
        assert heron_db.AREFAC(postcode) == 1.0
        assert rate(heron_db, pcode=postcode) == BASE_PREMIUM

    def test_unloaded_area(self, heron_db):
        assert rate(heron_db, pcode="NE14KV") == BASE_PREMIUM

    @pytest.mark.parametrize("construction,expected", [(1, 137703), (2, 165243), (3, 199669), (4, 179013)])
    def test_construction_factor(self, heron_db, construction, expected):
        assert rate(heron_db, constr=construction) == expected

    @pytest.mark.parametrize("claims,expected", [(0, 137703), (1, 159445), (2, 181188), (3, 217425), (5, 217425)])
    def test_claims_loading(self, heron_db, claims, expected):
        """Claim free earns 5% off. One claim +10%, two +25%, three or more +50%."""
        assert rate(heron_db, clmcnt=claims) == expected

    @pytest.mark.parametrize("excess,expected", [
        (0, 137703), (250, 137703), (499, 137703), (500, 134260), (750, 134260),
        (1000, 130817), (2500, 123932), (5000, 123932),
    ])
    def test_voluntary_excess_discount_bands(self, heron_db, excess, expected):
        """Bands, not a table: anything from 500 gets 2.5%, from 1,000 gets 5%, from 2,500 gets 10%."""
        assert rate(heron_db, volxs=excess) == expected

    def test_minimum_premium(self, heron_db):
        assert rate(heron_db, sibld=0, sicont=15000, sibi=0) == 17500


class TestLiabilityRating:
    """Combined liability: a rate per employee plus a rate on turnover, by trade."""

    def test_contractor(self, heron_db):
        # 22 x 340 + 1,800 x 3.20 = 13,240, x 0.95 claim free
        assert heron_db.CALCPRM(**LIABILITY) == 1257800

    def test_claims_loading(self, heron_db):
        assert heron_db.CALCPRM(**dict(LIABILITY, clmcnt=2)) == 1655000

    def test_large_turnover_discount_starts_above_two_million(self, heron_db):
        """10% off above 2,000,000 turnover. At exactly 2,000,000 there is no discount."""
        at = heron_db.CALCPRM(**dict(LIABILITY, turnov=2000000))
        above = heron_db.CALCPRM(**dict(LIABILITY, turnov=2000001))
        assert at == 1318600
        assert above == 1186740
        assert above < at

    def test_minimum_premium(self, heron_db):
        assert heron_db.CALCPRM(**dict(LIABILITY, trd="OFFC", turnov=60000, empcnt=1)) == 25000

    @pytest.mark.parametrize("trade,expected", [
        ("OFFC", 64125), ("SALN", 99750), ("RETL", 104500), ("WHSE", 178125), ("LMFG", 242250), ("FOOD", 209000),
        ("HOTL", 142500), ("MOTR", 289750), ("REST", 166250), ("CONS", 475000), ("WOOD", 375250), ("WSTE", 532000),
    ])
    def test_trade_rates(self, heron_db, trade, expected):
        assert heron_db.CALCPRM(**dict(LIABILITY, trd=trade, turnov=500000, empcnt=10)) == expected


class TestTaxAndCommission:
    def test_ipt_is_twelve_percent(self, heron_db):
        assert heron_db.CALCIPT(137703) == 16524

    def test_ipt_drops_fractions_of_a_penny(self, heron_db):
        """
        QUIRK 2. 12% of 175.05 is 21.006. Heron drops the fraction rather than
        rounding, and for a return premium it drops towards zero. Finance has
        reconciled to this for years (the ledger accepts a penny's tolerance).
        """
        assert heron_db.CALCIPT(17505) == 2100
        assert heron_db.CALCIPT(-17505) == -2100
        assert heron_db.CALCIPT(-1) == 0

    def test_commission_rounds_half_up(self, heron_db):
        assert heron_db.CALCCOM(137703, 2750) == 37868
        assert heron_db.CALCCOM(-137703, 2750) == -37868
        assert heron_db.CALCCOM(100, 1750) == 18      # 17.5 rounds up
        assert heron_db.CALCCOM(150, 1750) == 26      # 26.25 rounds down


class TestReferralRules:
    """CHKREF returns the reasons a risk needs an underwriter. An empty list means branch authority."""

    def test_total_sum_insured_over_five_million(self, heron_db):
        r = heron_db.CHKREF
        assert r("CP", "RETL", "S12KV", 1, 4000000, 600000, 400000, 0, 0, 0) == []
        assert r("CP", "RETL", "S12KV", 1, 4000000, 600000, 400001, 0, 0, 0) == ["R03 TOTAL SUM INSURED OVER 5,000,000"]

    def test_flood_area_buildings_over_one_million(self, heron_db):
        r = heron_db.CHKREF
        assert r("CP", "RETL", "HU37OC", 1, 1000000, 0, 0, 0, 0, 0) == []
        assert r("CP", "RETL", "HU37OC", 1, 1000001, 0, 0, 0, 0, 0) == ["R04 FLOOD AREA BUILDINGS OVER 1,000,000"]
        assert r("CP", "RETL", "LS11KV", 1, 1000001, 0, 0, 0, 0, 0) == []      # loaded, but not a flood area

    def test_timber_frame_with_cooking(self, heron_db):
        r = heron_db.CHKREF
        assert r("CP", "REST", "S12KV", 3, 100000, 0, 0, 0, 0, 0) == ["R05 TIMBER FRAME WITH COOKING RISK"]
        assert r("CP", "RETL", "S12KV", 3, 100000, 0, 0, 0, 0, 0) == []

    def test_claims_and_trade_can_both_apply(self, heron_db):
        assert heron_db.CHKREF("CP", "WOOD", "S12KV", 1, 100000, 0, 0, 0, 0, 3) == [
            "R01 THREE OR MORE CLAIMS IN 3 YEARS", "R02 TRADE REQUIRES UNDERWRITER APPROVAL"]

    def test_liability_size_limits(self, heron_db):
        r = heron_db.CHKREF
        assert r("CL", "OFFC", "S12KV", 1, 0, 0, 0, 10000000, 250, 0) == []
        assert r("CL", "OFFC", "S12KV", 1, 0, 0, 0, 10000001, 251, 0) == [
            "R06 OVER 250 EMPLOYEES", "R07 TURNOVER OVER 10,000,000"]
        assert r("CL", "CONS", "S12KV", 1, 0, 0, 0, 2000001, 5, 2) == ["R08 CONTRACTOR TURNOVER OVER 2,000,000"]
