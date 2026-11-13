# =============================================================================
#  HERON  -  POLICY ADMINISTRATION SYSTEM            LARKSPUR & DENE INSURANCE
#  COMMERCIAL LINES (SME)                            MODULE: HERON  V4.7.2
# =============================================================================
#  CHANGE LOG
#  2004-06  RJP  INITIAL RELEASE. COMMERCIAL PROPERTY (CP) NEW BUSINESS.
#  2005-02  RJP  COMBINED LIABILITY (CL) ADDED. EL/PL RATES IN RATTBL.
#  2006-11  RJP  MID TERM ADJUSTMENTS. PRO RATA ON 365 DAY BASIS.
#  2007-08  KAS  CHG0198 FLOOD LOADINGS BY POSTCODE AREA AFTER SUMMER FLOODS.
#  2009-03  KAS  CHG0412 EXTRA AREA LOADINGS (L, M, E, B, G) PER UW COMMITTEE.
#  2011-01  KAS  IPT RATE NOW HELD IN IPTRAT. TEST HARNESS: SYSDATE OVERRIDE.
#  2012-09  DMW  CHG0733 CANCELLATION RULES. COOLING OFF, MIN RETAINED PREMIUM.
#  2014-04  DMW  CHG0871 REFERRAL RULES TIGHTENED. TIMBER FRAME + COOKING.
#  2016-10  DMW  IPT 10 PCT.     2017-06  DMW  IPT 12 PCT.
#  2018-05  TNO  CHG1102 RENEWAL INDEX LINKING 4 PCT. PREMIUM CAP 15 PCT.
#  2019-11  TNO  CHG1190 MOVED FROM CGI TO PYTHON. SCREENS UNCHANGED.
#  2021-07  TNO  LARGE TURNOVER DISCOUNT (CL). UWMGR2 ADDED TO AUTHORITY LIST.
#
#  DATA CONVENTIONS - READ BEFORE YOU TOUCH ANYTHING
#   DATES     INTEGER CCYYMMDD. 0 = NOT SET.
#   PREMIUM   INTEGER PENCE, SIGNED. RETURN PREMIUMS ARE NEGATIVE.
#   SUMS INS  INTEGER WHOLE POUNDS. SO ARE TURNOVER AND VOLUNTARY EXCESS.
#   PERCENT   INTEGER PERCENT X 100 (2250 = 22.5 PCT).
#   POSTCODE  UPPER CASE NO SPACE.
#   STATCD    Q QUOTE  L LIVE  R RENEWED (SUPERSEDED BY NEXT POLSFX)
#             X CANCELLED  E EXPIRED/LAPSED  D DECLINED OR NOT TAKEN UP
#   POLSFX    TERM NUMBER. EACH RENEWAL WRITES A NEW POLMST ROW, POLSFX + 1.
#
#  PREMIUM TRANSACTIONS (PRMTRN) GO TO FINANCE IN THE OVERNIGHT FILE. FINREF IS
#  STAMPED WHEN FINANCE CONFIRM. CLAIMS ARE NOT HELD HERE. CLMCNT3 AND CLMCUR
#  ARE KEYED BY THE BRANCH FROM THE CLAIMS SYSTEM WHEN THEY REMEMBER.
# =============================================================================
import datetime
import html
import os
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from legacy import herondb

LK = herondb.LK
CN = None
_SYSDT = 0          # TEST HARNESS OVERRIDE. 0 = USE THE REAL DATE.

IPTRAT = 12         # INSURANCE PREMIUM TAX PCT
UWAUTH = ('UWMGR1', 'UWMGR2')
USRLST = ('CLERK1', 'CLERK2', 'BRANCH7', 'UWMGR1', 'UWMGR2')

TRDNAM = {
    'OFFC': 'OFFICE / PROFESSIONAL', 'SALN': 'HAIR AND BEAUTY', 'RETL': 'RETAIL SHOP',
    'WHSE': 'WAREHOUSE / STORAGE', 'LMFG': 'LIGHT MANUFACTURING', 'FOOD': 'FOOD MANUFACTURE',
    'HOTL': 'HOTEL / GUEST HOUSE', 'MOTR': 'MOTOR TRADE', 'REST': 'RESTAURANT / CAFE',
    'CONS': 'BUILDING CONTRACTOR', 'WOOD': 'WOODWORKING / JOINERY', 'WSTE': 'WASTE / RECYCLING',
}
CONNAM = {1: 'STANDARD BRICK/TILE', 2: 'NON STANDARD', 3: 'TIMBER FRAME', 4: 'LISTED BUILDING'}
PRDNAM = {'CP': 'COMMERCIAL PROPERTY', 'CL': 'COMBINED LIABILITY'}
STANAM = {'Q': 'QUOTE', 'L': 'LIVE', 'R': 'RENEWED', 'X': 'CANCELLED', 'E': 'EXPIRED', 'D': 'DECLINED/NTU'}

# AREA LOADINGS. CHG0198 FLOOD, CHG0412 THEFT/SUBSIDENCE. KEYED ON POSTCODE AREA.
AREAFC = {'HU': 1.35, 'YO': 1.20, 'CA': 1.25, 'DN': 1.15, 'TS': 1.10, 'BD': 1.16, 'SE': 1.14,
          'LS': 1.06, 'L': 1.15, 'M': 1.12, 'E': 1.18, 'B': 1.10, 'G': 1.08}
FLDARE = ('HU', 'YO', 'CA', 'DN')


class HeronErr(Exception):
    pass


# -----------------------------------------------------------------------------
#  HOUSEKEEPING
# -----------------------------------------------------------------------------
def INIT(datdir):
    global CN
    CN = herondb.OPENDB(datdir)
    return CN


def USEDB(cn):
    global CN
    CN = cn
    return CN


def SETSYSDT(d):
    """TEST HARNESS (2011). d = CCYYMMDD OR 0 TO GO BACK TO THE REAL DATE."""
    global _SYSDT
    _SYSDT = int(d or 0)


def SYSDT():
    if _SYSDT:
        return _SYSDT
    env = os.environ.get('HERON_SYSDATE')
    if env:
        return int(env)
    return D2I(datetime.date.today())


def D2I(d):
    return d.year * 10000 + d.month * 100 + d.day


