"""
Larkspur & Dene - policy modernisation workbench (backend, port 8001).

One process hosts four things so the lab runs on the same two ports as every
other Claude Code lab exercise:

  /api/legacy/...                the Heron legacy policy admin screens
  /api/systems/underwriting/...  Underwriting Workbench   (mock downstream system)
  /api/systems/claims/...        Claims Desk              (mock downstream system)
  /api/systems/finance/...       Finance Ledger           (mock downstream system)

Treat the three downstream systems as if they ran somewhere else: talk to them
over HTTP, never by importing their modules. Your new API belongs here, under
/api/v1/.
"""
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import data_health
from legacy import heron
from systems import claims, finance, underwriting
from systems.common import today
from modern.api import router as policy_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

heron.INIT(os.path.join(DATA_DIR, 'legacy'))
# The lab clock is frozen at the dataset's as-at date (server/data/as_at.json).
heron.SETSYSDT(heron.D2I(today()))

app = FastAPI(title='Larkspur & Dene Policy Modernisation Workbench', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(policy_router)

app.mount('/api/legacy', heron.app)
app.mount('/api/systems/underwriting', underwriting.app)
app.mount('/api/systems/claims', claims.app)
app.mount('/api/systems/finance', finance.app)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'service': 'modernisation-workbench', 'lab_date': today().isoformat()}


@app.get('/api/systems/status')
def systems_status():
    """One line per system in the estate: what it is, where it lives, what it holds."""
    live = heron.Q1("SELECT COUNT(*) AS N FROM POLMST WHERE STATCD='L'")['N']
    quotes = heron.Q1("SELECT COUNT(*) AS N FROM POLMST WHERE STATCD='Q'")['N']
    return [
        {'key': 'legacy', 'name': 'Heron policy admin', 'kind': 'Legacy system of record', 'status': 'up',
         'path': '/api/legacy/', 'docs': None,
         'holds': '%d live policies, %d open quotes' % (live, quotes), 'talks_to': 'Finance, by overnight file'},
        {'key': 'underwriting', 'name': 'Underwriting Workbench', 'kind': 'Downstream system', 'status': 'up',
         'path': '/api/systems/underwriting', 'docs': '/api/systems/underwriting/docs',
         'holds': '%(referrals)d referrals, %(districts)d postcode districts' % underwriting.health(),
         'talks_to': 'Nothing. Referrals are re-keyed by hand'},
        {'key': 'claims', 'name': 'Claims Desk', 'kind': 'Downstream system', 'status': 'up',
         'path': '/api/systems/claims', 'docs': '/api/systems/claims/docs',
         'holds': '%(claims)d claims, %(open_claims)d open' % claims.health(),
         'talks_to': 'Nothing. Claim counts are re-keyed into Heron by hand'},
        {'key': 'finance', 'name': 'Finance Ledger', 'kind': 'Downstream system', 'status': 'up',
         'path': '/api/systems/finance', 'docs': '/api/systems/finance/docs',
         'holds': '%(postings)d postings, %(payments)d payments' % finance.health(),
         'talks_to': 'Receives the Heron overnight file'},
    ]


@app.get('/api/data/health')
def data_health_report(min_policies: int = 0, coverage: bool = False):
    """Integrity checks across all four systems, read from the files in server/data."""
    return data_health.run(DATA_DIR, min_policies=min_policies, coverage=coverage)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8001)
