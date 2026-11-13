"""
Synthetic book generator for the Larkspur & Dene lab estate.

Builds a consistent dataset across all four systems:

  server/data/legacy/*.csv            Heron policy admin (system of record)
  server/data/claims/claims.json      Claims Desk
  server/data/finance/*.json          Finance Ledger (postings and payments)
  server/data/underwriting/*.json     Underwriting Workbench (referrals, accumulations)

How it stays consistent: it does not invent premiums. It replays each policy's
life through the real Heron engine (quote, bind, adjust, cancel, renew) with the
Heron system date moved to the day each event happened. Heron writes its own
rows, so every premium, IPT and commission figure is exactly what the legacy
system would have produced. The downstream systems are then derived from
Heron's transactions.

Reference data is left alone: RATTBL.csv, underwriting/appetite.json and
underwriting/technical_rates.json.

Nothing here is real. Company names are invented, and every postcode ends in
letters the Royal Mail never uses (C, I, K, M, O, V), so none can exist.

Usage:
    cd server
    uv run python generate_data.py --policies 1200
    uv run python ../scripts/check_data.py --min-policies 1000
"""
import argparse
import datetime
import json
import math
import os
import random

from legacy import heron, herondb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
H = heron

# (area, town, districts, weight). Loaded areas are over-represented on purpose.
TOWNS = [
    ('HU', 'HULL', [1, 3, 5, 9], 7), ('YO', 'YORK', [1, 10, 24, 31], 6), ('CA', 'CARLISLE', [1, 2, 3], 3),
    ('DN', 'DONCASTER', [1, 2, 4], 4), ('TS', 'MIDDLESBROUGH', [1, 3, 5], 3), ('BD', 'BRADFORD', [1, 3, 7], 4),
    ('SE', 'LONDON', [1, 8, 15], 5), ('LS', 'LEEDS', [1, 6, 11, 12], 6), ('L', 'LIVERPOOL', [1, 3, 8], 6),
    ('M', 'MANCHESTER', [1, 4, 14], 8), ('E', 'LONDON', [1, 2, 14], 5), ('B', 'BIRMINGHAM', [1, 5, 12], 7),
    ('G', 'GLASGOW', [1, 2, 41], 4), ('NE', 'NEWCASTLE', [1, 4], 4), ('S', 'SHEFFIELD', [1, 6], 5),
    ('BS', 'BRISTOL', [1, 3], 5), ('NG', 'NOTTINGHAM', [1, 7], 4), ('CF', 'CARDIFF', [10, 14], 3),
    ('EH', 'EDINBURGH', [1, 6], 3), ('PE', 'PETERBOROUGH', [1, 2], 2), ('NR', 'NORWICH', [1, 3], 3),
    ('OX', 'OXFORD', [1, 4], 2), ('RG', 'READING', [1, 2], 3), ('PL', 'PLYMOUTH', [1, 4], 2),
    ('LE', 'LEICESTER', [1, 2], 3), ('CV', 'COVENTRY', [1, 6], 3),
]
# trade: (weight, claim rate multiplier, name words)
TRADES = {
    'OFFC': (16, 0.6, ['CONSULTING', 'ASSOCIATES', 'SURVEYORS', 'ACCOUNTANCY', 'DESIGN STUDIO']),
    'SALN': (8, 0.7, ['HAIR STUDIO', 'BEAUTY ROOMS', 'BARBERS']),
    'RETL': (18, 1.0, ['HARDWARE', 'OUTFITTERS', 'BOOKS', 'CYCLES', 'HOMEWARES', 'PET SUPPLIES']),
    'WHSE': (8, 1.0, ['STORAGE', 'LOGISTICS', 'DISTRIBUTION']),
    'LMFG': (9, 1.2, ['ENGINEERING', 'FABRICATIONS', 'PLASTICS', 'PRECISION COMPONENTS']),
    'FOOD': (5, 1.3, ['BAKERY', 'FINE FOODS', 'DAIRY', 'PRESERVES']),
    'HOTL': (5, 1.2, ['HOTEL', 'GUEST HOUSE', 'LODGE']),
    'MOTR': (7, 1.4, ['MOTORS', 'AUTO REPAIRS', 'TYRE AND EXHAUST']),
    'REST': (10, 1.6, ['KITCHEN', 'BISTRO', 'CAFE', 'GRILL HOUSE']),
    'CONS': (8, 1.5, ['BUILDERS', 'ROOFING', 'GROUNDWORKS', 'SHOPFITTING']),
    'WOOD': (3, 1.8, ['JOINERY', 'CABINET MAKERS', 'TIMBER PRODUCTS']),
    'WSTE': (3, 2.0, ['RECYCLING', 'SKIP HIRE', 'WASTE SERVICES']),
}
STEMS = ['TESSEL', 'QUILLON', 'VARROW', 'OMBREL', 'KESTROW', 'MARRICK', 'DRAVEN', 'PELLOW', 'SORREN', 'WYNDLE',
         'HASKET', 'BRINDOL', 'CORVEN', 'ELSPETH', 'FARLOW', 'GRISSEL', 'IVERN', 'JORREL', 'LYSTER', 'NORBECK',
         'ORLIC', 'PERREN', 'RUDDLE', 'STRAVE', 'TOLLEN', 'UMBER', 'VESPIN', 'WARBLE', 'YARREN', 'ZENNICK']