def I2D(i):
    i = int(i)
    return datetime.date(i // 10000, (i // 100) % 100, i % 100)


def DAYS(a, b):
    """WHOLE DAYS FROM a TO b (BOTH CCYYMMDD)."""
    return (I2D(b) - I2D(a)).days


def ADDDAYS(a, n):
    return D2I(I2D(a) + datetime.timedelta(days=n))


def ADDYR(a):
    d = I2D(a)
    try:
        return D2I(d.replace(year=d.year + 1))
    except ValueError:          # 29 FEB
        return D2I(d.replace(year=d.year + 1, day=28))


def SCRDT(s):
    """SCREEN DATE DD/MM/CCYY (OR CCYYMMDD, OR CCYY-MM-DD) TO INTEGER."""
    s = str(s or '').strip()
    try:
        if '/' in s:
            dd, mm, yy = s.split('/')
            return D2I(datetime.date(int(yy), int(mm), int(dd)))
        if '-' in s:
            yy, mm, dd = s.split('-')
            return D2I(datetime.date(int(yy), int(mm), int(dd)))
        return D2I(I2D(int(s)))
    except Exception:
        raise HeronErr('INVALID DATE ' + s)


def DTSCR(i):
    if not i:
        return ''
    d = I2D(i)
    return '%02d/%02d/%04d' % (d.day, d.month, d.year)


def RND(x):
    """POUNDS (FLOAT) TO PENCE."""
    return int(x * 100 + 0.5)


def NUM(v, dflt=0):
    try:
        return int(str(v).replace(',', '').replace('£', '').strip() or dflt)
    except Exception:
        raise HeronErr('NOT NUMERIC: ' + str(v))


def PCD(v):
    p = str(v or '').upper().replace(' ', '')
    if len(p) < 5 or len(p) > 7 or not p.isalnum() or not p[0].isalpha() or not p[-2:].isalpha():
        raise HeronErr('INVALID POSTCODE ' + str(v))
    return p


def Q1(sql, args=()):
    with LK:
        return CN.execute(sql, args).fetchone()


def QA(sql, args=()):
    with LK:
        return CN.execute(sql, args).fetchall()


def GETPOL(polno, sfx=None):
    """CURRENT (HIGHEST POLSFX) ROW UNLESS sfx GIVEN."""
    if sfx:
        r = Q1('SELECT * FROM POLMST WHERE POLNO=? AND POLSFX=?', (polno, int(sfx)))
    else:
        r = Q1('SELECT * FROM POLMST WHERE POLNO=? ORDER BY POLSFX DESC', (polno,))
    if not r:
        raise HeronErr('POLICY NOT FOUND ' + str(polno))
    return dict(r)


# -----------------------------------------------------------------------------
#  RATING
# -----------------------------------------------------------------------------
def RATLKP(typ, key):
    r = Q1('SELECT RATVAL FROM RATTBL WHERE RATTYP=? AND RATKEY=?', (typ, str(key)))
    if not r:
        raise HeronErr('NO RATE FOR %s %s' % (typ, key))
    return float(r['RATVAL'])


def TRDFAC(trd):
    return RATLKP('TRADE', trd)


def AREFAC(pcode):
    # CHG0198/CHG0412. AREA IS THE FIRST TWO CHARACTERS OF THE POSTCODE.
    return AREAFC.get(pcode[:2], 1.00)


def CONFAC(constr):
    return RATLKP('CONSTR', constr)


def CLMFAC(clmcnt):
    if clmcnt <= 0:
        return 0.95             # CLAIM FREE DISCOUNT
    if clmcnt == 1:
        return 1.10
    if clmcnt == 2:
        return 1.25
    return 1.50


def XSDISC(volxs):
    if volxs >= 2500:
        return 0.10
    if volxs >= 1000:
        return 0.05
    if volxs >= 500:
        return 0.025
    return 0.0


def CALCPRM(prod, trd, pcode, constr, sibld, sicont, sibi, turnov, empcnt, volxs, clmcnt):
    """ANNUAL GROSS PREMIUM IN PENCE, EXCLUDING IPT."""
    if prod == 'CP':
        p = (sibld * RATLKP('BASE', 'BLD') + sicont * RATLKP('BASE', 'CNT') + sibi * RATLKP('BASE', 'BI')) / 1000.0
        p = p * TRDFAC(trd) * AREFAC(pcode) * CONFAC(constr) * CLMFAC(clmcnt)
        p = p * (1.0 - XSDISC(volxs))
        mn = RATLKP('MINPRM', 'CP')
    elif prod == 'CL':
        p = empcnt * RATLKP('ELRATE', trd) + (turnov / 1000.0) * RATLKP('PLRATE', trd)
        p = p * CLMFAC(clmcnt)
        if turnov > 2000000:
            p = p * 0.90        # 2021-07 LARGE TURNOVER DISCOUNT
        mn = RATLKP('MINPRM', 'CL')
    else:
        raise HeronErr('UNKNOWN PRODUCT ' + str(prod))
    if p < mn:
        p = mn
    return RND(p)


def CALCIPT(grs):
    """IPT IN PENCE ON A PREMIUM IN PENCE. FRACTIONS OF A PENNY ARE DROPPED."""
    if grs < 0:
        return -((-grs) * IPTRAT // 100)
    return grs * IPTRAT // 100


def CALCCOM(grs, commpc):
    if grs < 0:
        return -(((-grs) * commpc + 5000) // 10000)
    return (grs * commpc + 5000) // 10000


def CHKREF(prod, trd, pcode, constr, sibld, sicont, sibi, turnov, empcnt, clmcnt):
    """UNDERWRITING REFERRAL REASONS. EMPTY LIST = WITHIN BRANCH AUTHORITY."""
    rsn = []
    if clmcnt >= 3:
        rsn.append('R01 THREE OR MORE CLAIMS IN 3 YEARS')
    if trd in ('WOOD', 'WSTE'):
        rsn.append('R02 TRADE REQUIRES UNDERWRITER APPROVAL')
    if prod == 'CP':
        if sibld + sicont + sibi > 5000000:
            rsn.append('R03 TOTAL SUM INSURED OVER 5,000,000')
        if pcode[:2] in FLDARE and sibld > 1000000:
            rsn.append('R04 FLOOD AREA BUILDINGS OVER 1,000,000')
        if constr == 3 and trd in ('REST', 'HOTL', 'FOOD'):
            rsn.append('R05 TIMBER FRAME WITH COOKING RISK')
    else:
        if empcnt > 250:
            rsn.append('R06 OVER 250 EMPLOYEES')
        if turnov > 10000000:
            rsn.append('R07 TURNOVER OVER 10,000,000')
        if trd == 'CONS' and turnov > 2000000:
            rsn.append('R08 CONTRACTOR TURNOVER OVER 2,000,000')
    return rsn


# -----------------------------------------------------------------------------
#  NEW BUSINESS
# -----------------------------------------------------------------------------
def NXTNO(tbl, col, start):
    r = Q1('SELECT MAX(%s) AS M FROM %s' % (col, tbl))
    return max(int(r['M'] or 0), start - 1) + 1


def NXTPOL(prod):
    r = Q1('SELECT MAX(CAST(SUBSTR(POLNO, 4) AS INTEGER)) AS M FROM POLMST')
    n = max(int(r['M'] or 0), 10000) + 1
    return ('LDC' if prod == 'CP' else 'LDL') + '%07d' % n


def RSKFLD(f, cur=None):
    """PULL THE RISK FIELDS OFF THE SCREEN. cur = EXISTING POLICY ROW FOR AN MTA."""
    cur = cur or {}

    def g(k, d=0):
        v = f.get(k)
        if v is None or str(v).strip() == '':
            return cur.get(k, d)
        return v

    r = {}
    r['TRDCD'] = str(g('TRDCD', '')).upper().strip()
    if r['TRDCD'] not in TRDNAM:
        raise HeronErr('INVALID TRADE CODE ' + r['TRDCD'])
    r['PCODE'] = PCD(g('PCODE', ''))
    r['CONSTR'] = NUM(g('CONSTR', 1), 1)
    if r['CONSTR'] not in CONNAM:
        raise HeronErr('INVALID CONSTRUCTION CODE')
    for k in ('SIBLD', 'SICONT', 'SIBI', 'TURNOV', 'EMPCNT', 'VOLXS', 'CLMCNT3'):
        r[k] = NUM(g(k, 0))
        if r[k] < 0:
            raise HeronErr(k + ' CANNOT BE NEGATIVE')
    return r


def CHKLIM(prod, r):
    if prod == 'CP':
        if r['SIBLD'] + r['SICONT'] <= 0:
            raise HeronErr('BUILDINGS OR CONTENTS SUM INSURED REQUIRED')
        if r['SIBLD'] + r['SICONT'] + r['SIBI'] > 25000000:
            raise HeronErr('DECLINE - EXCEEDS MAXIMUM LINE 25,000,000')
    else:
        if r['EMPCNT'] < 1:
            raise HeronErr('AT LEAST ONE EMPLOYEE REQUIRED')
        if r['TURNOV'] <= 0:
            raise HeronErr('TURNOVER REQUIRED')
        if r['EMPCNT'] > 1000:
            raise HeronErr('DECLINE - OVER 1000 EMPLOYEES')


def NBQTE(f, usr='CLERK1'):
    """NEW BUSINESS QUOTE. WRITES POLMST STATCD Q. RETURNS A DICT."""
    with LK:
        prod = str(f.get('PRODCD', '')).upper().strip()
        if prod not in PRDNAM:
            raise HeronErr('INVALID PRODUCT')
        brk = Q1('SELECT * FROM BRKMST WHERE BRKCD=?', (str(f.get('BRKCD', '')).upper().strip(),))
        if not brk:
            raise HeronErr('BROKER NOT FOUND')
        if brk['STATCD'] != 'A':
            raise HeronErr('BROKER SUSPENDED - NO NEW BUSINESS')
        r = RSKFLD(f)
        CHKLIM(prod, r)
        today = SYSDT()
        incdt = SCRDT(f.get('INCDT'))
        if DAYS(today, incdt) < -30:
            raise HeronErr('INCEPTION MORE THAN 30 DAYS IN THE PAST')
        if DAYS(today, incdt) > 90:
            raise HeronErr('INCEPTION MORE THAN 90 DAYS AHEAD')
        # INSURED: USE EXISTING INSNO IF KEYED, ELSE ADD
        insno = NUM(f.get('INSNO', 0))
        if insno:
            if not Q1('SELECT INSNO FROM INSMST WHERE INSNO=?', (insno,)):
                raise HeronErr('INSURED NOT FOUND')
        else:
            nam = str(f.get('INSNAM', '')).strip().upper()
            if not nam:
                raise HeronErr('INSURED NAME REQUIRED')
            insno = NXTNO('INSMST', 'INSNO', 4000001)
            CN.execute('INSERT INTO INSMST VALUES (?,?,?,?,?,?,?,?)',
                       (insno, nam, str(f.get('ADDR1', '')).upper(), str(f.get('TOWN', '')).upper(),
                        r['PCODE'], r['TRDCD'], NUM(f.get('ESTYR', 0)), str(f.get('COMPNO', ''))))
        grs = CALCPRM(prod, r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                      r['TURNOV'], r['EMPCNT'], r['VOLXS'], r['CLMCNT3'])
        ipt = CALCIPT(grs)
        rsn = CHKREF(prod, r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                     r['TURNOV'], r['EMPCNT'], r['CLMCNT3'])
        polno = NXTPOL(prod)
        CN.execute('INSERT INTO POLMST VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (polno, 1, prod, insno, brk['BRKCD'], incdt, ADDYR(incdt), 'Q', r['TRDCD'], r['PCODE'],
                    r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'], r['TURNOV'], r['EMPCNT'], r['VOLXS'],
                    r['CLMCNT3'], 'N', grs, ipt, brk['COMMPC'], 'Y' if rsn else 'N', 0, usr, today, today))
        CN.commit()
        return {'POLNO': polno, 'POLSFX': 1, 'INSNO': insno, 'GRSPRM': grs, 'IPTAMT': ipt,
                'COMAMT': CALCCOM(grs, brk['COMMPC']), 'UWREF': 'Y' if rsn else 'N', 'REFRSN': rsn}


def WRTTRN(polno, sfx, typ, effdt, grs, commpc):
    trnno = NXTNO('PRMTRN', 'TRNNO', 1)
    ipt = CALCIPT(grs)
    com = CALCCOM(grs, commpc)
    CN.execute('INSERT INTO PRMTRN VALUES (?,?,?,?,?,?,?,?,?,?,?)',
               (trnno, polno, sfx, typ, effdt, grs, ipt, com, grs - com, '', SYSDT()))
    return {'TRNNO': trnno, 'TRNTYP': typ, 'EFFDT': effdt, 'GRSPRM': grs, 'IPTAMT': ipt,
            'COMAMT': com, 'NETAMT': grs - com}


def WRTEND(polno, sfx, typ, effdt, descr, adj):
    endno = NXTNO('ENDMST', 'ENDNO', 1)
    CN.execute('INSERT INTO ENDMST VALUES (?,?,?,?,?,?,?,?)',
               (endno, polno, sfx, typ, effdt, descr[:80], adj, SYSDT()))
    return endno


def NBBND(polno, usr='CLERK1'):
    """BIND A QUOTE. Q -> L. WRITES THE NB PREMIUM TRANSACTION."""
    with LK:
        p = GETPOL(polno)
        if p['STATCD'] != 'Q':
            raise HeronErr('POLICY IS NOT A QUOTE')
        if p['UWREF'] == 'Y' and usr not in UWAUTH:
            raise HeronErr('REFERRED - UNDERWRITER AUTHORITY REQUIRED TO BIND')
        today = SYSDT()
        if DAYS(p['CRTDT'], today) > 30:
            raise HeronErr('QUOTE EXPIRED - OVER 30 DAYS OLD')
        if DAYS(today, p['INCDT']) < -30:
            raise HeronErr('INCEPTION MORE THAN 30 DAYS IN THE PAST')
        CN.execute("UPDATE POLMST SET STATCD='L', UPDDT=?, USRID=? WHERE POLNO=? AND POLSFX=?",
                   (today, usr, polno, p['POLSFX']))
        t = WRTTRN(polno, p['POLSFX'], 'NB', p['INCDT'], p['GRSPRM'], p['COMMPC'])
        CN.commit()
        return t


def NTUQTE(polno, usr='CLERK1'):
    """QUOTE NOT TAKEN UP / DECLINED."""
    with LK:
        p = GETPOL(polno)
        if p['STATCD'] != 'Q':
            raise HeronErr('POLICY IS NOT A QUOTE')
        CN.execute("UPDATE POLMST SET STATCD='D', UPDDT=?, USRID=? WHERE POLNO=? AND POLSFX=?",
                   (SYSDT(), usr, polno, p['POLSFX']))
        CN.commit()


# -----------------------------------------------------------------------------
#  MID TERM ADJUSTMENT
# -----------------------------------------------------------------------------
def MTAENT(polno, f, usr='CLERK1'):
    """MID TERM ADJUSTMENT. f HOLDS EFFDT AND ANY CHANGED RISK FIELDS."""
    with LK:
        p = GETPOL(polno)
        if p['STATCD'] != 'L':
            raise HeronErr('POLICY IS NOT LIVE')
        effdt = SCRDT(f.get('EFFDT'))
        if effdt < p['INCDT'] or effdt >= p['EXPDT']:
            raise HeronErr('EFFECTIVE DATE OUTSIDE POLICY PERIOD')
        if DAYS(effdt, SYSDT()) > 30:
            raise HeronErr('CANNOT BACKDATE MORE THAN 30 DAYS')
        r = RSKFLD(f, p)
        r['CLMCNT3'] = p['CLMCNT3']             # NOT CHANGEABLE MID TERM
        CHKLIM(p['PRODCD'], r)
        rsn = CHKREF(p['PRODCD'], r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                     r['TURNOV'], r['EMPCNT'], r['CLMCNT3'])
        if rsn and usr not in UWAUTH:
            raise HeronErr('REFERRED - ' + rsn[0])
        new = CALCPRM(p['PRODCD'], r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                      r['TURNOV'], r['EMPCNT'], r['VOLXS'], r['CLMCNT3'])
        old = p['GRSPRM']
        dys = DAYS(effdt, p['EXPDT'])
        dif = new - old
        # 2006-11 PRO RATA ON A 365 DAY YEAR
        adj = RND(abs(dif) / 100.0 * dys / 365.0)
        if dif < 0:
            adj = -adj
        if abs(adj) < 1000:
            adj = 0                             # UNDER 10.00 NOT CHARGED OR REFUNDED
        if r['PCODE'] != p['PCODE']:
            typ = 'AD'
        elif (r['SIBLD'], r['SICONT'], r['SIBI']) != (p['SIBLD'], p['SICONT'], p['SIBI']):
            typ = 'SI'
        else:
            typ = 'CV'
        chg = [k for k in ('TRDCD', 'PCODE', 'CONSTR', 'SIBLD', 'SICONT', 'SIBI', 'TURNOV', 'EMPCNT', 'VOLXS')
               if r[k] != p[k]]
        if not chg:
            raise HeronErr('NO CHANGES KEYED')
        descr = ', '.join('%s %s>%s' % (k, p[k], r[k]) for k in chg)
        CN.execute('UPDATE POLMST SET TRDCD=?, PCODE=?, CONSTR=?, SIBLD=?, SICONT=?, SIBI=?, TURNOV=?, EMPCNT=?, '
                   'VOLXS=?, GRSPRM=?, IPTAMT=?, UWREF=?, UPDDT=?, USRID=? WHERE POLNO=? AND POLSFX=?',
                   (r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'], r['TURNOV'],
                    r['EMPCNT'], r['VOLXS'], new, CALCIPT(new), 'Y' if rsn else p['UWREF'], SYSDT(), usr,
                    polno, p['POLSFX']))
        endno = WRTEND(polno, p['POLSFX'], typ, effdt, descr, adj)
        t = None
        if adj != 0:
            t = WRTTRN(polno, p['POLSFX'], 'MTA', effdt, adj, p['COMMPC'])
        CN.commit()
        return {'POLNO': polno, 'POLSFX': p['POLSFX'], 'ENDNO': endno, 'ENDTYP': typ, 'OLDPRM': old,
                'NEWPRM': new, 'DAYS': dys, 'PRMADJ': adj, 'IPTADJ': CALCIPT(adj), 'TRN': t, 'REFRSN': rsn}


# -----------------------------------------------------------------------------
#  CANCELLATION  (CHG0733)
# -----------------------------------------------------------------------------
def CANENT(polno, effdt, usr='CLERK1'):
    with LK:
        p = GETPOL(polno)
        if p['STATCD'] != 'L':
            raise HeronErr('POLICY IS NOT LIVE')
        effdt = SCRDT(effdt)
        if effdt < p['INCDT'] or effdt >= p['EXPDT']:
            raise HeronErr('EFFECTIVE DATE OUTSIDE POLICY PERIOD')
        ann = p['GRSPRM']
        if DAYS(p['INCDT'], effdt) <= 14:
            rfd = ann - 2500                    # COOLING OFF. 25.00 ADMIN FEE
        elif p['CLMCUR'] == 'Y':
            rfd = 0                             # CLAIM IN CURRENT PERIOD. NO RETURN
        else:
            rfd = RND(ann / 100.0 * DAYS(effdt, p['EXPDT']) / 365.0 * 0.90)
        if ann - rfd < 5000:
            rfd = ann - 5000                    # MINIMUM RETAINED PREMIUM 50.00
        if rfd < 0:
            rfd = 0
        CN.execute("UPDATE POLMST SET STATCD='X', CANDT=?, UPDDT=?, USRID=? WHERE POLNO=? AND POLSFX=?",
                   (effdt, SYSDT(), usr, polno, p['POLSFX']))
        endno = WRTEND(polno, p['POLSFX'], 'CN', effdt, 'CANCELLED. RETURN PREMIUM %d' % rfd, -rfd)
        t = None
        if rfd:
            t = WRTTRN(polno, p['POLSFX'], 'CAN', effdt, -rfd, p['COMMPC'])
        CN.commit()
        return {'POLNO': polno, 'POLSFX': p['POLSFX'], 'ENDNO': endno, 'REFUND': rfd, 'TRN': t}


# -----------------------------------------------------------------------------
#  RENEWAL (CHG1102) AND EXPIRY
# -----------------------------------------------------------------------------
def RNWRUN(polno, usr='CLERK1', clmcnt=None):
    """RENEW A LIVE POLICY FOR A FURTHER YEAR. clmcnt = RE-KEYED CLAIM COUNT."""
    with LK:
        p = GETPOL(polno)
        if p['STATCD'] != 'L':
            raise HeronErr('POLICY IS NOT LIVE')
        today = SYSDT()
        if DAYS(today, p['EXPDT']) > 60:
            raise HeronErr('TOO EARLY - RENEWAL RUNS WITHIN 60 DAYS OF EXPIRY')
        if DAYS(p['EXPDT'], today) > 30:
            raise HeronErr('TOO LATE - EXPIRED MORE THAN 30 DAYS AGO')
        r = dict(p)
        if clmcnt is not None:
            r['CLMCNT3'] = int(clmcnt)
        if p['PRODCD'] == 'CP':
            r['SIBLD'] = int(p['SIBLD'] * 1.04 / 1000.0 + 0.5) * 1000      # INDEX LINKING
        new = CALCPRM(p['PRODCD'], r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                      r['TURNOV'], r['EMPCNT'], r['VOLXS'], r['CLMCNT3'])
        if r['CLMCNT3'] <= p['CLMCNT3']:
            cap = int(p['GRSPRM'] * 1.15)
            if new > cap:
                new = cap                       # 15 PCT CAP UNLESS CLAIMS HAVE WORSENED
        rsn = CHKREF(p['PRODCD'], r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'],
                     r['TURNOV'], r['EMPCNT'], r['CLMCNT3'])
        brk = Q1('SELECT * FROM BRKMST WHERE BRKCD=?', (p['BRKCD'],))
        sfx = p['POLSFX'] + 1
        CN.execute("UPDATE POLMST SET STATCD='R', UPDDT=? WHERE POLNO=? AND POLSFX=?", (today, polno, p['POLSFX']))
        CN.execute('INSERT INTO POLMST VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (polno, sfx, p['PRODCD'], p['INSNO'], p['BRKCD'], p['EXPDT'], ADDYR(p['EXPDT']), 'L',
                    r['TRDCD'], r['PCODE'], r['CONSTR'], r['SIBLD'], r['SICONT'], r['SIBI'], r['TURNOV'],
                    r['EMPCNT'], r['VOLXS'], r['CLMCNT3'], 'N', new, CALCIPT(new), brk['COMMPC'],
                    'Y' if rsn else 'N', 0, usr, today, today))
        t = WRTTRN(polno, sfx, 'RN', p['EXPDT'], new, brk['COMMPC'])
        CN.commit()
        return {'POLNO': polno, 'POLSFX': sfx, 'OLDPRM': p['GRSPRM'], 'NEWPRM': new, 'TRN': t, 'REFRSN': rsn}


def EXPRUN():
    """OVERNIGHT. LIVE POLICIES PAST EXPIRY AND NOT RENEWED GO TO E."""
    with LK:
        today = SYSDT()
        n = CN.execute("UPDATE POLMST SET STATCD='E', UPDDT=? WHERE STATCD='L' AND EXPDT<=?", (today, today)).rowcount
        CN.commit()
        return n


# =============================================================================
#  SCREENS. PLAIN HTML. ALL LINKS ARE RELATIVE SO THE PROXY PREFIX DOES NOT MATTER.
# =============================================================================
app = FastAPI(title='HERON PAS', docs_url=None, redoc_url=None, openapi_url=None)

CSS = ("body{font-family:Verdana,Arial,sans-serif;font-size:11px;background:#d4d0c8;margin:0}"
       ".hd{background:#000080;color:#fff;padding:4px 8px;font-weight:bold;font-size:12px}"
       ".hd span{float:right;font-weight:normal}.bd{padding:10px}"
       "table{border-collapse:collapse;background:#fff}td,th{border:1px solid #808080;padding:2px 6px;font-size:11px}"
       "th{background:#c0c0c0;text-align:left}.n{text-align:right}.er{color:#c00000;font-weight:bold}"
       ".ok{color:#006000;font-weight:bold}input,select{font-size:11px;font-family:Verdana}"
       "a{color:#000080}.mn a{display:block;padding:3px}.fk{margin-top:10px;color:#404040}")


def PAGE(ttl, body, msg='', err=''):
    h = ['<html><head><title>HERON - %s</title><style>%s</style></head><body>' % (ttl, CSS)]
    h.append('<div class="hd">HERON POLICY ADMINISTRATION &nbsp;-&nbsp; %s<span>LARKSPUR &amp; DENE &nbsp; SYSDATE %s</span></div>'
             % (ttl, DTSCR(SYSDT())))
    h.append('<div class="bd">')
    if err:
        h.append('<p class="er">*** %s ***</p>' % html.escape(err))
    if msg:
        h.append('<p class="ok">%s</p>' % html.escape(msg))
    h.append(body)
    h.append('<p class="fk">F3=<a href="./">MAIN MENU</a> &nbsp; F7=<a href="polenq">POLICY ENQUIRY</a> &nbsp; '
             'F9=<a href="nbqte">NEW BUSINESS</a></p></div></body></html>')
    return HTMLResponse(''.join(h))


def GBP(p):
    return '{:,.2f}'.format(p / 100.0)


def OPTS(d, sel):
    return ''.join('<option value="%s"%s>%s - %s</option>' % (k, ' selected' if str(k) == str(sel) else '', k, v)
                   for k, v in d.items())


def USRSEL(sel='CLERK1'):
    return '<select name="USRID">%s</select>' % ''.join(
        '<option%s>%s</option>' % (' selected' if u == sel else '', u) for u in USRLST)


async def FORM(request):
    raw = (await request.body()).decode('utf-8')
    return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}


