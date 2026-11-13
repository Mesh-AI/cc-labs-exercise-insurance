# HERONDB - DATABASE LOAD/UNLOAD FOR HERON PAS
# -----------------------------------------------------------------------------
# The production Heron database is DB2 on the group mainframe. For development
# we load the nightly CSV extracts in server/data/legacy into SQLite, in
# memory. Anything keyed during a session is lost on restart unless you call
# UNLOAD() to write the extracts back out.
#
# CONVENTIONS (see also the notes at the top of heron.py):
#   dates    integer CCYYMMDD            e.g. 20250301      0 = not set
#   premium  integer pence, signed       e.g. 123456 = GBP 1,234.56
#   sums ins integer whole pounds        e.g. 750000
#   percent  integer, percent x 100      e.g. 2250 = 22.5%
#   postcode upper case, no space        e.g. HU12KV
# -----------------------------------------------------------------------------
import csv
import os
import sqlite3
import threading

LK = threading.RLock()

SCHEMA = {
    'BRKMST': [('BRKCD', 'TEXT'), ('BRKNAM', 'TEXT'), ('REGION', 'TEXT'), ('COMMPC', 'INT'),
               ('STATCD', 'TEXT'), ('FCAREF', 'TEXT')],
    'INSMST': [('INSNO', 'INT'), ('INSNAM', 'TEXT'), ('ADDR1', 'TEXT'), ('TOWN', 'TEXT'),
               ('PCODE', 'TEXT'), ('TRDCD', 'TEXT'), ('ESTYR', 'INT'), ('COMPNO', 'TEXT')],
    'POLMST': [('POLNO', 'TEXT'), ('POLSFX', 'INT'), ('PRODCD', 'TEXT'), ('INSNO', 'INT'),
               ('BRKCD', 'TEXT'), ('INCDT', 'INT'), ('EXPDT', 'INT'), ('STATCD', 'TEXT'),
               ('TRDCD', 'TEXT'), ('PCODE', 'TEXT'), ('CONSTR', 'INT'), ('SIBLD', 'INT'),
               ('SICONT', 'INT'), ('SIBI', 'INT'), ('TURNOV', 'INT'), ('EMPCNT', 'INT'),
               ('VOLXS', 'INT'), ('CLMCNT3', 'INT'), ('CLMCUR', 'TEXT'), ('GRSPRM', 'INT'),
               ('IPTAMT', 'INT'), ('COMMPC', 'INT'), ('UWREF', 'TEXT'), ('CANDT', 'INT'),
               ('USRID', 'TEXT'), ('CRTDT', 'INT'), ('UPDDT', 'INT')],
    'PRMTRN': [('TRNNO', 'INT'), ('POLNO', 'TEXT'), ('POLSFX', 'INT'), ('TRNTYP', 'TEXT'),
               ('EFFDT', 'INT'), ('GRSPRM', 'INT'), ('IPTAMT', 'INT'), ('COMAMT', 'INT'),
               ('NETAMT', 'INT'), ('FINREF', 'TEXT'), ('CRTDT', 'INT')],
    'ENDMST': [('ENDNO', 'INT'), ('POLNO', 'TEXT'), ('POLSFX', 'INT'), ('ENDTYP', 'TEXT'),
               ('EFFDT', 'INT'), ('DESCR', 'TEXT'), ('PRMADJ', 'INT'), ('CRTDT', 'INT')],
    'RATTBL': [('RATTYP', 'TEXT'), ('RATKEY', 'TEXT'), ('RATVAL', 'TEXT'), ('DESCR', 'TEXT')],
}

_ORDER = {'BRKMST': 'BRKCD', 'INSMST': 'INSNO', 'POLMST': 'SUBSTR(POLNO, 4), POLSFX',
          'PRMTRN': 'TRNNO', 'ENDMST': 'ENDNO', 'RATTBL': 'RATTYP, RATKEY'}


def EMPTYDB():
    """An empty database with the Heron tables and no rows."""
    cn = sqlite3.connect(':memory:', check_same_thread=False)
    cn.row_factory = sqlite3.Row
    for tbl, cols in SCHEMA.items():
        cn.execute('CREATE TABLE %s (%s)' % (tbl, ', '.join('%s %s' % c for c in cols)))
    cn.execute('CREATE INDEX IX_POL ON POLMST (POLNO, POLSFX)')
    cn.execute('CREATE INDEX IX_TRN ON PRMTRN (POLNO, POLSFX)')
    cn.execute('CREATE INDEX IX_END ON ENDMST (POLNO, POLSFX)')
    cn.commit()
    return cn


def LOADTBL(cn, tbl, datdir):
    """Load one CSV extract into its table. Missing file = empty table."""
    cols = SCHEMA[tbl]
    fn = os.path.join(datdir, tbl + '.csv')
    if not os.path.exists(fn):
        return 0
    n = 0
    with open(fn, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            vals = []
            for c, t in cols:
                v = r.get(c, '')
                vals.append(int(v or 0) if t == 'INT' else (v or ''))
            cn.execute('INSERT INTO %s VALUES (%s)' % (tbl, ','.join('?' * len(cols))), vals)
            n += 1
    return n


def OPENDB(datdir):
    """Build an in-memory database from the CSV extracts in datdir."""
    cn = EMPTYDB()
    for tbl in SCHEMA:
        LOADTBL(cn, tbl, datdir)
    cn.commit()
    return cn


def UNLOAD(cn, datdir):
    """Write every table back out as a CSV extract (same layout OPENDB reads)."""
    os.makedirs(datdir, exist_ok=True)
    for tbl, cols in SCHEMA.items():
        with open(os.path.join(datdir, tbl + '.csv'), 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh, lineterminator='\n')
            w.writerow([c for c, _ in cols])
            for r in cn.execute('SELECT * FROM %s ORDER BY %s' % (tbl, _ORDER[tbl])):
                w.writerow(list(r))
