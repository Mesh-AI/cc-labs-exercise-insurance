"""
Characterisation tests for the Heron policy lifecycle: quote, bind, adjust,
cancel and renew.

Each test gets its own copy of the Heron database (the heron_db fixture) and
moves Heron's system date with SETSYSDT, the test harness the original team
left in. Expected values were produced by running Heron itself.
"""
import pytest

LAB_DATE = 20261112


def commission(heron, premium, broker="B001"):
    """Commission at the broker's own rate, so the tests do not depend on the generated broker table."""
    rate = heron.Q1("SELECT COMMPC FROM BRKMST WHERE BRKCD=?", (broker,))["COMMPC"]
    return heron.CALCCOM(premium, rate)


def quote(heron, **changes):
    form = dict(PRODCD="CP", BRKCD="B001", INSNAM="GOLDEN TEST LTD", ADDR1="1 TEST ROAD", TOWN="SHEFFIELD",
                PCODE="S1 2KV", INCDT="20/11/2026", TRDCD="RETL", CONSTR=1, SIBLD=650000, SICONT=180000,
                SIBI=250000, VOLXS=250, CLMCNT3=0)
    form.update(changes)
    return heron.NBQTE(form, "CLERK1")


@pytest.fixture
def heron(heron_db):
    heron_db.SETSYSDT(LAB_DATE)
    return heron_db


@pytest.fixture
def live_policy(heron):
    """A bound reference policy, incepting 20 November 2026 at 1,377.03 a year."""
    q = quote(heron)
    heron.NBBND(q["POLNO"])
    return q["POLNO"]


class TestNewBusiness:
    def test_quote_is_saved_as_status_q_with_no_transaction(self, heron):
        q = quote(heron)
        policy = heron.GETPOL(q["POLNO"])
        assert (q["GRSPRM"], q["IPTAMT"], q["COMAMT"], q["UWREF"]) == (137703, 16524, commission(heron, 137703), "N")
        assert policy["STATCD"] == "Q"
        assert policy["EXPDT"] == 20271120
        assert heron.QA("SELECT * FROM PRMTRN WHERE POLNO=?", (q["POLNO"],)) == []

    def test_bind_writes_the_new_business_transaction(self, heron):
        q = quote(heron)
        t = heron.NBBND(q["POLNO"])
        assert heron.GETPOL(q["POLNO"])["STATCD"] == "L"
        com = commission(heron, 137703)
        assert (t["TRNTYP"], t["EFFDT"], t["GRSPRM"], t["IPTAMT"], t["COMAMT"], t["NETAMT"]) == (
            "NB", 20261120, 137703, 16524, com, 137703 - com)

    @pytest.mark.parametrize("changes,message", [
        (dict(INCDT="01/10/2026"), "INCEPTION MORE THAN 30 DAYS IN THE PAST"),
        (dict(INCDT="01/03/2027"), "INCEPTION MORE THAN 90 DAYS AHEAD"),
        (dict(SIBLD=25000000), "DECLINE - EXCEEDS MAXIMUM LINE 25,000,000"),
        (dict(PCODE="XX"), "INVALID POSTCODE XX"),
        (dict(TRDCD="ZZZZ"), "INVALID TRADE CODE ZZZZ"),
    ])
    def test_quote_is_rejected(self, heron, changes, message):
        with pytest.raises(heron.HeronErr, match=message):
            quote(heron, **changes)

    def test_suspended_broker_cannot_place_new_business(self, heron):
        suspended = heron.Q1("SELECT BRKCD FROM BRKMST WHERE STATCD='S'")["BRKCD"]
        with pytest.raises(heron.HeronErr, match="BROKER SUSPENDED"):
            quote(heron, BRKCD=suspended)

    def test_referred_quote_needs_a_named_underwriter_to_bind(self, heron):
        """Authority is a hard-coded list of user ids (UWAUTH), not a decision recorded anywhere."""
        q = quote(heron, TRDCD="WOOD")
        assert q["UWREF"] == "Y"
        assert q["REFRSN"] == ["R02 TRADE REQUIRES UNDERWRITER APPROVAL"]
        with pytest.raises(heron.HeronErr, match="UNDERWRITER AUTHORITY REQUIRED"):
            heron.NBBND(q["POLNO"], "CLERK1")
        assert heron.NBBND(q["POLNO"], "UWMGR1")["TRNTYP"] == "NB"

    def test_quote_expires_after_thirty_days(self, heron):
        q = quote(heron)
        heron.SETSYSDT(20261215)
        with pytest.raises(heron.HeronErr, match="QUOTE EXPIRED"):
            heron.NBBND(q["POLNO"])