@app.get('/', response_class=HTMLResponse)
def MNU():
    c = Q1("SELECT COUNT(*) AS N FROM POLMST WHERE STATCD='L'")['N']
    q = Q1("SELECT COUNT(*) AS N FROM POLMST WHERE STATCD='Q'")['N']
    b = ('<table class="mn"><tr><th>OPT</th><th>FUNCTION</th></tr>'
         '<tr><td>1</td><td><a href="polenq">POLICY ENQUIRY</a></td></tr>'
         '<tr><td>2</td><td><a href="nbqte">NEW BUSINESS QUOTE</a></td></tr>'
         '<tr><td>3</td><td><a href="polenq?stat=Q">OUTSTANDING QUOTES</a></td></tr>'
         '<tr><td>4</td><td><a href="brkenq">BROKER ENQUIRY</a></td></tr>'
         '<tr><td>5</td><td><a href="rattbl">RATING TABLES</a></td></tr></table>'
         '<p>LIVE POLICIES %d &nbsp; OPEN QUOTES %d</p>'
         '<p>MID TERM ADJUSTMENT, CANCELLATION AND RENEWAL ARE REACHED FROM THE POLICY DISPLAY.</p>' % (c, q))
    return PAGE('MAIN MENU', b)


@app.get('/polenq', response_class=HTMLResponse)
def POLENQ(q: str = '', stat: str = ''):
    sql = ('SELECT P.*, I.INSNAM FROM POLMST P JOIN INSMST I ON I.INSNO=P.INSNO '
           'WHERE P.POLSFX=(SELECT MAX(POLSFX) FROM POLMST X WHERE X.POLNO=P.POLNO)')
    args = []
    if q:
        sql += ' AND (P.POLNO LIKE ? OR I.INSNAM LIKE ? OR P.PCODE LIKE ?)'
        args += ['%' + q.upper() + '%'] * 3
    if stat:
        sql += ' AND P.STATCD=?'
        args.append(stat.upper())
    rows = QA(sql + ' ORDER BY P.POLNO DESC LIMIT 60', args)
    b = ['<form method="get" action="polenq">POLICY NO / INSURED / POSTCODE <input name="q" value="%s" size="24"> '
         'STATUS <select name="stat"><option value="">ALL</option>%s</select> <input type="submit" value="ENTER"></form><br>'
         % (html.escape(q), OPTS(STANAM, stat))]
    b.append('<table><tr><th>POLICY</th><th>SFX</th><th>PROD</th><th>INSURED</th><th>BRK</th><th>INCEPT</th>'
             '<th>EXPIRY</th><th>ST</th><th>ANNUAL PREM</th></tr>')
    for r in rows:
        b.append('<tr><td><a href="poldsp?polno=%s">%s</a></td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                 '<td>%s</td><td>%s</td><td class="n">%s</td></tr>'
                 % (r['POLNO'], r['POLNO'], r['POLSFX'], r['PRODCD'], html.escape(r['INSNAM']), r['BRKCD'],
                    DTSCR(r['INCDT']), DTSCR(r['EXPDT']), r['STATCD'], GBP(r['GRSPRM'])))
    b.append('</table><p>%d SHOWN (MAX 60)</p>' % len(rows))
    return PAGE('POLICY ENQUIRY', ''.join(b))


