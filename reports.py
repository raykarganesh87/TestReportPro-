"""PDF generation (reportlab) and Excel export."""
import json, math, os, re, sys, subprocess
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether)
from reportlab.pdfgen import canvas as rl_canvas
from core import compute_job, fmt, d_show, REPORT_DIR, JOB_FIELDS
import branding

_FONT = None


FONT_USED = ''


def fonts():
    """Cambria (Windows Fonts folder) for every PDF. If Cambria is missing, the metric-compatible Caladea is used,
    and as a last resort a serif base font; reports.FONT_USED tells which one was picked."""
    global _FONT, FONT_USED
    if _FONT:
        return _FONT
    local = os.environ.get('LOCALAPPDATA', '')
    cands = [('Cambria', 'C:/Windows/Fonts/cambria.ttc', 'C:/Windows/Fonts/cambriab.ttf', 0),
             ('Cambria', os.path.join(local, 'Microsoft/Windows/Fonts/cambria.ttc'), os.path.join(local, 'Microsoft/Windows/Fonts/cambriab.ttf'), 0),
             ('Cambria', 'C:/Windows/Fonts/Cambria.ttf', 'C:/Windows/Fonts/Cambriab.ttf', 0),
             ('Caladea', '/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf', '/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf', 0)]
    for name, reg, bold, idx in cands:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont('LR', reg, subfontIndex=idx)); pdfmetrics.registerFont(TTFont('LR-B', bold))
                pdfmetrics.registerFontFamily('LR', normal='LR', bold='LR-B', italic='LR', boldItalic='LR-B')
                _FONT = ('LR', 'LR-B'); FONT_USED = name; return _FONT
            except Exception:
                pass
    _FONT = ('Times-Roman', 'Times-Bold'); FONT_USED = 'Times (Cambria not found)'
    return _FONT


def esc(s):
    return (str(s or '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def styles():
    r, b = fonts()
    S = lambda n, **k: ParagraphStyle(n, fontName=k.pop('fontName', r), **k)
    return dict(n=S('n', fontSize=9, leading=11), b=S('b', fontName=b, fontSize=9, leading=11),
                s=S('s', fontSize=7.5, leading=9, textColor=colors.HexColor('#555555')),
                title=S('t', fontName=b, fontSize=17, leading=20, alignment=1, textColor=colors.HexColor('#C00000')),
                h=S('h', fontName=b, fontSize=10, leading=12, alignment=1), c=S('c', fontSize=9, leading=11, alignment=1),
                cb=S('cb', fontName=b, fontSize=9, leading=11, alignment=1), r=S('r', fontSize=9, leading=11, alignment=2),
                note=S('note', fontSize=7.5, leading=9.5), hd=S('hd', fontName=b, fontSize=10.5, leading=13))


def prepare(db, jid):
    job = db.job(jid)
    mat = db.material(job['material_id'])
    tests = db.tests(job['material_id'])
    vals = db.job_values(jid)
    res = compute_job(tests, vals)
    ecode = {e['id']: f"{e['code']} {e['name']}" for e in db.equipment()}
    eq = db.job_equipment(jid)
    for t in tests:                                   # per-test meta shown on the observation sheet
        t['_date'] = vals.get((t['id'], '_date'), ''); t['_analyst'] = vals.get((t['id'], '_analyst'), '')
        t['_equip'] = '; '.join(ecode.get(i, '?') for i in eq.get(t['id'], []))
    return job, mat, tests, res


def header_rows(job, db, observation=False):
    rows = [('Customer Name', job['customer']), ('Address', job['address']), ('Name of Agency', job['agency']),
            ('Name of Work', job['work']), ('Material Identification', job['material_ident'])]
    if job['ref1']:
        rows.append(('Reference Letter No.', job['ref1']))
    if job['ref2']:
        rows.append(('Reference Letter No.', job['ref2']))
    rows += [('Testing Location', db.setting('location')), ('Job No.', job['job_no']),
             ('Date of receipt of material', d_show(job['receipt_date'])),
             ('Performance date', f"{d_show(job['start_date'])} to {d_show(job['end_date'])}" if job['start_date'] or job['end_date'] else ''),
             ('Environment Condition of Lab',
              f"{job['temp']}°C temperature & {job['rh']}% Relative Humidity" if job['temp'] or job['rh'] else '')]
    return rows


MAKER = 'Software by Mr. Ganesh Raykar'


def logo_flowable(height_mm=14):
    import io
    from reportlab.platypus import Image
    from reportlab.lib.utils import ImageReader
    data = branding.logo_bytes()
    w, h = ImageReader(io.BytesIO(data)).getSize()
    hh = height_mm * mm
    img = Image(io.BytesIO(data), width=hh * w / h, height=hh); img.hAlign = 'LEFT'
    return img


def add_logo_xlsx(ws, anchor='A1', width_px=64):
    import io
    from openpyxl.drawing.image import Image as XLImage
    from reportlab.lib.utils import ImageReader
    data = branding.logo_bytes()
    w, h = ImageReader(io.BytesIO(data)).getSize()
    im = XLImage(io.BytesIO(data)); im.width = width_px; im.height = int(width_px * h / w)
    ws.add_image(im, anchor)
    return im.height


def build_pdf(db, path, parts, report_no, title, top_full_mm, size=A4, lr_mm=18, bottom_mm=14, head='Report No :- '):
    """parts = list of stories. Each part starts on a fresh page with the full header; any further page of the same part
    ('continuation') shows only 'Report No' and 'Page x of y'."""
    r, b = fonts()
    W, H = size
    lr, bottom, top = lr_mm * mm, bottom_mm * mm, top_full_mm * mm
    gap = 9 * mm
    credit = db.setting('credit_on_reports') == '1'
    doc = BaseDocTemplate(path, pagesize=size, title=title, author=db.setting('lab_name'), leftMargin=lr, rightMargin=lr, topMargin=top, bottomMargin=bottom)
    kw = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    full = Frame(lr, bottom, W - 2 * lr, H - top - bottom, id='full', **kw)
    cont = Frame(lr, bottom, W - 2 * lr, H - top - bottom - gap, id='cont', **kw)

    def mark(flag):
        def f(c, d):
            c._cont = flag
        return f
    doc.addPageTemplates([PageTemplate('Full', [full], onPage=mark(False)), PageTemplate('Cont', [cont], onPage=mark(True))])
    story = []
    for i, p in enumerate(parts):
        if i:
            story += [NextPageTemplate('Full'), PageBreak()]
        story += [NextPageTemplate('Cont')] + p

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__)); self._startPage()

        def save(self):
            n = len(self._pages)
            for i, st in enumerate(self._pages, 1):
                self.__dict__.update(st)
                self.setFillColor(colors.black)
                if getattr(self, '_cont', False):                       # continuation page: Report No + Page No only
                    y = H - top - 5 * mm
                    self.setFont(b, 10); self.drawString(lr, y, f'{head}{report_no}')
                    self.drawRightString(W - lr, y, f'Page {i} of {n}')
                    self.setLineWidth(0.5); self.line(lr, y - 2 * mm, W - lr, y - 2 * mm)
                self.setFont(r, 8); self.setFillColor(colors.HexColor('#555555'))
                self.drawCentredString(W / 2, 7 * mm, f'Page {i} of {n}')
                if credit:
                    self.setFont(r, 7); self.drawString(lr, 7 * mm, MAKER)
                super().showPage()
            super().save()
    doc.build(story, canvasmaker=NumberedCanvas)
    return path