ENDS = ['MOOR', 'WICK', 'FIELD', 'GATE', 'HOLME', 'STONE', 'BROOK', 'MERE', 'CROFT', 'DENE']
STREETS = ['MILL LANE', 'STATION ROAD', 'CANAL STREET', 'FOUNDRY WAY', 'MARKET PLACE', 'QUAY SIDE', 'CHAPEL ROW',
           'TANNERY YARD', 'BRIDGE STREET', 'ORCHARD PARK', 'WHARF ROAD', 'KILN CLOSE']
BROKER_ENDS = ['INSURANCE BROKERS', 'RISK PARTNERS', 'COMMERCIAL INSURANCE', 'BROKING', 'INSURANCE SERVICES']
REGIONS = ['NORTH', 'YORKS', 'MIDLANDS', 'LONDON', 'SOUTH WEST', 'SCOTLAND', 'WALES', 'EAST']
PROPERTY_PERILS = [('escape_of_water', 28), ('theft', 20), ('storm', 14), ('accidental_damage', 14), ('fire', 9),
                   ('flood', 8), ('business_interruption', 7)]
LIABILITY_PERILS = [('public_liability_injury', 45), ('employers_liability', 35), ('public_liability_property', 20)]
PERIL_TEXT = {
    'escape_of_water': 'Burst pipe, water damage to stock and fittings', 'theft': 'Forced entry, stock and cash stolen',
    'storm': 'Storm damage to roof and signage', 'accidental_damage': 'Accidental damage to plant',
    'fire': 'Fire in premises, smoke damage throughout', 'flood': 'Surface water flooding to ground floor',
    'business_interruption': 'Loss of trade following insured damage',
    'public_liability_injury': 'Member of the public injured on the premises',
    'employers_liability': 'Employee injury at work', 'public_liability_property': 'Damage to third party property',
}
SEVERITY = {'escape_of_water': 6500, 'theft': 4200, 'storm': 3800, 'accidental_damage': 2600, 'fire': 42000,
            'flood': 28000, 'business_interruption': 15000, 'public_liability_injury': 9000,
            'employers_liability': 14000, 'public_liability_property': 5200}


# First word of each fixed case in anchors(). Random names never reuse these.
ANCHOR_NAMES = {'TESSELMOOR', 'QUILLONGATE', 'VARROWSTONE', 'OMBRELFIELD', 'KESTROWBROOK', 'MARRICKCROFT',
                'DRAVENMERE', 'PELLOWWICK'}


def wpick(rng, pairs):
    total = sum(w for _, w in pairs)
    x = rng.uniform(0, total)
    for v, w in pairs:
        x -= w
        if x <= 0:
            return v
    return pairs[-1][0]


def iso(i):
    return H.I2D(i).isoformat()