def DSPBODY(polno):
    p = GETPOL(polno)
    i = Q1('SELECT * FROM INSMST WHERE INSNO=?', (p['INSNO'],))
    k = Q1('SELECT * FROM BRKMST WHERE BRKCD=?', (p['BRKCD'],))
    b = ['<table><tr><th>POLICY</th><td>%s / %02d</td><th>STATUS</th><td>%s %s</td><th>PRODUCT</th><td>%s %s</td></tr>'
         % (p['POLNO'], p['POLSFX'], p['STATCD'], STANAM.get(p['STATCD'], ''), p['PRODCD'], PRDNAM[p['PRODCD']])]
    b.append('<tr><th>INSURED</th><td colspan="3">%d %s</td><th>BROKER</th><td>%s %s</td></tr>'
             % (i['INSNO'], html.escape(i['INSNAM']), k['BRKCD'], html.escape(k['BRKNAM'])))
    b.append('<tr><th>INCEPTION</th><td>%s</td><th>EXPIRY</th><td>%s</td><th>CANCELLED</th><td>%s</td></tr>'
             % (DTSCR(p['INCDT']), DTSCR(p['EXPDT']), DTSCR(p['CANDT'])))
    b.append('<tr><th>TRADE</th><td>%s %s</td><th>RISK PCODE</th><td>%s</td><th>CONSTR</th><td>%d %s</td></tr>'
             % (p['TRDCD'], TRDNAM.get(p['TRDCD'], ''), p['PCODE'], p['CONSTR'], CONNAM.get(p['CONSTR'], '')))
    b.append('<tr><th>SI BLDGS</th><td class="n">%s</td><th>SI CONTS</th><td class="n">%s</td><th>SI BI</th><td class="n">%s</td></tr>'
             % ('{:,}'.format(p['SIBLD']), '{:,}'.format(p['SICONT']), '{:,}'.format(p['SIBI'])))
    b.append('<tr><th>TURNOVER</th><td class="n">%s</td><th>EMPLOYEES</th><td class="n">%d</td><th>VOL XS</th><td class="n">%d</td></tr>'
             % ('{:,}'.format(p['TURNOV']), p['EMPCNT'], p['VOLXS']))
    b.append('<tr><th>CLAIMS 3YR</th><td>%d</td><th>CLAIM CUR</th><td>%s</td><th>UW REFER</th><td>%s</td></tr>'
             % (p['CLMCNT3'], p['CLMCUR'], p['UWREF']))
    b.append('<tr><th>ANNUAL PREM</th><td class="n">%s</td><th>IPT</th><td class="n">%s</td><th>COMM PCT</th><td class="n">%.2f</td></tr></table>'
             % (GBP(p['GRSPRM']), GBP(p['IPTAMT']), p['COMMPC'] / 100.0))
    trn = QA('SELECT * FROM PRMTRN WHERE POLNO=? ORDER BY TRNNO', (polno,))
    b.append('<p><b>PREMIUM TRANSACTIONS</b></p><table><tr><th>TRN</th><th>SFX</th><th>TYPE</th><th>EFFECTIVE</th>'
             '<th>GROSS</th><th>IPT</th><th>COMM</th><th>NET</th><th>FIN REF</th></tr>')
    for t in trn:
        b.append('<tr><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td class="n">%s</td><td class="n">%s</td>'
                 '<td class="n">%s</td><td class="n">%s</td><td>%s</td></tr>'
                 % (t['TRNNO'], t['POLSFX'], t['TRNTYP'], DTSCR(t['EFFDT']), GBP(t['GRSPRM']), GBP(t['IPTAMT']),
                    GBP(t['COMAMT']), GBP(t['NETAMT']), t['FINREF']))
    b.append('</table>')
    end = QA('SELECT * FROM ENDMST WHERE POLNO=? ORDER BY ENDNO', (polno,))
    if end:
        b.append('<p><b>ENDORSEMENTS</b></p><table><tr><th>END</th><th>SFX</th><th>TYPE</th><th>EFFECTIVE</th>'
                 '<th>DETAIL</th><th>PREM ADJ</th></tr>')
        for e in end:
            b.append('<tr><td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td class="n">%s</td></tr>'
                     % (e['ENDNO'], e['POLSFX'], e['ENDTYP'], DTSCR(e['EFFDT']), html.escape(e['DESCR']), GBP(e['PRMADJ'])))
        b.append('</table>')
    b.append('<p><b>ACTIONS</b></p>')
    if p['STATCD'] == 'Q':
        b.append('<form method="post" action="nbbind"><input type="hidden" name="POLNO" value="%s">USER %s '
                 '<input type="submit" value="BIND QUOTE"></form>' % (polno, USRSEL()))
    if p['STATCD'] == 'L':
        b.append('<a href="mtaent?polno=%s">MID TERM ADJUSTMENT</a><br><br>' % polno)
        b.append('<form method="post" action="canent"><input type="hidden" name="POLNO" value="%s">CANCEL FROM '
                 '<input name="EFFDT" size="10" value="%s"> USER %s <input type="submit" value="CANCEL POLICY"></form>'
                 % (polno, DTSCR(SYSDT()), USRSEL()))
        b.append('<form method="post" action="rnwrun"><input type="hidden" name="POLNO" value="%s">RE-KEY CLAIMS 3YR '
                 '<input name="CLMCNT3" size="2" value="%d"> USER %s <input type="submit" value="RENEW"></form>'
                 % (polno, p['CLMCNT3'], USRSEL()))
    return ''.join(b)


