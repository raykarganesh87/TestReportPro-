"""LabReport Pro - core: database, safe formula engine, default test library."""
import ast, contextlib, hashlib, json, math, operator, os, re, secrets, shutil, sqlite3, sys, datetime
from decimal import Decimal, ROUND_HALF_UP


def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Where the database lives.
    - a 'LabData' folder beside the program (portable use / older versions) is used if it exists;
    - the installed Windows version keeps data in C:\\ProgramData\\LabReportPro\\LabData (shared by all PC users, survives uninstall/upgrade)."""
    legacy = os.path.join(app_dir(), 'LabData')
    if os.path.isdir(legacy):
        return legacy
    pd = os.environ.get('PROGRAMDATA')
    if getattr(sys, 'frozen', False) and sys.platform.startswith('win') and pd:
        return os.path.join(pd, 'LabReportPro', 'LabData')
    return legacy


DATA_DIR = data_dir()
DB_PATH = os.path.join(DATA_DIR, 'labdata.db')
REPORT_DIR = os.path.join(DATA_DIR, 'Reports')
BACKUP_DIR = os.path.join(DATA_DIR, 'Backups')

# ------------------------------------------------------------------ formula engine
class Blank(Exception):
    pass


def _vals(args):
    v = [a for a in args if a is not None and a != '']
    if not v:
        raise Blank
    return v


def _need(x):
    if x is None or x == '':
        raise Blank
    return x


FUNCS = {
    'avg': lambda *a: sum(_vals(a)) / len(_vals(a)),
    'sum': lambda *a: sum(_vals(a)),
    'min': lambda *a: min(_vals(a)),
    'max': lambda *a: max(_vals(a)),
    'abs': lambda x: abs(_need(x)),
    'sqrt': lambda x: math.sqrt(_need(x)),
    'ln': lambda x: math.log(_need(x)),
    'log10': lambda x: math.log10(_need(x)),
    'round': lambda x, n=0: round(_need(x), int(n)),
    'blank': lambda x: x is None or x == '',
    'iff': lambda c, a, b: a if c else b,
}
CONSTS = {'pi': math.pi, 'e': math.e}
BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.Pow: operator.pow, ast.Mod: operator.mod}
CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
       ast.Eq: operator.eq, ast.NotEq: operator.ne}


def parse_expr(expr):
    return ast.parse(expr.strip().lstrip('='), mode='eval')


def expr_names(expr):
    """names used by an expression (raises SyntaxError for bad syntax)"""
    return {n.id for n in ast.walk(parse_expr(expr)) if isinstance(n, ast.Name)} - set(FUNCS) - set(CONSTS)


def safe_eval(expr, names):
    """Evaluate an arithmetic expression. Returns None when any needed value is blank / invalid."""
    try:
        tree = parse_expr(expr)
    except SyntaxError:
        return None

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in CONSTS:
                return CONSTS[n.id]
            return names.get(n.id)
        if isinstance(n, ast.BinOp) and type(n.op) in BIN:
            a, b = ev(n.left), ev(n.right)
            if a in (None, '') or b in (None, ''):
                raise Blank
            return BIN[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp):
            a = ev(n.operand)
            if a in (None, ''):
                raise Blank
            return -a if isinstance(n.op, ast.USub) else a
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, comp in zip(n.ops, n.comparators):
                right = ev(comp)
                if left in (None, '') or right in (None, ''):
                    raise Blank
                if not CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.IfExp):
            return ev(n.body) if ev(n.test) else ev(n.orelse)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
            return FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError('not allowed')

    try:
        r = ev(tree)
        if isinstance(r, float) and (math.isnan(r) or math.isinf(r)):
            return None
        return r
    except (Blank, ZeroDivisionError, TypeError, ValueError, OverflowError):
        return None


def to_num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(',', '')
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fmt(v, dec):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'Yes' if v else 'No'
    if isinstance(v, str):
        return v
    try:
        d = Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-int(dec)), rounding=ROUND_HALF_UP)
        return format(d, 'f')
    except Exception:
        return str(v)


def compute_job(tests, typed):
    """tests: list of dicts (with 'fields' and 'calcs'); typed: {(test_id,key): raw string}.
    returns {test_id: {'inputs':{key:value}, 'auto':{key:bool}, 'calcs':{key:value}, 'result':value}}"""
    G = {}
    out = {}
    for _ in range(4):                       # several passes so forward references settle
        out = {}
        for t in tests:
            code = t['code']
            local = {}
            res = {'inputs': {}, 'auto': {}, 'calcs': {}, 'result': None}
            for f in t['fields']:
                raw = typed.get((t['id'], f['key']))
                if f['kind'] == 'text':
                    val = raw.strip() if raw and raw.strip() else None
                else:
                    val = to_num(raw)
                auto = False
                if val is None and f['default_expr']:
                    names = dict(G); names.update(local)
                    val = safe_eval(f['default_expr'], names)
                    auto = val is not None
                local[f['key']] = val
                G[f'{code}_{f["key"]}'] = val
                res['inputs'][f['key']] = val
                res['auto'][f['key']] = auto
            for c in t['calcs']:
                names = dict(G); names.update(local)
                v = safe_eval(c['expr'], names)
                local[c['key']] = v
                G[f'{code}_{c["key"]}'] = v
                res['calcs'][c['key']] = v
                if c['is_result']:
                    res['result'] = v
                    G[f'{code}_result'] = v
            out[t['id']] = res
    return out


def guess_conc(label):
    """Normality / Molarity input fields are detected from the label ('N' / 'M' / '')."""
    l = (label or '').lower()
    if 'normality' in l or re.search(r'\(n\)', l):
        return 'N'
    if 'molarity' in l or re.search(r'\(m\)', l) or 'concentration of edta' in l:
        return 'M'
    return ''


def guess_reagent(label):
    m = re.search(r'\bof\s+(.*)$', label or '', re.I)
    r = (m.group(1) if m else label or '').strip()
    r = re.sub(r'\s*\([^)]*\)', '', r)
    r = re.sub(r'^[\d.]+\s*[NM]\s+', '', r)
    return r.strip() or (label or '')


def _iso(x):
    try:
        return datetime.datetime.strptime(x, '%Y-%m-%d').date()
    except Exception:
        return None


def check_dates(receipt, start, end, report):
    """All arguments are ISO strings ('' when empty). Rule: receipt <= test start <= test completion <= report date."""
    chain = [('Date of Receipt', receipt), ('Test Start Date', start), ('Test Completion Date', end), ('Report Date', report)]
    errs, ok = [], []
    for name, v in chain:
        if not v:
            continue
        d = _iso(v)
        if d is None:
            errs.append(f'{name} is not a valid date (use dd-mm-yyyy).')
        else:
            ok.append((name, d))
    for j in range(1, len(ok)):
        prev = max(ok[:j], key=lambda t: t[1])
        if ok[j][1] < prev[1]:
            errs.append(f'{ok[j][0]} ({d_show(ok[j][1].isoformat())}) cannot be before {prev[0]} ({d_show(prev[1].isoformat())}).')
    return errs


# ------------------------------------------------------------------ users, permissions
SECTIONS = [('jobs', 'Jobs / Reports', ['view', 'add', 'edit', 'delete']),
            ('library', 'Test Library', ['view', 'add', 'edit', 'delete']),
            ('equipment', 'Equipment & Logbook', ['view', 'add', 'edit', 'delete']),
            ('standard', 'Chemical Standardization Record', ['view', 'add', 'edit', 'delete']),
            ('settings', 'Settings & Backup', ['view', 'edit']),
            ('users', 'Users & Permissions', ['view', 'add', 'edit', 'delete']),
            ('audit', 'Audit Trail', ['view'])]
SECTION_NAME = {k: n for k, n, _ in SECTIONS}
ALL_PERMS = {k: list(a) for k, _, a in SECTIONS}
ROLE_TEMPLATES = {
    'Administrator': ALL_PERMS,
    'Analyst': {'jobs': ['view', 'add', 'edit'], 'library': ['view'], 'equipment': ['view', 'add'], 'standard': ['view', 'add', 'edit']},
    'Reviewer': {'jobs': ['view'], 'library': ['view'], 'equipment': ['view'], 'standard': ['view'], 'audit': ['view']},
    'Viewer': {'jobs': ['view']},
    'Custom': {}}
MAX_FAILED = 5


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), 200_000).hex()


def check_password_policy(pw):
    if len(pw or '') < 8:
        return 'Password must be at least 8 characters.'
    if not re.search(r'[A-Za-z]', pw) or not re.search(r'\d', pw):
        return 'Password must contain letters and digits.'
    return ''


def _chg(field, old, new):
    return {'field': field, 'old': '' if old is None else str(old), 'new': '' if new is None else str(new)}


def _diff(old, new, labels=None):
    out = []
    for k in new:
        o, n = (old or {}).get(k), new.get(k)
        if str(o if o is not None else '') != str(n if n is not None else ''):
            out.append(_chg((labels or {}).get(k, k), o, n))
    return out


# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY, name TEXT UNIQUE, spec TEXT, page_titles TEXT, group_name TEXT);
CREATE TABLE IF NOT EXISTS tests(id INTEGER PRIMARY KEY, material_id INTEGER, code TEXT, name TEXT, method TEXT, unit TEXT,
  limit_text TEXT, decimals INTEGER, page INTEGER, in_report INTEGER, sort INTEGER, report_name TEXT, equip_hint TEXT);
CREATE TABLE IF NOT EXISTS fields(id INTEGER PRIMARY KEY, test_id INTEGER, key TEXT, label TEXT, unit TEXT, kind TEXT,
  default_expr TEXT, sort INTEGER);
CREATE TABLE IF NOT EXISTS calcs(id INTEGER PRIMARY KEY, test_id INTEGER, key TEXT, label TEXT, expr TEXT, decimals INTEGER,
  is_result INTEGER, sort INTEGER);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, report_no TEXT UNIQUE, ulr TEXT, report_date TEXT, material_id INTEGER,
  customer TEXT, address TEXT, agency TEXT, work TEXT, material_ident TEXT, ref1 TEXT, ref2 TEXT, job_no TEXT, work_order TEXT,
  client_id TEXT, receipt_date TEXT, start_date TEXT, end_date TEXT, temp TEXT, rh TEXT, assigned_to TEXT, reviewer TEXT,
  analysed_by TEXT, verified_by TEXT, analysis_date TEXT, remarks TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS job_values(job_id INTEGER, test_id INTEGER, key TEXT, value TEXT, PRIMARY KEY(job_id,test_id,key));
CREATE TABLE IF NOT EXISTS equipment(id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, make_model TEXT, location TEXT, calib_due TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS test_equipment(test_id INTEGER, equipment_id INTEGER, PRIMARY KEY(test_id,equipment_id));
CREATE TABLE IF NOT EXISTS job_equipment(job_id INTEGER, test_id INTEGER, equipment_id INTEGER, PRIMARY KEY(job_id,test_id,equipment_id));
CREATE TABLE IF NOT EXISTS logbook(id INTEGER PRIMARY KEY, log_date TEXT, equipment_id INTEGER, job_id INTEGER, test_id INTEGER,
  report_no TEXT, job_no TEXT, test_name TEXT, analyst TEXT, remarks TEXT, auto INTEGER);
CREATE TABLE IF NOT EXISTS std_records(id INTEGER PRIMARY KEY, std_date TEXT, reagent TEXT, conc_type TEXT, value REAL, nominal TEXT,
  against TEXT, n_std REAL, v_std REAL, v_tit REAL, analyst TEXT, remarks TEXT, auto INTEGER);
CREATE TABLE IF NOT EXISTS std_links(std_id INTEGER, job_id INTEGER, test_id INTEGER, PRIMARY KEY(std_id,job_id,test_id));
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, full_name TEXT, salt TEXT, pw_hash TEXT, role TEXT, perms TEXT,
  active INTEGER DEFAULT 1, must_change INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, locked INTEGER DEFAULT 0, created TEXT, last_login TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, section TEXT, action TEXT, ref TEXT, details TEXT, prev_hash TEXT, hash TEXT);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'Audit trail is read-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'Audit trail is read-only'); END;
"""

