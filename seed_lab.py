"""Materials and tests taken from the lab's 'Observation_Sheet_Combine.xlsx' (one sheet per material).
Limits are left blank (the observation sheets do not give them) - fill them in the Test Library."""
from seed import N, C, T, cement_tests


def TE(code, name, method, unit, dec, fields, calcs, equip='', limit='', report_name='', rep=True):
    t = T(code, name, method, unit, limit, dec, 1, rep, fields, calcs, report_name)
    t['equip_hint'] = equip
    return t


def vol(code, name, method, unit, v1, v2, nlabel, expr, dec=2, equip='', v3='Sample volume V3 (ml)'):
    """Volumetric (titration) test: V3 sample volume, V1 / V2 titres, N strength."""
    return TE(code, name, method, unit, dec,
              [N('V3', v3), N('V1', v1), N('V2', v2), N('N', nlabel)], [C('res', name + ' = ' + expr, expr, dec + 2, True)], equip)


def curve(code, name, method, unit, wl, reagents, a_label, expr, dec=3, equip='', dil=True, a_key='A'):
    """Spectrophotometric test: reading taken from a standard graph."""
    f = [N('V', 'Sample volume V (ml)')]
    if dil:
        f.append(N('D', 'Dilution if any (factor)'))
    f += [N(k, l) for k, l in reagents]
    f += [N('Ab', f'Absorbance of the sample ({wl} nm)'), N(a_key, a_label)]
    return TE(code, name, method, unit, dec, f, [C('res', f'{name} = {expr}', expr, dec + 2, True)], equip)


def solids(code, name, method, empty_lbl, final_lbl, expr='(B-A)*1000*1000/V', equip='', unit='mg/L'):
    return TE(code, name, method, unit, 1,
              [N('V', 'Volume of sample taken V (ml)'), N('A', empty_lbl), N('B', final_lbl)],
              [C('res', f'{name} (mg/L) = {expr}', expr, 3, True)], equip)


# ====================================================================== AMBIENT AIR
def ambient_air():
    pm = lambda code, name, method, vexpr, vlabel: TE(
        code, name, method, 'ug/m3', 2,
        [N('fp', 'Filter paper No.', kind='text'), N('W1', 'Initial weight of filter paper (g) W1'), N('W2', 'Final weight of filter paper (g) W2'),
         N('st', 'Start time', kind='text'), N('et', 'End time', kind='text'), N('T', 'Time duration T (as used in your formula)'),
         N('Qi', 'Initial flow'), N('Qf', 'Final flow')],
        [C('W', 'Weight difference W = W2 - W1 (g)', 'W2-W1', 6), C('Q', 'Average flow rate Q = (initial + final) / 2', '(Qi+Qf)/2', 4),
         C('V', vlabel, vexpr, 3), C('res', f'{code} (ug/m3) = (W x 1000000) / V', '(W*1000000)/V', 2, True)])
    return [
        pm('PM10', 'Particulate Matter (PM10) - Ambient Air', 'IS 5182 (Part 23)', 'T*Q', 'Volume of gas V (m3) = T x Q'),
        pm('PM25', 'Fine Particulate Matter (PM2.5) - Ambient Air', 'IS 5182 (Part 24)', 'T*Q/1000', 'Volume of gas V (m3) = T x Q / 1000'),
        TE('SO2', 'Sulfur Dioxide (SO2)', 'IS 5182 (Part 2)', 'ug/m3', 2,
           [N('V', 'V = Volume of air sampled'), N('P', 'P = Barometric pressure (mm Hg)'), N('Tt', 'T = Temperature of air sampled (deg C)'),
            N('A', 'A = Sample absorbance'), N('A0', 'A0 = Reagent blank absorbance'), N('B', 'B = Calibration factor (ug / absorbance unit)'),
            N('D', 'D = Dilution factor (30 min & 1 h: 1; 24 h sample: 10)', '1')],
           [C('Vn', 'Vn = Volume of air at 25 C & 760 mm Hg = V x P/760 x 298/(t+273)', 'V*P/760*298/(Tt+273)', 4),
            C('res', 'SO2 ug/m3 (C) = ((A - A0) x 1000 x B x D) / Vn', '((A-A0)*1000*B*D)/Vn', 3, True)]),
        TE('NOX', 'Oxides of Nitrogen (as NO2)', 'IS 5182 (Part 6)', 'ug/m3', 2,
           [N('Fi', 'Fi = Air flow rate before sampling (Lpm)'), N('Fa', 'Fa = Air flow rate after sampling (Lpm)'), N('Ti', 'Ti = Initial time (hrs)'),
            N('Ta', 'Ta = Final time (hrs)'), N('As', 'Sample absorbance'), N('Ab', 'Blank absorbance'), N('GF', 'Graph factor'),
            N('Vs', 'Vs = Final volume of sample solution (ml)'), N('Vt', 'Vt = Aliquot taken for analysis (ml)'), N('D', 'D = Dilution factor', '1')],
           [C('Va', 'Va = Volume of air sampled = (Fi+Fa)/2 x (Ta-Ti) x 60 x 10-3', '(Fi+Fa)/2*(Ta-Ti)*60*0.001', 4), C('diff', 'Diff. absorbance = Sample - Blank', 'As-Ab', 4),
            C('no2', 'NO2 in analysed sample (ug) = Graph factor x Diff. abs', 'GF*diff', 4),
            C('res', 'NO2 ug/m3 = NO2 x D x Vs / (Va x 0.82 x Vt)   (0.82 = sampling efficiency)', '(no2*D*Vs)/(Va*0.82*Vt)', 3, True)]),
    ]


