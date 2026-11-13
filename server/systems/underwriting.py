"""
Underwriting Workbench (mock downstream system).

Owned by the underwriting team. Holds risk appetite, the technical pricing
model, postcode accumulations and the referral queue. Heron does not call it:
branch staff re-key referred risks into the workbench by hand.

Conventions: pounds as decimals, ISO dates, postcodes with or without a space.
Mounted at /api/systems/underwriting. Interactive docs at .../docs.
"""
import datetime
import re
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from systems.common import LOCK, load_json, money, today

app = FastAPI(title='Underwriting Workbench', version='2.3.0',
              description='Risk appetite, technical price, accumulations and referrals.')

STATE = {}


def load():
    with LOCK:
        STATE['appetite'] = load_json('underwriting', 'appetite.json')
        STATE['rates'] = load_json('underwriting', 'technical_rates.json', {})
        STATE['accumulations'] = load_json('underwriting', 'accumulations.json')
        STATE['referrals'] = load_json('underwriting', 'referrals.json')


load()


class RiskIn(BaseModel):
    product: str = Field(..., description="'CP' commercial property or 'CL' combined liability")
    trade_code: str
    postcode: str
    construction: int = 1
    sum_insured_buildings: float = 0
    sum_insured_contents: float = 0
    sum_insured_bi: float = 0
    turnover: float = 0
    employees: int = 0
    voluntary_excess: float = 0
    claims_count_3y: int = 0
    quoted_premium: Optional[float] = Field(None, description='Annual gross premium excluding IPT, if already priced')
    policy_ref: Optional[str] = None


class DecisionIn(BaseModel):
    decision: str = Field(..., description="'approved' or 'declined'")
    underwriter: str
    notes: str = ''


def area_of(postcode: str) -> str:
    m = re.match(r'^[A-Z]{1,2}', postcode.upper().replace(' ', ''))
    return m.group(0) if m else ''


def district_of(postcode: str) -> str:
    pc = postcode.upper().replace(' ', '')
    return pc[:-3] if len(pc) > 3 else pc


def technical_premium(r: RiskIn) -> float:
    """The underwriting team's own view of the annual price, in pounds."""
    t = STATE['rates']
    claims = t['claims_factor'][str(min(max(r.claims_count_3y, 0), 3))]
    if r.product == 'CP':
        base = (r.sum_insured_buildings * t['base']['buildings'] + r.sum_insured_contents * t['base']['contents']
                + r.sum_insured_bi * t['base']['bi']) / 1000.0
        excess = 0.10 if r.voluntary_excess >= 2500 else 0.05 if r.voluntary_excess >= 1000 else \
            0.025 if r.voluntary_excess >= 500 else 0.0
        p = base * t['trade'][r.trade_code] * t['area'].get(area_of(r.postcode), 1.0) \
            * t['construction'][str(r.construction)] * claims * (1 - excess)
        return money(max(p, t['minimum']['CP']))
    p = r.employees * t['el_per_employee'][r.trade_code] + r.turnover / 1000.0 * t['pl_per_1000_turnover'][r.trade_code]
    p = p * claims * (0.90 if r.turnover > 2000000 else 1.0)
    return money(max(p, t['minimum']['CL']))


def accumulation_for(district: str) -> dict:
    for a in STATE['accumulations']:
        if a['postcode_district'] == district:
            return a
    return {'postcode_district': district, 'live_total_si': 0.0, 'limit': 20000000.0, 'live_policies': 0}


@app.get('/health')
def health():
    return {'system': 'underwriting', 'status': 'up', 'referrals': len(STATE['referrals']),
            'districts': len(STATE['accumulations'])}


@app.get('/appetite')
def get_appetite():
    """Risk appetite by trade."""
    return STATE['appetite']


@app.get('/appetite/{trade_code}')
def get_trade_appetite(trade_code: str):
    for a in STATE['appetite']:
        if a['trade_code'] == trade_code.upper():
            return a
    raise HTTPException(status_code=404, detail='Unknown trade code')


@app.get('/accumulations')
def get_accumulations(min_utilisation_pct: float = 0):
    out = []
    for a in STATE['accumulations']:
        u = round(100.0 * a['live_total_si'] / a['limit'], 1) if a['limit'] else 0.0
        if u >= min_utilisation_pct:
            out.append({**a, 'utilisation_pct': u})
    return sorted(out, key=lambda x: -x['utilisation_pct'])


@app.get('/accumulations/{postcode_district}')
def get_accumulation(postcode_district: str):
    a = accumulation_for(postcode_district.upper().replace(' ', ''))
    return {**a, 'utilisation_pct': round(100.0 * a['live_total_si'] / a['limit'], 1) if a['limit'] else 0.0}


