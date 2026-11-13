"""
Claims Desk (mock downstream system).

Owned by the claims team. The system of record for every claim. Heron holds
only two hand-keyed fields about claims (CLMCNT3 and CLMCUR), which drift.

Conventions: pounds as decimals, ISO dates. policy_ref is the Heron POLNO and
policy_term is the Heron POLSFX. insured_ref is the Heron INSNO as a string.
Mounted at /api/systems/claims. Interactive docs at .../docs.
"""
import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from systems.common import LOCK, load_json, money, today

app = FastAPI(title='Claims Desk', version='5.1.0', description='Claims register and claims experience.')

STATE = {}
PERILS = ('fire', 'escape_of_water', 'storm', 'flood', 'theft', 'accidental_damage', 'business_interruption',
          'public_liability_injury', 'public_liability_property', 'employers_liability')


def load():
    with LOCK:
        STATE['claims'] = load_json('claims', 'claims.json')


load()


class FnolIn(BaseModel):
    policy_ref: str
    policy_term: int
    insured_ref: str
    loss_date: str
    peril: str
    description: str = ''
    estimate: float = 0


def _incurred(c):
    return money(c['paid'] + c['outstanding'])


@app.get('/health')
def health():
    return {'system': 'claims', 'status': 'up', 'claims': len(STATE['claims']),
            'open_claims': sum(1 for c in STATE['claims'] if c['status'] == 'open')}


@app.get('/claims')
def list_claims(policy_ref: Optional[str] = None, insured_ref: Optional[str] = None, status: Optional[str] = None,
                limit: int = 200):
    out = STATE['claims']
    if policy_ref:
        out = [c for c in out if c['policy_ref'] == policy_ref.upper()]
    if insured_ref:
        out = [c for c in out if c['insured_ref'] == str(insured_ref)]
    if status:
        out = [c for c in out if c['status'] == status]
    out = sorted(out, key=lambda c: c['loss_date'], reverse=True)
    return [{**c, 'incurred': _incurred(c)} for c in out[:limit]]


@app.get('/claims/{claim_ref}')
def get_claim(claim_ref: str):
    for c in STATE['claims']:
        if c['claim_ref'] == claim_ref:
            return {**c, 'incurred': _incurred(c)}
    raise HTTPException(status_code=404, detail='Claim not found')


@app.get('/experience')
def experience(policy_ref: Optional[str] = None, insured_ref: Optional[str] = None, as_at: Optional[str] = None,
               term_start: Optional[str] = None):
    """
    Claims experience for a policy or an insured.

    claims_count_3y counts claims with a loss date in the three years up to as_at
    (default today), excluding declined claims. Pass term_start (ISO date) to
    find out whether there is a claim in the current policy period.
    """
    if not policy_ref and not insured_ref:
        raise HTTPException(status_code=422, detail='policy_ref or insured_ref is required')
    at = datetime.date.fromisoformat(as_at) if as_at else today()
    try:
        frm = at.replace(year=at.year - 3)
    except ValueError:
        frm = at.replace(year=at.year - 3, day=28)
    rows = STATE['claims']
    if policy_ref:
        rows = [c for c in rows if c['policy_ref'] == policy_ref.upper()]
    if insured_ref:
        rows = [c for c in rows if c['insured_ref'] == str(insured_ref)]
    rows = [c for c in rows if c['loss_date'] <= at.isoformat()]
    counted = [c for c in rows if c['status'] != 'declined' and c['loss_date'] > frm.isoformat()]
    in_term = None
    if term_start:
        in_term = any(c['status'] != 'declined' and c['loss_date'] >= term_start for c in rows)
    return {'policy_ref': policy_ref.upper() if policy_ref else None, 'insured_ref': insured_ref,
            'as_at': at.isoformat(), 'claims_count_3y': len(counted),
            'open_claims': sum(1 for c in rows if c['status'] == 'open'),
            'total_paid': money(sum(c['paid'] for c in rows)),
            'total_outstanding': money(sum(c['outstanding'] for c in rows)),
            'total_incurred': money(sum(c['paid'] + c['outstanding'] for c in rows)),
            'last_loss_date': max((c['loss_date'] for c in rows), default=None),
            'claim_in_current_term': in_term}


@app.post('/claims', status_code=201)
def first_notification(body: FnolIn):
    """First notification of loss. Opens a claim with a reserve equal to the estimate."""
    if body.peril not in PERILS:
        raise HTTPException(status_code=422, detail='Unknown peril. One of: ' + ', '.join(PERILS))
    try:
        loss = datetime.date.fromisoformat(body.loss_date)
    except ValueError:
        raise HTTPException(status_code=422, detail='loss_date must be an ISO date')
    with LOCK:
        STATE['seq'] = STATE.get('seq', 0) + 1
        c = {'claim_ref': 'CLM-%d-9%05d' % (loss.year, STATE['seq']), 'policy_ref': body.policy_ref.upper(),
             'policy_term': body.policy_term, 'insured_ref': str(body.insured_ref), 'loss_date': body.loss_date,
             'notified_date': today().isoformat(), 'peril': body.peril,
             'description': body.description, 'status': 'open', 'paid': 0.0,
             'outstanding': money(body.estimate), 'handler': 'CH00'}
        STATE['claims'].append(c)
        return {**c, 'incurred': _incurred(c)}
