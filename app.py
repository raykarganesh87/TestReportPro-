"""LabReport Pro - desktop application (tkinter)."""
import json, os, re, sys, tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
import branding
from core import DB, JOB_FIELDS, compute_job, fmt, d_show, d_store, expr_names, safe_eval
import reports

APP = 'LabReport Pro'


def lines(s):
    return [x.strip() for x in (s or '').splitlines() if x.strip()]


class ScrollFrame(ttk.Frame):
    """Vertical scrolling container - put widgets into .inner. Nothing is ever cut off below the window edge."""
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = ttk.Frame(self.canvas)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.canvas.grid(row=0, column=0, sticky='nsew'); self.vsb.grid(row=0, column=1, sticky='ns')
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.win, width=e.width))


def install_wheel(root):
    """One mouse-wheel handler for the whole program: scrolls the list / box under the pointer, otherwise the page."""
    for cls in ('Treeview', 'Listbox', 'Text', 'TCombobox'):
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>', '<Shift-MouseWheel>'):
            try:
                root.unbind_class(cls, seq)
            except tk.TclError:
                pass

    def handler(e):
        num = getattr(e, 'num', None)
        if num in (4, 5):
            d = 1 if num == 4 else -1
        else:
            d = 1 if e.delta > 0 else -1
        w = root.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            cls = w.winfo_class()
            if cls in ('Treeview', 'Listbox', 'Text'):
                try:
                    y0, y1 = w.yview()
                    if (y0, y1) != (0.0, 1.0) and not ((d > 0 and y0 <= 0.0) or (d < 0 and y1 >= 1.0)):
                        w.yview_scroll(-d * 2, 'units'); return
                except tk.TclError:
                    pass
            if isinstance(w, ScrollFrame):
                w.canvas.yview_scroll(-d * 3, 'units'); return
            w = getattr(w, 'master', None)
    root.bind_all('<MouseWheel>', handler, add='+')
    root.bind_all('<Button-4>', handler, add='+'); root.bind_all('<Button-5>', handler, add='+')


def tree_with_scroll(parent, columns, height=10, **pack):
    """Treeview with its own vertical scrollbar; returns the tree."""
    f = ttk.Frame(parent); f.pack(**pack)
    t = ttk.Treeview(f, columns=columns, show='headings', height=height)
    sb = ttk.Scrollbar(f, orient='vertical', command=t.yview); t.configure(yscrollcommand=sb.set)
    t.pack(side='left', fill='both', expand=True); sb.pack(side='left', fill='y')
    return t


def gate(widget, db, rules):
    """Disable buttons the logged-in user is not allowed to use. rules: {button text: (section, action)}"""
    for ch in widget.winfo_children():
        if isinstance(ch, ttk.Button):
            r = rules.get(ch.cget('text'))
            if r and not db.can(*r):
                ch.state(['disabled'])
        gate(ch, db, rules)


class Modal(tk.Toplevel):
    def __init__(self, parent, title, w=None, h=None):
        super().__init__(parent)
        self.title(title); self.transient(parent); self.result = None
        if w:
            self.geometry(f'{min(w, self.winfo_screenwidth() - 40)}x{min(h, self.winfo_screenheight() - 90)}+15+15')
        self.after(50, self.grab_set)


def make_output(db, jid, what, fmt_, parent=None):
    fn = {('rep', 'pdf'): reports.report_pdf, ('rep', 'xlsx'): reports.report_xlsx,
          ('obs', 'pdf'): reports.observation_pdf, ('obs', 'xlsx'): reports.observation_xlsx}[(what, fmt_)]
    try:
        p = fn(db, jid)
    except PermissionError:
        messagebox.showwarning(APP, 'The file is open in another program. Close it and try again.', parent=parent); return
    if fmt_ == 'pdf' and not reports.FONT_USED.startswith('Cambria') and not getattr(make_output, 'warned', False):
        make_output.warned = True
        messagebox.showwarning(APP, f'Cambria font was not found on this PC; PDF used: {reports.FONT_USED}.\nInstall Cambria (comes with Windows / Microsoft Office) for exact Cambria output.', parent=parent)
    db.log_export('jobs', db.job(jid)['report_no'], {('rep', 'pdf'): 'Test Report PDF', ('rep', 'xlsx'): 'Test Report Excel', ('obs', 'pdf'): 'Observation Sheet PDF', ('obs', 'xlsx'): 'Observation Sheet Excel'}[(what, fmt_)])
    reports.open_file(p)


class AutoText(tk.Text):
    """Entry replacement: long text wraps onto extra lines and the box grows (up to maxlines) - same get()/set() as a StringVar."""
    def __init__(self, parent, width=20, maxlines=8, **kw):
        super().__init__(parent, width=width, height=1, wrap='word', relief='solid', borderwidth=1, undo=True,
                         font=ttk.Style().lookup('TEntry', 'font') or 'TkDefaultFont', padx=3, pady=2, **kw)
        self.maxlines = maxlines
        self.bind('<KeyRelease>', lambda e: self.fit()); self.bind('<Configure>', lambda e: self.fit())
        self.bind('<Return>', lambda e: 'break')                       # no manual line breaks; text simply wraps
        self.bind('<Tab>', lambda e: (self.tk_focusNext().focus_set(), 'break')[1])
        self.bind('<Shift-Tab>', lambda e: (self.tk_focusPrev().focus_set(), 'break')[1])
        self.bind('<<Paste>>', lambda e: self.after(20, self._clean))

    def _clean(self):
        t = super().get('1.0', 'end-1c')
        if '\n' in t:
            self.set(' '.join(t.split()))

    def fit(self):
        try:
            r = self.count('1.0', 'end-1c', 'displaylines')
            n = (r[0] if isinstance(r, (tuple, list)) else r) or 1
        except Exception:
            n = 1
        self.configure(height=max(1, min(self.maxlines, n)))

    def get(self, *a):
        return super().get('1.0', 'end-1c') if not a else super().get(*a)

    def set(self, v):
        self.delete('1.0', 'end'); self.insert('1.0', v or ''); self.after_idle(self.fit)


