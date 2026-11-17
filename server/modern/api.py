"""
The new policy API, /api/v1.

Two journeys run through it today: new business quote and bind, and mid-term
adjustment. Heron still prices and still holds every policy, so the answers
are exactly the legacy answers (see modern/adapter.py).

For an existing customer, pricing reads the claims count from the Claims Desk
over HTTP (card 1). Underwriting and finance are not connected yet: people
still carry that data between systems by hand.
"""
import json
import os
import urllib.parse
import urllib.request
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modern import adapter

router = APIRouter(prefix='/api/v1', tags=['policy'])


class Risk(BaseModel):
    product: str = Field(..., description="'CP' commercial property or 'CL' combined liability")
    trade_code: str
    postcode: str
    construction: int = 1
    sum_insured_buildings: int = 0
    sum_insured_contents: int = 0
    sum_insured_bi: int = 0
    turnover: int = 0
    employees: int = 0
    voluntary_excess: int = 250
    claims_count_3y: int = 0


class Insured(BaseModel):
    name: str
    address: str = ''
    town: str = ''


class PriceRequest(BaseModel):
    risk: Risk
    broker_code: Optional[str] = None
    insured_ref: Optional[str] = None


class QuoteRequest(BaseModel):
    risk: Risk
    broker_code: str
    inception_date: str = Field(..., description='ISO date')
    insured: Optional[Insured] = None
    insured_ref: Optional[str] = None
    user: str = 'CLERK1'


class BindRequest(BaseModel):
    user: str = 'CLERK1'


class AdjustmentRequest(BaseModel):
    effective_date: str = Field(..., description='ISO date')
    changes: dict = Field(..., description='Only the fields that change, e.g. {"sum_insured_contents": 240000}')
    user: str = 'CLERK1'


def _legacy(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except adapter.LegacyError as ex:
        raise HTTPException(status_code=422, detail=str(ex))


def _decision(price):
    """Heron's own referral rules, in the shape the front end shows them."""
    reasons = [{'source': 'Heron', 'text': text} for text in price['referral_reasons']]
    return {'decision': 'refer' if reasons else 'accept', 'decision_reasons': reasons}


CLAIMS_DESK_DOWN = 'Claims Desk not reachable: priced on the typed figure.'


def _fetch_claims_experience(insured_ref):
    """Ask the Claims Desk, over HTTP, for an insured's claims experience. Raises on any failure."""
    base = os.environ.get('ESTATE_BASE_URL', 'http://localhost:8001/api/systems').rstrip('/')
    url = '%s/claims/experience?%s' % (base, urllib.parse.urlencode({'insured_ref': insured_ref}))
    with urllib.request.urlopen(url, timeout=2) as resp:
        return json.load(resp)


def _resolve_claims_count(risk: Risk, insured_ref):
    """
    For an existing customer, price on the Claims Desk's claims_count_3y instead of the typed
    figure. New customers, or a Claims Desk that does not answer, keep the typed figure.
    """
    typed = {'value': risk.claims_count_3y, 'source': 'typed', 'claims_desk_unavailable': False, 'message': None}
    if not insured_ref:
        return typed
    try:
        count = int(_fetch_claims_experience(insured_ref)['claims_count_3y'])
    except Exception:
        return {**typed, 'claims_desk_unavailable': True, 'message': CLAIMS_DESK_DOWN}
    risk.claims_count_3y = count
    return {'value': count, 'source': 'claims_desk', 'claims_desk_unavailable': False, 'message': None}


def _commission_pct(broker_code):
    if not broker_code:
        return None
    for b in adapter.lookups()['brokers']:
        if b['code'] == broker_code.upper():
            return b['commission_pct']
    return None


@router.get('/lookups')
def get_lookups():
    """Reference lists for the forms: products, trades, constructions, excesses and active brokers."""
    return adapter.lookups()


@router.get('/insureds')
def find_insureds(q: str):
    """Find an existing insured by name."""
    return adapter.find_insureds(q) if len(q.strip()) >= 2 else []


@router.post('/quotes/price')
def price_quote(body: PriceRequest):
    """Price a risk without saving anything. Safe to call on every keystroke."""
    claims_count = _resolve_claims_count(body.risk, body.insured_ref)
    price = _legacy(adapter.price, body.risk.model_dump(), _commission_pct(body.broker_code))
    return {'price': price, 'claims_count': claims_count, **_decision(price)}


@router.post('/quotes', status_code=201)
def create_quote(body: QuoteRequest):
    """Save a quote in Heron. Returns the policy with its price."""
    if not body.insured and not body.insured_ref:
        raise HTTPException(status_code=422, detail='Give an insured name or an existing insured reference')
    claims_count = _resolve_claims_count(body.risk, body.insured_ref)
    q = _legacy(adapter.create_quote, body.risk.model_dump(), body.broker_code, body.inception_date,
                body.insured.model_dump() if body.insured else None, body.insured_ref, body.user)
    policy = adapter.policy_view(q['POLNO'])
    price = adapter.price(policy['risk'], policy['broker']['commission_pct'])
    return {'policy': policy, 'price': price, 'claims_count': claims_count, **_decision(price)}


@router.post('/quotes/{policy_ref}/bind')
def bind_quote(policy_ref: str, body: BindRequest):
    """Bind a saved quote. Heron writes the new business premium transaction."""
    trn = _legacy(adapter.bind_quote, policy_ref, body.user)
    return {'policy': adapter.policy_view(policy_ref), 'transaction': trn}


@router.get('/policies')
def list_policies(q: str = '', status: str = '', limit: int = 50):
    """Search by policy number, insured name or postcode. Latest term of each policy."""
    return adapter.search_policies(q, status, limit)


@router.get('/policies/{policy_ref}')
def get_policy(policy_ref: str):
    return _legacy(adapter.policy_view, policy_ref)


@router.post('/policies/{policy_ref}/adjustments/preview')
def preview_adjustment(policy_ref: str, body: AdjustmentRequest):
    """What would this change cost? Nothing is saved."""
    return _legacy(adapter.preview_adjustment, policy_ref, body.changes, body.effective_date, body.user)


@router.post('/policies/{policy_ref}/adjustments', status_code=201)
def apply_adjustment(policy_ref: str, body: AdjustmentRequest):
    """Apply a mid-term adjustment. Heron writes the endorsement and any premium transaction."""
    result = _legacy(adapter.apply_adjustment, policy_ref, body.changes, body.effective_date, body.user)
    return {'adjustment': result, 'policy': adapter.policy_view(policy_ref)}
