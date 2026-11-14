"""Default library built from the lab's existing Excel formats (OPC, PPC, Fly Ash, Admixture, Aggregate)."""


def N(key, label, default='', unit='', kind='number'):
    return dict(key=key, label=label, unit=unit, kind=kind, default_expr=default)


def C(key, label, expr, dec=2, res=False):
    return dict(key=key, label=label, expr=expr, decimals=dec, is_result=res)


def T(code, name, method, unit, limit, dec, page, rep, fields, calcs, report_name=''):
    return dict(code=code, name=name, method=method, unit=unit, limit_text=limit, decimals=dec, page=page,
                in_report=1 if rep else 0, fields=fields, calcs=calcs, report_name=report_name or name)


def crucible(sample_default='', sample_label='Sample taken (g)  A'):
    return [N('A', sample_label, sample_default), N('Bc', 'Weight of empty crucible (g)  B'),
            N('C', 'Weight of crucible + residue after ignition (g)  C')]


def cement_tests(m, lim, ppc):
    cl_lim = '0.1 and 0.05 (For Pre-stressed structure) Max.'
    return [
        T('LOI', 'Loss on Ignition', m, '%', lim['loi'], 2, 1, True,
          [N('A', 'Weight of crucible (g)  A'), N('B', 'Weight of crucible + sample (g)  B'),
           N('C', 'Weight of crucible + sample after ignition (g)  C')],
          [C('loi', 'LOI % = (B-C)*100/(B-A)', '(B-C)*100/(B-A)', 4, True)]),
        T('IR', 'Insoluble residue', m, '%', lim['ir'], 2, 1, True, crucible(),
          [C('ir', '% of IR = (C-B)*100/A', '(C-Bc)*100/A', 4, True)]),
        T('SO3', 'Sulphuric Anhydride (SO3)', m, '%', '3.5 Max.', 2, 1, True,
          [N('S', 'Sample taken (g)  A', 'IR_A'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C')],
          [C('so3', '% of SO3 = (C-B)*34.3/A', '(C-Bc)*34.3/S', 4, True)]),
        T('SIO2', 'Silica (SiO2)', m, '%', '', 2, 1, False,
          [N('A', 'Sample taken (g)  A'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C'),
           N('D', 'Weight of impurities after ignition & HF treatment (g)  D')],
          [C('sio2', '% of Silica = (C-D)*100/A', '(C-D)*100/A', 4, True)]),
        T('FE2O3', 'Ferric Oxide Fe2O3 (EDTA)', m, '%', '', 2, 1, False,
          [N('S', 'Sample taken (g)  W', 'SIO2_A'), N('N', 'Concentration of EDTA'), N('V', 'Volume of EDTA used (ml)  V')],
          [C('fe2o3', '% of Fe2O3 = 0.7985 x V / W', '0.7985*V/S', 3, True)]),
        T('CAO', 'Calcium Oxide (CaO)', m, '%', '', 2, 1, False,
          [N('S', 'Sample taken (g)  W (aliquot)', 'SIO2_A*100/250'), N('W2', 'Weight of empty crucible (g)  W2'),
           N('W3', 'Weight of crucible after drying (g)  W3')],
          [C('cao', '% of CaO = (W3-W2)*100/W', '(W3-W2)*100/S', 4, True)]),
        T('MGO', 'Magnesia (MgO)', m, '%', lim['mgo'], 2, 1, True,
          [N('S', 'Sample taken (g)  W (aliquot)', 'CAO_S'), N('W2', 'Weight of empty crucible (g)  W2'),
           N('W3', 'Weight of crucible after drying (g)  W3')],
          [C('mgo', '% of MgO = (W3-W2)*0.362*100/W', '(W3-W2)*0.362*100/S', 4, True)]),
        T('R2O3', 'Combined Alumina + Ferric Oxide', m, '%', '', 2, 1, False,
          [N('S', 'Sample taken (g)  A', 'MGO_S'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C')],
          [C('r2o3', '% of combined R2O3 = (C-B)*100/A', '(C-Bc)*100/S', 4),
           C('al2o3', '% of Al2O3 = R2O3 - Fe2O3', 'r2o3-FE2O3_result', 4, True)]),
        T('CL', 'Chloride', m, '%', cl_lim, 3, 1, True,
          [N('W', 'Weight of sample (g)  W'), N('N', 'Normality of Ammonium Thiocyanate (N)'),
           N('Ag', 'Volume of Silver nitrate added (ml)'), N('S', 'NH4SCN consumed by sample C (ml)'),
           N('B', 'NH4SCN consumed by blank B (ml)')],
          [C('cl', '% Chloride = (B-C)*0.03546*N*100/W', '(B-S)*0.03546*N*100/W', 4, True)]),
        T('ALFE', 'Lime Saturation Factor . (Al2O3 to Fe2O3 Ratio)', m, '', lim['alfe'], 2, 1, True, [],
          [C('ratio', 'Al2O3 / Fe2O3', 'R2O3_al2o3/FE2O3_result', 4, True)]),
        T('LSF', 'Ratio of percentage of lime to percentage of Silica, alumina and iron oxide', m, '', lim['lsf'], 2, 1,
          bool(lim['lsf']), [],
          [C('lsf', 'LSF = (CaO-0.7*SO3)/(2.8*SiO2+1.2*Al2O3+0.65*Fe2O3)',
             '(CAO_result-0.7*SO3_result)/((2.8*SIO2_result)+(1.2*R2O3_al2o3)+(0.65*FE2O3_result))', 4, True)]),
    ]


def fly_tests():
    m = 'IS 1727 :1967'
    return [
        T('LOI', 'Loss On Ignition', m, '%', '5.00 Max', 2, 1, True,
          [N('A', 'Weight of crucible (g)  A'), N('B', 'Weight of crucible + sample (g)  B'),
           N('C', 'Weight of crucible + sample after ignition (g)  C')],
          [C('loi', 'LOI % = (B-C)*100/(B-A)', '(B-C)*100/(B-A)', 4, True)]),
        T('SO3', 'Sulphur Anhydride (SO3)', 'IS 4032:2019', '%', '3.00 Max', 2, 1, True, crucible(),
          [C('so3', '% of SO3 = (C-B)*34.3/A', '(C-Bc)*34.3/A', 4, True)], report_name='Sulphur Anhydride (SO3)'),
        T('SIO2', 'Silica (SiO2)', 'IS 1727-1985', '%', '35.0 Min', 2, 1, True,
          crucible() + [N('D', 'Weight of impurities after ignition & HF treatment (g)  D')],
          [C('sio2', '% of Silica = (C-D)*100/A', '(C-D)*100/A', 4, True)], report_name='Silicon Dioxide as SiO2'),
        T('R2O3', 'Combined Alumina + Ferric Oxide', m, '%', '', 2, 1, False,
          [N('S', 'Sample taken (g)  A', 'SIO2_A'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C')],
          [C('r2o3', '% of combined R2O3 = (C-B)*100/A', '(C-Bc)*100/S', 4),
           C('al2o3', '% of Al2O3 = R2O3 - Fe2O3', 'r2o3-FE2O3_result', 4, True)]),
        T('FE2O3', 'Ferric Oxide Fe2O3', m, '%', '', 2, 1, False,
          [N('S', 'Sample taken (g)  W', 'SIO2_A'), N('N', 'Concentration of KMnO4 (N)'),
           N('V', 'Volume of KMnO4 used (ml)  V')],
          [C('fe2o3', '% of Fe2O3 = 0.07985*V*N*100/W', '0.07985*V*N*100/S', 4, True)]),
        T('CAO', 'Calcium Oxide (CaO)', m, '%', '', 2, 1, False,
          [N('S', 'Weight of sample (g)  A', 'FE2O3_S'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C')],
          [C('cao', 'CaO % = (C-B)*100/A', '(C-Bc)*100/S', 4, True)]),
        T('MGO', 'Magnesium oxide as MgO', m, '%', '5.00 Max', 2, 1, True,
          [N('S', 'Weight of sample (g)  A', 'CAO_S'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + residue after ignition (g)  C')],
          [C('mgo', 'MgO % = (C-B)/A*36.2', '(C-Bc)/S*36.2', 4, True)]),
        T('SUM', 'Silicon Dioxide + Iron Oxide + Aluminium Oxide', m, '%', '70 Min', 2, 1, True, [],
          [C('sum', 'SiO2 + Fe2O3 + Al2O3', 'SIO2_result+FE2O3_result+R2O3_al2o3', 4, True)]),
        T('IR', 'Insoluble Residue', 'IS 4032:2019', '%', '', 2, 1, False,
          [N('S', 'Initial weight of sample (g)  A', 'SO3_A'), N('Bc', 'Weight of empty crucible (g)  B'),
           N('C', 'Weight of crucible + sample after ignition (g)  C')],
          [C('ir', 'IR % = (C-B)/A*100', '(C-Bc)/S*100', 4, True)]),
        T('CL', 'Chloride', 'IS 4032 :1985', '%', '0.05 Max ', 3, 1, True,
          [N('W', 'Weight of sample (g)  W'), N('N', 'Normality of Ammonium Thiocyanate (N)'),
           N('Ag', 'Volume of Silver nitrate added (ml)'), N('S', 'NH4SCN consumed by sample (ml)'),
           N('B', 'NH4SCN consumed by blank (ml)')],
          [C('cl', '% Chloride = (B-C)*0.03546*N*100/W', '(B-S)*0.03546*N*100/W', 4, True)]),
    ]


def adm_tests():
    m = 'IS 9103:1999'
    T_ = lambda k, lab: N(k, lab)
    return [
        T('PH', 'pH', m, '--', 'Min. 6.0', 2, 1, True, [N('t', 'Temperature (°C)'), N('ph', 'pH'), T_('T', "Manufacturer's stated value (T)")],
          [C('res', 'pH', 'ph', 2, True)]),
        T('RD', 'Relative Density', m, '--', 'Within 0.02 of T', 3, 1, True, [N('t', 'Temperature (°C)'), N('rd', 'Relative density'), T_('T', "Manufacturer's stated value (T)")],
          [C('res', 'Relative density', 'rd', 3, True)]),
        T('DMC', 'Dry material content', m, '%', '0.95T ≤ DMC < 1.05T', 2, 1, True,
          [N('W1', 'Empty LOD bottle + sand (g)  W1'), N('W2', 'Sample + LOD bottle with sand (g)  W2'),
           N('W3', 'Weight after drying (g)  W3'), T_('T', "Manufacturer's stated value (T) %")],
          [C('res', 'DMC % = (W3-W1)*100/(W2-W1)', '(W3-W1)*100/(W2-W1)', 3, True)]),
        T('ASH', 'Ash Content', m, '%', '0.95T ≤ AC < 1.05T', 2, 1, True,
          [N('W1', 'Weight of empty crucible (g)  W1'), N('W2', 'Crucible + sample (g)  W2'),
           N('W3', 'Weight of crucible after ignition (g)  W3'), T_('T', "Manufacturer's stated value (T) %")],
          [C('res', 'Ash % = (W3-W1)*100/(W2-W1)', '(W3-W1)*100/(W2-W1)', 3, True)]),
        T('CL', 'Chloride Content', 'IS 9103:1999, IS 6925:1973', '%',
          'Within 10% of the value or within 0.20 % whichever is greater as stated by manufacturer', 3, 1, True,
          [N('W', 'Weight of sample (g)  W'), N('Ag', 'Volume of silver nitrate added (ml)'),
           N('N', 'Normality of Ammonium Thiocyanate (0.1N)'), N('B', 'NH4SCN consumed by blank B (ml)'),
           N('S', 'NH4SCN consumed by sample C (ml)'), T_('T', "Manufacturer's stated value (T) %")],
          [C('res', '% Chloride = (B-C)*0.03546*N*100/W', '(B-S)*0.03546*N*100/W', 4, True)]),
        T('SG', 'Specific Gravity at 27°C', m, '--', '', 3, 1, False,
          [N('W', 'Weight of empty S.G. bottle (g)  W'), N('W2', 'S.G. bottle + sample (g)  W2'),
           N('W1', 'S.G. bottle + water (g)  W1')],
          [C('res', 'Specific gravity = (W2-W)/(W1-W)', '(W2-W)/(W1-W)', 3, True)]),
    ]


def agg_tests(fine, sieve_p, sieve_r):
    soundness = lambda code, salt, lim: T(
        code, f'Soundness (IS 2386 Part V) in {salt}', 'IS 2386 (Part 5) : 1963 RA 2021', '%', lim, 2, 2, True,
        [N('pass', 'Sieve - passing', repr(sieve_p), kind='text'), N('ret', 'Sieve - retained', repr(sieve_r), kind='text'),
         N('W', 'Sample weight before test (g)')] + [N(f'c{i}', f'Weight retained on sieve after cycle {i} (g)') for i in range(1, 6)],
        [C(f'l{i}', f'Percent of loss, cycle {i}', f'(W-c{i})*100/W', 3) for i in range(1, 6)] +
        [C('avg', 'Soundness = average of cycles done', 'avg(l1,l2,l3,l4,l5)', 3, True)],
        report_name=f'Soundness in {"Sodium sulphates" if "Na" in salt else "Magnesium sulphate"}')
    m2 = 'IS 2386 (P2) 1963, RA 2016'
    lim_na, lim_mg = ('Max. 10 %', 'Max. 15 %') if fine else ('Max. 12 %', 'Max. 18 %')
    val = lambda code, name, lim, meth=m2, dec=2: T(code, name, meth, '%', lim, dec, 2, True,
                                                   [N('v', name + ' (%)')], [C('res', name, 'v', 6, True)])
    tests = [
        T('SILICA', 'Alkali Aggregate Reactivity - Silica Released', 'IS 2386 (P7) 1963, RA 2016', 'm mol/l', 'Not specified', 1, 1, True,
          [N('be', 'Blank: empty crucible weight (g)'), N('bi', 'Blank: weight after ignition (g)'), N('bh', 'Blank: crucible weight after HF treatment (g)'),
           N('se', 'Sample: empty crucible weight (g)'), N('si', 'Sample: weight after ignition (g)'), N('sh', 'Sample: crucible weight after HF treatment (g)')],
          [C('wb', 'Weight of silica - blank (W2)', '(bi-be)-(bh-be)', 5), C('ws', 'Weight of silica - sample (W1)', '(si-se)-(sh-se)', 5),
           C('res', 'Silica (m mol/l) = (W1-W2)*3330', '(ws-wb)*3330', 1, True)]),
        T('ALK', 'Alkali Aggregate Reactivity - Reduction in Alkali', 'IS 2386 (P7) 1963, RA 2016', 'm mol/l', 'Not specified', 1, 1, True,
          [N('N', 'Normality of 0.05N HCl'), N('V1', 'Diluted sample V1 (ml)'), N('V2', 'V2 sample (ml)'), N('V3', 'V3 blank (ml)')],
          [C('res', 'Reduction in alkalinity = 20*N*(V3-V2)*1000/V1', '20*N*(V3-V2)*1000/V1', 1, True)]),
        val('COAL', 'Coal', 'Max. 1%'), val('SHALE', 'Shale', 'Not specified'),
        val('CLAY', 'Clay Lumps', 'Max. 1%'),
        val('SILT', 'Silt Content' if fine else 'Silt & Clay Content', 'Not specified', 'IS 2386 (P2) 1963, RA 1997'),
        soundness('SNA', 'Na2SO4', lim_na), soundness('SMG', 'MgSO4', lim_mg),
        T('DEL', 'Deleterious Materials', m2, '%', 'Max. 2%', 2, 3, True, [],
          [C('res', 'Coal + Shale + Clay lumps + Silt', 'COAL_res+SHALE_res+CLAY_res+SILT_res', 4, True)]),
        T('ORG', 'Organic Impurities', m2, '', 'Not specified', 2, 3, True, [N('v', 'Organic impurities (e.g. Nil)', kind='text')],
          [C('res', 'Organic impurities', 'v', 2, True)]),
    ]
    for i, t in enumerate(tests):
        for c in t['calcs']:
            if c['is_result']:
                pass
    return tests


def seed_library(db):
    cem_titles = {'1': 'Chemical analysis of Cement Test'}
    opc = dict(loi='5.0 Max.', ir='5.0 Max.', mgo='6 Max.', alfe='Min. 0.66', lsf='0.66 - 1.02')
    for g in ('OPC 33', 'OPC 43', 'OPC 53'):
        mid = db.add_material(g, 'IS-269-2015', 'Cement', cem_titles)
        for i, t in enumerate(cement_tests('IS 4032:1985', opc, False)):
            t['sort'] = i; db.save_test(mid, t)
    ppc = dict(loi='5.0 Max', ir='Limits depends on declaired % of flyash in PPC cement. Refer the specification (IS 1489 Part 1 2015).',
               mgo='6.0 Max ', alfe='Not specified', lsf='')
    mid = db.add_material('PPC', 'IS-1489 (Pt-1)-2015', 'Cement', cem_titles)
    for i, t in enumerate(cement_tests('IS 4032:2019', ppc, True)):
        t['sort'] = i; db.save_test(mid, t)
    mid = db.add_material('Fly Ash', 'IS : 3812 -2022 (p-1)', 'Fly Ash', {'1': 'FLY ASH CHEMICAL ANALYSIS'})
    for i, t in enumerate(fly_tests()):
        t['sort'] = i; db.save_test(mid, t)
    mid = db.add_material('Admixture', 'IS 9103:1999 RA 2018', 'Admixture', {'1': 'Chemical analysis Parameters of Admixture'})
    for i, t in enumerate(adm_tests()):
        t['sort'] = i; db.save_test(mid, t)
    pages = {'1': 'AGGREGATE CHEMICAL ANALYSIS', '2': 'AGGREGATE ANALYSIS', '3': 'AGGREGATE ANALYSIS'}
    for name, fine, sp, sr in [('Fine Aggregate (Sand)', True, '600 micron', '300 micron'),
                               ('Coarse Aggregate 10mm', False, '10mm', '4.75mm'),
                               ('Coarse Aggregate 20mm', False, '20mm', '10mm')]:
        mid = db.add_material(name, 'IS 383:2016', 'Aggregate', pages)
        for i, t in enumerate(agg_tests(fine, sp, sr)):
            t['sort'] = i; db.save_test(mid, t)