JOB_FIELDS = [  # column, label, kind
    ('report_no', 'Report No.', 't'), ('ulr', 'ULR No.', 't'), ('report_date', 'Report Date', 'd'),
    ('customer', 'Customer Name', 't'), ('address', 'Address', 't'), ('agency', 'Name of Agency', 't'),
    ('work', 'Name of Work', 'm'), ('material_ident', 'Material Identification', 'm'),
    ('ref1', 'Reference Letter No. (1)', 't'), ('ref2', 'Reference Letter No. (2)', 't'),
    ('job_no', 'Job No.', 't'), ('work_order', 'Work Order No.', 't'), ('client_id', 'Client ID No.', 't'),
    ('receipt_date', 'Date of Receipt', 'd'), ('start_date', 'Test Start Date', 'd'), ('end_date', 'Test Completion Date', 'd'),
    ('temp', 'Temperature (°C)', 't'), ('rh', 'Relative Humidity (%)', 't'), ('assigned_to', 'Job Assigned To', 't'),
    ('reviewer', 'Reviewed & Authorised By', 't')]

DEFAULT_SETTINGS = {
    'lab_name': 'Civil Tech India Pvt. Ltd.',
    'location': 'Plot No. B-45, Satpur MIDC, NICE Area, Nashik-422007, Maharashtra.',
    'letterhead_mm': '35',
    'credit_on_reports': '0',
    'logo_on_obs': '1',
    'logo_on_reports': '0',
    'reviewers': 'Vitthal Nerkar\nGanesh Raykar',
    'analysts': 'Rahul',
    'notes': ('The reported results are related to the sample provided by the client & valid at environment condition in which test performed.\n'
              'Report shall not be reproduced except in full without prior written Permission of Civil Tech.\n'
              'Any correction invalidates this test report.\n'
              'This report is invalid without paper seal of Civil Tech India Pvt. Ltd.'),
}