@app.post('/assessments')
def assess(risk: RiskIn):
    """Assess a risk: appetite, technical price, accumulation and a decision."""
    trade = risk.trade_code.upper()
    appetite = next((a for a in STATE['appetite'] if a['trade_code'] == trade), None)
    if not appetite:
        raise HTTPException(status_code=422, detail='Unknown trade code')
    if risk.product not in ('CP', 'CL'):
        raise HTTPException(status_code=422, detail='Unknown product')
    risk.trade_code = trade
    reasons: List[dict] = []
    total_si = risk.sum_insured_buildings + risk.sum_insured_contents + risk.sum_insured_bi
    decision = 'accept'
    if appetite['appetite'] == 'closed':
        decision = 'decline'
        reasons.append({'code': 'APPETITE_CLOSED', 'detail': 'Trade is outside appetite: ' + appetite['notes']})
    if appetite['appetite'] == 'refer':
        reasons.append({'code': 'TRADE_REFER', 'detail': appetite['notes']})
    if risk.claims_count_3y >= 3:
        reasons.append({'code': 'CLAIMS_FREQUENCY', 'detail': '%d claims in three years' % risk.claims_count_3y})
    district = district_of(risk.postcode)
    acc = accumulation_for(district)
    accumulation = None
    if risk.product == 'CP':
        if total_si > appetite['max_total_si']:
            reasons.append({'code': 'LINE_SIZE', 'detail': 'Total sum insured %.0f exceeds trade line %.0f'
                            % (total_si, appetite['max_total_si'])})
        after = acc['live_total_si'] + total_si
        util = round(100.0 * after / acc['limit'], 1) if acc['limit'] else 0.0
        accumulation = {'postcode_district': district, 'live_total_si': acc['live_total_si'],
                        'limit': acc['limit'], 'utilisation_pct_after_bind': util}
        if util > 90.0:
            reasons.append({'code': 'ACCUMULATION', 'detail': 'District %s would be %.1f%% of its limit' % (district, util)})
        if risk.construction == 3 and trade in ('REST', 'HOTL', 'FOOD'):
            reasons.append({'code': 'CONSTRUCTION_HAZARD', 'detail': 'Timber frame with cooking risk'})
    else:
        if risk.employees > 250 or risk.turnover > 10000000:
            reasons.append({'code': 'LARGE_ACCOUNT', 'detail': 'Over 250 employees or turnover above 10m'})
    technical = technical_premium(risk)
    deviation = None
    if risk.quoted_premium is not None and technical:
        deviation = round(100.0 * (risk.quoted_premium - technical) / technical, 1)
        if deviation < -8.0:
            reasons.append({'code': 'PRICE_BELOW_TECHNICAL',
                            'detail': 'Quoted premium is %.1f%% below the technical price' % abs(deviation)})
    if decision != 'decline' and reasons:
        decision = 'refer'
    authority = 'branch'
    if decision == 'refer':
        authority = 'head_of_underwriting' if (total_si > 10000000 or len(reasons) >= 3) else 'senior_underwriter'
    with LOCK:
        STATE['seq'] = STATE.get('seq', 0) + 1
        ref = 'UWA-%s-%05d' % (today().strftime('%y%m'), STATE['seq'])
    return {'assessment_ref': ref, 'decision': decision, 'authority_required': authority, 'reasons': reasons,
            'technical_premium': technical, 'quoted_premium': risk.quoted_premium,
            'deviation_from_technical_pct': deviation, 'accumulation': accumulation,
            'appetite': appetite['appetite']}


@app.get('/referrals')
def list_referrals(status: Optional[str] = None, policy_ref: Optional[str] = None):
    out = STATE['referrals']
    if status:
        out = [r for r in out if r['status'] == status]
    if policy_ref:
        out = [r for r in out if r['policy_ref'] == policy_ref.upper()]
    return out


@app.get('/referrals/{referral_ref}')
def get_referral(referral_ref: str):
    for r in STATE['referrals']:
        if r['referral_ref'] == referral_ref:
            return r
    raise HTTPException(status_code=404, detail='Referral not found')


class ReferralIn(BaseModel):
    policy_ref: str
    policy_term: int = 1
    reasons: List[str]
    raised_by: str = 'modern-pas'


@app.post('/referrals', status_code=201)
def create_referral(body: ReferralIn):
    with LOCK:
        n = len(STATE['referrals']) + 1
        ref = {'referral_ref': 'REF-%06d' % n, 'policy_ref': body.policy_ref.upper(), 'policy_term': body.policy_term,
               'raised_date': today().isoformat(), 'reasons': body.reasons, 'status': 'open',
               'decided_by': None, 'decided_date': None, 'raised_by': body.raised_by, 'notes': ''}
        STATE['referrals'].append(ref)
        return ref


@app.post('/referrals/{referral_ref}/decision')
def decide_referral(referral_ref: str, body: DecisionIn):
    if body.decision not in ('approved', 'declined'):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'declined'")
    with LOCK:
        for r in STATE['referrals']:
            if r['referral_ref'] == referral_ref:
                if r['status'] != 'open':
                    raise HTTPException(status_code=409, detail='Referral already decided')
                r.update(status=body.decision, decided_by=body.underwriter,
                         decided_date=today().isoformat(), notes=body.notes)
                return r
    raise HTTPException(status_code=404, detail='Referral not found')
