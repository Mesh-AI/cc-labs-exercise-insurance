"""
Finance Ledger and Credit Control (mock downstream system).

Owned by finance. Receives Heron's premium transactions in an overnight file
and stamps a ledger reference on each. Brokers settle on account.

Conventions: pounds as decimals, ISO dates. transaction_ref is 'HERON-' plus
the seven digit Heron TRNNO. broker_account is 'BRK-' plus the Heron BRKCD.
net_due is what the broker owes: gross premium plus IPT, less commission.
Mounted at /api/systems/finance. Interactive docs at .../docs.
"""
import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from systems.common import LOCK, load_json, money, today

app = FastAPI(title='Finance Ledger', version='11.0.4', description='Premium postings, payments and broker balances.')

STATE = {}
IPT_RATE = 0.12
CREDIT_HOLD_DAYS = 60


def load():
    with LOCK:
        STATE['postings'] = load_json('finance', 'postings.json')
        STATE['payments'] = load_json('finance', 'payments.json')
        STATE['by_ref'] = {p['transaction_ref']: p for p in STATE['postings']}


load()


class PostingIn(BaseModel):
    transaction_ref: str = Field(..., description="Unique per transaction. 'HERON-0001234' for Heron transactions")
    policy_ref: str
    policy_term: int = 1
    broker_account: str
    transaction_type: str = Field(..., description='NB, RN, MTA or CAN')
    effective_date: str
    gross_premium: float
    ipt: float
    commission: float


@app.get('/health')
def health():
    return {'system': 'finance', 'status': 'up', 'postings': len(STATE['postings']),
            'payments': len(STATE['payments'])}


@app.get('/ledger')
def ledger(policy_ref: Optional[str] = None, broker_account: Optional[str] = None,
           transaction_ref: Optional[str] = None, limit: int = 500):
    out = STATE['postings']
    if policy_ref:
        out = [p for p in out if p['policy_ref'] == policy_ref.upper()]
    if broker_account:
        out = [p for p in out if p['broker_account'] == broker_account.upper()]
    if transaction_ref:
        out = [p for p in out if p['transaction_ref'] == transaction_ref]
    return out[-limit:]


@app.post('/postings', status_code=201)
def post_premium(body: PostingIn):
    """
    Post a premium transaction to the ledger.

    Idempotent on transaction_ref: posting the same reference again returns the
    original posting with duplicate=true. Rejected with 422 if the IPT is more
    than a penny away from 12% of the gross premium, or the type is unknown.
    """
    if body.transaction_type not in ('NB', 'RN', 'MTA', 'CAN'):
        raise HTTPException(status_code=422, detail='transaction_type must be NB, RN, MTA or CAN')
    if not body.broker_account.upper().startswith('BRK-'):
        raise HTTPException(status_code=422, detail="broker_account must look like 'BRK-B014'")
    if abs(body.ipt - body.gross_premium * IPT_RATE) > 0.011:
        raise HTTPException(status_code=422, detail='IPT does not reconcile to 12% of gross premium')
    try:
        datetime.date.fromisoformat(body.effective_date)
    except ValueError:
        raise HTTPException(status_code=422, detail='effective_date must be an ISO date')
    with LOCK:
        if body.transaction_ref in STATE['by_ref']:
            return {**STATE['by_ref'][body.transaction_ref], 'duplicate': True}
        seq = len(STATE['postings']) + 1
        p = {'posting_ref': 'GL-%s-%07d' % (body.effective_date[:4], seq), 'transaction_ref': body.transaction_ref,
             'policy_ref': body.policy_ref.upper(), 'policy_term': body.policy_term,
             'broker_account': body.broker_account.upper(), 'transaction_type': body.transaction_type,
             'effective_date': body.effective_date, 'gross_premium': money(body.gross_premium),
             'ipt': money(body.ipt), 'commission': money(body.commission),
             'net_due': money(body.gross_premium + body.ipt - body.commission),
             'posted_date': today().isoformat()}
        STATE['postings'].append(p)
        STATE['by_ref'][p['transaction_ref']] = p
        return {**p, 'duplicate': False}


def _balance(policy_ref: str, as_at: datetime.date) -> dict:
    posts = [p for p in STATE['postings'] if p['policy_ref'] == policy_ref]
    pays = [p for p in STATE['payments'] if p['policy_ref'] == policy_ref]
    billed = money(sum(p['net_due'] for p in posts))
    paid = money(sum(p['amount'] for p in pays))
    outstanding = money(billed - paid)
    oldest = 0
    if outstanding > 0.005 and posts:
        # Payments settle the oldest postings first
        remaining = paid
        for p in sorted(posts, key=lambda x: x['effective_date']):
            if p['net_due'] <= 0:
                continue
            if remaining >= p['net_due'] - 0.005:
                remaining -= p['net_due']
                continue
            oldest = max(0, (as_at - datetime.date.fromisoformat(p['effective_date'])).days)
            break
    return {'policy_ref': policy_ref, 'billed': billed, 'paid': paid, 'outstanding': outstanding,
            'oldest_unpaid_days': oldest, 'credit_hold': oldest > CREDIT_HOLD_DAYS, 'as_at': as_at.isoformat()}


@app.get('/policies/{policy_ref}/balance')
def policy_balance(policy_ref: str, as_at: Optional[str] = None):
    """Billed, paid and outstanding for a policy. credit_hold is true once a debt is over 60 days old."""
    at = datetime.date.fromisoformat(as_at) if as_at else today()
    return _balance(policy_ref.upper(), at)


@app.get('/brokers/{broker_account}/statement')
def broker_statement(broker_account: str, as_at: Optional[str] = None):
    at = datetime.date.fromisoformat(as_at) if as_at else today()
    acct = broker_account.upper()
    refs = sorted({p['policy_ref'] for p in STATE['postings'] if p['broker_account'] == acct})
    if not refs:
        raise HTTPException(status_code=404, detail='No postings for this broker account')
    lines = [_balance(r, at) for r in refs]
    open_lines = [b for b in lines if b['outstanding'] > 0.005]
    return {'broker_account': acct, 'as_at': at.isoformat(), 'policies': len(refs),
            'billed': money(sum(b['billed'] for b in lines)), 'paid': money(sum(b['paid'] for b in lines)),
            'outstanding': money(sum(b['outstanding'] for b in lines)),
            'policies_on_credit_hold': sum(1 for b in lines if b['credit_hold']),
            'overdue_amount': money(sum(b['outstanding'] for b in lines if b['credit_hold'])),
            'open_items': sorted(open_lines, key=lambda b: -b['oldest_unpaid_days'])[:50]}


class PaymentIn(BaseModel):
    policy_ref: str
    broker_account: str
    amount: float
    received_date: Optional[str] = None


@app.post('/payments', status_code=201)
def record_payment(body: PaymentIn):
    with LOCK:
        pay = {'payment_ref': 'PAY-%07d' % (len(STATE['payments']) + 1), 'policy_ref': body.policy_ref.upper(),
               'broker_account': body.broker_account.upper(), 'amount': money(body.amount),
               'received_date': body.received_date or today().isoformat()}
        STATE['payments'].append(pay)
        return pay
