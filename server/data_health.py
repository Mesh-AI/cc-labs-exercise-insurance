"""
Data health: integrity and coverage checks across all four systems.

Reads the files on disk in server/data (not the running servers' memory), so
it tells you whether a dataset is safe to load. Used by scripts/check_data.py
and by GET /api/data/health.

Three kinds of result:
  errors    the data breaks a rule that the systems rely on. Must be zero.
  warnings  known legacy drift (hand-keyed claim fields). Expected, not fatal.
  coverage  targets a synthetic test book should hit. Only when asked for.
"""
import csv
import json
import os
import re
from collections import Counter, defaultdict

from legacy import heron, herondb

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

PROPERTY_PERILS = {'fire', 'escape_of_water', 'storm', 'flood', 'theft', 'accidental_damage', 'business_interruption'}
LIABILITY_PERILS = {'public_liability_injury', 'public_liability_property', 'employers_liability'}
BOUND = ('L', 'R', 'X', 'E')


def _csv(data_dir, table):
    path = os.path.join(data_dir, 'legacy', table + '.csv')
    types = dict(herondb.SCHEMA[table])
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            rows.append({k: (int(v or 0) if types.get(k) == 'INT' else (v or '')) for k, v in r.items()})
    return rows


def _json(data_dir, system, name):
    path = os.path.join(data_dir, system, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _iso(i):
    return heron.I2D(i).isoformat() if i else None


def _p(pounds):
    """Pounds (decimal) to integer pence."""
    return int(round(float(pounds) * 100))


class _Report:
    def __init__(self):
        self.errors, self.warnings, self.coverage = {}, {}, []

    def err(self, code, title, example):
        e = self.errors.setdefault(code, {'check': code, 'title': title, 'count': 0, 'examples': []})
        e['count'] += 1
        if len(e['examples']) < 5:
            e['examples'].append(str(example))

    def warn(self, code, title, example):
        w = self.warnings.setdefault(code, {'check': code, 'title': title, 'count': 0, 'examples': []})
        w['count'] += 1
        if len(w['examples']) < 5:
            w['examples'].append(str(example))

    def cover(self, code, title, met, actual):
        self.coverage.append({'target': code, 'title': title, 'met': bool(met), 'actual': actual})


def run(data_dir=None, min_policies=0, coverage=False):
    data_dir = data_dir or DATA_DIR
    rep = _Report()
    brk = _csv(data_dir, 'BRKMST')
    ins = _csv(data_dir, 'INSMST')
    pol = _csv(data_dir, 'POLMST')
    trn = _csv(data_dir, 'PRMTRN')
    end = _csv(data_dir, 'ENDMST')
    claims = _json(data_dir, 'claims', 'claims.json')
    postings = _json(data_dir, 'finance', 'postings.json')
    payments = _json(data_dir, 'finance', 'payments.json')
    accum = _json(data_dir, 'underwriting', 'accumulations.json')
    referrals = _json(data_dir, 'underwriting', 'referrals.json')

    brokers = {b['BRKCD']: b for b in brk}
    insureds = {i['INSNO']: i for i in ins}
    terms = {}
    by_pol = defaultdict(list)
    for p in pol:
        key = (p['POLNO'], p['POLSFX'])
        if key in terms:
            rep.err('E03', 'Duplicate policy term', '%s/%d' % key)
        terms[key] = p
        by_pol[p['POLNO']].append(p)

    # ---- policy master ------------------------------------------------------------
    for p in pol:
        ref = '%s/%d' % (p['POLNO'], p['POLSFX'])
        if p['BRKCD'] not in brokers:
            rep.err('E01', 'Policy broker not in BRKMST', ref)
        if p['INSNO'] not in insureds:
            rep.err('E02', 'Policy insured not in INSMST', ref)
        if p['EXPDT'] != heron.ADDYR(p['INCDT']):
            rep.err('E05', 'Expiry is not one year after inception', ref)
        ok = (p['PRODCD'] in heron.PRDNAM and p['TRDCD'] in heron.TRDNAM and p['CONSTR'] in heron.CONNAM
              and p['STATCD'] in heron.STANAM and re.match(r'^[A-Z]{1,2}[0-9][0-9A-Z]?[0-9][A-Z]{2}$', p['PCODE'])
              and p['POLNO'][:3] == ('LDC' if p['PRODCD'] == 'CP' else 'LDL'))
        if not ok:
            rep.err('E08', 'Invalid code, postcode or policy number prefix', ref)
        if p['IPTAMT'] != heron.CALCIPT(p['GRSPRM']):
            rep.err('E15', 'Premium does not match the Heron rating engine', ref + ' IPTAMT')
        if (p['STATCD'] == 'X') != bool(p['CANDT']):
            rep.err('E14', 'Cancelled status and cancellation date disagree', ref)
    for polno, rows in by_pol.items():
        rows.sort(key=lambda r: r['POLSFX'])
        if [r['POLSFX'] for r in rows] != list(range(1, len(rows) + 1)):
            rep.err('E04', 'Policy terms are not numbered 1..n', polno)
        for a, b in zip(rows, rows[1:]):
            if b['INCDT'] != a['EXPDT']:
                rep.err('E06', 'Renewal term does not start when the previous term ends', '%s/%d' % (polno, b['POLSFX']))
            if a['STATCD'] != 'R':
                rep.err('E07', 'Status pattern invalid across terms', '%s/%d should be R' % (polno, a['POLSFX']))
        last = rows[-1]
        if last['STATCD'] == 'R' or (last['STATCD'] in ('Q', 'D') and last['POLSFX'] != 1):
            rep.err('E07', 'Status pattern invalid across terms', '%s/%d is %s' % (polno, last['POLSFX'], last['STATCD']))

    # ---- premium transactions and endorsements ------------------------------------
    trn_by_term = defaultdict(list)
    for t in trn:
        key = (t['POLNO'], t['POLSFX'])
        if key not in terms:
            rep.err('E09', 'Premium transaction for a policy term that does not exist', 'TRN %d' % t['TRNNO'])
            continue
        trn_by_term[key].append(t)
        p = terms[key]
        if (t['IPTAMT'] != heron.CALCIPT(t['GRSPRM']) or t['NETAMT'] != t['GRSPRM'] - t['COMAMT']
                or t['COMAMT'] != heron.CALCCOM(t['GRSPRM'], p['COMMPC'])):
            rep.err('E10', 'Transaction IPT, commission or net does not add up', 'TRN %d' % t['TRNNO'])
    end_by_term = defaultdict(list)
    for e in end:
        key = (e['POLNO'], e['POLSFX'])
        if key not in terms or not (terms[key]['INCDT'] <= e['EFFDT'] < terms[key]['EXPDT']):
            rep.err('E12', 'Endorsement outside its policy term', 'END %d' % e['ENDNO'])
            continue
        end_by_term[key].append(e)
    for key, p in terms.items():
        ref = '%s/%d' % key
        opening = [t for t in trn_by_term[key] if t['TRNTYP'] in ('NB', 'RN')]
        if p['STATCD'] in BOUND:
            want = 'NB' if p['POLSFX'] == 1 else 'RN'
            if len(opening) != 1 or opening[0]['TRNTYP'] != want or opening[0]['EFFDT'] != p['INCDT']:
                rep.err('E11', 'Bound term needs exactly one NB or RN transaction at inception', ref)
        elif trn_by_term[key]:
            rep.err('E11', 'Quote or declined term must not have premium transactions', ref)
        for t in trn_by_term[key]:
            if t['TRNTYP'] in ('MTA', 'CAN'):
                want_typ = ('CN',) if t['TRNTYP'] == 'CAN' else ('SI', 'AD', 'CV')
                if not any(e['EFFDT'] == t['EFFDT'] and e['PRMADJ'] == t['GRSPRM'] and e['ENDTYP'] in want_typ
                           for e in end_by_term[key]):
                    rep.err('E13', 'MTA or cancellation transaction has no matching endorsement', 'TRN %d' % t['TRNNO'])
        if p['STATCD'] == 'X' and not any(e['ENDTYP'] == 'CN' and e['EFFDT'] == p['CANDT'] for e in end_by_term[key]):
            rep.err('E14', 'Cancelled status and cancellation date disagree', ref + ' no CN endorsement')

    # ---- rating parity with the legacy engine -------------------------------------
    with heron.LK:
        keep = heron.CN
        try:
            heron.USEDB(herondb.OPENDB(os.path.join(data_dir, 'legacy')))
            for key, p in terms.items():
                if p['POLSFX'] != 1 or end_by_term[key] or p['STATCD'] == 'D':
                    continue
                try:
                    want = heron.CALCPRM(p['PRODCD'], p['TRDCD'], p['PCODE'], p['CONSTR'], p['SIBLD'], p['SICONT'],
                                         p['SIBI'], p['TURNOV'], p['EMPCNT'], p['VOLXS'], p['CLMCNT3'])
                except Exception as ex:
                    rep.err('E15', 'Premium does not match the Heron rating engine', '%s/%d %s' % (key + (ex,)))
                    continue
                if p['GRSPRM'] != want:
                    rep.err('E15', 'Premium does not match the Heron rating engine',
                            '%s/%d has %d, engine gives %d' % (key + (p['GRSPRM'], want)))
        finally:
            heron.USEDB(keep)

    # ---- claims -------------------------------------------------------------------
    claims_by_pol = defaultdict(list)
    for c in claims:
        key = (c.get('policy_ref'), c.get('policy_term'))
        p = terms.get(key)
        if not p:
            rep.err('E16', 'Claim for a policy term that does not exist', c.get('claim_ref'))
            continue
        claims_by_pol[c['policy_ref']].append(c)
        if str(p['INSNO']) != str(c.get('insured_ref')) or p['STATCD'] not in BOUND:
            rep.err('E16', 'Claim for a policy term that does not exist', '%s wrong insured or unbound term' % c['claim_ref'])
        end_cover = _iso(p['CANDT']) if p['CANDT'] else _iso(p['EXPDT'])
        if not (_iso(p['INCDT']) <= c['loss_date'] < end_cover) or c['notified_date'] < c['loss_date']:
            rep.err('E17', 'Claim loss date outside the period of cover, or notified before the loss', c['claim_ref'])
        perils = PROPERTY_PERILS if p['PRODCD'] == 'CP' else LIABILITY_PERILS
        bad = (c['peril'] not in perils or c['status'] not in ('open', 'settled', 'declined')
               or c['paid'] < 0 or c['outstanding'] < 0
               or (c['status'] != 'open' and c['outstanding'] != 0) or (c['status'] == 'declined' and c['paid'] != 0)
               or (c['status'] == 'open' and c['outstanding'] <= 0))
        if bad:
            rep.err('E18', 'Claim peril, status or amounts inconsistent', c['claim_ref'])

    # ---- finance ------------------------------------------------------------------
    post_by_ref = defaultdict(list)
    for q in postings:
        post_by_ref[q.get('transaction_ref')].append(q)
    trn_refs = set()
    for t in trn:
        ref = 'HERON-%07d' % t['TRNNO']
        trn_refs.add(ref)
        got = post_by_ref.get(ref, [])
        p = terms.get((t['POLNO'], t['POLSFX']))
        if len(got) != 1 or not p:
            rep.err('E19', 'Heron transaction missing from the ledger, or posted with different values', ref)
            continue
        q = got[0]
        same = (q['policy_ref'] == t['POLNO'] and q['policy_term'] == t['POLSFX']
                and q['broker_account'] == 'BRK-' + p['BRKCD'] and q['transaction_type'] == t['TRNTYP']
                and q['effective_date'] == _iso(t['EFFDT']) and _p(q['gross_premium']) == t['GRSPRM']
                and _p(q['ipt']) == t['IPTAMT'] and _p(q['commission']) == t['COMAMT']
                and _p(q['net_due']) == t['GRSPRM'] + t['IPTAMT'] - t['COMAMT'])
        if not same:
            rep.err('E19', 'Heron transaction missing from the ledger, or posted with different values', ref)
    for q in postings:
        if str(q.get('transaction_ref', '')).startswith('HERON-') and q['transaction_ref'] not in trn_refs:
            rep.err('E20', 'Ledger posting with no Heron transaction behind it', q['transaction_ref'])
    posted_pols = {q['policy_ref'] for q in postings}
    for y in payments:
        if y.get('policy_ref') not in posted_pols or y.get('amount', 0) <= 0:
            rep.err('E21', 'Payment for a policy with no postings, or not a positive amount', y.get('payment_ref'))

    # ---- underwriting -------------------------------------------------------------
    live = defaultdict(lambda: [0, 0])
    for p in pol:
        if p['STATCD'] == 'L' and p['PRODCD'] == 'CP':
            d = live[p['PCODE'][:-3]]
            d[0] += p['SIBLD'] + p['SICONT'] + p['SIBI']
            d[1] += 1
    seen = set()
    for a in accum:
        d = a.get('postcode_district')
        seen.add(d)
        si, n = live.get(d, [0, 0])
        if _p(a.get('live_total_si', 0)) != si * 100 or a.get('live_policies') != n or a.get('limit', 0) <= 0:
            rep.err('E22', 'Accumulation does not equal the live property sums insured in that district', d)
    for d in live:
        if d not in seen:
            rep.err('E22', 'Accumulation does not equal the live property sums insured in that district', d + ' missing')
    ref_keys = set()
    for r in referrals:
        key = (r.get('policy_ref'), r.get('policy_term'))
        ref_keys.add(key)
        if key not in terms or r.get('status') not in ('open', 'approved', 'declined'):
            rep.err('E23', 'Referral for a policy term that does not exist, or with an invalid status', r.get('referral_ref'))
    for key, p in terms.items():
        if p['UWREF'] == 'Y' and key not in ref_keys:
            rep.err('E24', 'Policy flagged as referred has no referral in the workbench', '%s/%d' % key)

    # ---- warnings: hand-keyed claim fields drift from the claims system -------------
    for polno, rows in by_pol.items():
        cur = rows[-1]
        if cur['STATCD'] != 'L':
            continue
        inc = _iso(cur['INCDT'])
        frm = _iso(_years_back(cur['INCDT'], 3))
        n3 = sum(1 for c in claims_by_pol[polno] if c['status'] != 'declined' and frm < c['loss_date'] < inc)
        if n3 > cur['CLMCNT3']:
            rep.warn('W01', 'Heron CLMCNT3 is lower than the claims system shows (risk is under-priced)',
                     '%s keyed %d, claims system %d' % (polno, cur['CLMCNT3'], n3))
        in_term = any(c['status'] != 'declined' and c['loss_date'] >= inc for c in claims_by_pol[polno])
        if in_term != (cur['CLMCUR'] == 'Y'):
            rep.warn('W02', 'Heron CLMCUR disagrees with the claims system (affects cancellation refunds)',
                     '%s keyed %s' % (polno, cur['CLMCUR']))

    counts = {'brokers': len(brk), 'insureds': len(ins), 'policies': len(by_pol), 'policy_terms': len(pol),
              'live_policies': sum(1 for r in by_pol.values() if r[-1]['STATCD'] == 'L'),
              'premium_transactions': len(trn), 'endorsements': len(end), 'claims': len(claims),
              'ledger_postings': len(postings), 'payments': len(payments), 'referrals': len(referrals),
              'accumulation_districts': len(accum)}

    # ---- coverage targets for a synthetic test book ---------------------------------
    if coverage or min_policies:
        n_pol = max(len(by_pol), 1)
        bound_terms = [p for p in pol if p['STATCD'] in BOUND]
        stat = Counter(p['STATCD'] for p in pol)
        areas = {re.match(r'^[A-Z]{1,2}', p['PCODE']).group(0) for p in pol if re.match(r'^[A-Z]', p['PCODE'])}
        loaded = areas & set(heron.AREAFC)
        mtas = sum(1 for e in end if e['ENDTYP'] != 'CN')
        with_claims = sum(1 for v in claims_by_pol.values() if v)
        rep.cover('C01', 'At least %d policies' % (min_policies or 1), len(by_pol) >= (min_policies or 1), len(by_pol))
        rep.cover('C02', 'All 12 trades used', len({p['TRDCD'] for p in pol}) == 12, len({p['TRDCD'] for p in pol}))
        rep.cover('C03', 'All 4 construction types used', len({p['CONSTR'] for p in pol}) == 4, len({p['CONSTR'] for p in pol}))
        rep.cover('C04', 'Both products, each at least 20% of policies',
                  min(sum(1 for r in by_pol.values() if r[0]['PRODCD'] == c) for c in ('CP', 'CL')) >= 0.2 * n_pol,
                  dict(Counter(r[0]['PRODCD'] for r in by_pol.values())))
        rep.cover('C05', 'Statuses Q, L, R, X and E all present', all(stat[s] for s in 'QLRXE'), dict(stat))
        rep.cover('C06', 'At least 5% of policies have three or more terms',
                  sum(1 for r in by_pol.values() if len(r) >= 3) >= 0.05 * n_pol,
                  sum(1 for r in by_pol.values() if len(r) >= 3))
        rep.cover('C07', 'Mid-term adjustments on at least 5% of bound terms', mtas >= 0.05 * max(len(bound_terms), 1), mtas)
        rep.cover('C08', 'Cancellations on at least 2% of policies', stat['X'] >= 0.02 * n_pol, stat['X'])
        rep.cover('C09', 'Claims on 10% to 35% of policies', 0.10 * n_pol <= with_claims <= 0.35 * n_pol, with_claims)
        rep.cover('C10', 'At least 8 loaded postcode areas, including a single-letter area',
                  len(loaded) >= 8 and any(len(a) == 1 for a in loaded), sorted(loaded))
        rep.cover('C11', 'At least 15 brokers and 10 referrals', len(brk) >= 15 and len(referrals) >= 10,
                  {'brokers': len(brk), 'referrals': len(referrals)})
        rep.cover('C12', 'Some unpaid balances over 60 days (credit hold cases)', _credit_holds(postings, payments) >= 3,
                  _credit_holds(postings, payments))

    errors = sorted(rep.errors.values(), key=lambda e: e['check'])
    warnings = sorted(rep.warnings.values(), key=lambda e: e['check'])
    return {'ok': not errors and all(c['met'] for c in rep.coverage), 'counts': counts,
            'error_count': sum(e['count'] for e in errors), 'errors': errors,
            'warning_count': sum(w['count'] for w in warnings), 'warnings': warnings, 'coverage': rep.coverage}


def _years_back(i, n):
    d = heron.I2D(i)
    try:
        return heron.D2I(d.replace(year=d.year - n))
    except ValueError:
        return heron.D2I(d.replace(year=d.year - n, day=28))


def _credit_holds(postings, payments):
    """Policies with more than a pound outstanding whose first posting is over 60 days before the latest one."""
    if not postings:
        return 0
    billed, paid, first = defaultdict(float), defaultdict(float), {}
    latest = max(q['effective_date'] for q in postings)
    for q in postings:
        billed[q['policy_ref']] += q['net_due']
        first[q['policy_ref']] = min(first.get(q['policy_ref'], q['effective_date']), q['effective_date'])
    for y in payments:
        paid[y['policy_ref']] += y['amount']
    cutoff = heron.I2D(int(latest.replace('-', ''))).toordinal() - 60
    return sum(1 for k in billed if billed[k] - paid[k] > 1.0
               and heron.I2D(int(first[k].replace('-', ''))).toordinal() < cutoff)


def format_report(rep):
    out = []
    c = rep['counts']
    out.append('DATA HEALTH   %d policies, %d terms, %d transactions, %d claims, %d postings'
               % (c['policies'], c['policy_terms'], c['premium_transactions'], c['claims'], c['ledger_postings']))
    out.append('')
    if rep['errors']:
        out.append('ERRORS (%d)' % rep['error_count'])
        for e in rep['errors']:
            out.append('  %s  %-70s %5d   e.g. %s' % (e['check'], e['title'], e['count'], '; '.join(e['examples'][:2])))
    else:
        out.append('ERRORS (0)   every integrity check passed')
    out.append('')
    out.append('WARNINGS (%d)   known drift in hand-keyed Heron fields' % rep['warning_count'])
    for w in rep['warnings']:
        out.append('  %s  %-70s %5d' % (w['check'], w['title'][:70], w['count']))
    if rep['coverage']:
        met = sum(1 for x in rep['coverage'] if x['met'])
        out.append('')
        out.append('COVERAGE (%d of %d targets met)' % (met, len(rep['coverage'])))
        for x in rep['coverage']:
            out.append('  %s  %s  %-62s %s' % (x['target'], 'PASS' if x['met'] else 'FAIL', x['title'], x['actual']))
    out.append('')
    out.append('RESULT: ' + ('PASS' if rep['ok'] else 'FAIL'))
    return '\n'.join(out)