# ======================================================================= Job editor
class JobEditor(tk.Toplevel):
    def __init__(self, app, jid=None):
        super().__init__(app)
        self.app, self.db, self.jid = app, app.db, jid
        self.title('Job - ' + ('edit' if jid else 'new'))
        self.geometry(f'{min(1150, self.winfo_screenwidth() - 40)}x{min(760, self.winfo_screenheight() - 90)}+10+10')
        self.bind('<Control-s>', lambda e: self.save())
        self.vars = {}; self.tvars = {}; self.test_ui = {}; self.tests = []; self.mat_id = None
        self.job = self.db.job(jid) if jid else {}
        self.typed = self.db.job_values(jid) if jid else {}
        self.equip = self.db.equipment(); self.job_eq = self.db.job_equipment(jid) if jid else {}; self.eq_boxes = {}
        self.build()
        self.load_material(self.job.get('material_id'))

    # ---- layout
    def build(self):
        bb = ttk.Frame(self); bb.pack(side='bottom', fill='x', padx=8, pady=(0, 8))       # buttons: always visible
        r1 = ttk.Frame(bb); r1.pack(fill='x'); r2 = ttk.Frame(bb); r2.pack(fill='x', pady=(4, 0))
        self.can_save = self.db.can('jobs', 'edit' if self.jid else 'add')
        for txt, cmd in [('SAVE', self.save), ('Save & Close', lambda: self.save(True)), ('Close', self.destroy)]:
            b_ = ttk.Button(r1, text=txt, command=cmd); b_.pack(side='left', padx=4)
            if txt != 'Close' and not self.can_save:
                b_.state(['disabled'])
        ttk.Label(r1, text='  (Ctrl+S = save)' if self.can_save else '  VIEW ONLY - you are not authorised to change this job', foreground='#777' if self.can_save else '#C00000').pack(side='left')
        for txt, cmd in [('Test Report - PDF', lambda: self.out('rep', 'pdf')), ('Test Report - Excel', lambda: self.out('rep', 'xlsx')),
                         ('Observation Sheet - PDF', lambda: self.out('obs', 'pdf')), ('Observation Sheet - Excel', lambda: self.out('obs', 'xlsx'))]:
            ttk.Button(r2, text=txt, command=cmd).pack(side='left', padx=4)
        self.body = ScrollFrame(self); self.body.pack(side='top', fill='both', expand=True)       # whole form scrolls
        P = self.body.inner
        top = ttk.LabelFrame(P, text=' Job details '); top.pack(side='top', fill='x', padx=8, pady=6)
        mats = self.db.materials()
        self.mat_names = {m['name']: m['id'] for m in mats}
        self.mat_var = tk.StringVar()
        ttk.Label(top, text='Material / Test group *', font=('', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=4, pady=2)
        cb = ttk.Combobox(top, textvariable=self.mat_var, values=list(self.mat_names), state='readonly', width=30)
        cb.grid(row=0, column=1, sticky='w', padx=4); cb.bind('<<ComboboxSelected>>', lambda e: self.on_material())
        cur = next((m['name'] for m in mats if m['id'] == self.job.get('material_id')), '')
        self.mat_var.set(cur)
        for cc in (1, 3, 5):
            top.columnconfigure(cc, weight=1, uniform='f')
        r, c = 1, 0
        for col, label, kind in JOB_FIELDS:
            init = d_show(self.job.get(col)) if kind == 'd' else (self.job.get(col) or '')
            ttk.Label(top, text=label).grid(row=r, column=c, sticky='nw', padx=4, pady=2)
            if col in ('reviewer', 'assigned_to'):
                v = tk.StringVar(value=init)
                w = ttk.Combobox(top, textvariable=v, values=lines(self.db.setting('reviewers' if col == 'reviewer' else 'analysts')))
            else:
                w = AutoText(top, width=16); w.set(init); v = w
            self.vars[col] = (v, kind)
            if kind == 'm':                                           # wide fields use the whole row
                w.grid(row=r, column=c + 1, columnspan=5 - c, sticky='ew', padx=4, pady=2)
                c = 0; r += 1
            else:
                w.grid(row=r, column=c + 1, sticky='ew', padx=4, pady=2)
                c += 2
                if c >= 6:
                    c = 0; r += 1
        if c:
            r += 1
        ttk.Label(top, text='dates: dd-mm-yyyy  (Receipt <= Test start <= Test completion <= Report date)', foreground='#777').grid(row=r, column=0, columnspan=3, sticky='w', padx=4)
        self.date_lbl = ttk.Label(top, text='', foreground='#C00000', font=('', 9, 'bold')); self.date_lbl.grid(row=r, column=3, columnspan=3, sticky='w', padx=4)
        for dc in ('receipt_date', 'start_date', 'end_date', 'report_date', 'job_no'):
            self.vars[dc][0].bind('<FocusOut>', lambda e: self.live_dates(), add='+')
        # tests
        self.nb = ttk.Notebook(P); self.nb.pack(side='top', fill='x', padx=8, pady=4)
        bot = ttk.Frame(P); bot.pack(side='top', fill='x', padx=8, pady=6)
        self.bvars = {}
        for i, (k, lab, vals) in enumerate([('analysed_by', 'Analysed by', lines(self.db.setting('analysts'))),
                                            ('verified_by', 'Verified by', lines(self.db.setting('reviewers'))),
                                            ('analysis_date', 'Date of analysis', None)]):
            ttk.Label(bot, text=lab).grid(row=0, column=2 * i, padx=4)
            v = tk.StringVar(value=(d_show(self.job.get(k)) if k == 'analysis_date' else self.job.get(k) or ''))
            self.bvars[k] = v
            (ttk.Combobox(bot, textvariable=v, values=vals, width=22) if vals is not None else ttk.Entry(bot, textvariable=v, width=14)).grid(row=0, column=2 * i + 1, padx=4)
        ttk.Label(bot, text='Remarks').grid(row=0, column=6, padx=4)
        self.bvars['remarks'] = tk.StringVar(value=self.job.get('remarks') or '')
        ttk.Entry(bot, textvariable=self.bvars['remarks'], width=30).grid(row=0, column=7, padx=4)

    def date_values(self):
        return [d_store(self.vars[k][0].get()) for k in ('receipt_date', 'start_date', 'end_date', 'report_date')]

    def job_no_error(self):
        d = {k: d_store(self.vars[k][0].get()) for k in ('receipt_date', 'start_date', 'report_date')}
        jn = self.vars['job_no'][0].get().strip()
        if self.job and (self.job.get('job_no') or '').strip().upper() == jn.upper() and self.db.job_year(self.job) == self.db.job_year(d):
            return ''
        c = self.db.job_no_conflict(jn, d, self.jid)
        return f"Job No. '{jn}' is already used in {c[1]} by Report No. {c[0]['report_no']}." if c else ''

    def live_dates(self):
        errs = core.check_dates(*self.date_values())
        if not errs:
            e2 = self.job_no_error()
            errs = [e2] if e2 else []
        self.date_lbl.config(text=('! ' + errs[0]) if errs else '')

    def hint_ids(self, t):
        hint = [h.strip().lower() for h in (t.get('equip_hint') or '').split(',') if h.strip()]
        return [e['id'] for e in self.equip if any(h in (e['name'] + ' ' + e['code']).lower() for h in hint)]

    def test_date_errors(self):
        """Each test's own Date of analysis must be a valid date inside the test period (start .. completion)."""
        d = self.date_values(); start, end = d[1], d[2]; out = []
        for t in self.tests:
            v = self.tvars.get((t['id'], '_date'))
            txt = v.get().strip() if v else ''
            if not txt:
                continue
            iso = d_store(txt)
            if not core._iso(iso):
                out.append(f"{t['name']}: date of analysis '{txt}' is not a valid date (dd-mm-yyyy)."); continue
            if start and iso < start:
                out.append(f"{t['name']}: date of analysis ({d_show(iso)}) is before the Test Start Date ({d_show(start)}).")
            if end and iso > end:
                out.append(f"{t['name']}: date of analysis ({d_show(iso)}) is after the Test Completion Date ({d_show(end)}).")
        return out

    def collect_equipment(self):
        return {tid: [self.equip[i]['id'] for i in lb.curselection()] for tid, lb in self.eq_boxes.items()}

    def on_material(self):
        if self.tvars and not messagebox.askyesno(APP, 'Change material? Readings entered for tests of the old material stay stored '
                                                         'but will not be shown.', parent=self):
            self.mat_var.set(next(n for n, i in self.mat_names.items() if i == self.mat_id)); return
        self.collect_typed()
        self.load_material(self.mat_names.get(self.mat_var.get()))

    def load_material(self, mid):
        for t in self.nb.tabs():
            self.nb.forget(t)
        self.tvars = {}; self.test_ui = {}; self.mat_id = mid; self.eq_boxes = {}
        self.tests = self.db.tests(mid) if mid else []
        self.summary = ttk.Frame(self.nb); self.nb.add(self.summary, text='  Summary  ')
        self.sum_tree = tree_with_scroll(self.summary, ('test', 'result', 'unit', 'limit', 'method'), height=14, fill='both', expand=True, padx=6, pady=6)
        for c, t, w in [('test', 'Test', 330), ('result', 'Result', 100), ('unit', 'Unit', 60), ('limit', 'Limit', 300), ('method', 'Method', 200)]:
            self.sum_tree.heading(c, text=t); self.sum_tree.column(c, width=w)
        for t in self.tests:
            fr = ttk.Frame(self.nb); self.nb.add(fr, text=f" {t['code']} ")
            ttk.Label(fr, text=f"{t['name']}   ({t['method']})", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w', padx=8, pady=6)
            ui = {'auto': {}, 'calc': {}}
            dv_ = tk.StringVar(value=self.typed.get((t['id'], '_date'), '')); av_ = tk.StringVar(value=self.typed.get((t['id'], '_analyst'), ''))
            self.tvars[(t['id'], '_date')] = dv_; self.tvars[(t['id'], '_analyst')] = av_
            hf = ttk.Frame(fr); hf.grid(row=1, column=0, columnspan=4, sticky='w', padx=8, pady=(0, 6))
            ttk.Label(hf, text='Date of analysis (dd-mm-yyyy)').pack(side='left'); ttk.Entry(hf, textvariable=dv_, width=12).pack(side='left', padx=6)
            ttk.Label(hf, text='Analysed by').pack(side='left', padx=(12, 0))
            ttk.Combobox(hf, textvariable=av_, values=lines(self.db.setting('analysts')), width=20).pack(side='left', padx=6)
            r = 2
            for f in t['fields']:
                v = tk.StringVar(value=self.typed.get((t['id'], f['key']), ''))
                v.trace_add('write', lambda *a: self.recalc())
                self.tvars[(t['id'], f['key'])] = v
                ttk.Label(fr, text=f['label'] + (f" ({f['unit']})" if f['unit'] else '')).grid(row=r, column=0, sticky='w', padx=8, pady=2)
                ttk.Entry(fr, textvariable=v, width=22).grid(row=r, column=1, padx=4)
                al = ttk.Label(fr, text='', foreground='#888'); al.grid(row=r, column=2, sticky='w'); ui['auto'][f['key']] = al
                if f.get('conc'):
                    ttk.Label(fr, text=('Normality' if f['conc'] == 'N' else 'Molarity') + ' - saved in Chemical Standardization Record',
                              foreground='#7030A0').grid(row=r, column=3, sticky='w', padx=6)
                r += 1
            if t['calcs']:
                ttk.Separator(fr).grid(row=r, column=0, columnspan=4, sticky='ew', pady=6); r += 1
            for c in t['calcs']:
                ttk.Label(fr, text=c['label'], font=('', 9, 'bold' if c['is_result'] else '')).grid(row=r, column=0, sticky='w', padx=8, pady=2)
                lb = ttk.Label(fr, text='', font=('', 10, 'bold'), foreground='#1F3864'); lb.grid(row=r, column=1, sticky='w', padx=6)
                ui['calc'][c['key']] = lb; r += 1
            ttk.Separator(fr).grid(row=r, column=0, columnspan=4, sticky='ew', pady=6); r += 1
            ttk.Label(fr, text='Equipment used (goes to the Logbook automatically with the test start date)', font=('', 9, 'bold')).grid(row=r, column=0, columnspan=3, sticky='w', padx=8); r += 1
            if t.get('equip_hint'):
                ttk.Label(fr, text='Equipment types on the observation sheet: ' + t['equip_hint'], foreground='#777').grid(row=r, column=0, columnspan=3, sticky='w', padx=8); r += 1
            if self.equip:
                lbf = ttk.Frame(fr)
                lb = tk.Listbox(lbf, selectmode='multiple', height=min(8, len(self.equip)), exportselection=False, width=70)
                lbs = ttk.Scrollbar(lbf, orient='vertical', command=lb.yview); lb.configure(yscrollcommand=lbs.set)
                lb.pack(side='left'); lbs.pack(side='left', fill='y')
                for e in self.equip:
                    lb.insert('end', f"{e['code']}  -  {e['name']}")
                chosen = self.job_eq.get(t['id']) or t.get('equipment_ids') or self.hint_ids(t)
                for i, e in enumerate(self.equip):
                    if e['id'] in chosen:
                        lb.selection_set(i)
                lbf.grid(row=r, column=0, columnspan=3, sticky='w', padx=8, pady=2); self.eq_boxes[t['id']] = lb
            else:
                ttk.Label(fr, foreground='#888', text="No equipment registered yet - add it in the 'Equipment & Logbook' tab, then tick it here.").grid(row=r, column=0, columnspan=3, sticky='w', padx=8)
            self.test_ui[t['id']] = ui
        self.recalc()

    def collect_typed(self):
        for k, v in self.tvars.items():
            self.typed[k] = v.get()

    def recalc(self):
        if not self.tests:
            return
        typed = {k: v.get() for k, v in self.tvars.items()}
        res = compute_job(self.tests, typed)
        for t in self.tests:
            r, ui = res[t['id']], self.test_ui[t['id']]
            for f in t['fields']:
                ui['auto'][f['key']].config(text=f"auto = {fmt(r['inputs'][f['key']], 4).rstrip('0').rstrip('.')}" if r['auto'][f['key']] else '')
            for c in t['calcs']:
                v = r['calcs'][c['key']]
                ui['calc'][c['key']].config(text=(fmt(v, c['decimals']) + (' ' + t['unit'] if c['is_result'] and t['unit'] not in ('', '--') and v is not None else '')) if v is not None else '-')
        self.sum_tree.delete(*self.sum_tree.get_children())
        for t in self.tests:
            self.sum_tree.insert('', 'end', values=(t['name'] + ('' if t['in_report'] else '  (calc only)'),
                                                    fmt(res[t['id']]['result'], t['decimals']) or '-', t['unit'], t['limit_text'], t['method']))

    # ---- actions
    def gather(self):
        data = {'material_id': self.mat_id}
        for col, (v, kind) in self.vars.items():
            data[col] = d_store(v.get()) if kind == 'd' else v.get().strip()
        for k, v in self.bvars.items():
            data[k] = d_store(v.get()) if k == 'analysis_date' else v.get().strip()
        return data

    def save(self, close=False, quiet=False):
        data = self.gather()
        if not data['report_no']:
            messagebox.showwarning(APP, 'Report No. is required.', parent=self); return False
        if not self.mat_id:
            messagebox.showwarning(APP, 'Select the material.', parent=self); return False
        dup = self.db.c.execute('SELECT id FROM jobs WHERE report_no=?', (data['report_no'],)).fetchone()
        if dup and dup[0] != self.jid:
            messagebox.showwarning(APP, f"Report No. '{data['report_no']}' already exists.", parent=self); return False
        errs = core.check_dates(data['receipt_date'], data['start_date'], data['end_date'], data['report_date'])
        if not errs:
            errs = self.test_date_errors()
        if errs:
            messagebox.showwarning(APP, 'Please correct the dates:\n\n' + '\n'.join('- ' + e for e in errs), parent=self); return False
        self.collect_typed()
        for k in list(self.typed):
            if k[1] == '_date' and str(self.typed[k]).strip():
                self.typed[k] = d_show(d_store(self.typed[k]))          # always stored as dd-mm-yyyy
        try:
            self.jid = self.db.save_job(self.jid, data, {k: v for k, v in self.typed.items()}, equipment=self.collect_equipment())
        except (ValueError, PermissionError) as ex:
            messagebox.showwarning(APP, str(ex), parent=self); return False
        self.job_eq = self.db.job_equipment(self.jid)
        self.title('Job - ' + data['report_no'] + '   (saved)'); self.app.refresh_jobs(); self.app.refresh_records()
        if not close and not quiet:
            messagebox.showinfo(APP, f"Job {data['report_no']} saved.", parent=self)
        if close:
            self.destroy()
        return True

    def out(self, what, fmt_):
        if self.can_save:
            if not self.save(quiet=True):
                return
        elif not self.jid:
            return
        make_output(self.db, self.jid, what, fmt_, self)


# ======================================================================= Test designer dialogs
class ListEditor(ttk.Frame):
    """small table editor used for fields and calculations"""
    def __init__(self, parent, cols, rows, edit_fn):
        super().__init__(parent)
        self.cols, self.edit_fn = cols, edit_fn
        self.tree = tree_with_scroll(self, [c for c, _, _ in cols], height=5, side='left', fill='both', expand=True)
        for c, t, w in cols:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        bt = ttk.Frame(self); bt.pack(side='left', fill='y', padx=4)
        for t, cmd in [('Add', self.add), ('Edit', self.edit), ('Delete', self.delete), ('Up', lambda: self.move(-1)), ('Down', lambda: self.move(1))]:
            ttk.Button(bt, text=t, width=7, command=cmd).pack(pady=1)
        self.rows = [dict(r) for r in rows]; self.draw()
        self.tree.bind('<Double-1>', lambda e: self.edit())

    def draw(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            self.tree.insert('', 'end', iid=str(i), values=[('Yes' if r.get(c) else '') if c in ('is_result',) else r.get(c, '') for c, _, _ in self.cols])

    def sel(self):
        s = self.tree.selection(); return int(s[0]) if s else None

    def add(self):
        r = self.edit_fn(self, None)
        if r:
            self.rows.append(r); self.draw()

    def edit(self):
        i = self.sel()
        if i is None: return
        r = self.edit_fn(self, self.rows[i])
        if r:
            self.rows[i] = r; self.draw()

    def delete(self):
        i = self.sel()
        if i is not None:
            del self.rows[i]; self.draw()

    def move(self, d):
        i = self.sel()
        if i is None or not 0 <= i + d < len(self.rows): return
        self.rows[i], self.rows[i + d] = self.rows[i + d], self.rows[i]; self.draw(); self.tree.selection_set(str(i + d))


def form_dialog(parent, title, spec, init, validate=None):
    """spec: list of (key, label, kind[text|choice|check], extra). returns dict or None"""
    dlg = Modal(parent, title, 760, min(120 + 34 * len(spec), 640))
    out = {}
    vars_ = {}
    bt = ttk.Frame(dlg); bt.pack(side='bottom', pady=8)
    sf = ScrollFrame(dlg); sf.pack(side='top', fill='both', expand=True)
    P = sf.inner
    for i, (k, lab, kind, extra) in enumerate(spec):
        ttk.Label(P, text=lab).grid(row=i, column=0, sticky='nw', padx=8, pady=3)
        if kind == 'check':
            v = tk.BooleanVar(value=bool(init.get(k))); ttk.Checkbutton(P, variable=v).grid(row=i, column=1, sticky='w')
        elif kind == 'choice':
            v = tk.StringVar(value=init.get(k, extra[0])); ttk.Combobox(P, textvariable=v, values=extra, state='readonly', width=34).grid(row=i, column=1, sticky='w', padx=4)
        else:
            v = tk.StringVar(value=str(init.get(k, '') if init.get(k) is not None else '')); ttk.Entry(P, textvariable=v, width=extra or 60).grid(row=i, column=1, sticky='w', padx=4)
        vars_[k] = v

    def ok():
        d = {k: v.get() for k, v in vars_.items()}
        if validate:
            msg = validate(d)
            if msg:
                messagebox.showwarning(APP, msg, parent=dlg); return
        out.update(d); dlg.destroy()
    ttk.Button(bt, text='OK', command=ok).pack(side='left', padx=6); ttk.Button(bt, text='Cancel', command=dlg.destroy).pack(side='left')
    dlg.wait_window()
    return out or None


IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


CONC_LABELS = {None: 'auto-detect from label', '': 'none', 'N': 'Normality (N)', 'M': 'Molarity (M)'}
CONC_BACK = {v: k for k, v in CONC_LABELS.items()}


def field_edit(parent, row):
    def val(d):
        if not IDENT.match(d['key']): return 'Variable name: letters, digits, underscore; must start with a letter (e.g. W1).'
        if d['default_expr']:
            try: expr_names(d['default_expr'])
            except SyntaxError: return 'Default formula is not valid.'
    init = dict(row or {'kind': 'number'})
    init['conc_sel'] = CONC_LABELS.get(init.get('conc') if row else None, 'auto-detect from label')
    r = form_dialog(parent, 'Observation field', [('key', 'Variable name', 'text', 14), ('label', 'Label shown to analyst', 'text', 60),
                                                  ('unit', 'Unit', 'text', 10), ('kind', 'Type', 'choice', ['number', 'text']),
                                                  ('default_expr', 'Default formula (optional)\ne.g. IR_A', 'text', 40),
                                                  ('conc_sel', 'Is this a Normality / Molarity?\n(saved in Standardization Record)', 'choice', list(CONC_LABELS.values())),
                                                  ('reagent', 'Reagent name (for the record)', 'text', 40)], init, val)
    if r:
        r['conc'] = CONC_BACK[r.pop('conc_sel')]
    return r


def calc_edit(parent, row):
    def val(d):
        if not IDENT.match(d['key']): return 'Variable name: letters, digits, underscore; must start with a letter.'
        try: expr_names(d['expr'])
        except SyntaxError: return 'Formula is not valid. Use + - * / ( ), numbers, variable names and avg(), sum(), min(), max(), round(), sqrt(), abs(), iff(cond,a,b).'
        if not d['decimals'].strip().lstrip('-').isdigit(): return 'Decimals must be a whole number.'
    r = form_dialog(parent, 'Calculation', [('key', 'Variable name', 'text', 14), ('label', 'Description', 'text', 60),
                                            ('expr', 'Formula', 'text', 60), ('decimals', 'Decimals', 'text', 5),
                                            ('is_result', 'This is the reported result', 'check', None)],
                    row or {'decimals': 2}, val)
    if r:
        r['decimals'] = int(r['decimals']); r['is_result'] = 1 if r['is_result'] else 0
    return r


class TestDialog(Modal):
    def __init__(self, parent, db, mid, test=None, others=()):
        super().__init__(parent, 'Test definition', 900, 700)
        self.db, self.mid, self.t = db, mid, test or {'fields': [], 'calcs': [], 'page': 1, 'in_report': 1, 'decimals': 2, 'unit': '%', 'sort': 999}
        self.others = others; self.saved = False
        bt = ttk.Frame(self); bt.pack(side='bottom', pady=8)                      # buttons always visible
        ttk.Button(bt, text='SAVE TEST', command=self.save).pack(side='left', padx=6)
        ttk.Button(bt, text='Test formulas with sample numbers', command=self.trial).pack(side='left', padx=6)
        ttk.Button(bt, text='Cancel', command=self.destroy).pack(side='left', padx=6)
        ttk.Label(self, foreground='#555', wrap=860, text="Formulas may use this test's variables directly, and other tests' values as CODE_variable "
                  "(e.g. IR_A, SIO2_result). The result of a test is CODE_result. Blank inputs give a blank result (no errors).").pack(side='bottom', padx=8, anchor='w')
        sf = ScrollFrame(self); sf.pack(side='top', fill='both', expand=True); P = sf.inner
        top = ttk.LabelFrame(P, text=' Test '); top.pack(side='top', fill='x', padx=8, pady=4)
        self.v = {}
        spec = [('code', 'Short code (e.g. SO3)', 12), ('name', 'Test name (observation sheet)', 50), ('report_name', 'Name shown on report (blank = same)', 50),
                ('method', 'Test method', 40), ('unit', 'Unit', 10), ('limit_text', 'Limit / specification text', 60),
                ('decimals', 'Decimals in report', 4), ('page', 'Report page no.', 4)]
        for i, (k, lab, w) in enumerate(spec):
            r_, c_ = i % 4, (i // 4) * 2
            ttk.Label(top, text=lab).grid(row=r_, column=c_, sticky='w', padx=6, pady=2)
            self.v[k] = tk.StringVar(value=str(self.t.get(k, '') if self.t.get(k) is not None else ''))
            ttk.Entry(top, textvariable=self.v[k], width=min(w, 38)).grid(row=r_, column=c_ + 1, sticky='w', padx=4)
        self.equip = self.db.equipment()
        ef = ttk.LabelFrame(top, text=' Equipment normally used (logbook) '); ef.grid(row=0, column=4, rowspan=5, padx=10, pady=2, sticky='n')
        if self.equip:
            self.eqb = tk.Listbox(ef, selectmode='multiple', height=6, width=34, exportselection=False)
            _sb = ttk.Scrollbar(ef, orient='vertical', command=self.eqb.yview); self.eqb.configure(yscrollcommand=_sb.set)
            for e in self.equip:
                self.eqb.insert('end', f"{e['code']} - {e['name']}")
            for i, e in enumerate(self.equip):
                if e['id'] in self.t.get('equipment_ids', []):
                    self.eqb.selection_set(i)
            self.eqb.pack(side='left', padx=4, pady=4); _sb.pack(side='left', fill='y')
        else:
            self.eqb = None
            ttk.Label(ef, text='No equipment yet.\nAdd it in the\n"Equipment & Logbook" tab.', foreground='#888').pack(padx=8, pady=8)
        self.rep = tk.BooleanVar(value=bool(self.t.get('in_report', 1)))
        ttk.Checkbutton(top, text='Show this test in the test report (untick = calculation-only step)', variable=self.rep).grid(row=4, column=0, columnspan=4, sticky='w', padx=6)
        self.hint = tk.StringVar(value=self.t.get('equip_hint') or '')
        ttk.Label(top, text='Equipment types on the observation sheet\n(e.g. Balance, Oven, Burette)').grid(row=5, column=0, sticky='w', padx=6, pady=2)
        ttk.Entry(top, textvariable=self.hint, width=50).grid(row=5, column=1, columnspan=3, sticky='w', padx=4)
        f1 = ttk.LabelFrame(P, text=' Observation fields the analyst types '); f1.pack(side='top', fill='x', padx=8, pady=4)
        self.fe = ListEditor(f1, [('key', 'Variable', 70), ('label', 'Label', 300), ('unit', 'Unit', 45), ('kind', 'Type', 55), ('conc', 'N/M', 40), ('default_expr', 'Default formula', 120)], self.t['fields'], field_edit)
        self.fe.pack(fill='both', expand=True, padx=4, pady=4)
        f2 = ttk.LabelFrame(P, text=' Calculations (top to bottom; tick exactly one as the reported result) '); f2.pack(side='top', fill='x', padx=8, pady=4)
        self.ce = ListEditor(f2, [('key', 'Variable', 70), ('label', 'Description', 250), ('expr', 'Formula', 280), ('decimals', 'Dec', 40), ('is_result', 'Result', 50)], self.t['calcs'], calc_edit)
        self.ce.pack(fill='both', expand=True, padx=4, pady=4)

    def build(self):
        v = {k: x.get().strip() for k, x in self.v.items()}
        if not v['code'] or not IDENT.match(v['code']):
            raise ValueError('Short code is required (letters/digits, no spaces).')
        if not v['name']:
            raise ValueError('Test name is required.')
        if not str(v['decimals']).isdigit() or not str(v['page']).isdigit():
            raise ValueError('Decimals and page must be whole numbers.')
        if any(o['code'].lower() == v['code'].lower() and o['id'] != self.t.get('id') for o in self.others):
            raise ValueError('This code is already used by another test of this material.')
        keys = [r['key'] for r in self.fe.rows] + [r['key'] for r in self.ce.rows]
        if len(keys) != len(set(keys)):
            raise ValueError('Variable names must be unique inside a test.')
        if self.ce.rows and sum(1 for r in self.ce.rows if r['is_result']) != 1:
            raise ValueError('Tick exactly one calculation as the reported result.')
        t = dict(self.t); t.update(code=v['code'], name=v['name'], report_name=v['report_name'] or v['name'], method=v['method'], unit=v['unit'],
                                  limit_text=v['limit_text'], decimals=int(v['decimals']), page=int(v['page']), in_report=1 if self.rep.get() else 0, equip_hint=self.hint.get().strip())
        t['fields'] = self.fe.rows; t['calcs'] = self.ce.rows
        t['equipment_ids'] = [self.equip[i]['id'] for i in self.eqb.curselection()] if self.eqb else self.t.get('equipment_ids', [])
        return t

    def trial(self):
        try:
            t = self.build()
        except ValueError as e:
            messagebox.showwarning(APP, str(e), parent=self); return
        vals = {}
        for f in t['fields']:
            s = simpledialog.askstring('Sample value', f"{f['label']}\n(leave empty for blank)", parent=self)
            if s is None: return
            vals[(0, f['key'])] = s
        tt = dict(t); tt['id'] = 0
        res = compute_job([tt], vals)[0]
        msg = '\n'.join(f"{c['label']}  =  {fmt(res['calcs'][c['key']], c['decimals']) or '(blank)'}" for c in t['calcs'])
        names = set(); [names.update(expr_names(c['expr'])) for c in t['calcs']]
        unknown = [n for n in names if n not in {f['key'] for f in t['fields']} | {c['key'] for c in t['calcs']} and '_' not in n]
        messagebox.showinfo(APP, msg + (f"\n\nUnknown names: {', '.join(unknown)}" if unknown else ''), parent=self)

    def save(self):
        try:
            t = self.build()
        except ValueError as e:
            messagebox.showwarning(APP, str(e), parent=self); return
        self.db.save_test(self.mid, t); self.saved = True; self.destroy()


# ======================================================================= Library tab
class LibraryTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        left = ttk.LabelFrame(self, text=' Materials / test groups '); left.pack(side='left', fill='y', padx=6, pady=6)
        _lf = ttk.Frame(left); _lf.pack(side='top', fill='both', expand=True, padx=4, pady=4)
        self.ml = tk.Listbox(_lf, width=30, height=16, exportselection=False)
        _ls = ttk.Scrollbar(_lf, orient='vertical', command=self.ml.yview); self.ml.configure(yscrollcommand=_ls.set)
        self.ml.pack(side='left', fill='both', expand=True); _ls.pack(side='left', fill='y')
        self.ml.bind('<<ListboxSelect>>', lambda e: self.show_tests())
        for t, c in [('New material', self.new_mat), ('Edit details / pages', self.edit_mat), ('Duplicate', self.dup_mat), ('Delete', self.del_mat)]:
            ttk.Button(left, text=t, command=c).pack(fill='x', padx=4, pady=1)
        right = ttk.LabelFrame(self, text=' Tests of the selected material (order = order on report) '); right.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        ttk.Label(right, foreground='#1F3864', text='1) click a material on the left   2) click "Add test" (or select a test and "Edit test")   3) fill the form and press SAVE TEST').pack(side='top', anchor='w', padx=6, pady=3)
        bt = ttk.Frame(right); bt.pack(side='bottom', fill='x')
        for t, c in [('ADD TEST', self.add_test), ('Edit test', self.edit_test), ('Duplicate test', self.dup_test), ('Delete test', self.del_test),
                     ('Move up', lambda: self.move(-1)), ('Move down', lambda: self.move(1))]:
            ttk.Button(bt, text=t, command=c).pack(side='left', padx=3, pady=4)
        cols = [('code', 'Code', 70), ('name', 'Test', 300), ('page', 'Pg', 35), ('rep', 'In report', 65), ('limit', 'Limit', 220), ('method', 'Method', 160)]
        self.tt = tree_with_scroll(right, [c for c, _, _ in cols], height=12, side='top', fill='both', expand=True, padx=4, pady=4)
        for c, t, w in cols:
            self.tt.heading(c, text=t); self.tt.column(c, width=w)
        self.tt.bind('<Double-1>', lambda e: self.edit_test())
        self.refresh()
        gate(self, self.db, {'New material': ('library', 'add'), 'Edit details / pages': ('library', 'edit'), 'Duplicate': ('library', 'add'),
                             'Delete': ('library', 'delete'), 'ADD TEST': ('library', 'add'), 'Duplicate test': ('library', 'add'),
                             'Delete test': ('library', 'delete'), 'Move up': ('library', 'edit'), 'Move down': ('library', 'edit')})

    def refresh(self, keep=None):
        self.mats = self.db.materials(); self.ml.delete(0, 'end')
        for m in self.mats:
            self.ml.insert('end', m['name'])
        if self.mats:
            i = next((k for k, m in enumerate(self.mats) if m['id'] == keep), 0); self.ml.selection_set(i)
        self.show_tests()

    def cur(self):
        s = self.ml.curselection(); return self.mats[s[0]] if s else None

    def show_tests(self):
        self.tt.delete(*self.tt.get_children()); m = self.cur()
        if not m: return
        self.tests = self.db.tests(m['id'])
        for t in self.tests:
            self.tt.insert('', 'end', iid=str(t['id']), values=(t['code'], t['name'], t['page'], 'Yes' if t['in_report'] else '', t['limit_text'], t['method']))

    def seltest(self):
        s = self.tt.selection()
        return next((t for t in self.tests if str(t['id']) == s[0]), None) if s else None

    def mat_dialog(self, m):
        init = dict(m) if m else {}
        if m:
            init['pages'] = '\n'.join(f'{k}={v}' for k, v in sorted(json.loads(m['page_titles'] or '{}').items()))
        else:
            init['pages'] = '1=TEST ANALYSIS'
        dlg = Modal(self, 'Material', 560, 330)
        v = {k: tk.StringVar(value=init.get(k) or '') for k in ('name', 'spec', 'group_name')}
        for i, (k, lab) in enumerate([('name', 'Material name'), ('spec', 'Limits "as per" standard (heading on report)'), ('group_name', 'Group (for sorting)')]):
            ttk.Label(dlg, text=lab).grid(row=i, column=0, sticky='w', padx=8, pady=4); ttk.Entry(dlg, textvariable=v[k], width=44).grid(row=i, column=1)
        ttk.Label(dlg, text='Report page titles\n(one per line:  page=Title)').grid(row=3, column=0, sticky='nw', padx=8, pady=4)
        txt = tk.Text(dlg, width=44, height=6); txt.grid(row=3, column=1); txt.insert('1.0', init['pages'])
        out = {}

        def ok():
            name = v['name'].get().strip()
            if not name: return
            pt = {}
            for ln in txt.get('1.0', 'end').splitlines():
                if '=' in ln:
                    a, b = ln.split('=', 1); pt[a.strip()] = b.strip()
            out.update(name=name, spec=v['spec'].get().strip(), group=v['group_name'].get().strip(), pages=pt); dlg.destroy()
        ttk.Button(dlg, text='OK', command=ok).grid(row=4, column=1, pady=10, sticky='w')
        dlg.wait_window(); return out or None

    def new_mat(self):
        r = self.mat_dialog(None)
        if r:
            try: mid = self.db.add_material(r['name'], r['spec'], r['group'], r['pages'])
            except Exception as e: messagebox.showerror(APP, str(e)); return
            self.refresh(mid); self.app.refresh_materials()
            if messagebox.askyesno(APP, f"Material '{r['name']}' created.\n\nAdd its tests now (parameters, limit, method, formulas)?"):
                self.add_tests_loop(mid)

    def add_tests_loop(self, mid):
        while True:
            d = TestDialog(self, self.db, mid, None, self.db.tests(mid)); self.wait_window(d); self.show_tests()
            if not d.saved or not messagebox.askyesno(APP, 'Test saved.  Add another test to this material?'):
                break

    def edit_mat(self):
        m = self.cur()
        if not m: return
        r = self.mat_dialog(m)
        if r:
            self.db.update_material(m['id'], r['name'], r['spec'], r['group'], r['pages']); self.refresh(m['id']); self.app.refresh_materials()

    def dup_mat(self):
        m = self.cur()
        if not m: return
        n = simpledialog.askstring(APP, 'Name of the copy (e.g. OPC 53 Grade - Brand X):', initialvalue=m['name'] + ' (copy)')
        if n:
            try: mid = self.db.duplicate_material(m['id'], n)
            except Exception as e: messagebox.showerror(APP, str(e)); return
            self.refresh(mid); self.app.refresh_materials()

    def del_mat(self):
        m = self.cur()
        if m and messagebox.askyesno(APP, f"Delete '{m['name']}' and all its test definitions?\nExisting jobs of this material will lose their test layout."):
            self.db.delete_material(m['id']); self.refresh(); self.app.refresh_materials()

    def add_test(self):
        m = self.cur()
        if not m:
            messagebox.showinfo(APP, 'First click a material in the left list (or create one with "New material").'); return
        d = TestDialog(self, self.db, m['id'], None, self.tests); self.wait_window(d); self.show_tests()

    def edit_test(self):
        m, t = self.cur(), self.seltest()
        if not t:
            messagebox.showinfo(APP, 'Click a test in the list first, then press "Edit test".'); return
        d = TestDialog(self, self.db, m['id'], t, self.tests); self.wait_window(d); self.show_tests()

    def dup_test(self):
        m, t = self.cur(), self.seltest()
        if not t: return
        t = json.loads(json.dumps(t)); t['id'] = None; t['code'] += '2'; t['sort'] = max(x['sort'] for x in self.tests) + 1
        self.db.save_test(m['id'], t); self.show_tests()

    def del_test(self):
        t = self.seltest()
        if t and messagebox.askyesno(APP, f"Delete test '{t['name']}'? Readings stored for it in old jobs will no longer show."):
            self.db.delete_test(t['id']); self.show_tests()

    def move(self, d):
        t = self.seltest(); m = self.cur()
        if not t or not m:
            return
        self.db.move_test(m['id'], t['id'], d)
        self.show_tests(); self.tt.selection_set(str(t['id']))

def date_or_blank(txt):
    return d_store(txt) if (txt or '').strip() else ''


class EquipmentTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        left = ttk.LabelFrame(self, text=' Equipment register '); left.pack(side='left', fill='y', padx=6, pady=6)
        bt = ttk.Frame(left); bt.pack(side='bottom', fill='x')
        for t, c in [('Add', self.add_eq), ('Edit', self.edit_eq), ('Delete', self.del_eq)]:
            ttk.Button(bt, text=t, command=c).pack(side='left', padx=3, pady=4)
        self.et = tree_with_scroll(left, ('code', 'name', 'due'), height=16, side='top', fill='y', padx=4, pady=4)
        for c, t, w in [('code', 'ID', 70), ('name', 'Equipment', 170), ('due', 'Calibration due', 95)]:
            self.et.heading(c, text=t); self.et.column(c, width=w)
        self.et.bind('<Double-1>', lambda e: self.edit_eq())
        right = ttk.LabelFrame(self, text=' Equipment usage logbook '); right.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        ttk.Label(right, foreground='#1F3864', wrap=760, text='Entries are written AUTOMATICALLY when you save a job: for every test that has readings, the equipment ticked on that '
                  'test tab is logged with the job\'s Test Start Date. You can also add manual entries (maintenance, calibration, breakdown).').pack(side='top', anchor='w', padx=6, pady=4)
        f = ttk.Frame(right); f.pack(side='top', fill='x', padx=6)
        self.eq_var = tk.StringVar(value='All equipment'); self.d1 = tk.StringVar(); self.d2 = tk.StringVar()
        ttk.Label(f, text='Equipment').pack(side='left'); self.cb = ttk.Combobox(f, textvariable=self.eq_var, state='readonly', width=30); self.cb.pack(side='left', padx=4)
        ttk.Label(f, text='From').pack(side='left'); ttk.Entry(f, textvariable=self.d1, width=11).pack(side='left', padx=3)
        ttk.Label(f, text='To').pack(side='left'); ttk.Entry(f, textvariable=self.d2, width=11).pack(side='left', padx=3)
        ttk.Button(f, text='Show', command=self.refresh_log).pack(side='left', padx=4)
        bb = ttk.Frame(right); bb.pack(side='bottom', fill='x', pady=4)
        for t, c in [('Add manual entry', self.add_log), ('Delete manual entry', self.del_log), ('Export Excel', lambda: self.export('xlsx')), ('Export PDF', lambda: self.export('pdf'))]:
            ttk.Button(bb, text=t, command=c).pack(side='left', padx=4)
        cols = [('date', 'Date', 85), ('ecode', 'Equip. ID', 75), ('ename', 'Equipment', 160), ('job', 'Job No.', 80), ('rep', 'Report No.', 140),
                ('test', 'Test', 190), ('who', 'Analyst', 80), ('src', 'Source', 60), ('rem', 'Remarks', 140)]
        self.lt = tree_with_scroll(right, [c for c, _, _ in cols], height=16, side='top', fill='both', expand=True, padx=6, pady=4)
        for c, t, w in cols:
            self.lt.heading(c, text=t); self.lt.column(c, width=w)
        self.refresh()
        gate(self, self.db, {'Add': ('equipment', 'add'), 'Edit': ('equipment', 'edit'), 'Delete': ('equipment', 'delete'),
                             'Add manual entry': ('equipment', 'add'), 'Delete manual entry': ('equipment', 'delete')})

    def refresh(self):
        self.eqs = self.db.equipment(); self.et.delete(*self.et.get_children())
        for e in self.eqs:
            self.et.insert('', 'end', iid=str(e['id']), values=(e['code'], e['name'], d_show(e['calib_due'])))
        self.cb['values'] = ['All equipment'] + [f"{e['code']} - {e['name']}" for e in self.eqs]
        self.refresh_log()

    def sel_eq(self):
        s = self.et.selection(); return next((e for e in self.eqs if str(e['id']) == s[0]), None) if s else None

    def eq_dialog(self, e):
        init = dict(e) if e else {}
        init['calib_due'] = d_show(init.get('calib_due'))
        def val(d):
            if not d['code'].strip() or not d['name'].strip(): return 'Equipment ID and name are required.'
        r = form_dialog(self, 'Equipment', [('code', 'Equipment ID / code', 'text', 20), ('name', 'Equipment name', 'text', 50), ('make_model', 'Make / model', 'text', 40),
                                            ('location', 'Location', 'text', 30), ('calib_due', 'Calibration due (dd-mm-yyyy)', 'text', 14), ('notes', 'Notes', 'text', 50)], init, val)
        if r:
            r = {k: v.strip() for k, v in r.items()}; r['calib_due'] = date_or_blank(r['calib_due']); r['id'] = e['id'] if e else None
        return r

    def add_eq(self):
        r = self.eq_dialog(None)
        if r:
            try: self.db.save_equipment(r)
            except Exception as ex: messagebox.showerror(APP, f'Could not save (is the ID already used?)\n{ex}'); return
            self.refresh()

    def edit_eq(self):
        e = self.sel_eq()
        if not e: messagebox.showinfo(APP, 'Click an equipment in the list first.'); return
        r = self.eq_dialog(e)
        if r:
            try: self.db.save_equipment(r)
            except Exception as ex: messagebox.showerror(APP, f'Could not save\n{ex}'); return
            self.refresh()

    def del_eq(self):
        e = self.sel_eq()
        if e and messagebox.askyesno(APP, f"Delete '{e['code']} - {e['name']}' and all its logbook entries?"):
            self.db.delete_equipment(e['id']); self.refresh()

    def rows(self):
        i = self.cb.current(); eid = self.eqs[i - 1]['id'] if i > 0 else None
        return self.db.logbook(eid, date_or_blank(self.d1.get()), date_or_blank(self.d2.get()))

    def refresh_log(self):
        self.lt.delete(*self.lt.get_children()); self.cur = self.rows()
        for r in self.cur:
            self.lt.insert('', 'end', iid=str(r['id']), values=(d_show(r['log_date']), r['ecode'] or '', r['ename'] or '', r['job_no'] or '', r['report_no'] or '',
                                                                r['test_name'] or '', r['analyst'] or '', 'Auto' if r['auto'] else 'Manual', r['remarks'] or ''))

    def add_log(self):
        if not self.eqs: messagebox.showinfo(APP, 'Register equipment first.'); return
        names = [f"{e['code']} - {e['name']}" for e in self.eqs]
        r = form_dialog(self, 'Manual logbook entry', [('eq', 'Equipment', 'choice', names), ('date', 'Date (dd-mm-yyyy)', 'text', 14), ('test', 'Activity / test', 'text', 40),
                                                       ('who', 'Done by', 'text', 25), ('rem', 'Remarks', 'text', 50)],
                        {'eq': names[0], 'date': d_show(__import__('datetime').date.today().isoformat())},
                        lambda d: None if _iso_ok(d['date']) else 'Enter a valid date dd-mm-yyyy.')
        if r:
            self.db.add_log(d_store(r['date']), self.eqs[names.index(r['eq'])]['id'], r['rem'], r['who'], r['test']); self.refresh_log()

    def del_log(self):
        s = self.lt.selection()
        if not s: return
        row = next((x for x in self.cur if str(x['id']) == s[0]), None)
        if row and row['auto']:
            messagebox.showinfo(APP, 'Automatic entries follow the job. Change the equipment / dates in the job and save it.'); return
        if row and messagebox.askyesno(APP, 'Delete this manual entry?'):
            self.db.delete_log(row['id']); self.refresh_log()

    def export(self, kind):
        rows = self.rows()
        if not rows: messagebox.showinfo(APP, 'No logbook entries for this selection.'); return
        i = self.cb.current(); title = 'Equipment Usage Logbook' + (f" - {self.eqs[i - 1]['code']} {self.eqs[i - 1]['name']}" if i > 0 else '')
        p = (reports.logbook_xlsx if kind == 'xlsx' else reports.logbook_pdf)(self.db, rows, None, title)
        self.db.log_export('equipment', title, 'Logbook ' + kind.upper())
        reports.open_file(p)


def _iso_ok(txt):
    return bool(core._iso(d_store(txt)))


# ======================================================================= Chemical Standardization Record
class StdTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        ttk.Label(self, foreground='#1F3864', wrap=1150, text='Whenever a test uses a Normality or Molarity (e.g. NH4SCN, EDTA, KMnO4, HCl), a record for the TESTING DAY is saved here automatically when the job is saved. '
                  'Select a record and press "Edit" to add how it was standardised (standard used, volumes, titre); the calculated strength is worked out for you.').pack(side='top', anchor='w', padx=8, pady=6)
        f = ttk.Frame(self); f.pack(side='top', fill='x', padx=8)
        self.d1 = tk.StringVar(); self.d2 = tk.StringVar()
        ttk.Label(f, text='From').pack(side='left'); ttk.Entry(f, textvariable=self.d1, width=11).pack(side='left', padx=3)
        ttk.Label(f, text='To').pack(side='left'); ttk.Entry(f, textvariable=self.d2, width=11).pack(side='left', padx=3)
        ttk.Button(f, text='Show', command=self.refresh).pack(side='left', padx=4)
        bb = ttk.Frame(self); bb.pack(side='bottom', fill='x', padx=8, pady=6)
        for t, c in [('Edit / add standardization details', self.edit), ('Add manual record', self.add), ('Delete', self.delete),
                     ('Export Excel', lambda: self.export('xlsx')), ('Export PDF', lambda: self.export('pdf'))]:
            ttk.Button(bb, text=t, command=c).pack(side='left', padx=4)
        cols = [('date', 'Date', 80), ('reagent', 'Reagent', 170), ('type', 'Type', 60), ('value', 'Strength found', 90), ('nominal', 'Nominal', 60), ('against', 'Standardised against', 150),
                ('calc', 'Calculated', 80), ('jobs', 'Used in report no.', 230), ('who', 'Analyst', 80), ('rem', 'Remarks', 120)]
        self.tree = tree_with_scroll(self, [c for c, _, _ in cols], height=14, side='top', fill='both', expand=True, padx=8, pady=6)
        for c, t, w in cols:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.bind('<Double-1>', lambda e: self.edit())
        self.refresh()
        gate(self, self.db, {'Edit / add standardization details': ('standard', 'edit'), 'Add manual record': ('standard', 'add'), 'Delete': ('standard', 'delete')})

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = self.db.std_records(date_or_blank(self.d1.get()), date_or_blank(self.d2.get()))
        for d in self.rows:
            c = reports._calc_std(d)
            self.tree.insert('', 'end', iid=str(d['id']), values=(d_show(d['std_date']), d['reagent'], d['conc_type'], d['value'] if d['value'] is not None else '', d['nominal'] or '',
                                                                  d['against'] or '', '' if c is None else round(c, 4), d['jobs'] or '', d['analyst'] or '', d['remarks'] or ''))

    def sel(self):
        s = self.tree.selection(); return next((r for r in self.rows if str(r['id']) == s[0]), None) if s else None

    def dialog(self, d):
        init = {k: ('' if v is None else v) for k, v in (d or {}).items()}
        init['std_date'] = d_show(init.get('std_date', '')) or d_show(__import__('datetime').date.today().isoformat())
        init['conc_sel'] = 'Molarity (M)' if init.get('conc_type') == 'M' else 'Normality (N)'
        spec = [('std_date', 'Date of standardization (dd-mm-yyyy)', 'text', 14), ('reagent', 'Reagent / solution', 'text', 40), ('conc_sel', 'Type', 'choice', ['Normality (N)', 'Molarity (M)']),
                ('value', 'Strength used / found', 'text', 12), ('nominal', 'Nominal (e.g. 0.1 N)', 'text', 12), ('against', 'Standardised against (primary standard)', 'text', 40),
                ('n_std', 'Strength of standard (N1)', 'text', 12), ('v_std', 'Volume of standard taken (ml) (V1)', 'text', 12), ('v_tit', 'Titre of this reagent (ml) (V2)', 'text', 12),
                ('analyst', 'Analyst', 'text', 25), ('remarks', 'Remarks', 'text', 50)]
        def val(x):
            if not _iso_ok(x['std_date']): return 'Enter a valid date dd-mm-yyyy.'
            if not x['reagent'].strip(): return 'Reagent name is required.'
        r = form_dialog(self, 'Chemical standardization', spec, init, val)
        if not r: return None
        out = dict(id=d['id'] if d else None, std_date=d_store(r['std_date']), reagent=r['reagent'].strip(), conc_type='M' if r['conc_sel'].startswith('M') else 'N',
                   value=core.to_num(r['value']), nominal=r['nominal'].strip(), against=r['against'].strip(), n_std=core.to_num(r['n_std']), v_std=core.to_num(r['v_std']),
                   v_tit=core.to_num(r['v_tit']), analyst=r['analyst'].strip(), remarks=r['remarks'].strip())
        return out

    def add(self):
        r = self.dialog(None)
        if r: self.db.save_std(r); self.refresh()

    def edit(self):
        d = self.sel()
        if not d: messagebox.showinfo(APP, 'Click a record first.'); return
        r = self.dialog(d)
        if r: self.db.save_std(r); self.refresh()

    def delete(self):
        d = self.sel()
        if d and messagebox.askyesno(APP, 'Delete this record? (It is created again if a saved job still uses it.)'):
            self.db.delete_std(d['id']); self.refresh()

    def export(self, kind):
        rows = self.db.std_records(date_or_blank(self.d1.get()), date_or_blank(self.d2.get()))
        if not rows: messagebox.showinfo(APP, 'No records for this selection.'); return
        p = (reports.std_xlsx if kind == 'xlsx' else reports.std_pdf)(self.db, rows)
        self.db.log_export('standard', 'Chemical Standardization Record', kind.upper())
        reports.open_file(p)


# ======================================================================= Settings tab
class SettingsTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        sf = ScrollFrame(self); sf.pack(fill='both', expand=True); P = sf.inner
        self.w = {}
        spec = [('lab_name', 'Laboratory name', 1), ('location', 'Testing location (printed on reports)', 2), ('letterhead_mm', 'Blank space at top of report for letterhead (mm)', 1),
                ('reviewers', 'Reviewed & Authorised by - names (one per line)', 4), ('analysts', 'Analysts / technicians (one per line)', 4),
                ('notes', 'Notes printed on every report (one per line)', 6)]
        for i, (k, lab, h) in enumerate(spec):
            ttk.Label(P, text=lab).grid(row=i, column=0, sticky='nw', padx=10, pady=6)
            t = tk.Text(P, width=80, height=h); t.insert('1.0', self.db.setting(k)); t.grid(row=i, column=1, pady=4, sticky='w'); self.w[k] = t
        r = len(spec)
        self.credit = tk.BooleanVar(value=self.db.setting('credit_on_reports') == '1')
        self.logo_obs = tk.BooleanVar(value=self.db.setting('logo_on_obs') != '0')
        self.logo_rep = tk.BooleanVar(value=self.db.setting('logo_on_reports') == '1')
        ttk.Checkbutton(P, text='Print "Software by Mr. Ganesh Raykar" in the footer of PDFs / Excel files', variable=self.credit).grid(row=r, column=1, sticky='w', padx=4); r += 1
        ttk.Checkbutton(P, text='Print the logo on Observation Sheets (PDF / Excel)', variable=self.logo_obs).grid(row=r, column=1, sticky='w', padx=4); r += 1
        ttk.Checkbutton(P, text='Print the logo on Test Reports (leave off if you print on letterhead paper)', variable=self.logo_rep).grid(row=r, column=1, sticky='w', padx=4); r += 1
        lf = ttk.LabelFrame(P, text=' Logo '); lf.grid(row=r, column=1, sticky='w', padx=4, pady=8); r += 1
        self.preview = tk.Label(lf); self.preview.pack(side='left', padx=8, pady=6); self.show_logo()
        ttk.Button(lf, text='Choose logo file...', command=self.choose_logo).pack(side='left', padx=4)
        ttk.Button(lf, text='Reset to default logo', command=self.reset_logo).pack(side='left', padx=4)
        bt = ttk.Frame(P); bt.grid(row=r, column=1, sticky='w', pady=10); r += 1
        for t, c in [('Save settings', self.save), ('Backup database now', self.backup), ('Export everything to Excel', self.export)]:
            ttk.Button(bt, text=t, command=c).pack(side='left', padx=4)
        ttk.Label(P, foreground='#666', text=f'Data folder: {core.DATA_DIR}').grid(row=r, column=1, sticky='w')
        gate(self, self.db, {'Save settings': ('settings', 'edit'), 'Backup database now': ('settings', 'edit'),
                             'Choose logo file...': ('settings', 'edit'), 'Reset to default logo': ('settings', 'edit')})

    def show_logo(self):
        self._img = branding.tk_photo(tk, 70); self.preview.configure(image=self._img)

    def choose_logo(self):
        p = filedialog.askopenfilename(title='Choose logo', filetypes=[('Images', '*.png *.jpg *.jpeg *.bmp *.gif'), ('All files', '*.*')])
        if p:
            self.db.require('settings', 'edit')
            try: branding.set_custom(p)
            except Exception as ex: messagebox.showerror(APP, f'Could not use this image:\n{ex}'); return
            self.db.audit('settings', 'edit', 'logo', [core._chg('Logo', 'previous', 'new file: ' + os.path.basename(p))])
            self.show_logo(); self.app.refresh_logo()

    def reset_logo(self):
        self.db.require('settings', 'edit'); branding.reset_custom()
        self.db.audit('settings', 'edit', 'logo', [core._chg('Logo', 'custom', 'default')])
        self.show_logo(); self.app.refresh_logo()

    def save(self):
        for k, t in self.w.items():
            self.db.set_setting(k, t.get('1.0', 'end').strip())
        self.db.set_setting('credit_on_reports', '1' if self.credit.get() else '0')
        self.db.set_setting('logo_on_obs', '1' if self.logo_obs.get() else '0')
        self.db.set_setting('logo_on_reports', '1' if self.logo_rep.get() else '0')
        messagebox.showinfo(APP, 'Settings saved.')

    def backup(self):
        messagebox.showinfo(APP, 'Backup created:\n' + self.db.backup())

    def export(self):
        self.db.require('jobs', 'view')
        p = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')], initialfile='LabReportPro_Export.xlsx')
        if p:
            reports.export_excel(self.db, p); self.db.log_export('jobs', 'All jobs', 'Excel export of register, results, observations')
            messagebox.showinfo(APP, 'Exported.'); reports.open_file(p)


# ======================================================================= Login / users / audit
def center_auto(win):
    """Size the window to its content (so no button is ever cut off, whatever the Windows text scaling) and centre it."""
    win.update_idletasks()
    w, h = max(win.winfo_reqwidth(), 360), win.winfo_reqheight() + 6
    win.minsize(w, h)
    win.geometry(f'+{max(0, (win.winfo_screenwidth() - w) // 2)}+{max(0, (win.winfo_screenheight() - h) // 3)}')


def center(win, w, h):
    win.update_idletasks()
    win.geometry(f'{w}x{h}+{(win.winfo_screenwidth() - w) // 2}+{(win.winfo_screenheight() - h) // 3}')


class LoginDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app, self.db, self.ok = app, app.db, False
        self.title(f'{APP} - Login'); self.configure(bg='white')
        self._logo = branding.tk_photo(tk, 70)
        tk.Label(self, image=self._logo, bg='white').pack(pady=(14, 2), padx=30)
        tk.Label(self, text=APP, font=('', 15, 'bold'), bg='white', fg='#1F3864').pack()
        tk.Label(self, text=self.db.setting('lab_name'), bg='white', fg='#555').pack(pady=(0, 8))
        f = tk.Frame(self, bg='white'); f.pack(padx=20)
        self.u = tk.StringVar(); self.p = tk.StringVar()
        tk.Label(f, text='User name', bg='white').grid(row=0, column=0, sticky='e', padx=6, pady=4)
        e1 = ttk.Entry(f, textvariable=self.u, width=26); e1.grid(row=0, column=1)
        tk.Label(f, text='Password', bg='white').grid(row=1, column=0, sticky='e', padx=6, pady=4)
        e2 = ttk.Entry(f, textvariable=self.p, show='*', width=26); e2.grid(row=1, column=1)
        self.msg = tk.Label(self, text='', fg='#C00000', bg='white', wraplength=330); self.msg.pack(pady=4)
        b = tk.Frame(self, bg='white'); b.pack(pady=4)
        ttk.Button(b, text='LOGIN', command=self.go, width=12).pack(side='left', padx=6)
        ttk.Button(b, text='Exit', command=self.cancel, width=8).pack(side='left', padx=6)
        fp = tk.Label(self, text='Forgot password?', fg='#0563C1', bg='white', cursor='hand2', font=('', 9, 'underline')); fp.pack(pady=(6, 2))
        fp.bind('<Button-1>', lambda e: self.forgot())
        tk.Label(self, text='Software by Mr. Ganesh Raykar', fg='#888', bg='white', font=('', 8)).pack(pady=(8, 10))
        self.bind('<Return>', lambda e: self.go()); self.protocol('WM_DELETE_WINDOW', self.cancel)
        center_auto(self); e1.focus_set(); self.lift(); self.attributes('-topmost', True); self.after(300, lambda: self.attributes('-topmost', False))
        self.grab_set(); self.wait_window(self)

    def go(self):
        u, m = self.db.login(self.u.get(), self.p.get())
        if u:
            self.ok = True; self.destroy()
        else:
            self.msg.config(text=m); self.p.set('')

    def forgot(self):
        ForgotPasswordDialog(self, self.db, self.u.get())

    def cancel(self):
        self.ok = False; self.destroy()


def show_recovery_code(parent, code, first=False):
    """Shows a recovery code once; the user must confirm that it has been saved."""
    d = tk.Toplevel(parent); d.title('Recovery code'); d.resizable(False, False)
    ttk.Label(d, text='Your RECOVERY CODE', font=('', 12, 'bold')).pack(padx=20, pady=(14, 4))
    ttk.Label(d, wraplength=420, justify='left', foreground='#555', text='If you ever forget the Administrator password, this code lets you set a new one from the login window '
              '("Forgot password?"). It is shown ONLY NOW. Write it down and keep it in a safe place (not on this PC). Each code works once; a new one is issued after use.').pack(padx=20)
    e = ttk.Entry(d, width=26, font=('Courier', 14, 'bold'), justify='center'); e.insert(0, code); e.configure(state='readonly'); e.pack(pady=10)
    def copy():
        d.clipboard_clear(); d.clipboard_append(code); copy_b.config(text='Copied')
    b = ttk.Frame(d); b.pack(pady=(0, 14)); copy_b = ttk.Button(b, text='Copy', command=copy); copy_b.pack(side='left', padx=6)
    ttk.Button(b, text='I have saved it', command=d.destroy).pack(side='left', padx=6)
    center_auto(d); d.attributes('-topmost', True); d.grab_set(); d.wait_window(d)


class ForgotPasswordDialog(tk.Toplevel):
    def __init__(self, parent, db, username=''):
        super().__init__(parent)
        self.db = db; self.title('Forgot password'); self.resizable(False, False)
        ttk.Label(self, text='Forgot password?', font=('', 12, 'bold')).pack(padx=20, pady=(14, 4), anchor='w')
        ttk.Label(self, wraplength=430, justify='left', foreground='#444', text='STAFF / ANALYSTS: ask your Administrator to reset it (Users & Permissions -> Reset password). '
                  'You will then get a temporary password and choose your own at first login.').pack(padx=20, anchor='w')
        ttk.Separator(self).pack(fill='x', padx=20, pady=8)
        ttk.Label(self, wraplength=430, justify='left', text='ADMINISTRATOR: enter your user name, the Recovery Code given when the account was created, and a new password.').pack(padx=20, anchor='w')
        f = ttk.Frame(self); f.pack(padx=20, pady=6)
        self.v = {k: tk.StringVar() for k in ('user', 'code', 'pw', 'pw2')}; self.v['user'].set(username)
        for i, (k, lab, show) in enumerate([('user', 'User name', ''), ('code', 'Recovery code', ''), ('pw', 'New password', '*'), ('pw2', 'Repeat new password', '*')]):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky='e', padx=6, pady=3); ttk.Entry(f, textvariable=self.v[k], show=show, width=30).grid(row=i, column=1)
        self.msg = ttk.Label(self, text='', foreground='#C00000', wraplength=430); self.msg.pack(padx=20, pady=2)
        b = ttk.Frame(self); b.pack(pady=(4, 14)); ttk.Button(b, text='Reset password', command=self.go).pack(side='left', padx=6); ttk.Button(b, text='Close', command=self.destroy).pack(side='left')
        center_auto(self); self.attributes('-topmost', True); self.grab_set(); self.wait_window(self)

    def go(self):
        v = {k: x.get() for k, x in self.v.items()}
        if v['pw'] != v['pw2']:
            self.msg.config(text='The two passwords do not match.'); return
        try:
            new_code = self.db.recover_password(v['user'], v['code'], v['pw'])
        except ValueError as e:
            self.msg.config(text=str(e)); return
        messagebox.showinfo(APP, 'Password reset. You can log in now.', parent=self)
        show_recovery_code(self, new_code)
        self.destroy()


class FirstRunDialog(tk.Toplevel):
    """Very first start: create the Administrator (no default password exists)."""
    def __init__(self, app):
        super().__init__(app)
        self.db, self.ok = app.db, False
        self.title(f'{APP} - create Administrator'); self.resizable(False, False)
        ttk.Label(self, text='Welcome! Create the Administrator account.', font=('', 12, 'bold')).pack(pady=(14, 2))
        ttk.Label(self, wraplength=420, foreground='#555', text='The Administrator creates the other users and decides what each user may view, add, edit or delete. '
                  'Remember this password - there is no default and no recovery without it.').pack(pady=4)
        f = ttk.Frame(self); f.pack(pady=6)
        self.v = {k: tk.StringVar() for k in ('name', 'user', 'pw', 'pw2')}
        for i, (k, lab, show) in enumerate([('name', 'Full name', ''), ('user', 'User name', ''), ('pw', 'Password', '*'), ('pw2', 'Repeat password', '*')]):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky='e', padx=6, pady=4); ttk.Entry(f, textvariable=self.v[k], show=show, width=30).grid(row=i, column=1)
        ttk.Label(self, text='Password: at least 8 characters, letters and digits.', foreground='#777').pack()
        self.msg = ttk.Label(self, text='', foreground='#C00000'); self.msg.pack(pady=4)
        b = ttk.Frame(self); b.pack(); ttk.Button(b, text='Create Administrator', command=self.go).pack(side='left', padx=6); ttk.Button(b, text='Exit', command=self.destroy).pack(side='left')
        self.protocol('WM_DELETE_WINDOW', self.destroy); center_auto(self); self.attributes('-topmost', True); self.after(300, lambda: self.attributes('-topmost', False))
        self.grab_set(); self.wait_window(self)

    def go(self):
        v = {k: x.get() for k, x in self.v.items()}
        if not v['name'].strip():
            self.msg.config(text='Enter the full name.'); return
        if v['pw'] != v['pw2']:
            self.msg.config(text='The two passwords do not match.'); return
        try:
            code = self.db.create_user(v['user'], v['name'], v['pw'], 'Administrator', {}, must_change=False)
        except ValueError as e:
            self.msg.config(text=str(e)); return
        self.ok = True
        if code:
            show_recovery_code(self, code, first=True)
        self.destroy()


class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, db, forced=False):
        super().__init__(parent)
        self.db, self.ok, self.forced = db, False, forced
        self.title('Change password'); self.resizable(False, False)
        ttk.Label(self, text='You must set a new password before continuing.' if forced else 'Change your password', font=('', 11, 'bold')).pack(pady=(14, 6))
        f = ttk.Frame(self); f.pack()
        self.v = {k: tk.StringVar() for k in ('old', 'new', 'new2')}
        for i, (k, lab) in enumerate([('old', 'Current password'), ('new', 'New password'), ('new2', 'Repeat new password')]):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky='e', padx=6, pady=4); ttk.Entry(f, textvariable=self.v[k], show='*', width=28).grid(row=i, column=1)
        ttk.Label(self, text='At least 8 characters, letters and digits.', foreground='#777').pack()
        self.msg = ttk.Label(self, text='', foreground='#C00000', wraplength=380); self.msg.pack(pady=4)
        b = ttk.Frame(self); b.pack(); ttk.Button(b, text='Change password', command=self.go).pack(side='left', padx=6)
        ttk.Button(b, text='Cancel', command=self.destroy).pack(side='left')
        center_auto(self); self.attributes('-topmost', True); self.after(300, lambda: self.attributes('-topmost', False)); self.grab_set(); self.wait_window(self)

    def go(self):
        v = {k: x.get() for k, x in self.v.items()}
        if v['new'] != v['new2']:
            self.msg.config(text='The two new passwords do not match.'); return
        try:
            self.db.change_password(v['old'], v['new'])
        except ValueError as e:
            self.msg.config(text=str(e)); return
        self.ok = True; messagebox.showinfo(APP, 'Password changed.', parent=self); self.destroy()


