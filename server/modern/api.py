"""
The new policy API, /api/v1.

Two journeys run through it today: new business quote and bind, and mid-term
adjustment. Heron still prices and still holds every policy, so the answers
are exactly the legacy answers (see modern/adapter.py).

For an existing customer, pricing reads the claims count from the Claims Desk
over HTTP (card 1), and binding posts the premium to the Finance Ledger
(card 2). Pricing also shows underwriting's technical price (card 3) and warns
when the broker has premium on credit hold (card 4), and the policy page lists
the policy's claims from the Claims Desk (card 5), all as advice only:
referrals are still re-keyed into the Workbench by hand.
"""
import datetime
import json
import os
import urllib.error
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


LEDGER_DOWN = 'Finance Ledger not reachable: the premium will go in the overnight file.'


def _post_to_ledger(posting):
    """POST a premium transaction to the Finance Ledger over HTTP. Raises on any failure."""
    base = os.environ.get('ESTATE_BASE_URL', 'http://localhost:8001/api/systems').rstrip('/')
    req = urllib.request.Request('%s/finance/postings' % base, data=json.dumps(posting).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.load(resp)


def _send_to_finance(trn, policy):
    """
    Post Heron's transaction to the ledger and stamp the ledger reference back on it.
    The ledger is idempotent on transaction_ref, so a repeat never double counts.
    If the ledger does not answer, the overnight file still carries the premium.
    """
    posting = {'transaction_ref': trn['transaction_ref'], 'policy_ref': policy['policy_ref'],
               'policy_term': trn['term'], 'broker_account': policy['broker']['account'],
               'transaction_type': trn['type'], 'effective_date': trn['effective_date'],
               'gross_premium': trn['gross_premium'], 'ipt': trn['ipt'], 'commission': trn['commission']}
    try:
        result = _post_to_ledger(posting)
        adapter.stamp_finance_ref(trn['number'], result['posting_ref'])
    except Exception:
        return {'posted': False, 'posting_ref': None, 'duplicate': False, 'message': LEDGER_DOWN}
    return {'posted': True, 'posting_ref': result['posting_ref'], 'duplicate': bool(result.get('duplicate')),
            'message': None}


WORKBENCH_DOWN = 'Underwriting Workbench not reachable: no technical price check.'
BELOW_TECHNICAL_PCT = 8.0


def _post_assessment(body):
    """POST a risk to the Underwriting Workbench over HTTP. Raises on any failure."""
    base = os.environ.get('ESTATE_BASE_URL', 'http://localhost:8001/api/systems').rstrip('/')
    req = urllib.request.Request('%s/underwriting/assessments' % base, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.load(resp)


def _technical_check(risk: Risk, quoted_premium):
    """
    Compare Heron's premium (excluding IPT) with underwriting's technical price.
    Advice only: the Workbench's own decision and reasons are ignored, so Heron's
    price and its accept/refer decision never change.
    """
    out = {'available': False, 'technical_premium': None, 'quoted_premium': quoted_premium,
           'deviation_pct': None, 'below_threshold': False, 'threshold_pct': BELOW_TECHNICAL_PCT,
           'message': WORKBENCH_DOWN}
    try:
        a = _post_assessment({**risk.model_dump(), 'quoted_premium': quoted_premium})
        deviation = float(a['deviation_from_technical_pct'])
        technical = float(a['technical_premium'])
    except Exception:
        return out
    return {**out, 'available': True, 'technical_premium': technical, 'deviation_pct': deviation,
            'below_threshold': deviation < -BELOW_TECHNICAL_PCT, 'message': None}


LEDGER_UNCHECKED = 'Finance Ledger not reachable: broker credit status not checked.'


def _ledger_get(path):
    """GET from the Finance Ledger over HTTP. Returns (status, json); raises on connection errors."""
    base = os.environ.get('ESTATE_BASE_URL', 'http://localhost:8001/api/systems').rstrip('/')
    try:
        with urllib.request.urlopen(base + path, timeout=2) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as ex:
        return ex.code, None


def _fetch_broker_statement(broker_code):
    """The broker's ledger statement, or None if the broker has no postings yet."""
    status, body = _ledger_get('/finance/brokers/BRK-%s/statement' % urllib.parse.quote(broker_code.upper()))
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError('Finance Ledger answered %s' % status)
    return body


def _broker_credit(broker_code):
    """
    Warn, never block: does the broker have policies on credit hold (unpaid over 60 days)?
    The 60-day rule is the ledger's; this only reads its answer.
    """
    if not broker_code:
        return None
    try:
        s = _fetch_broker_statement(broker_code)
    except Exception:
        return {'checked': False, 'on_hold': False, 'policies_on_credit_hold': None, 'overdue_amount': None,
                'message': LEDGER_UNCHECKED}
    held = int(s['policies_on_credit_hold']) if s else 0
    return {'checked': True, 'on_hold': held > 0, 'policies_on_credit_hold': held,
            'overdue_amount': float(s['overdue_amount']) if s else 0.0, 'message': None}


CLAIMS_HISTORY_DOWN = 'Claims Desk not reachable: claims history not shown.'


def _claims_desk_get(path, params):
    """GET from the Claims Desk over HTTP. Raises on any failure."""
    base = os.environ.get('ESTATE_BASE_URL', 'http://localhost:8001/api/systems').rstrip('/')
    with urllib.request.urlopen('%s/claims%s?%s' % (base, path, urllib.parse.urlencode(params)), timeout=2) as resp:
        return json.load(resp)


def _claims_history(policy):
    """
    The policy's claims from the Claims Desk, and whether Heron's keyed count for this
    term is lower than the Claims Desk's count in the three years before it started.
    Advice only: Heron's figure is never changed.
    """
    inception = datetime.date.fromisoformat(policy['inception_date'])
    as_at = (inception - datetime.timedelta(days=1)).isoformat()
    heron_count = policy['risk']['claims_count_3y']
    out = {'available': False, 'claims': [], 'heron_count': heron_count, 'claims_desk_count': None,
           'compared_as_at': as_at, 'inception_date': policy['inception_date'], 'lower_in_heron': False,
           'message': CLAIMS_HISTORY_DOWN}
    try:
        rows = _claims_desk_get('/claims', {'policy_ref': policy['policy_ref']})
        exp = _claims_desk_get('/experience', {'policy_ref': policy['policy_ref'], 'as_at': as_at})
        desk_count = int(exp['claims_count_3y'])
    except Exception:
        return out
    claims = [{'claim_ref': c['claim_ref'], 'loss_date': c['loss_date'], 'description': c['description'],
               'term': c['policy_term'], 'status': c['status'], 'paid': c['paid'], 'outstanding': c['outstanding']}
              for c in sorted(rows, key=lambda c: c['loss_date'], reverse=True)]
    return {**out, 'available': True, 'claims': claims, 'claims_desk_count': desk_count,
            'lower_in_heron': heron_count < desk_count, 'message': None}


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
    technical = _technical_check(body.risk, price['gross_premium'])
    return {'price': price, 'claims_count': claims_count, 'technical': technical,
            'broker_credit': _broker_credit(body.broker_code), **_decision(price)}


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
    """Bind a saved quote. Heron writes the premium transaction, and it is posted to the Finance Ledger."""
    trn = _legacy(adapter.bind_quote, policy_ref, body.user)
    finance = _send_to_finance(trn, adapter.policy_view(policy_ref))
    if finance['posted']:
        trn = {**trn, 'finance_ref': finance['posting_ref']}
    return {'policy': adapter.policy_view(policy_ref), 'transaction': trn, 'finance': finance}


@router.get('/policies')
def list_policies(q: str = '', status: str = '', limit: int = 50):
    """Search by policy number, insured name or postcode. Latest term of each policy."""
    return adapter.search_policies(q, status, limit)


@router.get('/policies/{policy_ref}')
def get_policy(policy_ref: str):
    policy = _legacy(adapter.policy_view, policy_ref)
    return {**policy, 'claims': _claims_history(policy)}


@router.post('/policies/{policy_ref}/adjustments/preview')
def preview_adjustment(policy_ref: str, body: AdjustmentRequest):
    """What would this change cost? Nothing is saved."""
    return _legacy(adapter.preview_adjustment, policy_ref, body.changes, body.effective_date, body.user)


@router.post('/policies/{policy_ref}/adjustments', status_code=201)
def apply_adjustment(policy_ref: str, body: AdjustmentRequest):
    """Apply a mid-term adjustment. Heron writes the endorsement and any premium transaction."""
    result = _legacy(adapter.apply_adjustment, policy_ref, body.changes, body.effective_date, body.user)
    return {'adjustment': result, 'policy': adapter.policy_view(policy_ref)}