@app.get('/poldsp', response_class=HTMLResponse)
def POLDSP(polno: str, msg: str = '', err: str = ''):
    try:
        return PAGE('POLICY DISPLAY', DSPBODY(polno.upper()), msg, err)
    except HeronErr as e:
        return PAGE('POLICY DISPLAY', '', err=str(e))


def QTEFRM(f):
    def v(k, d=''):
        return html.escape(str(f.get(k, d)))
    brk = {r['BRKCD']: r['BRKNAM'] for r in QA("SELECT * FROM BRKMST WHERE STATCD='A' ORDER BY BRKCD")}
    return ('<form method="post" action="nbqte"><table>'
            '<tr><th>PRODUCT</th><td><select name="PRODCD">%s</select></td><th>BROKER</th><td><select name="BRKCD">%s</select></td></tr>'
            '<tr><th>INSURED NAME</th><td><input name="INSNAM" size="34" value="%s"></td><th>OR INSURED NO</th><td><input name="INSNO" size="8" value="%s"></td></tr>'
            '<tr><th>ADDRESS</th><td><input name="ADDR1" size="34" value="%s"></td><th>TOWN</th><td><input name="TOWN" size="18" value="%s"></td></tr>'
            '<tr><th>RISK POSTCODE</th><td><input name="PCODE" size="8" value="%s"></td><th>INCEPTION DD/MM/CCYY</th><td><input name="INCDT" size="10" value="%s"></td></tr>'
            '<tr><th>TRADE</th><td><select name="TRDCD">%s</select></td><th>CONSTRUCTION</th><td><select name="CONSTR">%s</select></td></tr>'
            '<tr><th>SI BUILDINGS</th><td><input name="SIBLD" size="10" value="%s"></td><th>SI CONTENTS</th><td><input name="SICONT" size="10" value="%s"></td></tr>'
            '<tr><th>SI BUS INTERRUPTION</th><td><input name="SIBI" size="10" value="%s"></td><th>VOLUNTARY EXCESS</th><td><input name="VOLXS" size="6" value="%s"></td></tr>'
            '<tr><th>TURNOVER (CL)</th><td><input name="TURNOV" size="10" value="%s"></td><th>EMPLOYEES (CL)</th><td><input name="EMPCNT" size="5" value="%s"></td></tr>'
            '<tr><th>CLAIMS LAST 3 YRS</th><td><input name="CLMCNT3" size="2" value="%s"></td><th>USER</th><td>%s</td></tr>'
            '</table><br><input type="submit" value="CALCULATE QUOTE"></form>'
            % (OPTS(PRDNAM, f.get('PRODCD', 'CP')), OPTS(brk, f.get('BRKCD', '')), v('INSNAM'), v('INSNO'), v('ADDR1'),
               v('TOWN'), v('PCODE'), v('INCDT', DTSCR(SYSDT())), OPTS(TRDNAM, f.get('TRDCD', 'RETL')),
               OPTS(CONNAM, f.get('CONSTR', 1)), v('SIBLD', 0), v('SICONT', 0), v('SIBI', 0), v('VOLXS', 250),
               v('TURNOV', 0), v('EMPCNT', 0), v('CLMCNT3', 0), USRSEL(f.get('USRID', 'CLERK1'))))