class UserDialog(Modal):
    """Add / edit a user and allocate the sections they may use."""
    ACTS = ['view', 'add', 'edit', 'delete']

    def __init__(self, parent, db, user=None):
        super().__init__(parent, 'User' if not user else f"User - {user['username']}", 640, 640)
        self.db, self.user, self.saved = db, user, False
        bt = ttk.Frame(self); bt.pack(side='bottom', pady=8)
        ttk.Button(bt, text='SAVE USER', command=self.save).pack(side='left', padx=6); ttk.Button(bt, text='Cancel', command=self.destroy).pack(side='left')
        sf = ScrollFrame(self); sf.pack(side='top', fill='both', expand=True); P = sf.inner
        self.name = tk.StringVar(value=(user or {}).get('full_name', '')); self.un = tk.StringVar(value=(user or {}).get('username', ''))
        self.pw = tk.StringVar(); self.role = tk.StringVar(value=(user or {}).get('role', 'Analyst')); self.active = tk.BooleanVar(value=bool((user or {}).get('active', 1)))
        rows = [('User name', ttk.Entry(P, textvariable=self.un, width=30, state='normal' if not user else 'disabled')),
                ('Full name', ttk.Entry(P, textvariable=self.name, width=40))]
        if not user:
            rows.append(('Temporary password', ttk.Entry(P, textvariable=self.pw, width=30)))
        cb = ttk.Combobox(P, textvariable=self.role, values=list(core.ROLE_TEMPLATES), state='readonly', width=28); cb.bind('<<ComboboxSelected>>', lambda e: self.apply_role())
        rows.append(('Role (template)', cb)); rows.append(('Account active', ttk.Checkbutton(P, variable=self.active)))
        for i, (lab, w) in enumerate(rows):
            ttk.Label(P, text=lab).grid(row=i, column=0, sticky='w', padx=10, pady=4); w.grid(row=i, column=1, sticky='w', padx=4)
        if not user:
            ttk.Label(P, text='The user must change this password at first login.', foreground='#777').grid(row=len(rows), column=1, sticky='w', padx=4)
        r0 = len(rows) + 1
        ttk.Label(P, text='Allocate sections (tick what this user may do):', font=('', 10, 'bold')).grid(row=r0, column=0, columnspan=2, sticky='w', padx=10, pady=(10, 2))
        mx = ttk.Frame(P); mx.grid(row=r0 + 1, column=0, columnspan=2, sticky='w', padx=10)
        for j, a in enumerate(self.ACTS):
            ttk.Label(mx, text=a.capitalize(), font=('', 9, 'bold')).grid(row=0, column=1 + j, padx=10)
        self.cells = {}
        cur = json.loads((user or {}).get('perms') or '{}')
        for i, (sec, name, acts) in enumerate(core.SECTIONS, 1):
            ttk.Label(mx, text=name).grid(row=i, column=0, sticky='w', pady=2)
            for j, a in enumerate(self.ACTS):
                if a in acts:
                    v = tk.BooleanVar(value=a in cur.get(sec, [])); c = ttk.Checkbutton(mx, variable=v); c.grid(row=i, column=1 + j); self.cells[(sec, a)] = (v, c)
        if not user:
            self.apply_role()
        else:
            self.refresh_state()
        ttk.Label(P, wraplength=560, foreground='#555', text='Tip: "Delete" and "Edit" are what protect your records. Give analysts View + Add (+ Edit on Jobs) '
                  'and keep Delete for the Administrator. Every change anyone makes is written to the Audit Trail.').grid(row=r0 + 2, column=0, columnspan=2, sticky='w', padx=10, pady=8)

    def apply_role(self):
        t = core.ROLE_TEMPLATES.get(self.role.get(), {})
        if self.role.get() != 'Custom':
            for (sec, a), (v, c) in self.cells.items():
                v.set(a in t.get(sec, []))
        self.refresh_state()

    def refresh_state(self):
        adm = self.role.get() == 'Administrator'
        for (sec, a), (v, c) in self.cells.items():
            if adm: v.set(True)
            c.state(['disabled'] if adm else ['!disabled'])

    def save(self):
        perms = {}
        for (sec, a), (v, c) in self.cells.items():
            if v.get(): perms.setdefault(sec, []).append(a)
        try:
            if self.user:
                self.db.update_user(self.user['id'], self.name.get(), self.role.get(), perms, self.active.get())
            else:
                if not self.name.get().strip(): raise ValueError('Enter the full name.')
                code = self.db.create_user(self.un.get(), self.name.get(), self.pw.get(), self.role.get(), perms)
                if code:
                    show_recovery_code(self, code)
        except (ValueError, PermissionError) as e:
            messagebox.showwarning(APP, str(e), parent=self); return
        self.saved = True; self.destroy()


class UsersTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        ttk.Label(self, foreground='#1F3864', wraplength=1100, text='Only the Administrator (or a user given the "Users" section) can add users and decide what each person may view, add, edit or delete. '
                  'Wrong password 5 times locks an account - unlock it here.').pack(side='top', anchor='w', padx=8, pady=6)
        bb = ttk.Frame(self); bb.pack(side='bottom', fill='x', padx=8, pady=6)
        for t, c in [('Add user', self.add), ('Edit user / permissions', self.edit), ('Reset password', self.reset), ('Unlock account', self.unlock), ('Delete user', self.delete), ('My recovery code (new)', self.my_code)]:
            ttk.Button(bb, text=t, command=c).pack(side='left', padx=4)
        cols = [('user', 'User name', 120), ('name', 'Full name', 180), ('role', 'Role', 110), ('active', 'Active', 55), ('locked', 'Locked', 55),
                ('last', 'Last login', 130), ('perm', 'Allocated sections', 520)]
        self.tree = tree_with_scroll(self, [c for c, _, _ in cols], height=14, side='top', fill='both', expand=True, padx=8, pady=4)
        for c, t, w in cols:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.bind('<Double-1>', lambda e: self.edit())
        self.refresh()
        gate(self, self.db, {'Add user': ('users', 'add'), 'Edit user / permissions': ('users', 'edit'), 'Reset password': ('users', 'edit'),
                             'Unlock account': ('users', 'edit'), 'Delete user': ('users', 'delete')})

    def refresh(self):
        self.tree.delete(*self.tree.get_children()); self.rows = self.db.users()
        for u in self.rows:
            self.tree.insert('', 'end', iid=str(u['id']), values=(u['username'], u['full_name'], u['role'], 'Yes' if u['active'] else 'No', 'LOCKED' if u['locked'] else '',
                                                                  (u['last_login'] or '').replace('T', ' '), DB.perm_text(json.loads(u['perms'] or '{}'), u['role'])))

    def sel(self):
        s = self.tree.selection(); return next((u for u in self.rows if str(u['id']) == s[0]), None) if s else None

    def add(self):
        d = UserDialog(self, self.db); self.wait_window(d); self.refresh()

    def edit(self):
        u = self.sel()
        if not u: messagebox.showinfo(APP, 'Click a user first.'); return
        d = UserDialog(self, self.db, u); self.wait_window(d); self.refresh()

    def reset(self):
        u = self.sel()
        if not u: return
        pw = simpledialog.askstring(APP, f"New temporary password for {u['username']}\n(user must change it at next login):", parent=self)
        if pw:
            try: self.db.reset_password(u['id'], pw)
            except ValueError as e: messagebox.showwarning(APP, str(e)); return
            messagebox.showinfo(APP, 'Password reset. Tell the user the temporary password.'); self.refresh()

    def unlock(self):
        u = self.sel()
        if u: self.db.unlock_user(u['id']); self.refresh()

    def my_code(self):
        try:
            code = self.db.new_recovery_code()
        except PermissionError as e:
            messagebox.showwarning(APP, str(e)); return
        show_recovery_code(self, code)

    def delete(self):
        u = self.sel()
        if u and messagebox.askyesno(APP, f"Delete user '{u['username']}'?\n(Disabling the account instead keeps it for the record.)"):
            try: self.db.delete_user(u['id'])
            except ValueError as e: messagebox.showwarning(APP, str(e)); return
            self.refresh()