# ====================================================================== BUILDING LIME
def building_lime():
    return [
        TE('AVL', 'Available lime (as CaO)', 'IS 1514:1990', '%', 2,
           [N('M', 'M = mass of the material taken for the test (g)'), N('V1', 'V1 = volume of standard sodium thiosulphate used in the blank (ml)'),
            N('V2', 'V2 = volume of standard sodium thiosulphate used with the material (ml)'), N('N', 'N = Normality of standard sodium thiosulphate (N)')],
           [C('res', 'Available lime (as CaO) % = 56.08 x (V1-V2) x N / M', '56.08*(V1-V2)*N/M', 4, True)]),
        TE('LOI', 'Loss on Ignition', 'IS 4032:1985', '%', 2,
           [N('A', 'Weight of crucible (g) A'), N('B', 'Weight of crucible + sample (g) B'), N('C', 'Weight of crucible + sample after ignition (g) C')],
           [C('res', 'LOI % = (B-C) x 100 / (B-A)', '(B-C)*100/(B-A)', 4, True)]),
        TE('AIM', 'Acid Insoluble Matter', 'IS 6932 (Part 1)', '%', 2,
           [N('A', 'Sample taken (g) A'), N('Bc', 'Weight of empty crucible (g) B'), N('C', 'Weight of crucible + residue after ignition (g) C')],
           [C('res', '% of IR = (C-B) x 100 / A', '(C-Bc)*100/A', 4, True)]),
        TE('FM', 'Free Moisture', 'IS 1514:1990', '%', 2,
           [N('W1', 'Empty dish weight (g)'), N('W2', 'Sample + dish weight (g)'), N('W3', 'After drying weight (g)')],
           [C('res', '% Moisture = (W2-W3) x 100 / (W2-W1)', '(W2-W3)*100/(W2-W1)', 4, True)]),
        TE('SIO2', 'Silica (SiO2)', 'IS 6932 (Part 1)', '%', 2,
           [N('A', 'Sample taken (g) A'), N('Bc', 'Weight of empty crucible (g) B'), N('C', 'Weight of crucible + residue after ignition (g) C'),
            N('D', 'Weight of impurities after ignition & HF treatment (g) D')],
           [C('res', '% of Silica = (C-D) x 100 / A', '(C-D)*100/A', 4, True)]),
        TE('R2O3', 'Combined Ferric Oxide & Alumina', 'IS 6932 (Part 1)', '%', 2,
           [N('A', 'Sample weight (g)'), N('Bc', 'Empty crucible weight (g)'), N('C', 'Crucible + residue weight (g)')],
           [C('res', 'Combined Ferric Oxide & Alumina % = (C-B) x 100 / A', '(C-Bc)*100/A', 4, True),
            C('al2o3', 'Alumina % = Combined - Fe2O3 %', 'res-FE2O3_res', 4)]),
        TE('FE2O3', 'Ferric Oxide (Fe2O3)', 'IS 6932 (Part 1)', '%', 2,
           [N('W', 'Sample taken (g) W'), N('N', 'Normality of KMnO4 (0.04 N)'), N('V', 'Volume of potassium permanganate used (ml) V')],
           [C('res', '% of Fe2O3 = 0.07985 x V x N x 100 / W   (your sheet shows 0.7985 - see note)', '0.07985*V*N*100/W', 4, True)]),
        TE('CAO', 'Calcium Oxide (CaO)', 'IS 6932 (Part 1)', '%', 2,
           [N('W', 'Sample taken (g) W'), N('W2', 'Weight of empty crucible (g) W2'), N('W3', 'Weight of crucible after drying (g) W3')],
           [C('res', '% of CaO = (W3-W2) x 100 / W', '(W3-W2)*100/W', 4, True)]),
        TE('MGO', 'Magnesium Oxide (MgO)', 'IS 6932 (Part 1)', '%', 2,
           [N('M', 'M = mass of the sample (g)'), N('B', 'Weight of empty crucible (g) B'), N('C', 'Weight of crucible + residue after ignition (g)')],
           [C('res', 'MgO % = 36.2 x ignited residue / sample weight', '36.2*(C-B)/M', 4, True)]),
    ]


# ====================================================================== GGBS (same tests as cement)
def ggbs():
    tests = cement_tests('IS 4032:1985', dict(loi='', ir='', mgo='', alfe='', lsf=''), False)
    for t in tests:
        t['limit_text'] = ''
        if t['code'] in ('ALFE', 'LSF'):
            t['in_report'] = 0
    return tests


# ====================================================================== HARDENED CONCRETE
def hardened_concrete():
    return [
        TE('PH', 'pH of Hardened Concrete', 'CT-SOP-01-2025', '--', 2,
           [N('t', 'Temperature (deg C)'), N('ph', 'pH')], [C('res', 'pH', 'ph', 2, True)]),
        TE('CL', 'Chloride Test', 'IS 14959 (Part 2) : 2001', '%', 3,
           [N('sid', 'Sample identification', kind='text'), N('W', 'Sample weight (g)'), N('Vn', 'Volume of nitric acid (ml)'),
            N('x', 'Volume of silver nitrate (x) (ml)'), N('fa', 'Volume of ferric alum (ml)'), N('nb', 'Volume of nitrobenzene (ml)'),
            N('N', 'Normality of ammonium thiocyanate (N)'), N('y', 'B.R. (Y) (ml)')],
           [C('g', 'Chloride (helper) = 0.00142 x (x - y)', '0.00142*(x-y)', 5),
            C('res', 'Chloride = 2 x 0.709 x (x - y) / 100', '2*0.709*(x-y)/100', 4, True)]),
        TE('SO3', 'Acid Soluble Sulphate Test', 'BS 1881 (Part 124)', '% SO3', 3,
           [N('sid', 'Sample identification', kind='text'), N('grade', 'Grade of concrete', kind='text'), N('pc', 'Percent of cement (%)'),
            N('Md', 'Mass of sample (g) Md'), N('cr', 'Cement content of the sample (cr)', 'pc'), N('A', 'Empty crucible weight (A)'),
            N('B', 'Crucible + ignited sample (B)')],
           [C('L', 'L = B - A', 'B-A', 5), C('res', 'SO3 % = L / Md x 34.3 x 100 / cr', 'L/Md*34.3*100/cr', 4, True)]),
    ]