@app.get('/nbqte', response_class=HTMLResponse)
def NBQTE_GET():
    return PAGE('NEW BUSINESS QUOTE', QTEFRM({}))


@app.post('/nbqte', response_class=HTMLResponse)
async def NBQTE_POST(request: Request):
    f = await FORM(request)
    try:
        q = NBQTE(f, f.get('USRID', 'CLERK1'))
    except HeronErr as e:
        return PAGE('NEW BUSINESS QUOTE', QTEFRM(f), err=str(e))
    m = 'QUOTE %s  PREMIUM %s  IPT %s  TOTAL %s' % (q['POLNO'], GBP(q['GRSPRM']), GBP(q['IPTAMT']),
                                                   GBP(q['GRSPRM'] + q['IPTAMT']))
    e = ('REFERRED: ' + '; '.join(q['REFRSN'])) if q['REFRSN'] else ''
    return PAGE('POLICY DISPLAY', DSPBODY(q['POLNO']), m, e)


def BACK(polno, msg='', err=''):
    from urllib.parse import quote
    return RedirectResponse('poldsp?polno=%s&msg=%s&err=%s' % (polno, quote(msg), quote(err)), status_code=303)


@app.post('/nbbind')
async def NBBIND_POST(request: Request):
    f = await FORM(request)
    try:
        t = NBBND(f.get('POLNO', ''), f.get('USRID', 'CLERK1'))
        return BACK(f['POLNO'], 'BOUND. TRANSACTION %d WRITTEN' % t['TRNNO'])
    except HeronErr as e:
        return BACK(f.get('POLNO', ''), err=str(e))