class TestMidTermAdjustment:
    def test_additional_premium_is_pro_rata_over_365_days(self, heron, live_policy):
        m = heron.MTAENT(live_policy, dict(EFFDT="01/12/2026", SICONT=240000))
        # annual goes 1,377.03 -> 1,513.82. 354 of 365 days left: 136.79 x 354 / 365 = 132.67
        assert (m["OLDPRM"], m["NEWPRM"], m["DAYS"], m["PRMADJ"], m["IPTADJ"], m["ENDTYP"]) == (
            137703, 151382, 354, 13267, 1592, "SI")
        assert (m["TRN"]["TRNTYP"], m["TRN"]["GRSPRM"], m["TRN"]["COMAMT"]) == ("MTA", 13267, commission(heron, 13267))
        assert heron.GETPOL(live_policy)["GRSPRM"] == 151382

    def test_return_premium_is_negative(self, heron, live_policy):
        m = heron.MTAENT(live_policy, dict(EFFDT="10/12/2026", SICONT=150000))
        assert m["PRMADJ"] < 0
        assert m["IPTADJ"] == heron.CALCIPT(m["PRMADJ"])

    def test_adjustment_under_ten_pounds_is_waived(self, heron, live_policy):
        """The cover changes and an endorsement is written, but no premium transaction."""
        m = heron.MTAENT(live_policy, dict(EFFDT="01/12/2026", SICONT=181000))
        assert m["NEWPRM"] != m["OLDPRM"]
        assert m["PRMADJ"] == 0
        assert m["TRN"] is None

    def test_leap_year_term_charges_more_than_a_full_year(self, heron):
        """
        QUIRK 3. Pro rata always divides by 365 (change of 2006-11). A term that
        contains 29 February has 366 days, so an adjustment on day one is charged
        366/365 of the annual difference: 137.16 for a 136.79 increase.
        """
        heron.SETSYSDT(20270301)
        q = quote(heron, INCDT="01/03/2027")
        heron.NBBND(q["POLNO"])
        m = heron.MTAENT(q["POLNO"], dict(EFFDT="01/03/2027", SICONT=240000))
        assert m["DAYS"] == 366
        assert m["NEWPRM"] - m["OLDPRM"] == 13679
        assert m["PRMADJ"] == 13716

    def test_changes_that_trigger_a_referral_are_blocked_for_a_clerk(self, heron, live_policy):
        with pytest.raises(heron.HeronErr, match="REFERRED - R03"):
            heron.MTAENT(live_policy, dict(EFFDT="01/12/2026", SIBLD=4800000), "CLERK1")
        assert heron.MTAENT(live_policy, dict(EFFDT="01/12/2026", SIBLD=4800000), "UWMGR1")["REFRSN"]

    def test_effective_date_must_be_inside_the_term(self, heron, live_policy):
        with pytest.raises(heron.HeronErr, match="OUTSIDE POLICY PERIOD"):
            heron.MTAENT(live_policy, dict(EFFDT="20/11/2027", SICONT=240000))


class TestCancellation:
    def test_pro_rata_refund_less_ten_percent(self, heron, live_policy):
        c = heron.CANENT(live_policy, "15/01/2027")
        # 309 days left of 1,377.03: x 309 / 365 x 0.90 = 1,049.18
        assert c["REFUND"] == 104918
        assert c["TRN"]["GRSPRM"] == -104918
        policy = heron.GETPOL(live_policy)
        assert (policy["STATCD"], policy["CANDT"]) == ("X", 20270115)

    def test_cooling_off_keeps_the_minimum_retained_premium(self, heron, live_policy):
        """
        Within 14 days of inception the rule is everything back less a 25.00 fee,
        but the 50.00 minimum retained premium is applied afterwards and wins, so
        the customer actually loses 50.00, not 25.00.
        """
        assert heron.CANENT(live_policy, "30/11/2026")["REFUND"] == 137703 - 5000

    def test_no_refund_if_the_claim_marker_is_set(self, heron, live_policy):
        """CLMCUR is keyed by hand from the claims system. If it is wrong, so is the refund."""
        heron.CN.execute("UPDATE POLMST SET CLMCUR='Y' WHERE POLNO=?", (live_policy,))
        c = heron.CANENT(live_policy, "15/01/2027")
        assert c["REFUND"] == 0
        assert c["TRN"] is None

    def test_minimum_retained_premium(self, heron):
        """Heron always keeps at least 50.00 of the premium."""
        q = quote(heron, SIBLD=0, SICONT=15000, SIBI=0)
        heron.NBBND(q["POLNO"])
        assert heron.CANENT(q["POLNO"], "22/11/2026")["REFUND"] == 17500 - 5000


class TestRenewal:
    def test_buildings_are_index_linked_and_a_new_term_is_written(self, heron, live_policy):
        heron.SETSYSDT(20271101)
        r = heron.RNWRUN(live_policy, "CLERK1", 0)
        new, old = heron.GETPOL(live_policy), heron.GETPOL(live_policy, 1)
        assert (r["POLSFX"], old["STATCD"], new["STATCD"]) == (2, "R", "L")
        assert new["SIBLD"] == 676000                # 650,000 + 4%, to the nearest thousand
        assert (new["INCDT"], new["EXPDT"]) == (20271120, 20281120)
        assert r["NEWPRM"] == 140049
        assert r["TRN"]["TRNTYP"] == "RN"

    def test_increase_is_capped_at_fifteen_percent_when_claims_have_not_worsened(self, heron, live_policy):
        heron.CN.execute("UPDATE RATTBL SET RATVAL='1.30' WHERE RATTYP='TRADE' AND RATKEY='RETL'")
        heron.SETSYSDT(20271101)
        assert heron.RNWRUN(live_policy, "CLERK1", 0)["NEWPRM"] == int(137703 * 1.15)

    def test_cap_does_not_apply_when_claims_have_worsened(self, heron, live_policy):
        heron.SETSYSDT(20271101)
        r = heron.RNWRUN(live_policy, "CLERK1", 3)
        assert r["NEWPRM"] > int(137703 * 1.15)
        assert r["REFRSN"] == ["R01 THREE OR MORE CLAIMS IN 3 YEARS"]

    def test_renewal_only_runs_within_sixty_days_of_expiry(self, heron, live_policy):
        with pytest.raises(heron.HeronErr, match="TOO EARLY"):
            heron.RNWRUN(live_policy)