SECTION_SHOW = dict(core.SECTION_NAME); SECTION_SHOW['security'] = 'Login / Security'


class AuditTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.nb); self.app, self.db = app, app.db
        ttk.Label(self, foreground='#1F3864', wraplength=1100, text='Every login, save, edit, delete, export and permission change is recorded automatically with the actual date, time, user, section and the '
                  'old -> new values. Entries cannot be edited or deleted; "Verify integrity" detects any tampering.').pack(side='top', anchor='w', padx=8, pady=4)
        f = ttk.Frame(self); f.pack(side='top', fill='x', padx=8)
        self.d1, self.d2, self.us, self.se, self.tx = (tk.StringVar() for _ in range(5))
        ttk.Label(f, text='From').pack(side='left'); ttk.Entry(f, textvariable=self.d1, width=11).pack(side='left', padx=3)
        ttk.Label(f, text='To').pack(side='left'); ttk.Entry(f, textvariable=self.d2, width=11).pack(side='left', padx=3)
        ttk.Label(f, text='User').pack(side='left'); self.ucb = ttk.Combobox(f, textvariable=self.us, state='readonly', width=14); self.ucb.pack(side='left', padx=3)
        ttk.Label(f, text='Section').pack(side='left'); self.scb = ttk.Combobox(f, textvariable=self.se, state='readonly', width=24)
        self.scb['values'] = ['All sections'] + list(SECTION_SHOW.values()); self.scb.current(0); self.scb.pack(side='left', padx=3)
        ttk.Label(f, text='Search').pack(side='left'); ttk.Entry(f, textvariable=self.tx, width=18).pack(side='left', padx=3)
        ttk.Button(f, text='Show', command=self.refresh).pack(side='left', padx=4)
        bb = ttk.Frame(self); bb.pack(side='bottom', fill='x', padx=8, pady=6)
        for t, c in [('Verify integrity', self.verify), ('Export Excel', lambda: self.export('xlsx')), ('Export PDF', lambda: self.export('pdf'))]:
            ttk.Button(bb, text=t, command=c).pack(side='left', padx=4)
        dfr = ttk.LabelFrame(self, text=' Changes in the selected entry (old -> new) '); dfr.pack(side='bottom', fill='x', padx=8, pady=4)
        self.det = tk.Text(dfr, height=7, wrap='word', state='disabled'); ds = ttk.Scrollbar(dfr, orient='vertical', command=self.det.yview); self.det.configure(yscrollcommand=ds.set)
        self.det.pack(side='left', fill='x', expand=True); ds.pack(side='left', fill='y')
        cols = [('date', 'Date', 85), ('time', 'Time', 70), ('user', 'User', 100), ('section', 'Section', 170), ('action', 'Action', 100), ('ref', 'Record', 220), ('chg', 'Changes (first)', 360)]
        self.tree = tree_with_scroll(self, [c for c, _, _ in cols], height=12, side='top', fill='both', expand=True, padx=8, pady=4)
        for c, t, w in cols:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.show_det())
        self.refresh()

    @staticmethod
    def lines(row):
        out = []
        for d in json.loads(row['details'] or '[]'):
            o, n = d.get('old', ''), d.get('new', '')
            out.append(f"{d['field']}:  " + (f"'{o}'  ->  '{n}'" if o != '' and n != '' else (f"'{n}'" if n != '' else f"was '{o}'")))
        return out

    def rows(self):
        users = [r['user'] for r in self.db.audit_rows()]
        names = ['All users'] + sorted(set(users)); self.ucb['values'] = names
        if not self.us.get(): self.us.set('All users')
        sec = ''
        if self.scb.current() > 0:
            sec = list(SECTION_SHOW)[self.scb.current() - 1]
        return self.db.audit_rows(date_or_blank(self.d1.get()), date_or_blank(self.d2.get()), '' if self.us.get() in ('', 'All users') else self.us.get(), sec, self.tx.get().strip())

    def refresh(self):
        self.tree.delete(*self.tree.get_children()); self.cur = self.rows()
        for r in self.cur:
            ln = self.lines(r)
            self.tree.insert('', 'end', iid=str(r['id']), values=(d_show(r['ts'][:10]), r['ts'][11:], r['user'], SECTION_SHOW.get(r['section'], r['section']), r['action'], r['ref'] or '', (ln[0][:70] + ('  (+%d more)' % (len(ln) - 1) if len(ln) > 1 else '')) if ln else ''))
        self.show_det()

    def show_det(self):
        s = self.tree.selection(); row = next((r for r in self.cur if str(r['id']) == s[0]), None) if s else None
        self.det.configure(state='normal'); self.det.delete('1.0', 'end')
        if row:
            self.det.insert('1.0', f"{d_show(row['ts'][:10])} {row['ts'][11:]}   |   {row['user']}   |   {SECTION_SHOW.get(row['section'], row['section'])}   |   {row['action']}   |   {row['ref']}\n\n" + '\n'.join(self.lines(row)))
        self.det.configure(state='disabled')

    def verify(self):
        ok, msg = self.db.verify_audit()
        (messagebox.showinfo if ok else messagebox.showerror)(APP, msg)

    def export(self, kind):
        rows = self.rows()
        if not rows: messagebox.showinfo(APP, 'No entries for this selection.'); return
        p = (reports.audit_xlsx if kind == 'xlsx' else reports.audit_pdf)(self.db, list(reversed(rows)), SECTION_SHOW)
        self.db.log_export('audit', 'Audit Trail', kind.upper()); reports.open_file(p)