@app.get('/mtaent', response_class=HTMLResponse)
def MTAENT_GET(polno: str, err: str = ''):
    try:
        p = GETPOL(polno.upper())
    except HeronErr as e:
        return PAGE('MID TERM ADJUSTMENT', '', err=str(e))
    b = ('<p>POLICY %s / %02d &nbsp; PERIOD %s TO %s &nbsp; ANNUAL PREMIUM %s</p>'
         '<form method="post" action="mtaent"><input type="hidden" name="POLNO" value="%s"><table>'
         '<tr><th>EFFECTIVE DD/MM/CCYY</th><td><input name="EFFDT" size="10" value="%s"></td><th>USER</th><td>%s</td></tr>'
         '<tr><th>TRADE</th><td><select name="TRDCD">%s</select></td><th>CONSTRUCTION</th><td><select name="CONSTR">%s</select></td></tr>'
         '<tr><th>RISK POSTCODE</th><td><input name="PCODE" size="8" value="%s"></td><th>VOLUNTARY EXCESS</th><td><input name="VOLXS" size="6" value="%d"></td></tr>'
         '<tr><th>SI BUILDINGS</th><td><input name="SIBLD" size="10" value="%d"></td><th>SI CONTENTS</th><td><input name="SICONT" size="10" value="%d"></td></tr>'
         '<tr><th>SI BUS INTERRUPTION</th><td><input name="SIBI" size="10" value="%d"></td><th>&nbsp;</th><td>&nbsp;</td></tr>'
         '<tr><th>TURNOVER</th><td><input name="TURNOV" size="10" value="%d"></td><th>EMPLOYEES</th><td><input name="EMPCNT" size="5" value="%d"></td></tr>'
         '</table><br><input type="submit" value="APPLY ADJUSTMENT"></form>'
         % (p['POLNO'], p['POLSFX'], DTSCR(p['INCDT']), DTSCR(p['EXPDT']), GBP(p['GRSPRM']), p['POLNO'],
            DTSCR(SYSDT()), USRSEL(), OPTS(TRDNAM, p['TRDCD']), OPTS(CONNAM, p['CONSTR']), p['PCODE'], p['VOLXS'],
            p['SIBLD'], p['SICONT'], p['SIBI'], p['TURNOV'], p['EMPCNT']))
    return PAGE('MID TERM ADJUSTMENT', b, err=err)