# ====================================================================== SOIL
def soil():
    ma = 'Ministry of Agriculture 2011'
    return [
        TE('MC', 'Moisture Content', 'IS 2720 (Part 2)', '%', 2,
           [N('W1', 'Weight of empty petri dish (W1) (g)'), N('W2', 'Weight of petri dish + sample (W2) (g)'), N('W3', 'Weight of petri dish + sample after drying at 105 C (W3) (g)')],
           [C('res', '% Moisture = ((W2-W1)-(W3-W1)) x 100 / (W2-W1)', '((W2-W1)-(W3-W1))*100/(W2-W1)', 4, True)]),
        TE('TOM', 'Total Organic Matter', 'IS 2720 (Part 22)', '%', 2,
           [N('Y', 'Total volume of ferrous sulphate used in this test (Y) (ml)'), N('X', 'Total volume of ferrous sulphate used in the standardization test (X) (ml)'),
            N('W2', 'Weight (oven-dry) of soil passing 10 mm IS sieve (W2) (g)'), N('W1', 'Weight (oven-dry) of total soil sample before sieving (W1) (g)'),
            N('W3', 'Weight (oven-dry) of soil specimen used in the test (W3) (g)'), N('om', 'Organic matter % (enter from your calculation - formula not in sheet)')],
           [C('V', 'V = volume of potassium dichromate used to oxidise the organic matter = 10.5 x (1 - Y/X)', '10.5*(1-Y/X)', 4),
            C('res', 'Organic matter %', 'om', 3, True)]),
        TE('TOC', 'Total Organic Carbon', ma, '%', 2, [],
           [C('res', '% Organic carbon = % OM x 0.58', 'TOM_res*0.58', 4, True)]),
        TE('PH', 'pH', 'IS 2720 (Part 26)', '--', 2,
           [N('wt', 'Soil sample taken for analysis (g) (30 g)', '30'), N('susp', 'Suspension of sample in 75 ml aerated distilled water prepared', kind='text'),
            N('ph', 'pH observed')], [C('res', 'pH', 'ph', 2, True)]),
        TE('AS', 'Available Sulphur', ma, 'mg/kg', 2,
           [N('W', 'Quantity of sulphur (mg) read from standard curve (W)'), N('W1', 'Weight of the soil sample (g) (W1)', '20'),
            N('V1', 'Volume of the extractant (ml) (V1)', '100'), N('V2', 'Volume of extractant in which turbidity is developed (ml) (V2)', '10')],
           [C('res', 'Available Sulphur (SO4-S) mg/kg = W x V1 / (V2 x W1)', 'W*V1/(V2*W1)', 4, True)]),
        TE('TEMI', 'Total Exchangeable Metallic Ions', 'IS 2720 (Part 24)', 'meq', 2,
           [N('W', 'Dried soil sample taken for analysis (W) (g)'), N('Ve', 'Volume of extract taken (Ve) (ml)'), N('N', 'Normality of standard solution (N)'),
            N('Vb', 'Volume of std. NaOH used in blank (Vb) (ml)'), N('Va', 'Volume of std. HCl taken (Va) (ml)')],
           [C('res', 'Total exchangeable metallic ions (meq) = (Va-Vb) x N x (1000x100) / (Ve x W)', '(Va-Vb)*N*(1000*100)/(Ve*W)', 4, True)]),
        TE('TEHI', 'Total Exchangeable Hydrogen Ions', 'IS 2720 (Part 24)', 'meq/100 g', 2,
           [N('T', 'T = volume of sodium hydroxide used in titration of soil extraction (ml)'), N('B', 'B = volume of sodium hydroxide used for the blank titration (ml)'),
            N('N', 'N = Normality of standard sodium hydroxide solution (N)'), N('M', 'Mass of soil (g)')],
           [C('res', 'meq exchangeable H+ per 100 g soil = (T-B) x N x 100 / mass of soil', '(T-B)*N*100/M', 4, True)]),
        TE('CEC', 'Cation Exchange Capacity', 'IS 2720 (Part 24)', 'meq/100 g', 2, [],
           [C('res', 'CEC (meq/100 g) = exchangeable metallic ions + exchangeable hydrogen ions', 'TEMI_res+TEHI_res', 4, True)]),
        TE('CACO3', 'Calcium Carbonate', 'IS 2720 (Part 23)', '%', 2,
           [N('W', 'Dried soil sample taken for analysis (W) (g) (5 g)', '5'), N('V', 'Volume of 1 N HCl used by the soil (V) (ml)')],
           [C('res', 'Carbonate present % by mass = V x 0.05 x 100 / W', 'V*0.05*100/W', 4, True)]),
        TE('EC', 'Electrical Conductance', ma, 'mS/cm', 3,
           [N('wt', 'Exact weight of soil sample taken (40 g)', '40'), N('std', 'Conductivity of standard 1.412 mS/cm at 25 C (observed)'),
            N('ec', 'Electrical conductivity of soil filtrate (mS/cm)')], [C('res', 'Electrical conductivity of soil filtrate (mS/cm)', 'ec', 3, True)]),
        TE('AP', 'Available Phosphorus as P', ma, 'kg/ha', 2,
           [N('V', 'Sample volume V (ml)'), N('D', 'Dilution if any'), N('Ab', 'Absorbance of the sample at 420 nm'),
            N('A', 'Concentration of P in sample solution (ug/ml) (A) from std. curve'), N('Ws', 'Weight of soil (g)', '5'),
            N('Vx', "Bray's extractant (ml)", '50'), N('Va', 'Soil extract taken for colour development (ml)', '5'), N('Vf', 'Final volume after colour development (ml)', '25')],
           [C('pct', '% of Phosphorus P = A x Vf x Vx x 100 / (Va x 1000 x Ws x 1000)', 'A*Vf*Vx*100/(Va*1000*Ws*1000)', 6),
            C('res', 'Phosphorus as P (kg/ha) = A x 50 x 2000000 / (1000000 x 5 x 5) = 4A', '4*A', 4, True)]),
        TE('AK', 'Potassium as K', ma, 'kg/ha', 2,
           [N('S', 'Sample taken (g)'), N('D', 'Dilution if any'), N('DF', 'Dilution factor (D)'), N('A', 'Concentration of K in sample solution (ug/ml) (A) from std. curve'),
            N('Ve', 'Volume of ammonium acetate extractant (ml)', '25'), N('Ws', 'Weight of soil sample (g)', '5')],
           [C('pct', '% of Potassium K = A x Ve x 100 / (1000 x 1000 x Ws)', 'A*Ve*100/(1000*1000*Ws)', 6),
            C('res', 'Potassium as K (kg/ha) = 10 x A', '10*A', 4, True)]),
        TE('TN', 'Total Nitrogen (Kjeldahl Method)', ma, '%', 3,
           [N('V1', 'V1 - ml of standard acid taken in receiving flask for sample'), N('V2', 'V2 - ml of standard NaOH used in titration'),
            N('V3', 'V3 - ml of standard acid taken in receiving flask for blank'), N('V4', 'V4 - ml of standard NaOH used in titrating blank'),
            N('M1', 'M1 - Molarity of standard acid (M)'), N('M2', 'M2 - Molarity of standard NaOH (M)'), N('W', 'W - Weight of sample taken (g) (1 g)', '1'),
            N('df', 'df - dilution factor', '1')],
           [C('res', '% N = 1.401 x [(V1xM1 - V2xM2) - (V3xM1 - V4xM2)] x df / W', '1.401*((V1*M1-V2*M2)-(V3*M1-V4*M2))*df/W', 5, True)]),
        TE('CN', 'Carbon : Nitrogen Ratio (C:N)', ma, '--', 2,
           [N('C', 'Carbon %', 'TOC_res'), N('Nn', 'Nitrogen %', 'TN_res')], [C('res', 'Carbon / Nitrogen ratio', 'C/Nn', 3, True)]),
    ]


