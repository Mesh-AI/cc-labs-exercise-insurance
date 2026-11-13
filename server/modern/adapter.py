"""
Anti-corruption layer over Heron.

The new API never touches Heron's tables or conventions directly. Everything
goes through this module, which translates between the two worlds:

    modern                          Heron
    ------------------------------  ---------------------------------
    pounds as decimals              premium in integer pence
    ISO dates (2026-11-12)          integer CCYYMMDD (20261112)
    named fields (trade_code)       cryptic columns (TRDCD)
    exceptions with clear messages  HeronErr in upper case

Rules are never re-implemented here. Prices come from Heron's own functions,
and previews run the real Heron routine on a scratch copy of the database, so
the modern journey cannot drift from the legacy answer.
"""
import sqlite3

from legacy import heron as H

FIELD_MAP = {
    'product': 'PRODCD', 'trade_code': 'TRDCD', 'postcode': 'PCODE', 'construction': 'CONSTR',
    'sum_insured_buildings': 'SIBLD', 'sum_insured_contents': 'SICONT', 'sum_insured_bi': 'SIBI',
    'turnover': 'TURNOV', 'employees': 'EMPCNT', 'voluntary_excess': 'VOLXS', 'claims_count_3y': 'CLMCNT3',
}
REVERSE_MAP = {v: k for k, v in FIELD_MAP.items()}
CHANGEABLE = ('trade_code', 'postcode', 'construction', 'sum_insured_buildings', 'sum_insured_contents',
              'sum_insured_bi', 'turnover', 'employees', 'voluntary_excess')


class LegacyError(Exception):
    """A Heron rule said no. The message is safe to show to a user."""


def pounds(pence):
    return round(pence / 100.0, 2)


def iso(i):
    return H.I2D(i).isoformat() if i else None


def sentence(msg):
    """Heron shouts in upper case with rule codes. Say it the way a person would."""
    msg = str(msg).strip()
    referred = msg.upper().startswith('REFERRED - ')
    if referred:
        msg = msg[11:]
    if len(msg) > 4 and msg[0] == 'R' and msg[1:3].isdigit() and msg[3] == ' ':
        msg = msg[4:]
    msg = msg[:1].upper() + msg[1:].lower()
    return 'Needs an underwriter: %s. Sign in as an underwriting manager to make this change.' % msg.lower() \
        if referred else msg


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except H.HeronErr as ex:
        raise LegacyError(sentence(ex)) from ex


def _legacy_risk(risk: dict) -> dict:
    form = {FIELD_MAP[k]: v for k, v in risk.items() if k in FIELD_MAP and v is not None}
    return form


def lookups():
    return {
        'products': [{'code': k, 'name': v.title()} for k, v in H.PRDNAM.items()],
        'trades': [{'code': k, 'name': v.title()} for k, v in H.TRDNAM.items()],
        'constructions': [{'code': k, 'name': v.title()} for k, v in H.CONNAM.items()],
        'voluntary_excesses': [250, 500, 1000, 2500],
        'brokers': [{'code': b['BRKCD'], 'name': b['BRKNAM'].title(), 'commission_pct': b['COMMPC'] / 100.0}
                    for b in H.QA("SELECT * FROM BRKMST WHERE STATCD='A' ORDER BY BRKNAM")],
        'lab_date': iso(H.SYSDT()),
    }