@app.post('/mtaent')
async def MTAENT_POST(request: Request):
    f = await FORM(request)
    polno = f.get('POLNO', '')
    try:
        m = MTAENT(polno, f, f.get('USRID', 'CLERK1'))
        return BACK(polno, 'ENDORSEMENT %d APPLIED. ADJUSTMENT %s OVER %d DAYS' % (m['ENDNO'], GBP(m['PRMADJ']), m['DAYS']))
    except HeronErr as e:
        from urllib.parse import quote
        return RedirectResponse('mtaent?polno=%s&err=%s' % (polno, quote(str(e))), status_code=303)


@app.post('/canent')
async def CANENT_POST(request: Request):
    f = await FORM(request)
    try:
        c = CANENT(f.get('POLNO', ''), f.get('EFFDT', ''), f.get('USRID', 'CLERK1'))
        return BACK(f['POLNO'], 'CANCELLED. RETURN PREMIUM %s' % GBP(c['REFUND']))
    except HeronErr as e:
        return BACK(f.get('POLNO', ''), err=str(e))


@app.post('/rnwrun')
async def RNWRUN_POST(request: Request):
    f = await FORM(request)
    try:
        r = RNWRUN(f.get('POLNO', ''), f.get('USRID', 'CLERK1'), NUM(f.get('CLMCNT3', 0)))
        return BACK(f['POLNO'], 'RENEWED AS TERM %02d. PREMIUM %s (WAS %s)' % (r['POLSFX'], GBP(r['NEWPRM']), GBP(r['OLDPRM'])))
    except HeronErr as e:
        return BACK(f.get('POLNO', ''), err=str(e))


@app.get('/brkenq', response_class=HTMLResponse)
def BRKENQ():
    b = ['<table><tr><th>CODE</th><th>BROKER</th><th>REGION</th><th>COMM PCT</th><th>ST</th><th>FCA REF</th><th>LIVE POLS</th></tr>']
    for r in QA('SELECT B.*, (SELECT COUNT(*) FROM POLMST P WHERE P.BRKCD=B.BRKCD AND P.STATCD=\'L\') AS N '
                'FROM BRKMST B ORDER BY BRKCD'):
        b.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="n">%.2f</td><td>%s</td><td>%s</td><td class="n">%d</td></tr>'
                 % (r['BRKCD'], html.escape(r['BRKNAM']), r['REGION'], r['COMMPC'] / 100.0, r['STATCD'], r['FCAREF'], r['N']))
    b.append('</table>')
    return PAGE('BROKER ENQUIRY', ''.join(b))


@app.get('/rattbl', response_class=HTMLResponse)
def RATTBL_DSP():
    b = ['<table><tr><th>TYPE</th><th>KEY</th><th>VALUE</th><th>DESCRIPTION</th></tr>']
    for r in QA('SELECT * FROM RATTBL ORDER BY RATTYP, RATKEY'):
        b.append('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td>%s</td></tr>'
                 % (r['RATTYP'], r['RATKEY'], r['RATVAL'], html.escape(r['DESCR'])))
    b.append('</table><p>AREA LOADINGS, CLAIMS LOADINGS AND EXCESS DISCOUNTS ARE HELD IN PROGRAM HERON.</p>')
    return PAGE('RATING TABLES', ''.join(b))