# ====================================================================== WATER (waste / drinking / construction)
def ww_tests():
    ap = 'APHA 24th Edition '
    return [
        TE('COL', 'Colour', ap + '2120 B', 'CU', 0,
           [N('ph', 'pH'), N('A', 'Sample matching with colour standard (A) in CU'), N('B', 'Sample taken or sample quantity taken for dilution (if any) (B)')],
           [C('res', 'Colour Unit (CU) = (50 x A) / B', '(50*A)/B', 3, True)]),
        vol('ACID', 'Total Acidity', 'IS 3025 (Part 22)', 'mg/L', 'Vol. of NaOH used by sample (V1) (ml)', 'Vol. of NaOH used by blank (V2) (ml)',
            'Normality of NaOH (0.02 N)', '((V1-V2)*N*50*1000)/V3'),
        vol('ALK', 'Total Alkalinity', ap + '2320 B', 'mg/L', 'Vol. of H2SO4 used by sample (V1) (ml)', 'Vol. of H2SO4 used by blank (V2) (ml)',
            'Normality of H2SO4 (0.02 N)', '((V1-V2)*N*50*1000)/V3'),
        vol('NH3', 'Ammonical Nitrogen', ap + '4500 NH3 C', 'mg/L', 'Vol. of H2SO4 used by sample (V1) (ml)', 'Vol. of H2SO4 used by blank (V2) (ml)',
            'Normality of H2SO4 (0.02 N)', '((V1-V2)*N*14*1000)/V3'),
        vol('CL', 'Chloride', 'IS 3025 (Part 32)', 'mg/L', 'Vol. of AgNO3 by sample (V1) (ml)', 'Vol. of AgNO3 by blank (V2) (ml)',
            'Normality of Silver Nitrate (0.0141 N)', '((V1-V2)*N*35450)/V3'),
        TE('OG', 'Oil & Grease', 'IS 3025 (Part 39)', 'mg/L', 2,
           [N('V1', 'Sample volume (V1) (ml)'), N('W1', 'Empty weight of round bottom flask (W1) (g)'), N('W2', 'Weight of round bottom flask + oil residue (W2) (g)')],
           [C('res', 'Oil & Grease mg/L = (W2-W1) x 1000 x 1000 / V1', '(W2-W1)*1000*1000/V1', 3, True)]),
        TE('PH', 'pH', 'IS 3025 (Part 11)', '--', 2, [N('V', 'Volume of water (ml)'), N('ph', 'pH value')], [C('res', 'pH', 'ph', 2, True)]),
        TE('TURB', 'Turbidity', ap + '2130 B', 'NTU', 1, [N('V', 'Volume of water (ml)'), N('ntu', 'NTU')], [C('res', 'Turbidity NTU', 'ntu', 2, True)]),
        TE('EC', 'Electrical Conductivity', 'IS 3025 (Part 14)', 'mS/m', 2,
           [N('V', 'Volume of water (ml)'), N('t', 'Sample temperature (deg C)'), N('ec', 'Electrical conductivity (mS/m)')], [C('res', 'Electrical conductivity mS/m', 'ec', 2, True)]),
        TE('COD', 'Chemical Oxygen Demand', 'IS 3025 (Part 58)', 'mg/L', 1,
           [N('V0', 'Sample taken V0 (ml)'), N('V1', 'Burette reading for blank V1 (ml)'), N('V2', 'Burette reading for sample V2 (ml)'),
            N('N', 'Normality of Ferrous Ammonium Sulphate (N)')], [C('res', 'COD mg/L = (V1-V2) x N x 8000 / V0', '(V1-V2)*N*8000/V0', 3, True)]),
        TE('DO', 'Dissolved Oxygen', 'IS 3025 (Part 38)', 'mg/L', 2,
           [N('ml', 'ml of sample taken'), N('N', 'Normality of Sodium Thiosulphate (0.025 N)'), N('D1', 'Initial DO of sample (D1) - ml of thiosulphate consumed (V1)'),
            N('B1', 'Initial DO of blank (B1) - ml of thiosulphate consumed')],
           [C('blank', 'DO of blank (B1)', 'B1', 3), C('res', 'DO mg/L = volume of sodium thiosulphate consumed V1 (ml)', 'D1', 3, True)]),
        TE('BOD', 'Biochemical Oxygen Demand', 'IS 3025 (Part 44)', 'mg/L', 1,
           [N('D1', 'Initial DO of sample (D1)'), N('B1', 'Initial DO of blank (B1)'), N('D2', 'Final DO of sample (D2)'), N('B2', 'Final DO of blank (B2)'),
            N('sv', 'Sample volume (ml)'), N('dv', 'Diluted to (ml)'), N('seed', 'Seed (ml)')],
           [C('P', 'Dilution fraction P = sample volume / diluted volume', 'sv/dv', 5), C('pct', '% Dilution of sample', 'P*100', 3),
            C('res', 'BOD mg/L = ((D1-D2) - (B1-B2)) / P', '((D1-D2)-(B1-B2))/P', 3, True)]),
        vol('TH', 'Total Hardness', ap + '2340 C', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)',
            'Molarity of EDTA (0.01 M)', '((V1-V2)*N*100*1000)/V3'),
        vol('CAH', 'Calcium Hardness (as CaCO3)', ap + '3500 Ca B', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)',
            'Molarity of EDTA (0.01 M)', '((V1-V2)*N*100*1000)/V3'),
        vol('CA', 'Calcium as Ca', ap + '3500 Ca B', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)',
            'Molarity of EDTA (0.01 M)', '((V1-V2)*N*40.08*1000)/V3'),
        TE('MGH', 'Magnesium Hardness', ap + '3500 Mg B', 'mg/L', 2,
           [N('A', 'Total hardness (A) (mg/L)', 'TH_res'), N('B', 'Calcium hardness (B) (mg/L)', 'CAH_res')], [C('res', 'Magnesium hardness mg/L = A - B', 'A-B', 3, True)]),
        TE('MG', 'Magnesium as Mg', ap + '3500 Mg B', 'mg/L', 2,
           [N('H', 'Magnesium hardness (mg/L)', 'MGH_res')], [C('res', 'Magnesium as Mg mg/L = Magnesium hardness x 0.243', 'H*0.243', 3, True)]),
        TE('SULFIDE', 'Sulphide Content', ap + '4500 S2-F', 'mg/L', 2,
           [N('V', 'Sample volume (ml) (V)'), N('A', 'ml of iodine solution (A)'), N('B', 'Normality of Iodine Solution (B) (0.025 N)'),
            N('C', 'ml of sodium thiosulphate (C)'), N('D', 'Normality of Sodium Thiosulphate (D) (0.025 N)')],
           [C('res', 'Sulphide (S2-) mg/L = [(A x B) - (C x D)] x 16000 / V', '((A*B)-(C*D))*16000/V', 3, True)]),
        TE('SULFITE', 'Sulphite Content', ap + '4500 SO3 B', 'mg/L', 2,
           [N('V', 'Sample volume (ml) (V)'), N('A', 'ml of KI-KIO3 titrant consumed for sample (A)'), N('B', 'ml of KI-KIO3 titrant consumed for blank (B)'),
            N('M', 'Molarity of KI-KIO3 Solution (0.002083 M)')],
           [C('res', 'Sulphite (SO3-2) mg/L = (A-B) x M x 6 x 40000 / V', '(A-B)*M*6*40000/V', 3, True)]),
        solids('TDS', 'Total Dissolved Solids', ap + '2540 C', 'Weight of empty evaporating dish (g) (A)', 'Evaporating dish + residue after drying at 180 C (g) (B)'),
        solids('TS', 'Total Solids', ap + '2540 B', 'Weight of empty evaporating dish (g) (A)', 'Evaporating dish + residue after drying at 180 C (g) (B)'),
        solids('TSS', 'Total Suspended Solids', ap + '2540 D', 'Weight of Whatman filter paper 542 (g) (A)', 'Weight of filter paper after drying at 103-105 C for 1 hour (g) (B)'),
        TE('FR', 'Fixed Residue', 'IS 3025 (Part 18)', 'mg/L', 1,
           [N('V', 'Sample volume V (ml)'), N('A', 'Weight of empty evaporating dish (g) (A)'), N('C', 'Evaporating dish + residue after drying at 550 C for 1 hour (g) (C)')],
           [C('res', 'Fixed residue mg/L = (C-A) x 1000 x 1000 / V', '(C-A)*1000*1000/V', 3, True)]),
        TE('VR', 'Volatile Residue', 'IS 3025 (Part 18)', 'mg/L', 1,
           [N('A', 'Total solids mg/L (A)', 'TS_res'), N('B', 'Fixed residue mg/L (B)', 'FR_res')], [C('res', 'Volatile residue mg/L = A - B', 'A-B', 3, True)]),
        curve('SO4', 'Sulphate', ap + '4500 SO4-2 E', 'mg/L', 420, [('buf', 'Volume of buffer added (ml)')], 'Sulphate in sample from standard curve (mg/L)', 'A*iff(blank(D),1,D)', 2),
        TE('FLU', 'Fluoride', ap + '4500 F D', 'mg/L', 2,
           [N('V', 'Sample volume V (ml)'), N('sp', 'Volume of SPANDS added (ml)'), N('Ab', 'Absorbance of the sample (570 nm)'), N('A', 'ug of fluoride from std. graph (A)'),
            N('B', 'Final diluted volume of sample (ml) (B)'), N('Cv', 'Volume of diluted sample used for colour development (ml) (C)')],
           [C('res', 'Fluoride mg/L = A x B / (V x C)', 'A*B/(V*Cv)', 4, True)]),
        curve('FE', 'Iron', ap + '3500 Fe B', 'mg/L', 510, [('ph', 'Volume of phenanthroline added (ml)')], 'ug of iron from std. graph (A)', 'A/V', 3),
        curve('PO4', 'Phosphate', ap + '4500 P D', 'mg/L', 690, [('mo', 'Volume of ammonium molybdate reagent added (ml)'), ('sn', 'Volume of stannous chloride reagent added (ml)')],
              'mg of phosphate from std. graph (A)', 'A*1000/V', 3),
        curve('SIO2', 'Silica', ap + '4500 SiO2 C', 'mg/L', 410, [('mo', 'Volume of ammonium molybdate reagent added (ml)'), ('ox', 'Volume of oxalic acid reagent added (ml)')],
              'ug of silica from std. graph (A)', 'A/V', 3),
        curve('NO3', 'Nitrate', 'IS 3025 (Part 34)', 'mg/L', 410, [('sb', 'Volume of antimony reagent added (ml)'), ('cr', 'Volume of chromotropic acid reagent added (ml)')],
              'ug of nitrate from std. graph (A)', 'A/V', 3),
        curve('NO2', 'Nitrite', ap + '4500 NO2- B', 'mg/L', 543, [('cr', 'Volume of colour reagent added (ml)')], 'ug of nitrite from std. graph (A)', 'A/V', 3),
        TE('BOR', 'Boron', 'IS 3025 (Part 57)', 'mg/L', 3,
           [N('V', 'Sample volume (V) (ml)'), N('D', 'Dilution if any (D)', '1'), N('cr', 'Volume of colour reagent added (ml)'), N('Ab', 'Absorbance of the sample (540 nm)'),
            N('Bm', 'Mass of boron std taken in ug (B)')], [C('res', 'Boron mg/L = B x D / V', 'Bm*D/V', 5, True)]),
        curve('BR', 'Bromide', ap + '4500 Br B', 'mg/L', 590, [('ct', 'Volume of chloramine-T solution added (ml)')], 'mg of bromide/L from std. graph', 'A*iff(blank(D),1,D)', 3),
        curve('CR6', 'Hexavalent Chromium', 'IS 3025 (Part 52)', 'mg/L', 540, [('dp', 'Volume of diphenyl carbazide solution added (ml)')], 'ug chromium observed from std. graph (A)', 'A/V', 4),
        curve('PHEN', 'Phenol', ap + '5530 D', 'mg/L', 500, [('aap', 'Volume of 4-amino antipyrine solution added (ml)')], 'mg phenol observed from std. graph (A)', 'A*1000/V', 4, dil=False),
        TE('NA', 'Sodium', ap + '3500 Na B', 'mg/L', 2,
           [N('V', 'Sample quantity (V) (ml)'), N('D', 'Dilution ratio (D) = (V + ml water) / V'), N('R', 'Reading of diluted portion on flame photometer (mg/L)')],
           [C('res', 'Sodium mg/L = reading x D', 'R*D', 3, True)]),
        TE('K', 'Potassium', ap + '3500 K B', 'mg/L', 2,
           [N('V', 'Sample quantity (V) (ml)'), N('D', 'Dilution ratio (D) = (V + ml water) / V'), N('R', 'Reading of diluted portion on flame photometer (mg/L)')],
           [C('res', 'Potassium mg/L = reading x D', 'R*D', 3, True)]),
        TE('SAR', 'Sodium Absorption Ratio', 'IS 11624', '--', 2,
           [N('Ca', 'Calcium in mg/L (Ca)', 'CA_res'), N('Na', 'Sodium in mg/L (Na)', 'NA_res'), N('Mg', 'Magnesium in mg/L (Mg)', 'MG_res')],
           [C('res', 'SAR = Na / sqrt((Ca + Mg) / 2) with each in meq/L (Na/23, Ca/20.04, Mg/12.15)', 'Na/23/sqrt((Ca/20.04+Mg/12.15)/2)', 4, True)]),
        TE('TEMP', 'Temperature', ap + '2550 B', 'deg C', 1, [N('t', 'Temperature in deg C')], [C('res', 'Temperature', 't', 1, True)]),
    ]