def price(risk: dict, commission_pct: float = None) -> dict:
    """
    Price a risk with Heron's own rating functions. Reads only, writes nothing.

    Returns the premium and a line-by-line schedule of how Heron got there.
    """
    product = str(risk.get('product', '')).upper()
    if product not in H.PRDNAM:
        raise LegacyError('Unknown product')
    r = _guard(H.RSKFLD, _legacy_risk(risk))
    _guard(H.CHKLIM, product, r)
    gross = _guard(H.CALCPRM, product, r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                   r['TURNOV'], r['EMPCNT'], r['VOLXS'], r['CLMCNT3'])
    lines, factors = [], []
    if product == 'CP':
        for label, key, si in (('Buildings', 'BLD', r['SIBLD']), ('Contents', 'CNT', r['SICONT']),
                               ('Business interruption', 'BI', r['SIBI'])):
            if si:
                rate = H.RATLKP('BASE', key)
                lines.append({'label': label, 'basis': si, 'rate_per_1000': rate, 'amount': round(si * rate / 1000.0, 2)})
        factors = [
            {'label': 'Trade: ' + H.TRDNAM[r['TRDCD']].title(), 'factor': H.TRDFAC(r['TRDCD'])},
            {'label': 'Postcode area', 'factor': H.AREFAC(r['PCODE'])},
            {'label': 'Construction: ' + H.CONNAM[r['CONSTR']].title(), 'factor': H.CONFAC(r['CONSTR'])},
            {'label': 'Claims in last three years: %d' % r['CLMCNT3'], 'factor': H.CLMFAC(r['CLMCNT3'])},
            {'label': 'Voluntary excess £%s' % '{:,}'.format(r['VOLXS']), 'factor': round(1.0 - H.XSDISC(r['VOLXS']), 4)},
        ]
        minimum = H.RATLKP('MINPRM', 'CP')
    else:
        el, pl = H.RATLKP('ELRATE', r['TRDCD']), H.RATLKP('PLRATE', r['TRDCD'])
        lines = [
            {'label': 'Employers liability', 'basis': r['EMPCNT'], 'rate_per_employee': el, 'amount': round(r['EMPCNT'] * el, 2)},
            {'label': 'Public liability', 'basis': r['TURNOV'], 'rate_per_1000': pl, 'amount': round(r['TURNOV'] / 1000.0 * pl, 2)},
        ]
        factors = [{'label': 'Claims in last three years: %d' % r['CLMCNT3'], 'factor': H.CLMFAC(r['CLMCNT3'])}]
        if r['TURNOV'] > 2000000:
            factors.append({'label': 'Large turnover discount', 'factor': 0.90})
        minimum = H.RATLKP('MINPRM', 'CL')
    base = round(sum(x['amount'] for x in lines), 2)
    rated = base
    for f in factors:
        rated *= f['factor']
    ipt = H.CALCIPT(gross)
    out = {
        'gross_premium': pounds(gross), 'ipt': pounds(ipt), 'total_payable': pounds(gross + ipt),
        'schedule': {'lines': lines, 'base_premium': base, 'factors': factors,
                     'minimum_premium': minimum, 'minimum_premium_applied': rated < minimum},
        'referral_reasons': [sentence(x) for x in H.CHKREF(product, r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'],
                                                              r['SICONT'], r['SIBI'], r['TURNOV'], r['EMPCNT'], r['CLMCNT3'])],
        'referral_codes': [x[:3] for x in H.CHKREF(product, r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'],
                                                   r['SIBI'], r['TURNOV'], r['EMPCNT'], r['CLMCNT3'])],
        'priced_by': 'Heron CALCPRM',
    }
    if commission_pct is not None:
        out['commission'] = pounds(H.CALCCOM(gross, int(round(commission_pct * 100))))
    return out


def _risk_view(p: dict) -> dict:
    return {REVERSE_MAP[k]: p[k] for k in REVERSE_MAP}


def policy_view(policy_ref: str, term: int = None, detail: bool = True) -> dict:
    p = _guard(H.GETPOL, policy_ref.upper(), term)
    ins = H.Q1('SELECT * FROM INSMST WHERE INSNO=?', (p['INSNO'],))
    brk = H.Q1('SELECT * FROM BRKMST WHERE BRKCD=?', (p['BRKCD'],))
    out = {
        'policy_ref': p['POLNO'], 'term': p['POLSFX'], 'product': p['PRODCD'], 'product_name': H.PRDNAM[p['PRODCD']].title(),
        'status': p['STATCD'], 'status_name': H.STANAM[p['STATCD']].title(),
        'insured': {'ref': str(ins['INSNO']), 'name': ins['INSNAM'].title(), 'address': ins['ADDR1'].title(),
                    'town': ins['TOWN'].title(), 'postcode': ins['PCODE']},
        'broker': {'code': brk['BRKCD'], 'name': brk['BRKNAM'].title(), 'account': 'BRK-' + brk['BRKCD'],
                   'commission_pct': p['COMMPC'] / 100.0},
        'inception_date': iso(p['INCDT']), 'expiry_date': iso(p['EXPDT']), 'cancelled_date': iso(p['CANDT']),
        'risk': _risk_view(p),
        'trade_name': H.TRDNAM[p['TRDCD']].title(), 'construction_name': H.CONNAM[p['CONSTR']].title(),
        'premium': {'annual_gross': pounds(p['GRSPRM']), 'ipt': pounds(p['IPTAMT']),
                    'total': pounds(p['GRSPRM'] + p['IPTAMT'])},
        'referred_in_heron': p['UWREF'] == 'Y',
        'heron_claim_marker': p['CLMCUR'] == 'Y',
        'quoted_date': iso(p['CRTDT']),
    }
    if detail:
        out['transactions'] = [transaction_view(t) for t in
                               H.QA('SELECT * FROM PRMTRN WHERE POLNO=? ORDER BY TRNNO', (p['POLNO'],))]
        out['endorsements'] = [{'number': e['ENDNO'], 'term': e['POLSFX'], 'type': e['ENDTYP'],
                                'effective_date': iso(e['EFFDT']), 'detail': e['DESCR'],
                                'premium_adjustment': pounds(e['PRMADJ'])}
                               for e in H.QA('SELECT * FROM ENDMST WHERE POLNO=? ORDER BY ENDNO', (p['POLNO'],))]
    return out


def transaction_view(t) -> dict:
    return {'transaction_ref': 'HERON-%07d' % t['TRNNO'], 'number': t['TRNNO'], 'term': t['POLSFX'],
            'type': t['TRNTYP'], 'effective_date': iso(t['EFFDT']), 'gross_premium': pounds(t['GRSPRM']),
            'ipt': pounds(t['IPTAMT']), 'commission': pounds(t['COMAMT']), 'net_to_insurer': pounds(t['NETAMT']),
            'finance_ref': t['FINREF'] or None}