class DB:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.makedirs(REPORT_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self.path = path
        self.user = None; self.system = False; self.quiet = False
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        cols = {r[1] for r in self.c.execute('PRAGMA table_info(fields)')}
        for col in ('conc', 'reagent'):                     # databases created by older versions
            if col not in cols:
                self.c.execute(f'ALTER TABLE fields ADD COLUMN {col} TEXT')
        tcols = {r[1] for r in self.c.execute('PRAGMA table_info(tests)')}
        if 'equip_hint' not in tcols:
            self.c.execute('ALTER TABLE tests ADD COLUMN equip_hint TEXT')
        ucols = {r[1] for r in self.c.execute('PRAGMA table_info(users)')}
        for col in ('recovery_salt', 'recovery_hash'):
            if col not in ucols:
                self.c.execute(f'ALTER TABLE users ADD COLUMN {col} TEXT')
        for r in self.c.execute('SELECT id,label FROM fields WHERE conc IS NULL').fetchall():
            g = guess_conc(r['label'])
            self.c.execute('UPDATE fields SET conc=?, reagent=? WHERE id=?', (g, guess_reagent(r['label']) if g else '', r['id']))
        for k, v in DEFAULT_SETTINGS.items():
            self.c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)', (k, v))
        self.c.commit()
        if not self.c.execute('SELECT 1 FROM materials').fetchone():
            from seed import seed_library
            with self.as_system(quiet=True):
                seed_library(self)
        self._add_lab_library()

    def _add_lab_library(self):
        """Adds the materials / tests from the lab's combined observation sheet - once per database (never re-adds what you delete)."""
        if self.c.execute("SELECT value FROM settings WHERE key='lab_library_v1'").fetchone():
            return
        from seed_lab import seed_lab_library
        with self.as_system(quiet=True):
            added = seed_lab_library(self)
        self.c.execute("INSERT OR REPLACE INTO settings VALUES('lab_library_v1','1')"); self.c.commit()
        if added:
            self.audit('library', 'create', 'Library update (observation sheets)', [_chg('Materials added', '', ', '.join(added))], actor='SYSTEM')

    # ---- permissions / audit infrastructure
    @contextlib.contextmanager
    def as_system(self, quiet=False):
        old = (self.system, self.quiet); self.system = True; self.quiet = quiet or self.quiet
        try:
            yield
        finally:
            self.system, self.quiet = old

    def can(self, section, action):
        if self.system:
            return True
        u = self.user
        if not u:
            return False
        if u['role'] == 'Administrator':
            return True
        return action in json.loads(u['perms'] or '{}').get(section, [])

    def require(self, section, action):
        if not self.can(section, action):
            raise PermissionError(f'You are not authorised to {action} in "{SECTION_NAME.get(section, section)}".\nPlease ask the Administrator.')

    def _last_hash(self):
        r = self.c.execute('SELECT hash FROM audit ORDER BY id DESC LIMIT 1').fetchone()
        return r[0] if r else ''

    def audit(self, section, action, ref='', details=None, actor=None):
        """Tamper-evident audit trail: date, time, user, section, action, record and field-level old/new values."""
        if self.quiet:
            return
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = actor or (self.user['username'] if self.user else 'SYSTEM')
        det = json.dumps(details or [], ensure_ascii=False)
        prev = self._last_hash()
        h = hashlib.sha256('|'.join([prev, ts, user, section, action, ref or '', det]).encode('utf-8')).hexdigest()
        self.c.execute('INSERT INTO audit(ts,user,section,action,ref,details,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)', (ts, user, section, action, ref or '', det, prev, h))
        n = self.c.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
        self.c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', ('audit_head', f'{n}:{h}'))
        self.c.commit()

    def audit_rows(self, dfrom='', dto='', user='', section='', text=''):
        q = 'SELECT * FROM audit WHERE 1=1 '; a = []
        if dfrom:
            q += 'AND substr(ts,1,10)>=? '; a.append(dfrom)
        if dto:
            q += 'AND substr(ts,1,10)<=? '; a.append(dto)
        if user:
            q += 'AND user=? '; a.append(user)
        if section:
            q += 'AND section=? '; a.append(section)
        if text:
            q += 'AND (ref LIKE ? OR details LIKE ? OR action LIKE ?) '; a += [f'%{text}%'] * 3
        return [dict(r) for r in self.c.execute(q + 'ORDER BY id DESC', a)]

    def verify_audit(self):
        prev = ''; n = 0
        for r in self.c.execute('SELECT * FROM audit ORDER BY id'):
            h = hashlib.sha256('|'.join([prev, r['ts'], r['user'], r['section'], r['action'], r['ref'] or '', r['details']]).encode('utf-8')).hexdigest()
            if r['prev_hash'] != prev or r['hash'] != h:
                return False, f'Audit trail altered at entry no. {r["id"]} ({r["ts"]}).'
            prev = h; n += 1
        head = self.c.execute("SELECT value FROM settings WHERE key='audit_head'").fetchone()
        if head and head[0] != f'{n}:{prev}' and not (n == 0 and not head[0]):
            return False, 'Audit trail has missing or added entries at the end (does not match the recorded total).'
        return True, f'Audit trail intact - {n} entries verified.'

    # ---- users
    def has_users(self):
        return self.c.execute('SELECT 1 FROM users').fetchone() is not None

    def users(self):
        return [dict(r) for r in self.c.execute('SELECT id,username,full_name,role,perms,active,must_change,failed,locked,created,last_login FROM users ORDER BY username')]

    def _admins(self):
        return self.c.execute("SELECT COUNT(*) FROM users WHERE role='Administrator' AND active=1 AND locked=0").fetchone()[0]

    def create_user(self, username, full_name, password, role, perms, must_change=True):
        if self.has_users() or self.user:
            self.require('users', 'add')
        username = (username or '').strip()
        if not re.match(r'^[A-Za-z0-9._-]{3,30}$', username):
            raise ValueError('User name: 3-30 characters (letters, digits, . _ -).')
        msg = check_password_policy(password)
        if msg:
            raise ValueError(msg)
        if self.c.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)', (username,)).fetchone():
            raise ValueError('This user name already exists.')
        salt, h = hash_pw(password)
        perms = ALL_PERMS if role == 'Administrator' else perms
        self.c.execute('INSERT INTO users(username,full_name,salt,pw_hash,role,perms,active,must_change,created) VALUES(?,?,?,?,?,?,1,?,?)',
                       (username, full_name.strip(), salt, h, role, json.dumps(perms), 1 if must_change else 0, datetime.datetime.now().isoformat(timespec='seconds')))
        self.c.commit()
        self.audit('users', 'create', username, [_chg('Role', '', role), _chg('Name', '', full_name),
                                                 _chg('Permissions', '', self.perm_text(perms, role))])
        if role == 'Administrator':
            return self._make_recovery(username)
        return None

    @staticmethod
    def perm_text(perms, role=''):
        if role == 'Administrator':
            return 'ALL'
        return '; '.join(f"{SECTION_NAME[k]}: {'/'.join(v)}" for k, v in (perms or {}).items() if v and k in SECTION_NAME) or 'none'

    def update_user(self, uid, full_name, role, perms, active):
        self.require('users', 'edit')
        old = dict(self.c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
        if uid == (self.user or {}).get('id') and (not active or role != 'Administrator' and old['role'] == 'Administrator'):
            raise ValueError('You cannot disable or demote your own account.')
        if old['role'] == 'Administrator' and (role != 'Administrator' or not active) and self._admins() <= 1:
            raise ValueError('At least one active Administrator is required.')
        perms = ALL_PERMS if role == 'Administrator' else perms
        self.c.execute('UPDATE users SET full_name=?,role=?,perms=?,active=? WHERE id=?', (full_name.strip(), role, json.dumps(perms), 1 if active else 0, uid))
        self.c.commit()
        det = []
        if old['full_name'] != full_name.strip(): det.append(_chg('Name', old['full_name'], full_name.strip()))
        if old['role'] != role: det.append(_chg('Role', old['role'], role))
        if json.loads(old['perms'] or '{}') != perms or old['role'] != role:
            det.append(_chg('Permissions', self.perm_text(json.loads(old['perms'] or '{}'), old['role']), self.perm_text(perms, role)))
        if bool(old['active']) != bool(active): det.append(_chg('Active', 'Yes' if old['active'] else 'No', 'Yes' if active else 'No'))
        self.audit('users', 'edit', old['username'], det)

    def reset_password(self, uid, new_pw):
        self.require('users', 'edit')
        msg = check_password_policy(new_pw)
        if msg:
            raise ValueError(msg)
        u = dict(self.c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
        salt, h = hash_pw(new_pw)
        self.c.execute('UPDATE users SET salt=?,pw_hash=?,must_change=1,failed=0,locked=0 WHERE id=?', (salt, h, uid)); self.c.commit()
        self.audit('users', 'password reset', u['username'], [_chg('Password', '', 'reset by administrator (must change at next login)')])

    def unlock_user(self, uid):
        self.require('users', 'edit')
        u = dict(self.c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
        self.c.execute('UPDATE users SET failed=0,locked=0 WHERE id=?', (uid,)); self.c.commit()
        self.audit('users', 'unlock', u['username'], [_chg('Locked', 'Yes' if u['locked'] else 'No', 'No')])

    def delete_user(self, uid):
        self.require('users', 'delete')
        u = dict(self.c.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
        if uid == (self.user or {}).get('id'):
            raise ValueError('You cannot delete your own account.')
        if u['role'] == 'Administrator' and self._admins() <= 1:
            raise ValueError('At least one active Administrator is required.')
        self.c.execute('DELETE FROM users WHERE id=?', (uid,)); self.c.commit()
        self.audit('users', 'delete', u['username'], [_chg('Role', u['role'], '')])

    # ---- recovery code (for a forgotten Administrator password)
    def _make_recovery(self, username):
        raw = secrets.token_hex(8).upper()                      # 16 characters
        code = '-'.join(raw[i:i + 4] for i in range(0, 16, 4))
        salt, h = hash_pw(code.replace('-', ''))
        self.c.execute('UPDATE users SET recovery_salt=?, recovery_hash=? WHERE lower(username)=lower(?)', (salt, h, username)); self.c.commit()
        return code

    def new_recovery_code(self):
        """The logged-in Administrator creates a fresh recovery code for their own account (shown once)."""
        u = self.user
        if not u or u['role'] != 'Administrator':
            raise PermissionError('Only an Administrator has a recovery code.')
        code = self._make_recovery(u['username'])
        self.audit('security', 'recovery code', u['username'], [_chg('Recovery code', '', 'new code generated')])
        return code

    def recover_password(self, username, code, new_pw):
        """Forgot password: Administrator accounts can be reset with the recovery code. Returns the NEW recovery code."""
        r = self.c.execute('SELECT * FROM users WHERE lower(username)=lower(?)', ((username or '').strip(),)).fetchone()
        u = dict(r) if r else None
        bad = 'User name or recovery code is not correct. (Only Administrator accounts have a recovery code - other users should ask the Administrator.)'
        if not u or u['role'] != 'Administrator' or not u.get('recovery_hash'):
            self.audit('security', 'recovery failed', username or '', [_chg('Reason', '', 'unknown user / no recovery code')], actor=username or 'unknown')
            raise ValueError(bad)
        _, h = hash_pw((code or '').replace('-', '').replace(' ', '').upper(), u['recovery_salt'])
        if h != u['recovery_hash']:
            self.audit('security', 'recovery failed', u['username'], [_chg('Reason', '', 'wrong recovery code')], actor=u['username'])
            raise ValueError(bad)
        msg = check_password_policy(new_pw)
        if msg:
            raise ValueError(msg)
        salt, nh = hash_pw(new_pw)
        self.c.execute('UPDATE users SET salt=?,pw_hash=?,must_change=0,failed=0,locked=0,active=1 WHERE id=?', (salt, nh, u['id'])); self.c.commit()
        self.audit('security', 'password reset', u['username'], [_chg('Password', '', 'reset with recovery code')], actor=u['username'])
        return self._make_recovery(u['username'])

    def login(self, username, password):
        r = self.c.execute('SELECT * FROM users WHERE lower(username)=lower(?)', ((username or '').strip(),)).fetchone()
        if not r:
            self.audit('security', 'login failed', username or '', [_chg('Reason', '', 'unknown user')], actor=username or 'unknown')
            return None, 'Invalid user name or password.'
        u = dict(r)
        if not u['active']:
            return None, 'This account is disabled. Contact the Administrator.'
        if u['locked']:
            return None, 'Account locked after repeated wrong passwords. Ask the Administrator to unlock it.'
        _, h = hash_pw(password or '', u['salt'])
        if h != u['pw_hash']:
            f = u['failed'] + 1
            lock = 1 if f >= MAX_FAILED else 0
            self.c.execute('UPDATE users SET failed=?,locked=? WHERE id=?', (f, lock, u['id'])); self.c.commit()
            self.audit('security', 'login failed', u['username'], [_chg('Reason', '', f'wrong password ({f}/{MAX_FAILED})' + (' - ACCOUNT LOCKED' if lock else ''))], actor=u['username'])
            return None, ('Account locked after repeated wrong passwords.' if lock else f'Invalid user name or password. ({MAX_FAILED - f} attempts left)')
        now = datetime.datetime.now().isoformat(timespec='seconds')
        self.c.execute('UPDATE users SET failed=0,last_login=? WHERE id=?', (now, u['id'])); self.c.commit()
        u['last_login'] = now; self.user = u
        self.audit('security', 'login', u['username'], [])
        return u, ''

    def logout(self):
        if self.user:
            self.audit('security', 'logout', self.user['username'], [])
        self.user = None

    def change_password(self, old_pw, new_pw):
        u = self.user
        if not u:
            raise PermissionError('Not logged in.')
        _, h = hash_pw(old_pw or '', u['salt'])
        if h != u['pw_hash']:
            raise ValueError('Current password is wrong.')
        msg = check_password_policy(new_pw)
        if msg:
            raise ValueError(msg)
        if new_pw == old_pw:
            raise ValueError('New password must be different.')
        salt, nh = hash_pw(new_pw)
        self.c.execute('UPDATE users SET salt=?,pw_hash=?,must_change=0 WHERE id=?', (salt, nh, u['id'])); self.c.commit()
        u.update(salt=salt, pw_hash=nh, must_change=0)
        self.audit('users', 'password change', u['username'], [_chg('Password', '', 'changed by user')])

    def log_export(self, section, ref, what):
        self.audit(section, 'export', ref, [_chg('Output', '', what)])

    # ---- settings
    def setting(self, k):
        r = self.c.execute('SELECT value FROM settings WHERE key=?', (k,)).fetchone()
        return r[0] if r else DEFAULT_SETTINGS.get(k, '')

    def set_setting(self, k, v):
        self.require('settings', 'edit')
        old = self.setting(k)
        self.c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (k, v)); self.c.commit()
        if str(old) != str(v):
            self.audit('settings', 'edit', k, [_chg(k, old, v)])

    # ---- library
    def materials(self):
        return [dict(r) for r in self.c.execute('SELECT * FROM materials ORDER BY group_name, name')]

    def material(self, mid):
        r = self.c.execute('SELECT * FROM materials WHERE id=?', (mid,)).fetchone()
        return dict(r) if r else None

    def add_material(self, name, spec='', group='', page_titles=None):
        self.require('library', 'add')
        cur = self.c.execute('INSERT INTO materials(name,spec,page_titles,group_name) VALUES(?,?,?,?)',
                             (name, spec, json.dumps(page_titles or {'1': 'TEST ANALYSIS'}), group))
        self.c.commit()
        self.audit('library', 'create', f'Material: {name}', [_chg('Limits as per', '', spec), _chg('Group', '', group)])
        return cur.lastrowid

    def update_material(self, mid, name, spec, group, page_titles):
        self.require('library', 'edit')
        old = self.material(mid)
        self.c.execute('UPDATE materials SET name=?,spec=?,group_name=?,page_titles=? WHERE id=?',
                       (name, spec, group, json.dumps(page_titles), mid)); self.c.commit()
        det = _diff({'Name': old['name'], 'Limits as per': old['spec'], 'Group': old['group_name'], 'Report page titles': old['page_titles']},
                    {'Name': name, 'Limits as per': spec, 'Group': group, 'Report page titles': json.dumps(page_titles)})
        self.audit('library', 'edit', f"Material: {old['name']}", det)

    def delete_material(self, mid):
        self.require('library', 'delete')
        m = self.material(mid); n = len(self.tests(mid, full=False))
        with self.as_system(quiet=True):
            for t in self.tests(mid, full=False):
                self.delete_test(t['id'])
        self.c.execute('DELETE FROM materials WHERE id=?', (mid,)); self.c.commit()
        self.audit('library', 'delete', f"Material: {m['name']}", [_chg('Tests removed', '', n)])

    def tests(self, mid, full=True):
        ts = [dict(r) for r in self.c.execute('SELECT * FROM tests WHERE material_id=? ORDER BY sort,id', (mid,))]
        if full:
            for t in ts:
                t['fields'] = [dict(r) for r in self.c.execute('SELECT * FROM fields WHERE test_id=? ORDER BY sort,id', (t['id'],))]
                t['calcs'] = [dict(r) for r in self.c.execute('SELECT * FROM calcs WHERE test_id=? ORDER BY sort,id', (t['id'],))]
                t['equipment_ids'] = self.test_equipment(t['id'])
        return ts

    def _test_snapshot(self, t):
        snap = {'Code': t.get('code'), 'Name': t.get('name'), 'Report name': t.get('report_name'), 'Method': t.get('method'), 'Unit': t.get('unit'),
                'Limit': t.get('limit_text'), 'Equipment types': t.get('equip_hint') or '', 'Decimals': t.get('decimals'), 'Report page': t.get('page'), 'In report': 'Yes' if t.get('in_report') else 'No'}
        for f in t.get('fields', []):
            snap['Field ' + f['key']] = f"{f['label']} | unit {f.get('unit', '')} | {f.get('kind', 'number')} | default {f.get('default_expr', '')} | conc {f.get('conc') or ''} {f.get('reagent') or ''}"
        for c in t.get('calcs', []):
            snap['Calc ' + c['key']] = f"{c['label']} | {c['expr']} | dec {c.get('decimals', 2)} | {'RESULT' if c.get('is_result') else ''}"
        eq = {e['id']: e['code'] for e in self.equipment()}
        if t.get('equipment_ids') is not None:
            snap['Equipment'] = ', '.join(sorted(eq.get(i, str(i)) for i in t['equipment_ids']))
        return snap

    def save_test(self, mid, t):
        """t: dict with optional id, plus fields[], calcs[]"""
        self.require('library', 'edit' if t.get('id') else 'add')
        mname = (self.material(mid) or {}).get('name', '')
        old = None
        if t.get('id'):
            row = [x for x in self.tests(mid) if x['id'] == t['id']]
            old = self._test_snapshot(row[0]) if row else None
        if t.get('id'):
            self.c.execute('UPDATE tests SET code=?,name=?,method=?,unit=?,limit_text=?,decimals=?,page=?,in_report=?,sort=?,report_name=?,equip_hint=? WHERE id=?',
                           (t['code'], t['name'], t['method'], t['unit'], t['limit_text'], t['decimals'], t['page'],
                            t['in_report'], t['sort'], t.get('report_name', ''), t.get('equip_hint', ''), t['id']))
            tid = t['id']
            self.c.execute('DELETE FROM fields WHERE test_id=?', (tid,)); self.c.execute('DELETE FROM calcs WHERE test_id=?', (tid,))
        else:
            cur = self.c.execute('INSERT INTO tests(material_id,code,name,method,unit,limit_text,decimals,page,in_report,sort,report_name,equip_hint) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (mid, t['code'], t['name'], t['method'], t['unit'], t['limit_text'], t['decimals'], t['page'],
                                  t['in_report'], t['sort'], t.get('report_name', ''), t.get('equip_hint', '')))
            tid = cur.lastrowid
        for i, f in enumerate(t['fields']):
            conc = f.get('conc')
            if conc is None:
                conc = guess_conc(f['label'])
            reagent = f.get('reagent') or (guess_reagent(f['label']) if conc else '')
            self.c.execute('INSERT INTO fields(test_id,key,label,unit,kind,default_expr,sort,conc,reagent) VALUES(?,?,?,?,?,?,?,?,?)',
                           (tid, f['key'], f['label'], f.get('unit', ''), f.get('kind', 'number'), f.get('default_expr', ''), i, conc, reagent if conc else ''))
        for i, c in enumerate(t['calcs']):
            self.c.execute('INSERT INTO calcs(test_id,key,label,expr,decimals,is_result,sort) VALUES(?,?,?,?,?,?,?)',
                           (tid, c['key'], c['label'], c['expr'], c.get('decimals', 2), 1 if c.get('is_result') else 0, i))
        if t.get('equipment_ids') is not None:
            with self.as_system(quiet=True):
                self.set_test_equipment(tid, t['equipment_ids'])
        self.c.commit()
        new = self._test_snapshot(t)
        if old is None:
            self.audit('library', 'create', f"{mname} / {t['name']}", [_chg(k, '', v) for k, v in new.items() if v not in (None, '')])
        else:
            keys = list(dict.fromkeys(list(old) + list(new)))
            det = [_chg(k, old.get(k, ''), new.get(k, '')) for k in keys if str(old.get(k, '')) != str(new.get(k, ''))]
            if det:
                self.audit('library', 'edit', f"{mname} / {t['name']}", det)
        return tid

    def delete_test(self, tid):
        self.require('library', 'delete')
        t = self.c.execute('SELECT t.name, m.name AS mn FROM tests t LEFT JOIN materials m ON m.id=t.material_id WHERE t.id=?', (tid,)).fetchone()
        for tb in ('fields', 'calcs', 'job_values', 'test_equipment', 'job_equipment'):
            self.c.execute(f'DELETE FROM {tb} WHERE test_id=?', (tid,))
        self.c.execute('DELETE FROM tests WHERE id=?', (tid,)); self.c.commit()
        if t:
            self.audit('library', 'delete', f"{t['mn']} / {t['name']}", [_chg('Test', t['name'], '')])

    def move_test(self, mid, tid, delta):
        self.require('library', 'edit')
        ts = self.tests(mid, full=False); ids = [t['id'] for t in ts]
        if tid not in ids:
            return
        i = ids.index(tid); j = i + delta
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        for k, x in enumerate(ids):
            self.c.execute('UPDATE tests SET sort=? WHERE id=?', (k, x))
        self.c.commit()
        nm = {t['id']: t['name'] for t in ts}
        self.audit('library', 'reorder', f"{self.material(mid)['name']} / {nm[tid]}", [_chg('Position', i + 1, j + 1)])

    def duplicate_material(self, mid, new_name):
        self.require('library', 'add')
        m = self.material(mid)
        with self.as_system(quiet=True):
            nid = self.add_material(new_name, m['spec'], m['group_name'], json.loads(m['page_titles'] or '{}'))
            for t in self.tests(mid):
                t = dict(t); t['id'] = None
                self.save_test(nid, t)
        self.audit('library', 'create', f'Material: {new_name}', [_chg('Copied from', '', m['name'])])
        return nid

    # ---- jobs
    def jobs(self, search=''):
        q = ('SELECT j.*, m.name AS material FROM jobs j LEFT JOIN materials m ON m.id=j.material_id ')
        args = []
        if search:
            q += 'WHERE j.report_no LIKE ? OR j.customer LIKE ? OR m.name LIKE ? OR j.job_no LIKE ? OR j.work LIKE ? OR j.material_ident LIKE ? '
            args = [f'%{search}%'] * 6
        q += 'ORDER BY j.id DESC'
        return [dict(r) for r in self.c.execute(q, args)]

    def job(self, jid):
        r = self.c.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
        return dict(r) if r else None

    def job_values(self, jid):
        return {(r['test_id'], r['key']): r['value'] for r in self.c.execute('SELECT * FROM job_values WHERE job_id=?', (jid,))}

    JOB_LABELS = None

    def _job_labels(self):
        if DB.JOB_LABELS is None:
            DB.JOB_LABELS = {c: l for c, l, _ in JOB_FIELDS}
            DB.JOB_LABELS.update(material_id='Material', analysed_by='Analysed by', verified_by='Verified by', analysis_date='Date of analysis', remarks='Remarks')
        return DB.JOB_LABELS

    def job_year(self, d):
        """The year a job belongs to = year of the Date of Receipt (falls back to test start / report date / today)."""
        for k in ('receipt_date', 'start_date', 'report_date'):
            v = (d.get(k) or '')
            if len(v) >= 4 and v[:4].isdigit():
                return int(v[:4])
        return datetime.date.today().year

    def job_no_conflict(self, job_no, data, exclude_id=None):
        jn = (job_no or '').strip().upper()
        if not jn:
            return None
        yr = self.job_year(data)
        for r in self.c.execute('SELECT * FROM jobs WHERE upper(trim(job_no))=?', (jn,)):
            if exclude_id and r['id'] == exclude_id:
                continue
            if self.job_year(dict(r)) == yr:
                return dict(r), yr
        return None

    def save_job(self, jid, data, values, equipment=None):
        self.require('jobs', 'edit' if jid else 'add')
        old = self.job(jid) if jid else None
        oldvals = self.job_values(jid) if jid else {}
        oldeq = self.job_equipment(jid) if jid else {}
        jn = (data.get('job_no') or '').strip().upper()
        if jn and (not old or (old['job_no'] or '').strip().upper() != jn or self.job_year(old) != self.job_year(data)):
            c = self.job_no_conflict(jn, data, jid)
            if c:
                raise ValueError(f"Job No. '{data.get('job_no')}' is already used in {c[1]} by Report No. {c[0]['report_no']}.\n"
                                 f"A Job No. may repeat only in a different year.")
        cols = [c for c, _, _ in JOB_FIELDS] + ['material_id', 'analysed_by', 'verified_by', 'analysis_date', 'remarks']
        if jid:
            self.c.execute('UPDATE jobs SET ' + ','.join(f'{c}=?' for c in cols) + ' WHERE id=?', [data.get(c) for c in cols] + [jid])
        else:
            cur = self.c.execute('INSERT INTO jobs(' + ','.join(cols) + ',created) VALUES(' + ','.join('?' * (len(cols) + 1)) + ')',
                                 [data.get(c) for c in cols] + [datetime.datetime.now().isoformat(timespec='seconds')])
            jid = cur.lastrowid
        self.c.execute('DELETE FROM job_values WHERE job_id=?', (jid,))
        newvals = {}
        for (tid, key), v in values.items():
            if v is not None and str(v).strip() != '':
                self.c.execute('INSERT INTO job_values VALUES(?,?,?,?)', (jid, tid, key, str(v)))
                newvals[(tid, key)] = str(v).strip()
        if equipment is not None:
            self.c.execute('DELETE FROM job_equipment WHERE job_id=?', (jid,))
            for tid, eids in equipment.items():
                for e in eids:
                    self.c.execute('INSERT OR IGNORE INTO job_equipment VALUES(?,?,?)', (jid, tid, e))
        self.c.commit()
        newjob = self.job(jid)
        with self.as_system():
            self.sync_logbook(jid); self.sync_standardization(jid)
        # ---- audit: field level old -> new
        L = self._job_labels(); det = []
        mats = {m['id']: m['name'] for m in self.materials()}
        def show(col, v):
            if col == 'material_id':
                return mats.get(v, v)
            if col in ('report_date', 'receipt_date', 'start_date', 'end_date', 'analysis_date'):
                return d_show(v)
            return v
        for c in cols:
            o = show(c, old.get(c)) if old else ''
            n = show(c, newjob.get(c))
            if str(o or '') != str(n or ''):
                det.append(_chg(L.get(c, c), o, n))
        labels = {}
        for mid in {newjob['material_id'], (old or {}).get('material_id')} - {None}:
            for t in self.tests(mid):
                for f in t['fields']:
                    labels[(t['id'], f['key'])] = f"{t['name']} - {f['label']}"
                labels[('t', t['id'])] = t['name']
                labels[(t['id'], '_date')] = f"{t['name']} - Date of analysis"
                labels[(t['id'], '_analyst')] = f"{t['name']} - Analysed by"
        for k in sorted(set(oldvals) | set(newvals), key=lambda k: labels.get(k, str(k))):
            o, n = str(oldvals.get(k, '')).strip(), newvals.get(k, '')
            if o != n:
                det.append(_chg('Reading: ' + labels.get(k, str(k)), o, n))
        if equipment is not None:
            ecode = {e['id']: e['code'] for e in self.equipment()}
            for tid in sorted(set(oldeq) | set(equipment), key=str):
                o = ', '.join(sorted(ecode.get(i, '?') for i in oldeq.get(tid, [])))
                n = ', '.join(sorted(ecode.get(i, '?') for i in equipment.get(tid, [])))
                if o != n:
                    det.append(_chg('Equipment: ' + labels.get(('t', tid), str(tid)), o, n))
        self.audit('jobs', 'edit' if old else 'create', newjob['report_no'], det)
        return jid

    def delete_job(self, jid):
        self.require('jobs', 'delete')
        j = self.job(jid)
        for tb in ('job_values', 'job_equipment', 'std_links'):
            self.c.execute(f'DELETE FROM {tb} WHERE job_id=?', (jid,))
        self.c.execute('DELETE FROM logbook WHERE job_id=? AND auto=1', (jid,))
        self.c.execute('DELETE FROM jobs WHERE id=?', (jid,)); self._clean_std(); self.c.commit()
        if j:
            self.audit('jobs', 'delete', j['report_no'], [_chg('Customer', j['customer'], ''), _chg('Job No.', j['job_no'], ''), _chg('Readings', 'all', 'deleted')])

    # ---- equipment, logbook, standardization
    def equipment(self):
        return [dict(r) for r in self.c.execute('SELECT * FROM equipment ORDER BY code')]

    def save_equipment(self, e):
        self.require('equipment', 'edit' if e.get('id') else 'add')
        old = None
        if e.get('id'):
            r = self.c.execute('SELECT * FROM equipment WHERE id=?', (e['id'],)).fetchone(); old = dict(r) if r else None
            self.c.execute('UPDATE equipment SET code=?,name=?,make_model=?,location=?,calib_due=?,notes=? WHERE id=?',
                           (e['code'], e['name'], e['make_model'], e['location'], e['calib_due'], e['notes'], e['id']))
        else:
            self.c.execute('INSERT INTO equipment(code,name,make_model,location,calib_due,notes) VALUES(?,?,?,?,?,?)',
                           (e['code'], e['name'], e['make_model'], e['location'], e['calib_due'], e['notes']))
        self.c.commit()
        new = {k: e[k] for k in ('code', 'name', 'make_model', 'location', 'calib_due', 'notes')}
        new['calib_due'] = d_show(new['calib_due'])
        if old:
            old['calib_due'] = d_show(old['calib_due'])
            self.audit('equipment', 'edit', f"{e['code']} - {e['name']}", _diff(old, new))
        else:
            self.audit('equipment', 'create', f"{e['code']} - {e['name']}", [_chg(k, '', v) for k, v in new.items() if v])

    def delete_equipment(self, eid):
        self.require('equipment', 'delete')
        r = self.c.execute('SELECT * FROM equipment WHERE id=?', (eid,)).fetchone()
        n = self.c.execute('SELECT COUNT(*) FROM logbook WHERE equipment_id=?', (eid,)).fetchone()[0]
        for tb in ('test_equipment', 'job_equipment', 'logbook'):
            self.c.execute(f'DELETE FROM {tb} WHERE equipment_id=?', (eid,))
        self.c.execute('DELETE FROM equipment WHERE id=?', (eid,)); self.c.commit()
        if r:
            self.audit('equipment', 'delete', f"{r['code']} - {r['name']}", [_chg('Logbook entries removed', '', n)])

    def test_equipment(self, tid):
        return [r[0] for r in self.c.execute('SELECT equipment_id FROM test_equipment WHERE test_id=?', (tid,))]

    def set_test_equipment(self, tid, ids):
        self.c.execute('DELETE FROM test_equipment WHERE test_id=?', (tid,))
        for e in ids:
            self.c.execute('INSERT OR IGNORE INTO test_equipment VALUES(?,?)', (tid, e))
        self.c.commit()

    def job_equipment(self, jid):
        out = {}
        for r in self.c.execute('SELECT test_id,equipment_id FROM job_equipment WHERE job_id=?', (jid,)):
            out.setdefault(r[0], []).append(r[1])
        return out

    def _job_day(self, job):
        return job.get('start_date') or job.get('analysis_date') or job.get('receipt_date') or datetime.date.today().isoformat()

    def sync_logbook(self, jid):
        """Equipment logbook rows are written automatically for every test that has readings: date = test start date."""
        job = self.job(jid)
        self.c.execute('DELETE FROM logbook WHERE job_id=? AND auto=1', (jid,))
        if not job or not job['material_id']:
            self.c.commit(); return
        vals = self.job_values(jid); chosen = self.job_equipment(jid)
        for t in self.tests(job['material_id'], full=False):
            if not any(k[0] == t['id'] and not str(k[1]).startswith('_') and str(v).strip() for k, v in vals.items()):
                continue                                              # test not done on this job
            for eid in chosen.get(t['id'], []):
                self.c.execute('INSERT INTO logbook(log_date,equipment_id,job_id,test_id,report_no,job_no,test_name,analyst,remarks,auto) VALUES(?,?,?,?,?,?,?,?,?,1)',
                               (self._job_day(job), eid, jid, t['id'], job['report_no'], job['job_no'], t['name'],
                                job['analysed_by'] or job['assigned_to'] or '', ''))
        self.c.commit()

    def logbook(self, equipment_id=None, dfrom='', dto=''):
        q = ('SELECT l.*, e.code AS ecode, e.name AS ename FROM logbook l LEFT JOIN equipment e ON e.id=l.equipment_id WHERE 1=1 ')
        a = []
        if equipment_id:
            q += 'AND l.equipment_id=? '; a.append(equipment_id)
        if dfrom:
            q += 'AND l.log_date>=? '; a.append(dfrom)
        if dto:
            q += 'AND l.log_date<=? '; a.append(dto)
        return [dict(r) for r in self.c.execute(q + 'ORDER BY l.log_date, l.id', a)]

    def add_log(self, date, eid, remarks, analyst='', test_name=''):
        self.require('equipment', 'add')
        self.c.execute('INSERT INTO logbook(log_date,equipment_id,test_name,analyst,remarks,auto) VALUES(?,?,?,?,?,0)', (date, eid, test_name, analyst, remarks))
        self.c.commit()
        e = self.c.execute('SELECT code,name FROM equipment WHERE id=?', (eid,)).fetchone()
        self.audit('equipment', 'create', f"Logbook: {e['code'] if e else eid}", [_chg('Date', '', d_show(date)), _chg('Activity', '', test_name), _chg('Remarks', '', remarks)])

    def delete_log(self, lid):
        self.require('equipment', 'delete')
        r = self.c.execute('SELECT l.*, e.code FROM logbook l LEFT JOIN equipment e ON e.id=l.equipment_id WHERE l.id=? AND l.auto=0', (lid,)).fetchone()
        self.c.execute('DELETE FROM logbook WHERE id=? AND auto=0', (lid,)); self.c.commit()
        if r:
            self.audit('equipment', 'delete', f"Logbook: {r['code']}", [_chg('Date', d_show(r['log_date']), ''), _chg('Remarks', r['remarks'], '')])

    def sync_standardization(self, jid):
        """Every Normality / Molarity value used in a job is saved in the Chemical Standardization Record of the testing day."""
        job = self.job(jid)
        self.c.execute('DELETE FROM std_links WHERE job_id=?', (jid,))
        if job and job['material_id']:
            vals = self.job_values(jid); day = self._job_day(job)
            for t in self.tests(job['material_id']):
                tday = d_store(vals.get((t['id'], '_date'), '')) if vals.get((t['id'], '_date')) else day
                if not _iso(tday):
                    tday = day
                for f in t['fields']:
                    if not f.get('conc'):
                        continue
                    v = to_num(vals.get((t['id'], f['key'])))
                    if v is None:
                        continue
                    reagent = (f.get('reagent') or guess_reagent(f['label'])).strip()
                    row = self.c.execute('SELECT id FROM std_records WHERE std_date=? AND lower(reagent)=lower(?) AND conc_type=? AND abs(value-?)<1e-9',
                                         (tday, reagent, f['conc'], v)).fetchone()
                    if row:
                        sid = row[0]
                    else:
                        sid = self.c.execute('INSERT INTO std_records(std_date,reagent,conc_type,value,analyst,auto) VALUES(?,?,?,?,?,1)',
                                             (tday, reagent, f['conc'], v, vals.get((t['id'], '_analyst')) or job['analysed_by'] or job['assigned_to'] or '')).lastrowid
                        self.quiet or self.audit('standard', 'auto-create', f"{d_show(tday)} {reagent}", [_chg('Strength', '', v), _chg('From job', '', job['report_no'])])
                    self.c.execute('INSERT OR IGNORE INTO std_links VALUES(?,?,?)', (sid, jid, t['id']))
        self._clean_std(); self.c.commit()

    def _clean_std(self):
        self.c.execute("DELETE FROM std_records WHERE auto=1 AND COALESCE(against,'')='' AND n_std IS NULL AND v_std IS NULL AND v_tit IS NULL "
                       "AND COALESCE(remarks,'')='' AND id NOT IN (SELECT std_id FROM std_links)")

    def std_records(self, dfrom='', dto=''):
        q = 'SELECT * FROM std_records WHERE 1=1 '; a = []
        if dfrom:
            q += 'AND std_date>=? '; a.append(dfrom)
        if dto:
            q += 'AND std_date<=? '; a.append(dto)
        out = []
        for r in self.c.execute(q + 'ORDER BY std_date, reagent, id', a):
            d = dict(r)
            d['jobs'] = ', '.join(x[0] for x in self.c.execute(
                'SELECT DISTINCT j.report_no FROM std_links l JOIN jobs j ON j.id=l.job_id WHERE l.std_id=? ORDER BY j.report_no', (d['id'],)))
            out.append(d)
        return out

    def save_std(self, d):
        self.require('standard', 'edit' if d.get('id') else 'add')
        cols = ['std_date', 'reagent', 'conc_type', 'value', 'nominal', 'against', 'n_std', 'v_std', 'v_tit', 'analyst', 'remarks']
        old = None
        if d.get('id'):
            r = self.c.execute('SELECT * FROM std_records WHERE id=?', (d['id'],)).fetchone(); old = dict(r) if r else None
            self.c.execute('UPDATE std_records SET ' + ','.join(f'{c}=?' for c in cols) + ' WHERE id=?', [d.get(c) for c in cols] + [d['id']])
        else:
            self.c.execute('INSERT INTO std_records(' + ','.join(cols) + ',auto) VALUES(' + ','.join('?' * len(cols)) + ',0)', [d.get(c) for c in cols])
        self.c.commit()
        new = {c: d.get(c) for c in cols}
        ref = f"{d_show(d.get('std_date'))} {d.get('reagent')}"
        if old:
            self.audit('standard', 'edit', ref, _diff({c: old.get(c) for c in cols}, new))
        else:
            self.audit('standard', 'create', ref, [_chg(k, '', v) for k, v in new.items() if v not in (None, '')])

    def delete_std(self, sid):
        self.require('standard', 'delete')
        r = self.c.execute('SELECT * FROM std_records WHERE id=?', (sid,)).fetchone()
        self.c.execute('DELETE FROM std_links WHERE std_id=?', (sid,)); self.c.execute('DELETE FROM std_records WHERE id=?', (sid,)); self.c.commit()
        if r:
            self.audit('standard', 'delete', f"{d_show(r['std_date'])} {r['reagent']}", [_chg('Strength', r['value'], '')])

    def backup(self):
        self.require('settings', 'edit')
        self.c.commit()
        p = os.path.join(BACKUP_DIR, 'labdata_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.db')
        shutil.copy2(self.path, p)
        self.audit('settings', 'backup', os.path.basename(p), [])
        return p

# ------------------------------------------------------------------ date helpers
def d_show(iso):
    try:
        return datetime.datetime.strptime(iso, '%Y-%m-%d').strftime('%d-%m-%Y')
    except Exception:
        return iso or ''


def d_store(txt):
    txt = (txt or '').strip()
    for f in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.datetime.strptime(txt, f).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return txt