def report_pdf(db, jid, path=None):
    job, mat, tests, res = prepare(db, jid)
    S = styles()
    path = path or os.path.join(REPORT_DIR, re.sub(r'[^\w\-]+', '_', job['report_no']) + '_Report.pdf')
    lh = float(db.setting('letterhead_mm') or 0)
    titles = json.loads(mat['page_titles'] or '{}')
    pages = sorted({t['page'] for t in tests if t['in_report']}) or [1]
    parts = []
    for pi, pg in enumerate(pages):
        story = [logo_flowable(14), Spacer(1, 2 * mm)] if (pi == 0 and db.setting('logo_on_reports') == '1') else []
        top = Table([[Paragraph(f"<b>Report No :- {esc(job['report_no'])}</b>", S['n']),
                      Paragraph(f"<b>Date :- {d_show(job['report_date'])}</b>", S['r'])]], colWidths=[100 * mm, 74 * mm])
        story += [top]
        if job['ulr']:
            story.append(Paragraph(f"<b>ULR No.:- {esc(job['ulr'])}</b>", S['n']))
        story += [Spacer(1, 3 * mm), Paragraph('Test Report', S['title']), Spacer(1, 3 * mm)]
        hr = [[Paragraph(f'<b>{esc(a)}</b>', S['n']), Paragraph(':- ' + esc(b), S['n'])] for a, b in header_rows(job, db)]
        ht = Table(hr, colWidths=[48 * mm, 126 * mm])
        ht.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5)]))
        story += [ht, Spacer(1, 4 * mm), Paragraph(esc(titles.get(str(pg), 'TEST ANALYSIS')), S['h']), Spacer(1, 1.5 * mm)]
        rep = [t for t in tests if t['in_report'] and t['page'] == pg and res[t['id']]['result'] not in (None, '')]   # tests not done are left out
        has_unit = any(t['unit'] for t in rep)
        head = ['Sr. No', 'Test'] + (['Unit'] if has_unit else []) + ['Result', f"Limits as per {mat['spec']}" if mat['spec'] else 'Limits', 'Test Method']
        data = [[Paragraph(h, S['cb']) for h in head]]
        for i, t in enumerate(rep, 1):
            r = res[t['id']]
            rc = next((c for c in t['calcs'] if c['is_result']), None)
            val = fmt(r['result'], t['decimals'])
            row = [Paragraph(str(i), S['c']), Paragraph(esc(t['report_name'] or t['name']), S['n'])]
            if has_unit:
                row.append(Paragraph(esc(t['unit']), S['c']))
            row += [Paragraph(esc(val), S['c']), Paragraph(esc(t['limit_text']), S['n']), Paragraph(esc(t['method']), S['n'])]
            data.append(row)
        widths = [12, 52] + ([14] if has_unit else []) + [20, 44 if has_unit else 50, 32]
        tot = sum(widths); widths = [w * 174 / tot * mm for w in widths]
        tb = Table(data, colWidths=widths, repeatRows=1)
        tb.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.6, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        story += [tb, Spacer(1, 3 * mm), Paragraph('<b>Note :-</b>', S['note'])]
        for i, ln in enumerate([x for x in db.setting('notes').splitlines() if x.strip()], 1):
            story.append(Paragraph(f'{i}) {esc(ln)}', S['note']))
        sign = [Spacer(1, 5 * mm), Paragraph(f"<b>For {esc(db.setting('lab_name'))},</b>", S['r']), Spacer(1, 16 * mm),
                Paragraph('<b>Reviewed &amp; Authorised by</b>', S['r']), Paragraph(f"<b>{esc(job['reviewer'])}</b>", S['r'])]
        story.append(KeepTogether(sign))
        parts.append(story)
    return build_pdf(db, path, parts, job['report_no'], f"Test Report {job['report_no']}", max(lh, 12))