def waste_water():
    return ww_tests()


def drinking_water():
    ap = 'APHA 24th Edition '
    e = lambda a, b: f'{a}, {b}'
    tests = [
        TE('ODOUR', 'Odour', 'IS 3025 (Part 5)', '--', 0,
           [N('egg', 'Rotten egg', kind='text'), N('sugar', 'Burnt sugar', kind='text'), N('soap', 'Soapy', kind='text'), N('fish', 'Fishy septic', kind='text'),
            N('arom', 'Aromatic', kind='text'), N('chl', 'Chlorinous', kind='text'), N('alc', 'Alcoholic', kind='text'), N('oth', 'Any other', kind='text'),
            N('agr', 'Agreeable / Not agreeable', kind='text')], [C('res', 'Odour', 'agr', 0, True)]),
        TE('PH', 'pH', 'IS 3025 (Part 11)', '--', 2, [N('V', 'Volume of water (ml)'), N('ph', 'pH value')], [C('res', 'pH', 'ph', 2, True)]),
        TE('TURB', 'Turbidity', 'IS 3025 (Part 10)', 'NTU', 1, [N('V', 'Volume of water (ml)'), N('ntu', 'NTU')], [C('res', 'Turbidity NTU', 'ntu', 2, True)]),
        TE('COLOUR', 'Colour', 'IS 3025 (Part 4) by visual comparison', 'Hazen', 0, [N('c', 'Colour (Hazen units)')], [C('res', 'Colour', 'c', 1, True)]),
    ]
    # taste panel: 6 members x 4 dilutions
    f = []
    for i in range(1, 7):
        f += [N(f'p{i}', f'Panel member {i} - name', kind='text'), N(f'o{i}', f'Member {i} - original sample'), N(f'a{i}', f'Member {i} - dilution A (25 ml to 200 ml)'),
              N(f'b{i}', f'Member {i} - dilution B (25 ml of A to 200 ml)'), N(f'c{i}', f'Member {i} - dilution C (25 ml of B to 200 ml)')]
    f.append(N('verdict', 'Acceptable / Not acceptable', kind='text'))
    tests.append(TE('TASTE', 'Taste', 'IS 3025 (Part 7)', '--', 1, f,
                    [C('mo', 'Mean - original sample', 'avg(o1,o2,o3,o4,o5,o6)', 2), C('ma', 'Mean - dilution A', 'avg(a1,a2,a3,a4,a5,a6)', 2),
                     C('mb', 'Mean - dilution B', 'avg(b1,b2,b3,b4,b5,b6)', 2), C('mc', 'Mean - dilution C', 'avg(c1,c2,c3,c4,c5,c6)', 2),
                     C('res', 'Taste: acceptable / not acceptable', 'verdict', 0, True)]))
    BO, BP, PS, BB = 'Balance, Oven', 'Burette, Pipette', 'Pipette, Spectrophotometer', 'Balance, Burette'
    t = lambda x, eq: (x.__setitem__('equip_hint', eq), x)[1]
    tests += [
        t(solids('TDS', 'Total Dissolved Solids', 'IS 3025 (Part 16)', 'Weight of empty evaporating dish (g) (A)', 'Evaporating dish + residue after drying at 180 C (g) (B)'), BO),
        t(vol('CL', 'Chloride', 'IS 3025 (Part 32)', 'mg/L', 'Vol. of AgNO3 by sample (V1) (ml)', 'Vol. of AgNO3 by distilled water (V2) (ml)', 'Normality of Silver Nitrate (0.0141 N)', '((V1-V2)*N*35450)/V3'), BP),
        t(TE('OG', 'Oil & Grease', 'IS 3025 (Part 39)', 'mg/L', 2,
             [N('V1', 'Sample volume (V1) (ml)'), N('W1', 'Empty weight of round bottom flask (W1) (g)'), N('W2', 'Weight of round bottom flask + oil residue (W2) (g)')],
             [C('res', 'Oil & Grease mg/L = (W2-W1) x 1000 x 1000 / V1', '(W2-W1)*1000*1000/V1', 3, True)]), BO),
        t(TE('COD', 'Chemical Oxygen Demand', 'IS 3025 (Part 58)', 'mg/L', 1,
             [N('V0', 'Sample taken V0 (ml)'), N('V1', 'Burette reading for blank V1 (ml)'), N('V2', 'Burette reading for sample V2 (ml)'),
              N('N', 'Normality of Ferrous Ammonium Sulphate (N)')], [C('res', 'COD mg/L = (V1-V2) x N x 8000 / V0', '(V1-V2)*N*8000/V0', 3, True)]), 'Burette, COD Digestor'),
        t(TE('DO', 'Dissolved Oxygen', 'IS 3025 (Part 38)', 'mg/L', 2,
             [N('ml', 'ml of sample taken'), N('N', 'Normality of Sodium Thiosulphate (0.025 N)'), N('D1', 'Initial DO of sample (D1) - ml of thiosulphate consumed (V1)'),
              N('B1', 'Initial DO of blank (B1) - ml of thiosulphate consumed')],
             [C('blank', 'DO of blank (B1)', 'B1', 3), C('res', 'DO mg/L = volume of sodium thiosulphate consumed V1 (ml)', 'D1', 3, True)]), BP),
        t(TE('BOD', 'Biochemical Oxygen Demand', 'IS 3025 (Part 44)', 'mg/L', 1,
             [N('D1', 'Initial DO of sample (D1)'), N('B1', 'Initial DO of blank (B1)'), N('D2', 'Final DO of sample (D2)'), N('B2', 'Final DO of blank (B2)'),
              N('sv', 'Sample volume (ml)'), N('dv', 'Diluted to (ml)'), N('seed', 'Seed (ml)')],
             [C('P', 'Dilution fraction P = sample volume / diluted volume', 'sv/dv', 5), C('pct', '% Dilution of sample', 'P*100', 3),
              C('res', 'BOD mg/L = ((D1-D2) - (B1-B2)) / P', '((D1-D2)-(B1-B2))/P', 3, True)]), BP),
        t(vol('TH', 'Total Hardness', 'IS 3025 (Part 21)', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)', 'Molarity of EDTA (0.01 M)', '((V1-V2)*N*100*1000)/V3'), BP),
        t(vol('CAH', 'Calcium Hardness', ap + '3500 Ca B', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)', 'Molarity of EDTA (0.01 M)', '((V1-V2)*N*100*1000)/V3'), BP),
        t(vol('CA', 'Calcium as Ca', ap + '3500 Ca B', 'mg/L', 'Vol. of EDTA used by sample (V1) (ml)', 'Vol. of EDTA used by blank (V2) (ml)', 'Molarity of EDTA (0.01 M)', '((V1-V2)*N*40.08*1000)/V3'), BP),
        t(TE('MGH', 'Magnesium Hardness', ap + '3500 Mg B', 'mg/L', 2, [N('A', 'Total hardness (A) (mg/L)', 'TH_res'), N('B', 'Calcium hardness (B) (mg/L)', 'CAH_res')],
             [C('res', 'Magnesium hardness mg/L = A - B', 'A-B', 3, True)]), BP),
        t(TE('MG', 'Magnesium as Mg', ap + '3500 Mg B', 'mg/L', 2, [N('H', 'Magnesium hardness (mg/L)', 'MGH_res')],
             [C('res', 'Magnesium as Mg mg/L = Magnesium hardness x 0.243', 'H*0.243', 3, True)]), BP),
        t(vol('ALK', 'Total Alkalinity', ap + '2320 Alk', 'mg/L', 'Vol. of H2SO4 consumed by sample (V1) (ml)', 'Vol. of H2SO4 consumed by blank (V2) (ml)', 'Normality of H2SO4 (0.02 N)', '((V1-V2)*N*50*1000)/V3'), BP),
        t(TE('EC', 'Electrical Conductivity', 'IS 3025 (Part 14)', 'mS/m', 2, [N('V', 'Volume of water (ml)'), N('t', 'Sample temperature (deg C)'), N('ec', 'Electrical conductivity (mS/m)')],
             [C('res', 'Electrical conductivity mS/m', 'ec', 2, True)]), 'Burette, Conductivity Meter'),
        t(vol('RCL', 'Residual Chlorine', ap + '4500 Cl B', 'mg/L', 'Vol. of Na2S2O3 used by sample (V1) (ml)', 'Vol. of Na2S2O3 used by blank (V2) (ml)', 'Normality of Na2S2O3 (0.1 N)', '((V1-V2)*N*35450)/V3', v3='Sample volume (ml) (V3)'), BP),
        t(curve('SO4', 'Sulphate', 'IS 3025 (Part 24 Sec 1)', 'mg/L', 420, [('buf', 'Volume of buffer added (ml)')], 'Sulphate in sample from standard curve (mg/L)', 'A*iff(blank(D),1,D)', 2), PS),
        t(TE('FLU', 'Fluoride', ap + '4500 F', 'mg/L', 2,
             [N('V', 'Sample volume V (ml)'), N('sp', 'Volume of SPANDS added (ml)'), N('Ab', 'Absorbance of the sample (570 nm)'), N('A', 'ug of fluoride from std. graph (A)'),
              N('B', 'Final diluted volume of sample (ml) (B)'), N('Cv', 'Volume of diluted sample used for colour development (ml) (C)')],
             [C('res', 'Fluoride mg/L = A x B / (V x C)', 'A*B/(V*Cv)', 4, True)]), PS),
        t(curve('FE', 'Iron', ap + '3500 Fe', 'mg/L', 510, [('ph', 'Volume of phenanthroline added (ml)')], 'ug of iron from std. graph (A)', 'A/V', 3), PS),
        t(curve('PO4', 'Phosphate', ap + '4500 P D', 'mg/L', 690, [('mo', 'Volume of ammonium molybdate reagent added (ml)'), ('sn', 'Volume of stannous chloride reagent added (ml)')],
                'mg of phosphate from std. graph (A)', 'A*1000/V', 3), PS),
        t(curve('SIO2', 'Silica', ap + '4500 SiO2 C', 'mg/L', 610, [('mo', 'Volume of ammonium molybdate reagent added (ml)'), ('ox', 'Volume of oxalic acid reagent added (ml)')],
                'ug of silica from std. graph (A)', 'A/V', 3), PS),
        t(curve('NO3', 'Nitrate', 'IS 3025 (Part 34)', 'mg/L', 410, [('sb', 'Volume of antimony reagent added (ml)'), ('cr', 'Volume of chromotropic acid reagent added (ml)')],
                'ug of nitrate from std. graph (A)', 'A/V', 3), PS),
        t(TE('COLI', 'Coliform', 'IS 15185 : 2016', '--', 0,
             [N('start', 'Date analysis started', kind='text'), N('end', 'Analysis completion date', kind='text'), N('st', 'Observation status (Absent / Present)', kind='text')],
             [C('res', 'Coliform: absent / present', 'st', 0, True)]), 'Incubator, Balance'),
        t(TE('ECOLI', 'E. coli', 'IS 15185 : 2016', '--', 0,
             [N('start', 'Date analysis started', 'COLI_start', kind='text'), N('end', 'Analysis completion date', 'COLI_end', kind='text'),
              N('st', 'Observation status (Absent / Present)', kind='text')], [C('res', 'E. coli: absent / present', 'st', 0, True)]), 'Incubator, Balance'),
    ]
    return tests


def construction_water():
    return [
        TE('CL', 'Chloride', 'IS 3025 (Part 32)', 'mg/L', 1,
           [N('V3', 'Sample volume V3 (ml)'), N('V1', 'Vol. of AgNO3 by sample V1 (ml)'), N('V2', 'Vol. of AgNO3 by distilled water V2 (ml)'),
            N('N', 'Normality of Silver Nitrate (0.0141 N)')], [C('res', 'Chloride mg/L = ((V1-V2) x N x 35450) / V3', '((V1-V2)*N*35450)/V3', 4, True)], 'Balance, Burette'),
        TE('TSOL', 'Total Solids', 'IS 3025 (Part 18)', 'mg/L', 1,
           [N('V', 'Sample volume V (ml)'), N('A', 'Weight of empty evaporating dish (g) (A)'), N('B', 'Evaporating dish + residue after drying at 179 to 181 C for 1 hour (g) (B)')],
           [C('res', "Solids mg/L = (B-A) x 1000 x 1000 / V   (labelled 'Organic Solid' in your sheet)", '(B-A)*1000*1000/V', 3, True)], 'Balance, Oven'),
        TE('INSOL', 'Inorganic Solids', 'IS 3025 (Part 18)', 'mg/L', 1,
           [N('V', 'Sample volume V (ml)'), N('A', 'Weight of empty evaporating dish (g) (A)'), N('C', 'Evaporating dish + residue after drying at 550 C for 1 hour (g) (C)')],
           [C('res', 'Inorganic solid mg/L = (C-A) x 1000 x 1000 / V', '(C-A)*1000*1000/V', 3, True)], 'Balance, Oven'),
        TE('ORG', 'Organic Residue', 'IS 3025 (Part 18)', 'mg/L', 1,
           [N('A', 'Total solid mg/L (A)', 'TSOL_res'), N('B', 'Inorganic residue mg/L (B)', 'INSOL_res')], [C('res', 'Organic residue mg/L = A - B', 'A-B', 3, True)], 'Balance, Oven'),
        TE('PH', 'pH', 'IS 3025 (Part 11)', '--', 2, [N('V', 'Volume of water (ml)'), N('ph', 'pH value')], [C('res', 'pH', 'ph', 2, True)], 'pH Meter, Thermometer'),
        solids('TSS', 'Total Suspended Solids', 'IS 3025 (Part 17)', 'Weight of Whatman filter paper 542 (g) (A)', 'Weight of filter paper after drying at 105 C for 1 hour (g) (B)', equip='Balance, Oven'),
        curve('SO4', 'Sulphate', 'IS 3025 (Part 24 Sec 1)', 'mg/L', 420, [('buf', 'Volume of buffer added (ml)')], 'Sulphate in sample from standard curve (mg/L)', 'A*iff(blank(D),1,D)', 2, equip='Balance, Spectrophotometer'),
        vol('ACID', 'Acidity', 'IS 3025 (Part 22)', 'mg/L', 'Vol. of NaOH consumed by sample (V1) (ml)', 'Vol. of NaOH consumed by blank (V2) (ml)', 'Normality of NaOH (0.02 N)', '((V1-V2)*N*50*1000)/V3', equip='Balance, Burette'),
        vol('ALK', 'Alkalinity', 'IS 3025 (Part 23)', 'mg/L', 'Vol. of H2SO4 consumed by sample (V1) (ml)', 'Vol. of H2SO4 consumed by blank (V2) (ml)', 'Normality of H2SO4 (0.02 N)', '((V1-V2)*N*50*1000)/V3', equip='Balance, Burette'),
    ]


# fix argument order of TE for construction_water (equip is the 8th positional) - handled by wrapper below
def _fix(tests):
    return tests


LIBRARY = [  # (name, group, spec, page title, builder)
    ('Ambient Air', 'Air', '', 'Ambient Air Analysis', ambient_air),
    ('Building Lime', 'Lime', '', 'Building Lime Chemical Analysis', building_lime),
    ('GGBS', 'Cement', '', 'Chemical analysis of GGBS', ggbs),
    ('Hardened Concrete', 'Concrete', '', 'Hardened Concrete Analysis', hardened_concrete),
    ('Soil', 'Soil', '', 'Soil Chemical Analysis', soil),
    ('Waste Water', 'Water', '', 'Waste Water Analysis', waste_water),
    ('Drinking Water', 'Water', '', 'Drinking Water Analysis', drinking_water),
    ('Construction Water', 'Water', '', 'Construction Water Analysis', construction_water),
]


def seed_lab_library(db):
    """Adds every material that does not exist yet. Returns the list of names added."""
    have = {m['name'] for m in db.materials()}
    added = []
    for name, group, spec, title, builder in LIBRARY:
        if name in have:
            continue
        mid = db.add_material(name, spec, group, {'1': title})
        for i, t in enumerate(builder()):
            t['sort'] = i
            db.save_test(mid, t)
        added.append(name)
    return added