def search_policies(q: str = '', status: str = '', limit: int = 50) -> list:
    sql = ('SELECT P.POLNO FROM POLMST P JOIN INSMST I ON I.INSNO=P.INSNO '
           'WHERE P.POLSFX=(SELECT MAX(POLSFX) FROM POLMST X WHERE X.POLNO=P.POLNO)')
    args = []
    if q:
        sql += ' AND (P.POLNO LIKE ? OR I.INSNAM LIKE ? OR P.PCODE LIKE ?)'
        args += ['%' + q.upper().replace(' ', '') + '%', '%' + q.upper() + '%', '%' + q.upper().replace(' ', '') + '%']
    if status:
        sql += ' AND P.STATCD=?'
        args.append(status.upper())
    sql += ' ORDER BY P.UPDDT DESC, P.POLNO DESC LIMIT ?'
    args.append(int(limit))
    return [policy_view(r['POLNO'], detail=False) for r in H.QA(sql, args)]


def find_insureds(q: str, limit: int = 10) -> list:
    rows = H.QA('SELECT * FROM INSMST WHERE INSNAM LIKE ? ORDER BY INSNAM LIMIT ?', ('%' + q.upper() + '%', limit))
    return [{'ref': str(r['INSNO']), 'name': r['INSNAM'].title(), 'town': r['TOWN'].title(), 'postcode': r['PCODE'],
             'trade_code': r['TRDCD']} for r in rows]


def create_quote(risk: dict, broker_code: str, inception_date: str, insured: dict = None, insured_ref: str = None,
                 user: str = 'CLERK1') -> dict:
    """Key a new business quote into Heron (screen NBQTE). Heron remains the system of record."""
    form = _legacy_risk(risk)
    form.update({'BRKCD': broker_code, 'INCDT': inception_date})
    if insured_ref:
        form['INSNO'] = insured_ref
    else:
        insured = insured or {}
        form.update({'INSNAM': insured.get('name', ''), 'ADDR1': insured.get('address', ''),
                     'TOWN': insured.get('town', '')})
    q = _guard(H.NBQTE, form, user)
    return q


def bind_quote(policy_ref: str, user: str = 'CLERK1') -> dict:
    return transaction_view_from_engine(_guard(H.NBBND, policy_ref.upper(), user))


def transaction_view_from_engine(t: dict) -> dict:
    row = H.Q1('SELECT * FROM PRMTRN WHERE TRNNO=?', (t['TRNNO'],))
    return transaction_view(row)


def stamp_finance_ref(transaction_number: int, posting_ref: str):
    """Record the ledger reference on the Heron transaction, as the overnight job would have."""
    with H.LK:
        H.CN.execute('UPDATE PRMTRN SET FINREF=? WHERE TRNNO=?', (posting_ref, transaction_number))
        H.CN.commit()


def _adjust_form(changes: dict, effective_date: str) -> dict:
    form = {FIELD_MAP[k]: v for k, v in changes.items() if k in CHANGEABLE and v is not None}
    form['EFFDT'] = effective_date
    return form


def _adjust_view(m: dict) -> dict:
    return {'policy_ref': m['POLNO'], 'term': m['POLSFX'], 'endorsement_type': m['ENDTYP'],
            'old_annual_premium': pounds(m['OLDPRM']), 'new_annual_premium': pounds(m['NEWPRM']),
            'days_remaining': m['DAYS'], 'premium_adjustment': pounds(m['PRMADJ']),
            'ipt_adjustment': pounds(m['IPTADJ']), 'total_adjustment': pounds(m['PRMADJ'] + m['IPTADJ']),
            'waived_as_small': m['PRMADJ'] == 0 and m['OLDPRM'] != m['NEWPRM'],
            'referral_reasons': [sentence(x) for x in m['REFRSN']],
            'endorsement_number': m.get('ENDNO'),
            'transaction': transaction_view_from_engine(m['TRN']) if m.get('TRN') else None}


def preview_adjustment(policy_ref: str, changes: dict, effective_date: str, user: str = 'CLERK1') -> dict:
    """
    What would this mid-term adjustment cost? Runs Heron's real MTAENT routine
    on a scratch copy of the database and throws the copy away, so the preview
    is the legacy answer by construction.
    """
    with H.LK:
        real = H.CN
        scratch = sqlite3.connect(':memory:', check_same_thread=False)
        scratch.row_factory = sqlite3.Row
        real.backup(scratch)
        try:
            H.USEDB(scratch)
            m = _guard(H.MTAENT, policy_ref.upper(), _adjust_form(changes, effective_date), user)
            view = _adjust_view(dict(m, ENDNO=None, TRN=None))
            return view
        finally:
            H.USEDB(real)
            scratch.close()


def apply_adjustment(policy_ref: str, changes: dict, effective_date: str, user: str = 'CLERK1') -> dict:
    return _adjust_view(_guard(H.MTAENT, policy_ref.upper(), _adjust_form(changes, effective_date), user))