def observation_pdf(db, jid, path=None):
    job, mat, tests, res = prepare(db, jid)
    S = styles()
    path = path or os.path.join(REPORT_DIR, re.sub(r'[^\w\-]+', '_', job['report_no']) + '_Observation.pdf')
    head_ = Paragraph(esc(db.setting('lab_name')), S['h'])
    if db.setting('logo_on_obs') != '0':
        lt = Table([[logo_flowable(15), head_, '']], colWidths=[40 * mm, 102 * mm, 40 * mm]); lt.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])); head_ = lt
    story = [head_,
             Paragraph(f"{esc(mat['name'])} - Test Observation Sheet", ParagraphStyle('x', parent=S['title'], textColor=colors.black)), Spacer(1, 3 * mm)]
    g = lambda k: esc(job[k])
    hd = [[Paragraph('<b>Job No :-</b> ' + g('job_no'), S['n']), Paragraph('<b>Job assigned to :-</b> ' + g('assigned_to'), S['n'])],
          [Paragraph('<b>Work Order No :-</b> ' + g('work_order'), S['n']), Paragraph('<b>Test starting date :-</b> ' + d_show(job['start_date']), S['n'])],
          [Paragraph(f"<b>Temperature &amp; Humidity :-</b> {g('temp')}°C &amp; {g('rh')}%", S['n']), Paragraph('<b>Test complete date :-</b> ' + d_show(job['end_date']), S['n'])],
          [Paragraph('<b>Report No :-</b> ' + g('report_no'), S['n']), Paragraph('<b>Sample receive date :-</b> ' + d_show(job['receipt_date']) + '    <b>Client ID :-</b> ' + g('client_id'), S['n'])],
          [Paragraph('<b>Material :-</b> ' + g('material_ident'), S['n']), Paragraph('<b>Customer :-</b> ' + g('customer'), S['n'])]]
    t = Table(hd, colWidths=[91 * mm, 91 * mm])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.6, colors.black), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story += [t, Spacer(1, 4 * mm)]
    for tt in tests:
        r = res[tt['id']]
        rows = [[Paragraph('Observation', S['cb']), Paragraph('Value', S['cb']), Paragraph('Calculation', S['cb'])]]
        for f in tt['fields']:
            v = r['inputs'].get(f['key'])
            txt = '' if v is None else (v if isinstance(v, str) else fmt(v, 4).rstrip('0').rstrip('.') if fmt(v, 4) else '')
            if r['auto'].get(f['key']):
                txt += ' (auto)'
            rows.append([Paragraph(esc(f['label']), S['n']), Paragraph(esc(txt) + (' ' + esc(f['unit']) if f['unit'] and txt else ''), S['c']), ''])
        for c in tt['calcs']:
            v = r['calcs'].get(c['key'])
            bold = c['is_result']
            val = fmt(v, c['decimals'])
            rows.append([Paragraph(('<b>%s</b>' if bold else '%s') % esc(c['label']), S['n']),
                         Paragraph(('<b>%s</b>' if bold else '%s') % esc(val + (' ' + tt['unit'] if bold and tt['unit'] not in ('', '--') and val else '')), S['c']),
                         Paragraph(esc(c['expr']), S['s'])])
        tbl = Table(rows, colWidths=[92 * mm, 36 * mm, 54 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7E6E6')),
                                 ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        meta = []
        if tt['_date']: meta.append(f"Date of analysis: {esc(tt['_date'])}")
        if tt['_analyst']: meta.append(f"Analysed by: {esc(tt['_analyst'])}")
        if tt['_equip']: meta.append(f"Equipment used: {esc(tt['_equip'])}")
        parts_ = [Paragraph(f"{esc(tt['name'])} ({esc(tt['method'])})", S['hd'])]
        if meta: parts_.append(Paragraph('   |   '.join(meta), S['s']))
        story.append(KeepTogether(parts_ + [Spacer(1, 1 * mm), tbl, Spacer(1, 3 * mm)]))
    sig = Table([[Paragraph(f"Date of analysis: {d_show(job['analysis_date'])}", S['n']), '', ''],
                 [Paragraph('<b>Analysed by:</b> ' + esc(job['analysed_by']), S['n']), '', Paragraph('<b>Verified by:</b> ' + esc(job['verified_by']), S['n'])]],
                colWidths=[70 * mm, 40 * mm, 72 * mm], rowHeights=[8 * mm, 16 * mm])
    sig.setStyle(TableStyle([('VALIGN', (0, 1), (-1, 1), 'BOTTOM')]))
    story.append(KeepTogether([Spacer(1, 4 * mm), sig]))
    return build_pdf(db, path, [story], job['report_no'], f"Observation Sheet {job['report_no']}", 14, lr_mm=14)


def open_file(p):
    try:
        if sys.platform.startswith('win'):
            os.startfile(p)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', p])
        else:
            subprocess.Popen(['xdg-open', p])
    except Exception:
        pass


def export_excel(db, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); ws = wb.active; ws.title = 'Register'
    ws2 = wb.create_sheet('Results'); ws3 = wb.create_sheet('Observations')
    hdr = ['Material'] + [l for _, l, _ in JOB_FIELDS] + ['Analysed by', 'Verified by', 'Date of analysis', 'Remarks']
    ws.append(hdr); ws2.append(['Report No.', 'Material', 'Customer', 'Report Date', 'Test', 'Unit', 'Result', 'Limit', 'Method'])
    ws3.append(['Report No.', 'Material', 'Test', 'Item', 'Value'])
    for j in db.jobs():
        full = db.job(j['id'])
        row = [j['material']] + [d_show(full[c]) if k == 'd' else full[c] for c, _, k in JOB_FIELDS] + \
              [full['analysed_by'], full['verified_by'], d_show(full['analysis_date']), full['remarks']]
        ws.append(row)
        if not full['material_id']:
            continue
        tests = db.tests(full['material_id']); res = compute_job(tests, db.job_values(j['id']))
        for t in tests:
            r = res[t['id']]
            ws2.append([full['report_no'], j['material'], full['customer'], d_show(full['report_date']), t['name'], t['unit'],
                        r['result'] if not isinstance(r['result'], float) else float(fmt(r['result'], t['decimals']) or 0) if r['result'] is not None else None,
                        t['limit_text'], t['method']])
            for f in t['fields']:
                if r['inputs'].get(f['key']) is not None:
                    ws3.append([full['report_no'], j['material'], t['name'], f['label'], r['inputs'][f['key']]])
    for w in (ws, ws2, ws3):
        for c in w[1]:
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='1F3864'); c.alignment = Alignment(wrap_text=True)
        w.freeze_panes = 'A2'
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = min(40, max(10, max(len(str(c.value or '')) for c in col[:50]) + 2))
    wb.save(path)
    return path


# ======================================================================= Excel versions (same content as the PDFs)
def _lines(text, width):
    return sum(max(1, math.ceil(len(p) / max(1, width))) for p in str(text or '').split('\n'))


def _xl_common():
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    thin = Side(style='thin', color='000000')
    return dict(Font=Font, Al=Alignment, box=Border(left=thin, right=thin, top=thin, bottom=thin), Fill=PatternFill)


def _setup_page(ws, db, last_row, last_col, top_mm=15, report_no=''):
    ws.HeaderFooter.differentFirst = True            # continuation pages: Report No + Page No only
    ws.oddHeader.left.text = f'Report No :- {report_no}'; ws.oddHeader.left.font = 'Cambria,Bold'; ws.oddHeader.left.size = 10
    ws.oddHeader.right.text = 'Page &P of &N'; ws.oddHeader.right.font = 'Cambria,Bold'; ws.oddHeader.right.size = 10
    ws.oddFooter.center.text = 'Page &P of &N'; ws.firstFooter.center.text = 'Page &P of &N'
    if db.setting('credit_on_reports') == '1':
        ws.oddFooter.left.text = MAKER; ws.firstFooter.left.text = MAKER
    ws.page_setup.paperSize = 9; ws.page_setup.orientation = 'portrait'
    ws.sheet_properties.pageSetUpPr = __import__('openpyxl').worksheet.properties.PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.page_margins.top = max(top_mm, 10) / 25.4; ws.page_margins.left = ws.page_margins.right = 0.6; ws.page_margins.bottom = 0.6
    ws.print_area = f'A1:{last_col}{last_row}'
    ws.sheet_view.showGridLines = False


def report_xlsx(db, jid, path=None):
    from openpyxl import Workbook
    X = _xl_common(); Font, Al, box = X['Font'], X['Al'], X['box']
    job, mat, tests, res = prepare(db, jid)
    path = path or os.path.join(REPORT_DIR, re.sub(r'[^\w\-]+', '_', job['report_no']) + '_Report.xlsx')
    titles = json.loads(mat['page_titles'] or '{}')
    pages = sorted({t['page'] for t in tests if t['in_report']}) or [1]
    wb = Workbook(); wb.remove(wb.active)
    FN = 'Cambria'
    f = lambda **k: Font(name=FN, size=k.pop('size', 10), **k)
    for pg in pages:
        ws = wb.create_sheet(('Page %s' % pg) if len(pages) > 1 else 'Test Report')
        for col, w in zip('ABCDEF', [7, 40, 9, 14, 34, 28]):
            ws.column_dimensions[col].width = w
        r = 1
        if db.setting('logo_on_reports') == '1':
            add_logo_xlsx(ws, 'A1', 64); r = 4
        ws.merge_cells(f'A{r}:C{r}'); ws[f'A{r}'] = f"Report No :- {job['report_no']}"; ws[f'A{r}'].font = f(bold=True)
        ws.merge_cells(f'D{r}:F{r}'); ws[f'D{r}'] = f"Date :- {d_show(job['report_date'])}"; ws[f'D{r}'].font = f(bold=True); ws[f'D{r}'].alignment = Al(horizontal='right')
        r += 1
        if job['ulr']:
            ws.merge_cells(f'A{r}:F{r}'); ws[f'A{r}'] = f"ULR No.:- {job['ulr']}"; ws[f'A{r}'].font = f(bold=True); r += 1
        r += 1
        ws.merge_cells(f'A{r}:F{r}'); ws[f'A{r}'] = 'Test Report'; ws[f'A{r}'].font = f(size=18, bold=True, color='C00000')
        ws[f'A{r}'].alignment = Al(horizontal='center'); ws.row_dimensions[r].height = 28; r += 2
        for lab, val in header_rows(job, db):
            ws.merge_cells(f'A{r}:B{r}'); ws.merge_cells(f'C{r}:F{r}')
            ws[f'A{r}'] = lab; ws[f'A{r}'].font = f(bold=True); ws[f'A{r}'].alignment = Al(vertical='top', wrap_text=True)
            ws[f'C{r}'] = ':- ' + str(val or ''); ws[f'C{r}'].font = f(); ws[f'C{r}'].alignment = Al(vertical='top', wrap_text=True)
            ws.row_dimensions[r].height = max(15, 13.5 * _lines(':- ' + str(val or ''), 80) + 3); r += 1
        r += 1
        ws.merge_cells(f'A{r}:F{r}'); ws[f'A{r}'] = titles.get(str(pg), 'TEST ANALYSIS'); ws[f'A{r}'].font = f(size=11, bold=True)
        ws[f'A{r}'].alignment = Al(horizontal='center'); r += 1
        head = ['Sr. No', 'Test', 'Unit', 'Result', f"Limits as per {mat['spec']}" if mat['spec'] else 'Limits', 'Test Method']
        for c, h in zip('ABCDEF', head):
            cell = ws[f'{c}{r}']; cell.value = h; cell.font = f(bold=True); cell.border = box
            cell.alignment = Al(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[r].height = 30; r += 1
        rep = [t for t in tests if t['in_report'] and t['page'] == pg and res[t['id']]['result'] not in (None, '')]
        for i, t in enumerate(rep, 1):
            v = res[t['id']]['result']
            vals = [i, t['report_name'] or t['name'], t['unit'], None, t['limit_text'], t['method']]
            for c, x in zip('ABCDEF', vals):
                cell = ws[f'{c}{r}']; cell.value = x; cell.font = f(); cell.border = box
                cell.alignment = Al(horizontal='center' if c in 'ACD' else 'left', vertical='center', wrap_text=True)
            cell = ws[f'D{r}']
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cell.value = float(fmt(v, t['decimals'])); cell.number_format = '0.' + '0' * t['decimals'] if t['decimals'] else '0'
            else:
                cell.value = fmt(v, t['decimals'])
            ws.row_dimensions[r].height = max(20, 13.5 * max(_lines(vals[1], 38), _lines(t['limit_text'], 32), _lines(t['method'], 26)) + 6)
            r += 1
        r += 1
        ws[f'A{r}'] = 'Note :-'; ws[f'A{r}'].font = f(size=9, bold=True); r += 1
        for i, ln in enumerate([x for x in db.setting('notes').splitlines() if x.strip()], 1):
            ws.merge_cells(f'A{r}:F{r}'); ws[f'A{r}'] = f'{i}) {ln}'; ws[f'A{r}'].font = f(size=9); ws[f'A{r}'].alignment = Al(wrap_text=True, vertical='top')
            ws.row_dimensions[r].height = max(13, 12 * _lines(ln, 105) + 2); r += 1
        r += 1
        for txt, ht, bold in [(f"For {db.setting('lab_name')},", 18, True), ('', 40, False), ('Reviewed & Authorised by', 16, True), (job['reviewer'] or '', 16, True)]:
            ws.merge_cells(f'D{r}:F{r}'); ws[f'D{r}'] = txt; ws[f'D{r}'].font = f(bold=bold); ws[f'D{r}'].alignment = Al(horizontal='right')
            ws.row_dimensions[r].height = ht; r += 1
        _setup_page(ws, db, r, 'F', float(db.setting('letterhead_mm') or 15), job['report_no'])
    wb.save(path)
    return path


def observation_xlsx(db, jid, path=None):
    from openpyxl import Workbook
    X = _xl_common(); Font, Al, box, Fill = X['Font'], X['Al'], X['box'], X['Fill']
    job, mat, tests, res = prepare(db, jid)
    path = path or os.path.join(REPORT_DIR, re.sub(r'[^\w\-]+', '_', job['report_no']) + '_Observation.xlsx')
    wb = Workbook(); ws = wb.active; ws.title = 'Observation Sheet'
    FN = 'Cambria'
    f = lambda **k: Font(name=FN, size=k.pop('size', 10), **k)
    for col, w in zip('ABC', [62, 22, 52]):
        ws.column_dimensions[col].width = w
    ws.merge_cells('A1:C1'); ws['A1'] = db.setting('lab_name'); ws['A1'].font = f(size=11, bold=True); ws['A1'].alignment = Al(horizontal='center')
    ws.merge_cells('A2:C2'); ws['A2'] = f"{mat['name']} - Test Observation Sheet"; ws['A2'].font = f(size=16, bold=True); ws['A2'].alignment = Al(horizontal='center')
    ws.row_dimensions[2].height = 26
    if db.setting('logo_on_obs') != '0':
        hpx = add_logo_xlsx(ws, 'A1', 64); ws.row_dimensions[1].height = max(18, hpx * 0.75 - 26)
    hd = [('Job No :- ' + (job['job_no'] or ''), 'Job assigned to :- ' + (job['assigned_to'] or '')),
          ('Work Order No :- ' + (job['work_order'] or ''), 'Test starting date :- ' + d_show(job['start_date'])),
          (f"Temperature & Humidity :- {job['temp'] or ''}°C & {job['rh'] or ''}%", 'Test complete date :- ' + d_show(job['end_date'])),
          ('Report No :- ' + (job['report_no'] or ''), f"Sample receive date :- {d_show(job['receipt_date'])}   Client ID :- {job['client_id'] or ''}"),
          ('Material :- ' + (job['material_ident'] or ''), 'Customer :- ' + (job['customer'] or ''))]
    r = 4
    for a, b in hd:
        ws[f'A{r}'] = a; ws.merge_cells(f'B{r}:C{r}'); ws[f'B{r}'] = b
        for c in 'ABC':
            ws[f'{c}{r}'].font = f(); ws[f'{c}{r}'].border = box; ws[f'{c}{r}'].alignment = Al(wrap_text=True, vertical='top')
        ws.row_dimensions[r].height = max(16, 13.5 * max(_lines(a, 60), _lines(b, 70)) + 3); r += 1
    r += 1
    grey = Fill('solid', fgColor='E7E6E6')
    for t in tests:
        rr = res[t['id']]
        ws.merge_cells(f'A{r}:C{r}'); ws[f'A{r}'] = f"{t['name']} ({t['method']})" if t['method'] else t['name']; ws[f'A{r}'].font = f(size=11, bold=True); r += 1
        meta = ' | '.join(x for x in [f"Date of analysis: {t['_date']}" if t['_date'] else '', f"Analysed by: {t['_analyst']}" if t['_analyst'] else '',
                                      f"Equipment used: {t['_equip']}" if t['_equip'] else ''] if x)
        if meta:
            ws.merge_cells(f'A{r}:C{r}'); ws[f'A{r}'] = meta; ws[f'A{r}'].font = f(size=9, color='666666'); r += 1
        for c, h in zip('ABC', ['Observation', 'Value', 'Calculation']):
            ws[f'{c}{r}'] = h; ws[f'{c}{r}'].font = f(bold=True); ws[f'{c}{r}'].fill = grey; ws[f'{c}{r}'].border = box
            ws[f'{c}{r}'].alignment = Al(horizontal='center')
        r += 1
        for fl in t['fields']:
            v = rr['inputs'].get(fl['key'])
            ws[f'A{r}'] = fl['label'] + (f" ({fl['unit']})" if fl['unit'] else ''); ws[f'B{r}'] = v
            ws[f'C{r}'] = '(auto from earlier test)' if rr['auto'].get(fl['key']) else ''
            for c in 'ABC':
                ws[f'{c}{r}'].font = f(); ws[f'{c}{r}'].border = box; ws[f'{c}{r}'].alignment = Al(wrap_text=True, vertical='center', horizontal='center' if c == 'B' else 'left')
            ws.row_dimensions[r].height = max(15, 13.5 * _lines(ws[f'A{r}'].value, 58) + 2); r += 1
        for c_ in t['calcs']:
            v = rr['calcs'].get(c_['key']); bold = bool(c_['is_result'])
            ws[f'A{r}'] = c_['label']; ws[f'C{r}'] = c_['expr']
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                ws[f'B{r}'] = float(fmt(v, c_['decimals'])); ws[f'B{r}'].number_format = '0.' + '0' * c_['decimals'] if c_['decimals'] else '0'
            else:
                ws[f'B{r}'] = v
            for c in 'ABC':
                ws[f'{c}{r}'].font = f(bold=bold, size=(9 if c == 'C' else 10), color=('666666' if c == 'C' else '000000'))
                ws[f'{c}{r}'].border = box; ws[f'{c}{r}'].alignment = Al(wrap_text=True, vertical='center', horizontal='center' if c == 'B' else 'left')
            ws.row_dimensions[r].height = max(15, 13.5 * max(_lines(c_['label'], 58), _lines(c_['expr'], 50)) + 2); r += 1
        r += 1
    ws[f'A{r}'] = f"Date of analysis: {d_show(job['analysis_date'])}"; ws[f'A{r}'].font = f(); r += 2
    ws[f'A{r}'] = 'Analysed by: ' + (job['analysed_by'] or ''); ws[f'C{r}'] = 'Verified by: ' + (job['verified_by'] or '')
    ws[f'A{r}'].font = f(bold=True); ws[f'C{r}'].font = f(bold=True); ws.row_dimensions[r].height = 30
    _setup_page(ws, db, r, 'C', 15, job['report_no'])
    wb.save(path)
    return path


# ======================================================================= Logbook and Standardization records
def _calc_std(d):
    try:
        if d['n_std'] and d['v_std'] and d['v_tit']:
            return d['n_std'] * d['v_std'] / d['v_tit']
    except Exception:
        pass
    return None


def _table_xlsx(db, path, sheet, title, headers, rows, widths_):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    thin = Side(style='thin', color='000000'); box = Border(left=thin, right=thin, top=thin, bottom=thin)
    wb = Workbook(); ws = wb.active; ws.title = sheet
    n = len(headers)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    ws['A1'] = db.setting('lab_name'); ws['A1'].font = Font(name='Cambria', size=11, bold=True); ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    ws['A2'] = title; ws['A2'].font = Font(name='Cambria', size=14, bold=True); ws['A2'].alignment = Alignment(horizontal='center')
    for i, (h, w) in enumerate(zip(headers, widths_), 1):
        c = ws.cell(4, i, h); c.font = Font(name='Cambria', bold=True); c.fill = PatternFill('solid', fgColor='E7E6E6'); c.border = box
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[ws.cell(4, i).column_letter].width = w
    ws.row_dimensions[4].height = 32
    for r, row in enumerate(rows, 5):
        for i, v in enumerate(row, 1):
            c = ws.cell(r, i, v); c.font = Font(name='Cambria', size=10); c.border = box
            c.alignment = Alignment(wrap_text=True, vertical='top', horizontal='center' if i == 1 else 'left')
    ws.page_setup.orientation = 'landscape'; ws.page_setup.paperSize = 9
    ws.sheet_properties.pageSetUpPr = __import__('openpyxl').worksheet.properties.PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.print_title_rows = '4:4'; ws.freeze_panes = 'A5'
    ws.oddFooter.center.text = 'Page &P of &N'
    if db.setting('credit_on_reports') == '1':
        ws.oddFooter.left.text = MAKER
    wb.save(path); return path


def _table_pdf(db, path, title, headers, rows, widths_):
    S = styles(); size = (A4[1], A4[0])
    head = [Paragraph(esc(h), S['cb']) for h in headers]
    data = [head] + [[Paragraph(esc(v).replace('\n', '<br/>'), S['c'] if i == 0 else S['n']) for i, v in enumerate(r)] for r in rows]
    tot = sum(widths_); usable = (size[0] - 24 * mm)
    t = Table(data, colWidths=[w / tot * usable for w in widths_], repeatRows=1)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7E6E6')),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    story = [Paragraph(esc(db.setting('lab_name')), S['h']), Paragraph(esc(title), S['h']), Spacer(1, 4 * mm), t]
    return build_pdf(db, path, [story], title, title, 12, size=size, lr_mm=12, head='')


def logbook_rows(db, rows):
    return [[i, d_show(r['log_date']), r['ecode'] or '', r['ename'] or '', r['job_no'] or '', r['report_no'] or '', r['test_name'] or '',
             r['analyst'] or '', r['remarks'] or ''] for i, r in enumerate(rows, 1)]


LOG_H = ['Sr. No', 'Date', 'Equipment ID', 'Equipment', 'Job No.', 'Report No.', 'Test performed', 'Analyst', 'Remarks']
LOG_W = [6, 10, 11, 20, 10, 18, 24, 12, 18]


def logbook_xlsx(db, rows, path=None, title='Equipment Usage Logbook'):
    path = path or os.path.join(REPORT_DIR, 'Equipment_Logbook.xlsx')
    return _table_xlsx(db, path, 'Logbook', title, LOG_H, logbook_rows(db, rows), [6, 12, 13, 26, 12, 24, 32, 14, 28])


def logbook_pdf(db, rows, path=None, title='Equipment Usage Logbook'):
    path = path or os.path.join(REPORT_DIR, 'Equipment_Logbook.pdf')
    return _table_pdf(db, path, title, LOG_H, logbook_rows(db, rows), LOG_W)


STD_H = ['Sr. No', 'Date', 'Reagent', 'Type', 'Strength found', 'Nominal', 'Standardised against', 'Std. strength', 'Std. vol. (ml)',
         'Titre (ml)', 'Calculated (N1V1=N2V2)', 'Used in Report No.', 'Analyst', 'Remarks']
STD_W = [5, 9, 14, 8, 8, 7, 14, 7, 7, 7, 9, 18, 9, 12]


def std_rows(rows):
    f = lambda v: '' if v is None else v
    out = []
    for i, d in enumerate(rows, 1):
        c = _calc_std(d)
        out.append([i, d_show(d['std_date']), d['reagent'], 'Normality (N)' if d['conc_type'] == 'N' else 'Molarity (M)', f(d['value']),
                    d['nominal'] or '', d['against'] or '', f(d['n_std']), f(d['v_std']), f(d['v_tit']), '' if c is None else round(c, 4),
                    d['jobs'] or '', d['analyst'] or '', d['remarks'] or ''])
    return out


def std_xlsx(db, rows, path=None, title='Chemical Standardization Record'):
    path = path or os.path.join(REPORT_DIR, 'Chemical_Standardization_Record.xlsx')
    return _table_xlsx(db, path, 'Standardization', title, STD_H, std_rows(rows), [6, 12, 20, 14, 11, 10, 22, 10, 10, 10, 14, 28, 12, 20])


def std_pdf(db, rows, path=None, title='Chemical Standardization Record'):
    path = path or os.path.join(REPORT_DIR, 'Chemical_Standardization_Record.pdf')
    return _table_pdf(db, path, title, STD_H, std_rows(rows), STD_W)


# ======================================================================= Audit trail export
AUD_H = ['Sr. No', 'Date', 'Time', 'User', 'Section', 'Action', 'Record', 'Changes (old -> new)']
AUD_W = [5, 9, 8, 10, 16, 10, 20, 52]


def audit_table(rows, secnames):
    import json as _json
    out = []
    for i, r in enumerate(rows, 1):
        ch = []
        for d in _json.loads(r['details'] or '[]'):
            o, n = d.get('old', ''), d.get('new', '')
            ch.append(f"{d['field']}: " + (f"'{o}' -> '{n}'" if o != '' and n != '' else (f"'{n}'" if n != '' else f"was '{o}'")))
        out.append([i, d_show(r['ts'][:10]), r['ts'][11:], r['user'], secnames.get(r['section'], r['section']), r['action'], r['ref'] or '', '\n'.join(ch)])
    return out


def audit_xlsx(db, rows, secnames, path=None, title='Audit Trail'):
    path = path or os.path.join(REPORT_DIR, 'Audit_Trail.xlsx')
    return _table_xlsx(db, path, 'Audit Trail', title, AUD_H, audit_table(rows, secnames), [6, 12, 10, 14, 24, 14, 28, 80])


def audit_pdf(db, rows, secnames, path=None, title='Audit Trail'):
    path = path or os.path.join(REPORT_DIR, 'Audit_Trail.pdf')
    return _table_pdf(db, path, title, AUD_H, audit_table(rows, secnames), AUD_W)