# ======================================================================= Main window
class App(tk.Tk):
    def __init__(self, test_login=None):
        super().__init__()
        self.withdraw(); self.title(f'{APP} - Material Testing Reports'); self.test_login = test_login
        self.geometry(f'{min(1250, self.winfo_screenwidth() - 40)}x{min(720, self.winfo_screenheight() - 90)}+10+10')
        self.db = DB(); self.ready = False
        st = ttk.Style(self)
        try: st.theme_use('vista' if sys.platform.startswith('win') else 'clam')
        except tk.TclError: pass
        install_wheel(self)
        self._icon = branding.tk_photo(tk, 64)
        try: self.iconphoto(True, self._icon)
        except tk.TclError: pass
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.ready = self.start_session()
        if not self.ready:
            self.destroy()

    # ---- session
    def start_session(self):
        if not self.db.has_users():
            if self.test_login:
                self.db.create_user(self.test_login[0], 'Test Admin', self.test_login[1], 'Administrator', {}, must_change=False)
            elif not FirstRunDialog(self).ok:
                return False
        if self.test_login:
            u, m = self.db.login(*self.test_login)
            if not u: return False
        else:
            if not LoginDialog(self).ok:
                return False
        if self.db.user['must_change']:
            if not ChangePasswordDialog(self, self.db, forced=True).ok:
                self.db.logout(); return False
        self.build_ui(); self.deiconify(); self.lift()
        u = self.db.user
        if u['role'] == 'Administrator' and not self.test_login and not self.db.c.execute('SELECT recovery_hash FROM users WHERE id=?', (u['id'],)).fetchone()[0]:
            messagebox.showinfo(APP, 'Your Administrator account has no recovery code yet.\nA code is created now - write it down. It lets you reset a forgotten password.', parent=self)
            show_recovery_code(self, self.db.new_recovery_code())
        return True

    def logout(self):
        for w in list(self.winfo_children()):
            if isinstance(w, tk.Toplevel): w.destroy()
        for w in list(self.winfo_children()):
            w.destroy()
        self.db.logout(); self.test_login = None; self.withdraw()
        self.ready = self.start_session()
        if not self.ready:
            self.destroy()

    def on_close(self):
        if self.db.user: self.db.logout()
        self.destroy()

    def report_callback_exception(self, exc, val, tb):
        import sqlite3, traceback
        if isinstance(val, (PermissionError, ValueError)):
            messagebox.showwarning(APP, str(val))
        elif isinstance(val, sqlite3.IntegrityError):
            messagebox.showerror(APP, 'This record already exists or conflicts with another one.\n' + str(val))
        else:
            try:
                with open(os.path.join(core.DATA_DIR, 'error.log'), 'a', encoding='utf-8') as f:
                    f.write(''.join(traceback.format_exception(exc, val, tb)) + '\n')
            except OSError:
                pass
            messagebox.showerror(APP, f'Unexpected error:\n{val}\n\n(details saved in LabData\\error.log)')

    # ---- UI
    def build_ui(self):
        u = self.db.user
        self.banner = tk.Frame(self, bg='white', highlightbackground='#cccccc', highlightthickness=1); self.banner.pack(side='top', fill='x')
        self.logo_lbl = tk.Label(self.banner, bg='white'); self.logo_lbl.pack(side='left', padx=10, pady=4); self.refresh_logo()
        tf = tk.Frame(self.banner, bg='white'); tf.pack(side='left', padx=4)
        tk.Label(tf, text=APP, font=('', 15, 'bold'), bg='white', fg='#1F3864').pack(anchor='w')
        self.lab_lbl = tk.Label(tf, text=self.db.setting('lab_name'), bg='white', fg='#555'); self.lab_lbl.pack(anchor='w')
        rf = tk.Frame(self.banner, bg='white'); rf.pack(side='right', padx=10)
        tk.Label(rf, text=f"Logged in: {u['full_name'] or u['username']}  ({u['role']})", bg='white', fg='#1F3864', font=('', 9, 'bold')).pack(anchor='e')
        bf = tk.Frame(rf, bg='white'); bf.pack(anchor='e', pady=2)
        ttk.Button(bf, text='Change password', command=lambda: ChangePasswordDialog(self, self.db)).pack(side='left', padx=3)
        ttk.Button(bf, text='Log out', command=self.logout).pack(side='left', padx=3)
        foot = ttk.Frame(self); foot.pack(side='bottom', fill='x')
        ttk.Label(foot, text='  Software by Mr. Ganesh Raykar', foreground='#555').pack(side='left')
        ttk.Button(foot, text='About', command=self.about).pack(side='right', padx=6, pady=2)
        self.nb = ttk.Notebook(self); self.nb.pack(side='top', fill='both', expand=True)
        self.tree = self.lib = self.eq_tab = self.std_tab = self.users_tab = self.audit_tab = None
        if self.db.can('jobs', 'view'): self.build_jobs_tab()
        if self.db.can('library', 'view'): self.lib = LibraryTab(self); self.nb.add(self.lib, text='  Test Library  ')
        if self.db.can('equipment', 'view'): self.eq_tab = EquipmentTab(self); self.nb.add(self.eq_tab, text='  Equipment & Logbook  ')
        if self.db.can('standard', 'view'): self.std_tab = StdTab(self); self.nb.add(self.std_tab, text='  Chemical Standardization Record  ')
        if self.db.can('users', 'view'): self.users_tab = UsersTab(self); self.nb.add(self.users_tab, text='  Users & Permissions  ')
        if self.db.can('audit', 'view'): self.audit_tab = AuditTab(self); self.nb.add(self.audit_tab, text='  Audit Trail  ')
        if self.db.can('settings', 'view'): self.set_tab = SettingsTab(self); self.nb.add(self.set_tab, text='  Settings & Backup  ')
        if not self.nb.tabs():
            ttk.Label(self.nb, text='No sections are allocated to your account. Please contact the Administrator.').pack(pady=40)
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.on_tab())

    def on_tab(self):
        cur = self.nametowidget(self.nb.select()) if self.nb.tabs() else None
        for tab in (self.audit_tab, self.users_tab, self.eq_tab, self.std_tab):
            if tab is not None and cur is tab:
                (tab.refresh if hasattr(tab, 'refresh') else tab.refresh_log)()

    def refresh_logo(self):
        self._banner_img = branding.tk_photo(tk, 56); self.logo_lbl.configure(image=self._banner_img)

    def build_jobs_tab(self):
        jf = ttk.Frame(self.nb); self.nb.add(jf, text='  Jobs / Reports  ')
        bar = ttk.Frame(jf); bar.pack(fill='x', padx=8, pady=8)
        ttk.Button(bar, text='+ New job', command=self.new_job).pack(side='left', padx=3)
        ttk.Button(bar, text='Open / Edit', command=self.edit_job).pack(side='left', padx=3)
        for txt, w_, f_ in [('Report PDF', 'rep', 'pdf'), ('Report Excel', 'rep', 'xlsx'), ('Observation PDF', 'obs', 'pdf'), ('Observation Excel', 'obs', 'xlsx')]:
            ttk.Button(bar, text=txt, command=lambda w_=w_, f_=f_: self.pdf(w_, f_)).pack(side='left', padx=3)
        ttk.Button(bar, text='Copy job as new', command=self.copy_job).pack(side='left', padx=3)
        ttk.Button(bar, text='Delete', command=self.del_job).pack(side='left', padx=3)
        ttk.Label(bar, text='   Search:').pack(side='left')
        self.q = tk.StringVar(); self.q.trace_add('write', lambda *a: self.refresh_jobs())
        ttk.Entry(bar, textvariable=self.q, width=32).pack(side='left', padx=4)
        cols = [('report_no', 'Report No.', 170), ('report_date', 'Date', 85), ('material', 'Material', 170), ('customer', 'Customer', 280),
                ('job_no', 'Job No.', 90), ('material_ident', 'Material identification', 330)]
        self.tree = tree_with_scroll(jf, [c for c, _, _ in cols], height=18, fill='both', expand=True, padx=8, pady=(0, 8))
        for c, t, w in cols:
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.bind('<Double-1>', lambda e: self.edit_job())
        gate(jf, self.db, {'+ New job': ('jobs', 'add'), 'Copy job as new': ('jobs', 'add'), 'Delete': ('jobs', 'delete')})
        self.refresh_jobs()

    def refresh_materials(self):
        pass

    def refresh_records(self):
        for tab in (self.eq_tab,):
            if tab is not None: tab.refresh_log()
        if self.std_tab is not None: self.std_tab.refresh()

    def about(self):
        messagebox.showinfo(APP, f'{APP}\nMaterial testing reports, observation sheets, equipment logbook,\nchemical standardization records, user control and audit trail.\n\nSoftware by Mr. Ganesh Raykar', parent=self)

    def refresh_jobs(self):
        if self.tree is None: return
        self.tree.delete(*self.tree.get_children())
        for j in self.db.jobs(self.q.get().strip()):
            self.tree.insert('', 'end', iid=str(j['id']), values=(j['report_no'], d_show(j['report_date']), j['material'] or '', j['customer'], j['job_no'], j['material_ident']))

    def sel(self):
        s = self.tree.selection(); return int(s[0]) if s else None

    def new_job(self):
        JobEditor(self)

    def edit_job(self):
        j = self.sel()
        if j: JobEditor(self, j)

    def pdf(self, kind, fmt_='pdf'):
        j = self.sel()
        if not j: messagebox.showinfo(APP, 'Select a job first.'); return
        job = self.db.job(j)
        if not job['material_id']: messagebox.showwarning(APP, 'This job has no material.'); return
        make_output(self.db, j, kind, fmt_, self)

    def copy_job(self):
        j = self.sel()
        if not j: return
        n = simpledialog.askstring(APP, 'Report No. for the new job:')
        if not n: return
        job = self.db.job(j)
        job['report_no'] = n; job['ulr'] = ''; job['job_no'] = ''          # a Job No. must be new: enter it when you open the copy
        self.db.save_job(None, job, {})
        self.refresh_jobs()
        messagebox.showinfo(APP, 'Copy created. Open it and enter the new Job No. and readings.')

    def del_job(self):
        j = self.sel()
        if j and messagebox.askyesno(APP, 'Delete this job and its readings permanently?\n(The deletion is recorded in the Audit Trail.)'):
            self.db.delete_job(j); self.refresh_jobs(); self.refresh_records()


if __name__ == '__main__':
    app = App()
    if app.ready:
        app.mainloop()