class Generator:
    def __init__(self, policies, seed, as_at, out_dir):
        self.n = policies
        self.rng = random.Random(seed)
        self.seed = seed
        self.as_at = H.D2I(as_at)
        self.out = out_dir
        self.meta = {}          # polno -> plan
        self.claims = []
        self.rejects = 0
        self.names = set()
        self.insureds = []      # (insno, trade, pcode)

    # ---- building blocks ---------------------------------------------------------
    def postcode(self, town=None):
        area, name, districts, _ = town or wpick(self.rng, [(t, t[3]) for t in TOWNS])
        unit = ''.join(self.rng.choice('CIKMOV') for _ in range(2))      # never issued by Royal Mail
        return '%s%d%d%s' % (area, self.rng.choice(districts), self.rng.randint(1, 9), unit), name

    def company(self, trade):
        for _ in range(50):
            nm = '%s%s %s LTD' % (self.rng.choice(STEMS), self.rng.choice(ENDS), self.rng.choice(TRADES[trade][2]))
            if nm.split()[0] in ANCHOR_NAMES:
                continue                                   # keep the guide's named cases unique
            if nm not in self.names:
                self.names.add(nm)
                return nm
        nm = '%s %d LTD' % (nm[:-4], len(self.names))
        self.names.add(nm)
        return nm

    def brokers(self):
        k = min(24, max(15, self.n // 40))
        used = set()
        for i in range(1, k + 1):
            while True:
                nm = '%s %s' % (self.rng.choice(STEMS) + self.rng.choice(['', ' AND ' + self.rng.choice(STEMS)]),
                                self.rng.choice(BROKER_ENDS))
                if nm not in used:
                    used.add(nm)
                    break
            H.CN.execute('INSERT INTO BRKMST VALUES (?,?,?,?,?,?)',
                         ('B%03d' % i, nm, self.rng.choice(REGIONS), self.rng.choice([1500, 1750, 2000, 2000, 2250, 2500, 2750]),
                          'A', 'T%05d' % self.rng.randint(10000, 99999)))
        H.CN.commit()
        self.broker_codes = ['B%03d' % i for i in range(1, k + 1)]

    def risk(self, product, trade):
        r = self.rng
        d = {'SIBLD': 0, 'SICONT': 0, 'SIBI': 0, 'TURNOV': 0, 'EMPCNT': 0,
             'VOLXS': wpick(r, [(250, 55), (500, 25), (1000, 15), (2500, 5)]),
             'CONSTR': wpick(r, [(1, 70), (2, 15), (3, 8), (4, 7)]),
             'CLMCNT3': wpick(r, [(0, 70), (1, 18), (2, 8), (3, 3), (4, 1)])}
        if product == 'CP':
            if r.random() < 0.65:
                d['SIBLD'] = int(round(math.exp(r.gauss(13.1, 0.85)) / 5000.0)) * 5000
                d['SIBLD'] = min(max(d['SIBLD'], 120000), 9000000)
            d['SICONT'] = min(max(int(round(math.exp(r.gauss(11.2, 0.9)) / 1000.0)) * 1000, 15000), 1500000)
            if r.random() < 0.55:
                d['SIBI'] = min(max(int(round(math.exp(r.gauss(12.0, 0.8)) / 5000.0)) * 5000, 25000), 2500000)
        else:
            d['EMPCNT'] = min(max(int(math.exp(r.gauss(2.3, 1.0))), 1), 400)
            per_head = r.uniform(38000, 140000)
            d['TURNOV'] = max(int(round(d['EMPCNT'] * per_head / 5000.0)) * 5000, 60000)
            d['VOLXS'] = 0
            d['CONSTR'] = 1
        return d

    def plan(self, quote_date=None):
        r = self.rng
        product = 'CP' if r.random() < 0.62 else 'CL'
        trade = wpick(r, [(k, v[0]) for k, v in TRADES.items()])
        pcode, town = self.postcode()
        span = 4.6 * 365
        if quote_date is None:
            quote_date = H.ADDDAYS(self.as_at, -int(r.uniform(0, span)))
        p = {'PRODCD': product, 'TRDCD': trade, 'PCODE': pcode, 'TOWN': town, 'quote_date': quote_date,
             'incept_lag': r.randint(0, 24), 'BRKCD': r.choice(self.broker_codes),
             'usr': r.choice(['CLERK1', 'CLERK1', 'CLERK2', 'BRANCH7'])}
        p.update(self.risk(product, trade))
        return p

    def anchors(self):
        """A few fixed cases the guide refers to by insured name. Dates are relative to the as-at date."""
        a = self.as_at
        base = {'SIBLD': 0, 'SICONT': 0, 'SIBI': 0, 'TURNOV': 0, 'EMPCNT': 0, 'VOLXS': 250, 'CONSTR': 1,
                'CLMCNT3': 0, 'usr': 'CLERK1', 'incept_lag': 10, 'no_cancel': True, 'always_renew': True}
        rows = [
            # live Manchester shop: single-letter area, shows the area lookup behaviour
            dict(base, INSNAM='TESSELMOOR HARDWARE LTD', PRODCD='CP', TRDCD='RETL', PCODE='M43KV', TOWN='MANCHESTER',
                 SIBLD=650000, SICONT=180000, SIBI=250000, BRKCD='B001', quote_date=H.ADDDAYS(a, -520), no_mta=True,
                 no_claims=True),
            # Hull restaurant, buildings over 1m in a flood area: referred, approved
            dict(base, INSNAM='QUILLONGATE KITCHEN LTD', PRODCD='CP', TRDCD='REST', PCODE='HU37OC', TOWN='HULL',
                 SIBLD=1400000, SICONT=220000, SIBI=600000, VOLXS=1000, BRKCD='B002', quote_date=H.ADDDAYS(a, -300),
                 no_mta=True, no_claims=True),
            # contractor with two claims the branch never keyed
            dict(base, INSNAM='VARROWSTONE BUILDERS LTD', PRODCD='CL', TRDCD='CONS', PCODE='LS117MK', TOWN='LEEDS',
                 TURNOV=1800000, EMPCNT=22, VOLXS=0, BRKCD='B003', quote_date=H.ADDDAYS(a, -820), no_mta=True,
                 stale_claims=True, force_claims=[(-200, 'employers_liability'), (-95, 'public_liability_injury')]),
            # warehouse whose broker has not paid: credit hold
            dict(base, INSNAM='OMBRELFIELD STORAGE LTD', PRODCD='CP', TRDCD='WHSE', PCODE='LS124VC', TOWN='LEEDS',
                 SIBLD=2100000, SICONT=900000, SIBI=400000, VOLXS=500, BRKCD='B004', quote_date=H.ADDDAYS(a, -150),
                 no_mta=True, no_claims=True, unpaid=True),
            # open quote in a single-letter area, ready to bind
            dict(base, INSNAM='KESTROWBROOK DESIGN STUDIO LTD', PRODCD='CP', TRDCD='OFFC', PCODE='E14IO', TOWN='LONDON',
                 SIBLD=0, SICONT=95000, SIBI=150000, BRKCD='B005', quote_date=H.ADDDAYS(a, -6), incept_lag=16,
                 leave_quote=True),
            # open quote that Heron referred: woodworking in a timber frame building
            dict(base, INSNAM='MARRICKCROFT JOINERY LTD', PRODCD='CP', TRDCD='WOOD', PCODE='YO108CV', TOWN='YORK',
                 SIBLD=480000, SICONT=260000, SIBI=200000, CONSTR=3, CLMCNT3=1, BRKCD='B006',
                 quote_date=H.ADDDAYS(a, -4), incept_lag=20, leave_quote=True),
            # leap day inception: the 365 day pro rata rule meets a 366 day year
            dict(base, INSNAM='DRAVENMERE HOTEL LTD', PRODCD='CP', TRDCD='HOTL', PCODE='YO12MO', TOWN='YORK',
                 SIBLD=1850000, SICONT=420000, SIBI=900000, CONSTR=4, VOLXS=1000, BRKCD='B007',
                 quote_date=20240215, incept_lag=14, no_claims=True,
                 force_mta=[(150, {'SICONT': 520000})]),
            # cancelled inside the 14 day cooling off period
            dict(base, INSNAM='PELLOWWICK BARBERS LTD', PRODCD='CL', TRDCD='SALN', PCODE='B52KM', TOWN='BIRMINGHAM',
                 TURNOV=140000, EMPCNT=4, VOLXS=0, BRKCD='B008', quote_date=H.ADDDAYS(a, -90), incept_lag=5,
                 no_cancel=False, force_cancel=9, no_mta=True, no_claims=True),
        ]
        for r in rows:
            self.names.add(r['INSNAM'])
        return rows

    # ---- one policy's life, replayed through Heron ----------------------------------
    def simulate(self, pl):
        r = self.rng
        a = self.as_at
        H.SETSYSDT(pl['quote_date'])
        incdt = H.ADDDAYS(pl['quote_date'], pl['incept_lag'])
        f = {k: pl[k] for k in ('PRODCD', 'BRKCD', 'TRDCD', 'PCODE', 'CONSTR', 'SIBLD', 'SICONT', 'SIBI', 'TURNOV',
                                'EMPCNT', 'VOLXS', 'CLMCNT3', 'TOWN')}
        f['INCDT'] = H.DTSCR(incdt)
        if not pl.get('INSNAM') and self.insureds and r.random() < 0.10:
            f['INSNO'] = r.choice(self.insureds)[0]          # an existing customer takes a second policy
        else:
            f['INSNAM'] = pl.get('INSNAM') or self.company(pl['TRDCD'])
            f['ADDR1'] = '%d %s' % (r.randint(1, 180), r.choice(STREETS))
            f['ESTYR'] = r.randint(1962, 2023)
            f['COMPNO'] = 'ZZ%06d' % r.randint(100000, 999999)
        try:
            q = H.NBQTE(f, pl['usr'])
        except H.HeronErr:
            self.rejects += 1
            return
        polno = q['POLNO']
        self.meta[polno] = pl
        self.insureds.append((q['INSNO'], pl['TRDCD'], pl['PCODE']))
        if pl.get('leave_quote'):
            return
        if incdt > a:                                     # future inception: an open quote
            if H.DAYS(pl['quote_date'], a) > 25 or r.random() < 0.3:
                H.NTUQTE(polno, pl['usr'])
            return
        if not pl.get('always_renew') and r.random() < 0.06:
            H.SETSYSDT(min(a, H.ADDDAYS(pl['quote_date'], r.randint(1, 20))))
            H.NTUQTE(polno, pl['usr'])
            return
        binder = pl['usr']
        if q['UWREF'] == 'Y':
            binder = 'UWMGR1'
            if not pl.get('always_renew') and r.random() < 0.15:
                H.SETSYSDT(min(a, H.ADDDAYS(pl['quote_date'], r.randint(1, 5))))
                H.NTUQTE(polno, 'UWMGR1')                 # underwriter declined the referral
                return
        H.SETSYSDT(min(a, H.ADDDAYS(pl['quote_date'], r.randint(0, 6))))
        H.NBBND(polno, binder)
        keyed = pl['CLMCNT3']
        history = []                                      # non-declined loss dates on this policy
        while True:
            p = H.GETPOL(polno)
            s, e = p['INCDT'], p['EXPDT']
            last = min(H.ADDDAYS(e, -1), a)               # last day something can happen in this term
            if last <= s:
                break
            # cancellation?
            cand = 0
            if pl.get('force_cancel') and p['POLSFX'] == 1:
                cand = H.ADDDAYS(s, pl['force_cancel'])
            elif not pl.get('no_cancel') and r.random() < 0.05:
                cand = H.ADDDAYS(s, r.randint(3, 12) if r.random() < 0.15 else r.randint(20, 340))
            if cand and cand > last:
                cand = 0
            stop = cand or H.ADDDAYS(last, 1)             # events happen strictly before this date
            # mid term adjustments
            mtas = []
            if pl.get('force_mta') and p['POLSFX'] == 1:
                mtas = [(H.ADDDAYS(s, d), chg) for d, chg in pl['force_mta']]
            elif not pl.get('no_mta'):
                for _ in range(2 if r.random() < 0.03 else 1):
                    if r.random() < 0.17 and H.DAYS(s, stop) > 50:
                        mtas.append((H.ADDDAYS(s, r.randint(20, H.DAYS(s, stop) - 10)), None))
            for eff, chg in sorted(mtas, key=lambda m: m[0]):
                if eff >= stop:
                    continue
                self.adjust(polno, eff, chg)
            # claims in this term
            for loss, peril in self.term_claims(pl, p, s, stop):
                st = self.add_claim(polno, p, loss, peril)
                if st != 'declined':
                    history.append(loss)
            in_term = any(x >= s for x in history)
            if in_term and r.random() < 0.70:             # the branch usually keys the claim marker
                H.CN.execute("UPDATE POLMST SET CLMCUR='Y' WHERE POLNO=? AND POLSFX=?", (polno, p['POLSFX']))
                H.CN.commit()
            if cand:
                H.SETSYSDT(min(a, H.ADDDAYS(cand, r.randint(0, 4))))
                H.CANENT(polno, H.DTSCR(cand), pl['usr'])
                break
            if e > a:
                break                                     # still live at the as-at date
            if pl.get('always_renew') or r.random() < 0.84:
                actual = sum(1 for x in history if x > H.ADDDAYS(e, -1096))
                carried = max(0, pl['CLMCNT3'] - p['POLSFX']) if p['POLSFX'] < 3 else 0
                if not pl.get('stale_claims') and r.random() < 0.70:
                    keyed = actual + carried              # re-keyed from the claims system at renewal
                H.SETSYSDT(H.ADDDAYS(e, -r.randint(5, 45)))
                H.RNWRUN(polno, pl['usr'], keyed)
            else:
                H.SETSYSDT(e)
                H.CN.execute("UPDATE POLMST SET STATCD='E', UPDDT=? WHERE POLNO=? AND POLSFX=?", (e, polno, p['POLSFX']))
                H.CN.commit()
                break

    def adjust(self, polno, eff, chg):
        r = self.rng
        p = H.GETPOL(polno)
        if chg is None:
            chg = {}
            if p['PRODCD'] == 'CP':
                kind = wpick(r, [('bld', 30), ('cont', 30), ('bi', 15), ('xs', 12), ('move', 13)])
                if kind == 'bld' and p['SIBLD']:
                    chg['SIBLD'] = int(round(p['SIBLD'] * r.uniform(1.05, 1.35) / 5000.0)) * 5000
                elif kind == 'bi':
                    chg['SIBI'] = max(50000, int(round((p['SIBI'] or 100000) * r.uniform(0.7, 1.6) / 5000.0)) * 5000)
                elif kind == 'xs':
                    chg['VOLXS'] = r.choice([v for v in (250, 500, 1000, 2500) if v != p['VOLXS']])
                elif kind == 'move':
                    chg['PCODE'] = self.postcode()[0]
                else:
                    chg['SICONT'] = max(15000, int(round(p['SICONT'] * r.uniform(0.8, 1.5) / 1000.0)) * 1000)
            else:
                chg['EMPCNT'] = max(1, int(p['EMPCNT'] * r.uniform(0.8, 1.4)) + r.choice([0, 1, 2]))
                chg['TURNOV'] = max(60000, int(round(p['TURNOV'] * r.uniform(0.85, 1.4) / 5000.0)) * 5000)
        f = dict(chg)
        f['EFFDT'] = H.DTSCR(eff)
        H.SETSYSDT(min(self.as_at, max(p['CRTDT'], H.ADDDAYS(eff, r.randint(-10, 12)))))
        for usr in (self.meta[polno]['usr'], 'UWMGR1'):
            try:
                H.MTAENT(polno, f, usr)
                return
            except H.HeronErr as ex:
                if 'REFERRED' not in str(ex):
                    return

    def term_claims(self, pl, p, s, stop):
        r = self.rng
        out = []
        window = H.DAYS(s, stop)
        if window < 2:
            return out
        if pl.get('force_claims') is not None or pl.get('no_claims'):
            for off, peril in pl.get('force_claims') or []:
                loss = H.ADDDAYS(self.as_at, off)
                if s <= loss < stop:
                    out.append((loss, peril))
            return out
        rate = (0.15 if p['PRODCD'] == 'CP' else 0.12) * TRADES[p['TRDCD']][1] * (window / 365.0)
        n = 0
        x = r.random()
        cum = term = math.exp(-rate)
        while x > cum and n < 4:                           # Poisson draw
            n += 1
            term *= rate / n
            cum += term
        perils = PROPERTY_PERILS if p['PRODCD'] == 'CP' else LIABILITY_PERILS
        for _ in range(n):
            out.append((H.ADDDAYS(s, r.randint(0, window - 1)), wpick(r, perils)))
        return sorted(out)

    def add_claim(self, polno, p, loss, peril):
        r = self.rng
        a = self.as_at
        notified = min(a, H.ADDDAYS(loss, int(abs(r.gauss(0, 9)))))
        amount = round(SEVERITY[peril] * math.exp(r.gauss(-0.35, 0.95)), 2)
        age = H.DAYS(notified, a)
        if age > 270:
            status = wpick(r, [('settled', 82), ('declined', 9), ('open', 9)])
        elif age > 90:
            status = wpick(r, [('settled', 50), ('open', 42), ('declined', 8)])
        else:
            status = wpick(r, [('open', 85), ('settled', 10), ('declined', 5)])
        paid = outstanding = 0.0
        if status == 'settled':
            paid = amount
        elif status == 'open':
            paid = round(amount * r.choice([0, 0, 0.1, 0.25, 0.4]), 2)
            outstanding = max(round(amount - paid, 2), 250.0)
        self.claims.append({'claim_ref': None, 'policy_ref': polno, 'policy_term': p['POLSFX'],
                            'insured_ref': str(p['INSNO']), 'loss_date': iso(loss), 'notified_date': iso(notified),
                            'peril': peril, 'description': PERIL_TEXT[peril], 'status': status, 'paid': paid,
                            'outstanding': outstanding, 'handler': 'CH%02d' % r.randint(1, 12)})
        return status

    # ---- derive the downstream systems from what Heron wrote -------------------------
    def renumber(self):
        cn = H.CN
        for tbl, col in (('PRMTRN', 'TRNNO'), ('ENDMST', 'ENDNO')):
            rows = cn.execute('SELECT rowid AS RID FROM %s ORDER BY CRTDT, %s' % (tbl, col)).fetchall()
            cn.execute('UPDATE %s SET %s = -%s' % (tbl, col, col))
            for i, row in enumerate(rows, 1):
                cn.execute('UPDATE %s SET %s=? WHERE rowid=?' % (tbl, col), (i, row['RID']))
        cn.commit()

    def finance(self):
        r = self.rng
        a = self.as_at
        postings, payments = [], []
        # Two brokers pay late, so credit hold shows up on some brokers and not others
        self.slow_payers = {'BRK-B004', 'BRK-%s' % self.broker_codes[9]}
        for t in H.QA('SELECT T.*, P.BRKCD FROM PRMTRN T JOIN POLMST P ON P.POLNO=T.POLNO AND P.POLSFX=T.POLSFX ORDER BY TRNNO'):
            ref = 'GL-%d-%07d' % (t['EFFDT'] // 10000, t['TRNNO'])
            H.CN.execute('UPDATE PRMTRN SET FINREF=? WHERE TRNNO=?', (ref, t['TRNNO']))
            postings.append({'posting_ref': ref, 'transaction_ref': 'HERON-%07d' % t['TRNNO'], 'policy_ref': t['POLNO'],
                             'policy_term': t['POLSFX'], 'broker_account': 'BRK-' + t['BRKCD'],
                             'transaction_type': t['TRNTYP'], 'effective_date': iso(t['EFFDT']),
                             'gross_premium': t['GRSPRM'] / 100.0, 'ipt': t['IPTAMT'] / 100.0,
                             'commission': t['COMAMT'] / 100.0,
                             'net_due': (t['GRSPRM'] + t['IPTAMT'] - t['COMAMT']) / 100.0,
                             'posted_date': iso(min(a, H.ADDDAYS(t['CRTDT'], 1)))})
        H.CN.commit()
        for q in postings:
            if q['net_due'] <= 0:
                continue
            eff = int(q['effective_date'].replace('-', ''))
            age = H.DAYS(eff, a)
            if age < 8 or self.meta[q['policy_ref']].get('unpaid'):
                continue
            x = r.random()
            share = 0.0
            slow = q['broker_account'] in self.slow_payers
            if age > 60:
                share = 1.0 if not slow else (0.0 if x < 0.35 else r.uniform(0.5, 0.8) if x < 0.45 else 1.0)
            elif age > 25:
                share = 1.0 if x < 0.70 else 0.0
            else:
                share = 1.0 if x < 0.25 else 0.0
            if share:
                payments.append({'payment_ref': None, 'policy_ref': q['policy_ref'], 'broker_account': q['broker_account'],
                                 'amount': round(q['net_due'] * share, 2),
                                 'received_date': iso(min(a, H.ADDDAYS(eff, r.randint(8, min(50, age)))))})
        payments.sort(key=lambda y: y['received_date'])
        for i, y in enumerate(payments, 1):
            y['payment_ref'] = 'PAY-%07d' % i
        return postings, payments

    def underwriting(self):
        r = self.rng
        a = self.as_at
        referrals = []
        for p in H.QA("SELECT * FROM POLMST WHERE UWREF='Y' ORDER BY CRTDT, POLNO, POLSFX"):
            reasons = H.CHKREF(p['PRODCD'], p['TRDCD'], p['PCODE'], p['CONSTR'], p['SIBLD'], p['SICONT'], p['SIBI'],
                               p['TURNOV'], p['EMPCNT'], p['CLMCNT3']) or ['R00 REFERRED ON AN EARLIER VERSION OF THE RISK']
            status = 'open' if p['STATCD'] == 'Q' else 'declined' if p['STATCD'] == 'D' else 'approved'
            decided = None if status == 'open' else iso(min(a, H.ADDDAYS(p['CRTDT'], r.randint(0, 4))))
            referrals.append({'referral_ref': 'REF-%06d' % (len(referrals) + 1), 'policy_ref': p['POLNO'],
                              'policy_term': p['POLSFX'], 'raised_date': iso(p['CRTDT']), 'reasons': reasons,
                              'status': status, 'decided_by': None if status == 'open' else r.choice(['UWMGR1', 'UWMGR2']),
                              'decided_date': decided, 'raised_by': 'heron-rekey', 'notes': ''})
        live = {}
        for p in H.QA("SELECT * FROM POLMST WHERE STATCD='L' AND PRODCD='CP'"):
            d = live.setdefault(p['PCODE'][:-3], [0, 0])
            d[0] += p['SIBLD'] + p['SICONT'] + p['SIBI']
            d[1] += 1
        tight = {d for d, _ in sorted(live.items(), key=lambda kv: -kv[1][0])[:4]}
        accum = []
        for d in sorted(live):
            si, n = live[d]
            if d in tight:
                limit = math.ceil(si * 1.06 / 250000.0) * 250000
            else:
                limit = max(12000000, math.ceil(si * r.uniform(1.3, 3.0) / 1000000.0) * 1000000)
            accum.append({'postcode_district': d, 'live_total_si': float(si), 'live_policies': n, 'limit': float(limit)})
        return referrals, accum

    # ---- run -------------------------------------------------------------------------
    def run(self):
        cn = herondb.EMPTYDB()
        herondb.LOADTBL(cn, 'RATTBL', os.path.join(DATA_DIR, 'legacy'))      # reference data, kept as is
        H.USEDB(cn)
        self.brokers()
        plans = self.anchors() + [self.plan() for _ in range(max(0, self.n - 8))]
        # a handful of quotes keyed in the last three weeks so there is something to bind on the day
        for _ in range(max(4, self.n // 60)):
            plans.append(self.plan(quote_date=H.ADDDAYS(self.as_at, -self.rng.randint(0, 20))))
        plans.sort(key=lambda p: p['quote_date'])
        for pl in plans:
            self.simulate(pl)
        # two brokers were suspended after writing business
        for code in self.broker_codes[-2:]:
            cn.execute("UPDATE BRKMST SET STATCD='S' WHERE BRKCD=?", (code,))
        cn.commit()
        self.renumber()
        postings, payments = self.finance()
        referrals, accum = self.underwriting()
        self.claims.sort(key=lambda c: (c['notified_date'], c['policy_ref']))
        for i, c in enumerate(self.claims, 1):
            c['claim_ref'] = 'CLM-%s-%06d' % (c['loss_date'][:4], i)
        H.SETSYSDT(self.as_at)
        self.write(postings, payments, referrals, accum)
        return {'policies': H.Q1('SELECT COUNT(DISTINCT POLNO) AS N FROM POLMST')['N'],
                'terms': H.Q1('SELECT COUNT(*) AS N FROM POLMST')['N'],
                'transactions': len(postings), 'claims': len(self.claims), 'payments': len(payments),
                'referrals': len(referrals), 'rejected_quotes': self.rejects}

    def write(self, postings, payments, referrals, accum):
        herondb.UNLOAD(H.CN, os.path.join(self.out, 'legacy'))

        def dump(system, name, rows):
            os.makedirs(os.path.join(self.out, system), exist_ok=True)
            with open(os.path.join(self.out, system, name), 'w', encoding='utf-8') as fh:
                fh.write('[\n' + ',\n'.join(json.dumps(x, separators=(', ', ': ')) for x in rows) + '\n]\n')

        dump('claims', 'claims.json', self.claims)
        dump('finance', 'postings.json', postings)
        dump('finance', 'payments.json', payments)
        dump('underwriting', 'referrals.json', referrals)
        dump('underwriting', 'accumulations.json', accum)
        with open(os.path.join(self.out, 'as_at.json'), 'w', encoding='utf-8') as fh:
            json.dump({'as_at': iso(self.as_at), 'seed': self.seed, 'requested_policies': self.n,
                       'note': 'The lab clock is frozen at this date. Synthetic data: nothing here is real.'}, fh, indent=1)
            fh.write('\n')


def main():
    ap = argparse.ArgumentParser(description='Generate a consistent synthetic book across all four systems.')
    ap.add_argument('--policies', type=int, default=1200)
    ap.add_argument('--seed', type=int, default=20261112)
    ap.add_argument('--as-at', default='2026-11-12', help='lab date, ISO format')
    ap.add_argument('--out', default=DATA_DIR)
    a = ap.parse_args()
    stats = Generator(a.policies, a.seed, datetime.date.fromisoformat(a.as_at), a.out).run()
    print('Generated: ' + ', '.join('%s %s' % (v, k.replace('_', ' ')) for k, v in stats.items()))
    print('Now run: uv run python ../scripts/check_data.py --min-policies %d' % int(a.policies * 0.8))


if __name__ == '__main__':
    main()
