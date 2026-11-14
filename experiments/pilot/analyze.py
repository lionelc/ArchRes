"""Analysis of the pilot, following REGISTRATION.md (and DEVIATIONS.md). Writes results/summary.json.

  python3 analyze.py"""
import json, math, os, re, statistics, sys

sys.path.insert(0, '/workspace/gapCR')
from celltest.noise import estimator, band
from celltest.write import rounds_by_arm

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
HELD = {'C': (3000, 6000), 'B': (2,), 'A': (2,)}
ASM = re.compile(r'_(sse2|ssse3|sse4|sse41|avx2|avx512icl|avx512)(\b|$|\.|_)')


def load(exp):
    p = os.path.join(RES, f'{exp}.json')
    return json.load(open(p))['records'] if os.path.exists(p) else []


def timed(r):
    return bool(r['timing']['rounds'])


def est(r, a, b):
    return estimator(r, a, b)


def med_s(r, arm):
    return statistics.median(v for rd in rounds_by_arm(r)[arm] for v in rd) / 1e9


def stratum(t):
    return '<0.1s' if t < 0.1 else ('0.1-1s' if t < 1.0 else '>1s')


def aa_single(r, arms):
    out = []
    for a, rounds in rounds_by_arm(r).items():
        if a in arms:
            out += [abs(math.log(x[0] / x[1])) for x in rounds if len(x) == 2]
    return out


def bands(survey, ref='Rd'):
    by = {}
    for r in survey:
        if timed(r):
            by.setdefault(stratum(med_s(r, ref)), []).extend(aa_single(r, {'Yd', 'Ya', 'Rd', 'Ra'}))
    return {k: band(v) for k, v in by.items()}


def matched_null(survey):
    vals = [abs(est(r, 'Ya', 'Yd')) for r in survey if timed(r)] + [abs(est(r, 'Ra', 'Rd')) for r in survey if timed(r)]
    return band(vals), vals


def b_for(bands_, r, ref='Rd'):
    return bands_.get(stratum(med_s(r, ref)), max(bands_.values()))


def group(records, key=lambda r: (r['cell'], r['state'])):
    g = {}
    for r in records:
        if timed(r):
            g.setdefault(key(r), []).append(r)
    return g


def robust(rs, a, b_, bands_, ref):
    gs = [est(r, a, b_) for r in rs]
    bs = [b_for(bands_, r, ref) for r in rs]
    ok = all(abs(g) > b for g, b in zip(gs, bs)) and (all(g > 0 for g in gs) or all(g < 0 for g in gs))
    return ok, gs, bs


def verdict_effect(es, bm, sign=None, lo=None, hi=None, predicts_large=False):
    """Registered pilot verdict on held-out seeds."""
    if sign is not None and all(math.copysign(1, e) == sign and abs(e) > bm for e in es):
        if (lo is None or all(e >= lo for e in es)) and (hi is None or all(e <= hi for e in es)):
            return 'confirmed'
        return 'confirmed in direction, outside the predicted range'
    if sign is not None and all(math.copysign(1, e) == -sign and abs(e) > bm for e in es):
        return 'refuted (opposite sign)'
    if all(abs(e) <= bm for e in es):
        return 'refuted (null)' if predicts_large else 'null-consistent'
    return 'inconclusive'


def r4(x):
    return None if x is None else round(x, 4)


# ------------------------------------------------------------------------------------------------ captures
P = '/work/pilot'
OBJ = {'Y1': f'{P}/rav1d/target/release/dav1d', 'R1': f'{P}/rav1d/build/src/libdav1d.so.7.0.0',
       'Y0': f'{P}/wt_v110/target/release/dav1d', 'R0': f'{P}/dav1d_151/build/src/libdav1d.so.7.0.0',
       'P1400p': f'{P}/wt_pr1400p/target/release/dav1d', 'P1400': f'{P}/wt_pr1400/target/release/dav1d',
       'P1397p': f'{P}/wt_pr1397p/target/release/dav1d', 'P1397': f'{P}/wt_pr1397/target/release/dav1d'}
_NM = {}


def nm_table(obj):
    """Sorted (address, name) of the object's named text symbols, nasm local labels ('..@', '.') excluded."""
    if obj not in _NM:
        import bisect, subprocess
        out = subprocess.run(['nm', '-n', obj], capture_output=True, text=True).stdout
        rows = []
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) == 3 and parts[1] in 'tT' and not parts[2].startswith('.'):
                rows.append((int(parts[0], 16), parts[2]))
        _NM[obj] = rows
    return _NM[obj]


def resolve(funcs, obj):
    """Replaces callgrind's bare hex names (zero-size nasm symbols) by the nearest preceding named symbol of obj."""
    if not obj or not os.path.exists(obj):
        return funcs
    import bisect
    tab = nm_table(obj); addrs = [a for a, _ in tab]
    out = {}
    for k, v in funcs.items():
        if re.fullmatch(r'0x[0-9a-fA-F]+', k):
            i = bisect.bisect_right(addrs, int(k, 16)) - 1
            k = tab[i][1] if i >= 0 else k
        out[k] = out.get(k, 0) + v
    return out


def norm_fn(name):
    n = re.sub(r'::h[0-9a-f]{16}$', '', name)
    n = re.sub(r'<[^<>]*>', '', n); n = re.sub(r'<[^<>]*>', '', n)
    n = n.replace('{{closure}}', 'closure').rstrip(':')
    n = n.split('::')[-1] if '::' in n else n
    n = re.sub(r'^(rav1d|dav1d)_', '', n)
    n = re.sub(r'_(8|16)bpc$', '', n)
    n = re.sub(r'\.(isra|part|constprop|cold|lto_priv)\.\d+', '', n)
    return n


def captures_summary(cap):
    out = {}
    if not cap:
        return out
    c = {}
    for mask in ('-1', 'none'):
        y, r = cap.get(f'C|Y1|{mask}'), cap.get(f'C|R1|{mask}')
        if y and r:
            c[f'instr_ratio_Y1_R1_{mask}'] = r4(math.log(y['total'] / r['total']))
    for key in list(cap):
        if key.startswith('C|'):
            cap[key] = dict(cap[key], funcs=resolve(cap[key]['funcs'], OBJ.get(key.split('|')[1])))
    y, r = cap['C|Y1|-1'], cap['C|R1|-1']
    is_asm = lambda k: k.startswith('dav1d_') and bool(ASM.search(k))
    asm_y = {k: v for k, v in y['funcs'].items() if is_asm(k)}
    asm_r = {k: v for k, v in r['funcs'].items() if is_asm(k)}
    common = set(asm_y) & set(asm_r)
    eq = [k for k in common if abs(asm_y[k] - asm_r[k]) <= 0.001 * max(asm_r[k], 1)]
    c['anchor'] = {'asm_symbols_Y': len(asm_y), 'asm_symbols_R': len(asm_r), 'common': len(common), 'equal_within_0.1pct': len(eq),
                   'asm_instr_Y': sum(asm_y.values()), 'asm_instr_R': sum(asm_r.values()),
                   'share_of_common_asm_instr_in_equal_symbols': r4(sum(asm_r[k] for k in eq) / max(1, sum(asm_r[k] for k in common))),
                   'largest_unequal': sorted(((k, asm_y[k], asm_r[k]) for k in common if k not in eq), key=lambda t: -abs(t[1] - t[2]))[:5]}
    for yk, rk in (('Y1', 'R0'), ('Y0', 'R0')):
        ay = {k: v for k, v in cap[f'C|{yk}|-1']['funcs'].items() if is_asm(k)}
        ar = {k: v for k, v in cap[f'C|{rk}|-1']['funcs'].items() if is_asm(k)}
        cm = set(ay) & set(ar); e = [k for k in cm if abs(ay[k] - ar[k]) <= 0.001 * max(ar[k], 1)]
        c[f'anchor_{yk}_{rk}'] = {'common': len(cm), 'equal_within_0.1pct': len(e),
                                  'share_of_common_asm_instr_in_equal_symbols': r4(sum(ar[k] for k in e) / max(1, sum(ar[k] for k in cm))),
                                  'only_in_Y': len(set(ay) - set(ar)), 'only_in_R': len(set(ar) - set(ay))}
    c['C2_rust_share_instr'] = r4(1 - sum(asm_y.values()) / y['total'])
    c['C_share_instr_dav1d_nonasm'] = r4(1 - sum(asm_r.values()) / r['total'])
    ny, nr = {}, {}
    for k, v in y['funcs'].items():
        if not is_asm(k):
            ny[norm_fn(k)] = ny.get(norm_fn(k), 0) + v
    for k, v in r['funcs'].items():
        if not is_asm(k):
            nr[norm_fn(k)] = nr.get(norm_fn(k), 0) + v
    keys = set(ny) | set(nr)
    diff = {k: ny.get(k, 0) - nr.get(k, 0) for k in keys}
    excess_total = y['total'] - r['total']
    pos = sorted(((k, d) for k, d in diff.items() if d > 0), key=lambda t: -t[1])
    matched = sum(v for k, v in ny.items() if k in nr)
    c['C3'] = {'excess_instr_total': excess_total, 'top_functions': [(k, d, r4(d / excess_total)) for k, d in pos[:10]],
               'max_single_share': r4(pos[0][1] / excess_total) if pos else None,
               'top5_share': r4(sum(d for _, d in pos[:5]) / excess_total) if pos else None,
               'matched_share_of_Y_nonasm': r4(matched / max(1, sum(ny.values())))}
    c['versions'] = {k: cap[f'C|{k}|-1']['total'] for k in ('Y1', 'R1', 'Y0', 'R0', 'P1400p', 'P1400', 'P1397p', 'P1397') if f'C|{k}|-1' in cap}
    c['C5_instr_change_P1397'] = r4(math.log(cap['C|P1397|-1']['total'] / cap['C|P1397p|-1']['total']))
    c['C6_instr_change_P1400'] = r4(math.log(cap['C|P1400|-1']['total'] / cap['C|P1400p|-1']['total']))
    # RQ3 (profile prediction for PR #1400): parent's excess over dav1d in the functions the PR's inlined eq() lands in
    pp = cap['C|P1400p|-1']['funcs']; r0 = cap['C|R0|-1']['funcs']
    tgt = re.compile(r'(refmvs|add_spatial|add_temporal|add_compound|scan_row|scan_col|scan_tmvs|mv_|refmv)', re.I)
    ex = 0
    for k, v in pp.items():
        if tgt.search(k) and not ASM.search(k):
            ex += v
    exr = sum(v for k, v in r0.items() if tgt.search(k) and not ASM.search(k))
    c['RQ3_PR1400_profile'] = {'parent_instr_in_mv_functions': ex, 'dav1d_instr_in_mv_functions': exr,
                               'excess': ex - exr, 'excess_share_of_total_gap': r4((ex - exr) / (cap['C|P1400p|-1']['total'] - cap['C|R0|-1']['total']))}
    out['C'] = c
    b = {}
    for cell in ('base64', 'cksum', 'sha256sum', 'wc_l', 'sort', 'cut'):
        R, Y1, Y0 = cap[f'B|R|{cell}']['total'], cap[f'B|Y1|{cell}']['total'], cap[f'B|Y0|{cell}']['total']
        b[cell] = {'Y1_R': r4(math.log(Y1 / R)), 'Y0_R': r4(math.log(Y0 / R))}
    out['B'] = b
    a = {}
    for q in ('scan_agg', 'point_rowid', 'join2'):
        R, Y1, Y0 = cap[f'A|R|{q}']['total'], cap[f'A|Y1|{q}']['total'], cap[f'A|Y0|{q}']['total']
        a[q] = {'Y1_R': r4(math.log(Y1 / R)), 'Y0_R': r4(math.log(Y0 / R))}
    out['A'] = a
    return out


# ------------------------------------------------------------------------------------------------ plans
ALIAS = {'o': 'orders', 'c': 'customers', 'i': 'items'}


def plan_sig(raw):
    top, sub, flags = [], [], set()
    for ln in raw.splitlines():
        m = re.match(r'^(\d+)\|(\d+)\|\d+\|(.*)$', ln)
        if m:
            depth = 0 if m.group(2) == '0' else 1
            text = m.group(3).strip()
        else:
            if ln.strip() in ('', 'QUERY PLAN'):
                continue
            stripped = re.sub(r'^[|`\- ]+', '', ln)
            depth = 0 if (len(ln) - len(ln.lstrip(' '))) == 0 else 1
            text = stripped.strip()
        if 'BLOOM' in text:
            flags.add('bloom'); continue
        if text.startswith('HASH JOIN'):
            flags.add('hash_join')
        mm = re.match(r'(SCAN|SEARCH|HASH JOIN)\s+(\w+)(?:\s+AS\s+(\w+))?(.*)', text)
        if not mm:
            continue
        tbl = ALIAS.get(mm.group(2), mm.group(2))
        how = mm.group(4)
        idx = re.search(r'INDEX (\w+)', how)
        key = 'PK' if ('PRIMARY KEY' in how or 'rowid' in how) else (idx.group(1) if idx else 'full')
        step = (mm.group(1), tbl, key)
        (top if depth == 0 else sub).append(step)
    return {'top': top, 'sub': sorted(sub), 'flags': sorted(flags)}


def plans_summary():
    p = os.path.join(RES, 'plans.json')
    if not os.path.exists(p):
        return {}
    raw = json.load(open(p))
    out = {}
    for k, v in raw.items():
        sr, s1, s0 = plan_sig(v['R']['raw']), plan_sig(v['Y1']['raw']), plan_sig(v['Y0']['raw'])
        out[k] = {'R': sr, 'Y1': s1, 'Y0': s0,
                  'same_access_R_Y1': sr['top'] == s1['top'] and sr['sub'] == s1['sub'],
                  'same_plan_R_Y1': sr == s1, 'same_access_R_Y0': sr['top'] == s0['top'] and sr['sub'] == s0['sub'], 'same_plan_R_Y0': sr == s0}
    return out


# ------------------------------------------------------------------------------------------------ main
def plants(records, bm):
    exp = {'P2': math.log(1.02), 'P5': math.log(1.05), 'P15': math.log(1.15)}
    rows = []
    for r in records:
        if not timed(r):
            continue
        for arm in ('P2', 'P5', 'P15', 'Pnull', 'Psham', 'Ya'):
            rows.append({'cell': r['cell'], 'seed': r['seed'], 'arm': arm, 'effect': r4(est(r, arm, 'Yd')),
                         'expected': r4(exp.get(arm, 0.0)), 'detected': est(r, arm, 'Yd') > bm})
    by = {}
    for x in rows:
        by.setdefault(x['arm'], []).append(x['detected'])
    return {'rows': rows, 'detection_rate': {k: r4(sum(v) / len(v)) for k, v in by.items()}}


def layout(records, bs_, ref='Yd'):
    out = []
    for r in records:
        if not timed(r):
            continue
        es = [0.0] + [est(r, a, 'Yd') for a in ('Ye1', 'Ye2', 'Ye3')]
        out.append({'cell': r['cell'], 'state': r['state'], 'spread': r4(max(es) - min(es)), 'effects': [r4(e) for e in es[1:]],
                    'band': r4(b_for(bs_, r, 'Yd'))})
    return out


def logical(r):
    """Pair C keeps each clip segment as its own cell id; the logical cell drops the segment (the seed)."""
    return (re.sub(r'^C_s\d+_', 'C_', r['cell']), r['state'])


def survey_table(records, bs_, ref='Rd'):
    rows = []
    for (cell, state), rs in sorted(group(records, key=logical).items()):
        ok, gs, bs = robust(rs, 'Yd', 'Rd', bs_, ref)
        null_ok, ngs, _ = robust(rs, 'Ya', 'Yd', bs_, ref)
        null_ok_r, _, _ = robust(rs, 'Ra', 'Rd', bs_, ref)
        alt = []
        for r in rs:
            ra = rounds_by_arm(r)
            y = statistics.median(v for rd in ra['Yd'] for v in rd); x = statistics.median(v for rd in ra['Rd'] for v in rd)
            alt.append(math.log(y / x))
        rows.append({'cell': cell, 'state': state, 'seeds': [r['seed'] for r in rs], 'g': [r4(g) for g in gs], 'band': [r4(b) for b in bs],
                     'robust': ok, 'R_s': [r4(med_s(r, 'Rd')) for r in rs], 'Y_s': [r4(med_s(r, 'Yd')) for r in rs],
                     'pseudo_gap_robust': null_ok or null_ok_r, 'alt_estimator_sign_agrees': all((a > 0) == (g > 0) for a, g in zip(alt, gs))})
    return rows


def main():
    S = {'registration': json.load(open(os.path.join(HERE, 'registration.json')))}
    cap = json.load(open(os.path.join(RES, 'captures.json'))) if os.path.exists(os.path.join(RES, 'captures.json')) else {}
    S['captures'] = captures_summary(cap)
    S['plans'] = plans_summary()
    for pair, survey_exp in (('C', 'C_SURVEY'), ('B', 'B_SURVEY'), ('A', 'A_SURVEY')):
        sv = load(survey_exp)
        if not sv:
            continue
        bs_ = bands(sv); bm, nulls = matched_null(sv)
        S[pair] = {'bands': {k: r4(v) for k, v in bs_.items()}, 'matched_null_p95': r4(bm), 'survey': survey_table(sv, bs_),
                   'cells_measured': len(group(sv)), 'records': len(sv),
                   'not_timed_outputs_differ': sorted({(r['cell'], r['state']) for r in sv if not timed(r)})}
        S[pair]['robust_gaps'] = sum(x['robust'] for x in S[pair]['survey'])
        S[pair]['robust_pseudo_gaps'] = sum(x['pseudo_gap_robust'] for x in S[pair]['survey'])
        pl = load(f'{pair}_PLANTS')
        if pl:
            S[pair]['plants'] = plants(pl, bm)
        lo = load(f'{pair}_LAYOUT')
        if lo:
            S[pair]['layout'] = layout(lo, bs_)
    claims = {}
    # ---------------- Pair C
    if 'C' in S:
        C = S['C']; bm = C['matched_null_p95']; bsC = bands(load('C_SURVEY'))
        surv = {(x['cell']): x for x in C['survey']}
        ts = group(load('C_TIMESPLIT'), key=lambda r: r['cell'])
        sw = group(load('C_SWAPS'), key=lambda r: r['cell'])
        held = HELD['C']
        def held_rs(rs):
            return [r for r in rs if r['seed'] in held]
        if ts:
            rs = held_rs(ts.get('C_s0_t1_m-1', []) + ts.get('C_s3000_t1_m-1', []) + ts.get('C_s6000_t1_m-1', []))
            rs = [r for r in rs if r['cell'] == f"C_s{r['seed']}_t1_m-1"]
            g0 = [est(r, 'Y0d', 'R0d') for r in rs]
            b0 = [b_for(bsC, r, 'R0d') for r in rs]
            claims['C1'] = {'g_Y0_R0': [r4(x) for x in g0], 'band': [r4(x) for x in b0],
                            'verdict': 'confirmed' if all(abs(g) > b and 0.03 <= g <= 0.07 for g, b in zip(g0, b0)) else
                            ('robust slower, outside [0.03, 0.07]' if all(g > b for g, b in zip(g0, b0)) else 'not robust')}
            e7 = [est(r, 'Y1d', 'Y0d') for r in rs]
            claims['C7'] = {'est_Y1_vs_Y0': [r4(x) for x in e7], 'g_Y1_R0': [r4(est(r, 'Y1d', 'R0d')) for r in rs],
                            'verdict': verdict_effect(e7, bm, sign=-1)}
            allts = []
            for cell, rr in sorted(ts.items()):
                for r in rr:
                    allts.append({'cell': cell, 'seed': r['seed'], 'g_Y0_R0': r4(est(r, 'Y0d', 'R0d')), 'g_Y1_R0': r4(est(r, 'Y1d', 'R0d')),
                                  'est_Y1_Y0': r4(est(r, 'Y1d', 'Y0d')), 'Y0_aa': r4(est(r, 'Y0a', 'Y0d')), 'band': r4(b_for(bsC, r, 'R0d'))})
            C['timesplit'] = allts
        if sw:
            rows = []
            for cell, rr in sorted(sw.items()):
                for r in rr:
                    rows.append({'cell': cell, 'seed': r['seed'], 'e1400': r4(est(r, 'P1400', 'P1400p')), 'e1397': r4(est(r, 'P1397', 'P1397p')),
                                 'g_P1400p_vs_P1397p': r4(est(r, 'P1400p', 'P1397p'))})
            C['swaps'] = rows
            hr = [x for x in rows if x['seed'] in held]
            claims['C5'] = {'e': [x['e1397'] for x in hr], 'instr': S['captures'].get('C', {}).get('C5_instr_change_P1397'),
                            'verdict_timing': verdict_effect([x['e1397'] for x in hr], bm),
                            'verdict_deterministic': 'confirmed' if abs(S['captures']['C']['C5_instr_change_P1397']) < 0.001 else 'refuted'}
            claims['C6'] = {'e': [x['e1400'] for x in hr], 'instr': S['captures'].get('C', {}).get('C6_instr_change_P1400'),
                            'verdict_timing': verdict_effect([x['e1400'] for x in hr], bm, sign=-1),
                            'verdict_deterministic': 'confirmed' if S['captures']['C']['C6_instr_change_P1400'] < 0 else 'refuted (more instructions)'}
        if surv:
            rows = {x['cell']: x for x in C['survey']}
            diffs, bands8 = [], []
            n, d = rows.get('C_t1_mnone'), rows.get('C_t1_m-1')
            if n and d:
                for s in held:
                    if s in n['seeds'] and s in d['seeds']:
                        i, j = n['seeds'].index(s), d['seeds'].index(s)
                        diffs.append(n['g'][i] - d['g'][j]); bands8.append(max(n['band'][i], d['band'][j]))
            claims['C8'] = {'g_none_minus_g_default': [r4(x) for x in diffs], 'band': [r4(x) for x in bands8],
                            'verdict': 'confirmed' if diffs and all(x > b for x, b in zip(diffs, bands8)) else 'not confirmed'}
        cc = S['captures'].get('C', {})
        if cc:
            claims['C2'] = {'rust_share_instr': cc['C2_rust_share_instr'], 'verdict': 'confirmed' if 0.40 <= cc['C2_rust_share_instr'] <= 0.60 else 'refuted'}
            claims['C3'] = {'max_single_share': cc['C3']['max_single_share'], 'top': cc['C3']['top_functions'][:5],
                            'verdict': 'confirmed' if (cc['C3']['max_single_share'] or 1) <= 0.20 else 'refuted'}
        claims['C4'] = {'verdict': 'untestable without repair (needs a modified rustc)'}
    # ---------------- Pair B
    if 'B' in S:
        B = S['B']; bm = B['matched_null_p95']; bsB = bands(load('B_SURVEY'))
        ts = group(load('B_TIMESPLIT'), key=lambda r: r['cell'])
        rows = []
        for cell, rr in sorted(ts.items()):
            for r in rr:
                rows.append({'cell': cell, 'seed': r['seed'], 'g_Y0_R': r4(est(r, 'Y0d', 'Rd')), 'g_Y1_R': r4(est(r, 'Yd', 'Rd')),
                             'est_Y1_Y0': r4(est(r, 'Yd', 'Y0d')), 'band': r4(b_for(bsB, r, 'Rd')), 'Y0_s': r4(med_s(r, 'Y0d')), 'R_s': r4(med_s(r, 'Rd'))})
        B['timesplit'] = rows
        def pick(cell, seed):
            return next((x for x in rows if x['cell'] == cell and x['seed'] == seed), None)
        for cid, util in (('B1', 'B_base64'), ('B3', 'B_cksum')):
            x = pick(util, 2)
            if x:
                claims[cid] = {'g_Y0_R': x['g_Y0_R'], 'ratio': r4(math.exp(x['g_Y0_R'])), 'band': x['band'],
                               'verdict': 'confirmed' if x['g_Y0_R'] >= math.log(4) and x['g_Y0_R'] > x['band'] else
                               ('robust slower, ratio below 4' if x['g_Y0_R'] > x['band'] else 'not robust')}
        x = pick('B_base64', 2)
        if x:
            claims['B2'] = {'g_Y1_R': x['g_Y1_R'], 'band': x['band'], 'verdict': 'confirmed' if (x['g_Y1_R'] <= 0 or abs(x['g_Y1_R']) <= x['band']) else 'refuted'}
        x = pick('B_cksum', 2)
        if x and 'B3' in claims:
            claims['B3']['g_Y1_R'] = x['g_Y1_R']
            claims['B3']['Y1_fixed'] = (x['g_Y1_R'] <= 0 or abs(x['g_Y1_R']) <= x['band'])
        ko = group(load('B_KO'), key=lambda r: r['cell'])
        krows = []
        for cell, rr in sorted(ko.items()):
            for r in rr:
                krows.append({'cell': cell, 'seed': r['seed'], 'e_KO_on_R': r4(est(r, 'Rk', 'Rd')), 'g_Y0_R': r4(est(r, 'Y0d', 'Rd')),
                              'g_Y0_Rk': r4(est(r, 'Y0d', 'Rk')), 'g_Y1_R': r4(est(r, 'Yd', 'Rd')), 'g_Y1_Rk': r4(est(r, 'Yd', 'Rk'))})
        B['ko'] = krows
        def kpick(cell, seed):
            return next((x for x in krows if x['cell'] == cell and x['seed'] == seed), None)
        x, y = kpick('B_cksum', 2), kpick('B_base64', 2)
        if x and y:
            claims['B4'] = {'cksum': {'g_Y0_R': x['g_Y0_R'], 'g_Y0_Rk': x['g_Y0_Rk'], 'e_KO_on_R': x['e_KO_on_R'],
                                      'verdict': 'confirmed' if abs(x['g_Y0_Rk']) <= 0.5 * abs(x['g_Y0_R']) else 'refuted'},
                            'base64': {'e_KO_on_R': y['e_KO_on_R'], 'g_Y0_R': y['g_Y0_R'],
                                       'verdict': 'refuted (GNU base64 has no hardware path; the gap is not a SIMD gap)' if abs(y['e_KO_on_R']) <= bm else 'knock-out moved GNU base64'}}
    # ---------------- Pair A
    if 'A' in S:
        A = S['A']; bm = A['matched_null_p95']; bsA = bands(load('A_SURVEY'))
        PL = S['plans']
        rows = A['survey']
        mass_ident = mass_diff = 0.0; detail = []
        for x in rows:
            if x['state'] != 'S1' or not x['robust'] or x['g'][0] <= 0:
                continue
            q = x['cell'][2:]
            k = f'1|S1|{q}'
            same = PL.get(k, {}).get('same_plan_R_Y1') if q not in ('insert_txn', 'startup') else True
            m = statistics.mean(x['g'])
            detail.append({'cell': x['cell'], 'g_mean': r4(m), 'same_plan': same})
            if same:
                mass_ident += m
            else:
                mass_diff += m
        share = mass_ident / (mass_ident + mass_diff) if (mass_ident + mass_diff) else None
        claims['A1'] = {'share_of_slower_gap_mass_in_plan_identical_cells': r4(share), 'cells': detail,
                        'verdict': ('confirmed' if share is not None and share <= 0.20 else 'refuted') if share is not None else 'no robust gaps'}
        def g1(cell):
            x = next((x for x in rows if x['cell'] == cell and x['state'] == 'S1'), None)
            return x
        a2 = {}
        for cell, thr in (('A_scan_agg', math.log(2)), ('A_point_rowid', math.log(1.3)), ('A_join2', math.log(1.3))):
            x = g1(cell)
            if x:
                a2[cell] = {'g': x['g'], 'threshold': r4(thr), 'meets': all(g >= thr for g in x['g'])}
        claims['A2'] = {'cells': a2, 'verdict': 'confirmed' if a2 and all(v['meets'] for v in a2.values()) else 'partly or not confirmed'}
        ts = group(load('A_TIMESPLIT'), key=lambda r: r['cell'])
        trows = []
        for cell, rr in sorted(ts.items()):
            for r in rr:
                trows.append({'cell': cell, 'seed': r['seed'], 'g_Y0_R': r4(est(r, 'Y0d', 'Rd')), 'g_Y1_R': r4(est(r, 'Yd', 'Rd')),
                              'est_Y1_Y0': r4(est(r, 'Yd', 'Y0d')), 'band': r4(b_for(bsA, r, 'Rd'))})
        A['timesplit'] = trows
        rob0 = [x for x in trows if x['g_Y0_R'] > x['band']]
        shrunk = [x for x in rob0 if x['est_Y1_Y0'] < -bm]
        claims['A3'] = {'robust_Y0_gap_cells': len(rob0), 'shrunk_beyond_null': len(shrunk),
                        'verdict': 'confirmed' if rob0 and len(shrunk) > len(rob0) / 2 else 'refuted' if rob0 else 'no robust Y0 gaps'}
        ko = load('A_KO')
        krows = []
        for r in ko:
            if not timed(r):
                continue
            q = r['cell']
            if q == 'A_in_subquery':
                krows.append({'cell': q, 'seed': r['seed'], 'g_default': r4(est(r, 'Yp', 'Rp')), 'g_equalized': r4(est(r, 'Yp', 'Rk')),
                              'plan_part': r4(est(r, 'Yp', 'Rp') - est(r, 'Yp', 'Rk')), 'Y_aa': r4(est(r, 'Ya', 'Yp'))})
            elif q == 'A_join3_star':
                krows.append({'cell': q, 'seed': r['seed'], 'g_default_Y0': r4(est(r, 'Y0p', 'Rp')), 'g_equalized_Y0': r4(est(r, 'Y0p', 'Rk')),
                              'g_default_Y1_hashjoin': r4(est(r, 'Y1p', 'Rp')), 'g_Y1_vs_R_nobloom': r4(est(r, 'Y1p', 'Rk'))})
            elif q == 'A_join2':
                krows.append({'cell': q, 'seed': r['seed'], 'g_S1_default': r4(est(r, 'Y_S1', 'R_S1')), 'g_S0_default': r4(est(r, 'Y_S0', 'R_S0')),
                              'exec_plan_customers_first': r4(est(r, 'Y_S1', 'R_S0')), 'exec_plan_orders_first': r4(est(r, 'Y_S0', 'R_S1'))})
        A['ko'] = krows
    mk = os.path.join(RES, 'markers.json')
    if os.path.exists(mk):
        m = json.load(open(mk))
        S['markers'] = {'gnu_accelerated_cells': m['gnu_accelerated_cells'], 'B5': m['B5']}
        claims['B5'] = {'gnu': m['B5']['gnu'], 'uu12': m['B5']['uu12'],
                        'verdict': 'confirmed' if all(v['KO_switches_all'] and v['cells_with_feature_in_use'] for v in m['B5'].values()) else 'refuted'}
    S['claims'] = claims
    S['captures_heldout'] = heldout_profiles()
    if cap:
        S['captures_heldout']['s0'] = profile_metrics({k: cap[f'C|{k}|-1'] for k in ('Y1', 'R1', 'R0', 'P1400p', 'P1400', 'P1397p', 'P1397')})
    bm6 = os.path.join(RES, 'base64_mechanism.json')
    if os.path.exists(bm6):
        S['base64_mechanism'] = json.load(open(bm6))
    S['funnel'] = funnel(S)
    S['rq4'] = rq4(S)
    S['cg'] = cg_comparisons(S, cap)
    S['posthoc'] = posthoc(S)
    S['planted_classes'] = planted_classes(S)
    S['wasi_classes'] = wasi_classes(S)
    json.dump(S, open(os.path.join(RES, 'summary.json'), 'w'), indent=1, default=str)
    print(json.dumps(claims, indent=1, default=str))
    print(json.dumps(S['cg'], indent=1, default=str))


MV = r'(refmv|add_spatial|add_temporal|add_compound|scan_row|scan_col|scan_tmvs|levels)'


def profile_metrics(cc):
    """Pair C profile metrics of one segment; cc maps an engine key to its capture (default mask)."""
    is_asm = lambda k: k.startswith('dav1d_') and bool(ASM.search(k))
    f = {k: resolve(v['funcs'], OBJ.get(k)) for k, v in cc.items()}
    t = {k: v['total'] for k, v in cc.items()}
    ay = {k: v for k, v in f['Y1'].items() if is_asm(k)}; ar = {k: v for k, v in f['R1'].items() if is_asm(k)}
    cm = set(ay) & set(ar); eq = [k for k in cm if abs(ay[k] - ar[k]) <= 0.001 * max(ar[k], 1)]
    ny, nr = {}, {}
    for src, dst in ((f['Y1'], ny), (f['R1'], nr)):
        for k, v in src.items():
            if not is_asm(k):
                dst[norm_fn(k)] = dst.get(norm_fn(k), 0) + v
    ex = t['Y1'] - t['R1']
    pos = sorted(((k, ny.get(k, 0) - nr.get(k, 0)) for k in set(ny) | set(nr)), key=lambda x: -x[1])
    pos = [p for p in pos if p[1] > 0]

    def share(sk, rk, pat):
        rx = re.compile(pat, re.I)
        e = sum(v for k, v in f[sk].items() if rx.search(k)) - sum(v for k, v in f[rk].items() if rx.search(k))
        return r4(e / (t[sk] - t[rk]))
    def gain(sk, rk, pat):   # the profile's predicted log-instruction gain of removing the excess in pat
        rx = re.compile(pat, re.I)
        e = sum(v for k, v in f[sk].items() if rx.search(k)) - sum(v for k, v in f[rk].items() if rx.search(k))
        return r4(math.log((t[sk] - e) / t[sk]))
    return {'cg2_predicted_log_gain': gain('P1400p', 'R0', MV), 'cg3_predicted_log_gain': gain('P1397p', 'R0', r'cdef'),
            'instr_log_ratio_Y1_R1': r4(math.log(t['Y1'] / t['R1'])), 'anchor_equal': f'{len(eq)}/{len(cm)}',
            'C2_rust_share_instr': r4(1 - sum(ay.values()) / t['Y1']),
            'C3_top': [(k, r4(d / ex)) for k, d in pos[:6]], 'C3_max_single_share': r4(pos[0][1] / ex),
            'C3_top5_share': r4(sum(d for _, d in pos[:5]) / ex),
            'C5_instr_change_P1397': r4(math.log(t['P1397'] / t['P1397p'])), 'C6_instr_change_P1400': r4(math.log(t['P1400'] / t['P1400p'])),
            'cg2_profile_share_mv_P1400p_vs_R0': share('P1400p', 'R0', MV), 'cg3_profile_share_cdef_P1397p_vs_R0': share('P1397p', 'R0', r'cdef')}


def heldout_profiles():
    p = os.path.join(RES, 'captures_heldout.json')
    if not os.path.exists(p):
        return {}
    cap = json.load(open(p)); out = {}
    for s in (3000, 6000):
        cc = {k.split('|')[1]: v for k, v in cap.items() if k.endswith(f'|s{s}')}
        if len(cc) == 7:
            out[f's{s}'] = profile_metrics(cc)
    return out


def funnel(S):
    """RQ1: robust gaps after each registered filter, per pair."""
    out = {}
    det = {'C': {'C_t1_m-1': S['captures'].get('C', {}).get('instr_ratio_Y1_R1_-1'),
                 'C_t1_mnone': S['captures'].get('C', {}).get('instr_ratio_Y1_R1_none')},
           'B': {f'B_{k}': v['Y1_R'] for k, v in S['captures'].get('B', {}).items()},
           'A': {f'A_{k}': v['Y1_R'] for k, v in S['captures'].get('A', {}).items()}}
    for pair in ('C', 'B', 'A'):
        if pair not in S:
            continue
        X = S[pair]; rows = X['survey']
        spread = max((x['spread'] for x in X.get('layout', [])), default=None)
        after_layout = [x for x in rows if x['robust'] and (spread is None or min(abs(g) for g in x['g']) > spread)]
        sign = []
        for x in rows:
            ins = det[pair].get(x['cell'])
            if ins is not None and x['state'] in ('-', 'C', 'S1'):
                sign.append({'cell': x['cell'], 'instr_log_ratio': ins, 'g': x['g'], 'robust': x['robust'],
                             'sign_agrees': all((g > 0) == (ins > 0) for g in x['g'])})
        out[pair] = {'cells': len(rows), 'robust_gaps': X['robust_gaps'], 'robust_pseudo_gaps': X['robust_pseudo_gaps'],
                     'layout_spread_max': spread, 'robust_after_layout': len(after_layout),
                     'robust_after_layout_cells': [x['cell'] + ('' if x['state'] in ('-', 'C', 'S1') else '/' + x['state']) for x in after_layout],
                     'alt_estimator_disagreements': [x['cell'] for x in rows if not x['alt_estimator_sign_agrees']],
                     'deterministic_counterparts': sign, 'transport': 'not available (one host)'}
    return out


def rq4(S):
    """RQ4 with natural witnesses only (Corollary 1, L = -inf): a cell with a robust Y0 gap is decided (fixable) if the
    later version's gap U = g(Y1, R) is at most the band in every seed; otherwise it stays a candidate."""
    out = {}
    spec = {'C': ('timesplit', 'g_Y0_R0', 'g_Y1_R0', lambda c: re.sub(r'^C_s\d+_', 'C_', c)),
            'B': ('timesplit', 'g_Y0_R', 'g_Y1_R', lambda c: c),
            'A': ('timesplit', 'g_Y0_R', 'g_Y1_R', lambda c: c)}
    for pair, (key, g0k, g1k, lc) in spec.items():
        rows = S.get(pair, {}).get(key)
        if not rows:
            continue
        by = {}
        for x in rows:
            by.setdefault(lc(x['cell']), []).append(x)
        cells = []
        for cell, xs in sorted(by.items()):
            g0 = [x[g0k] for x in xs]; g1 = [x[g1k] for x in xs]; b = [x['band'] for x in xs]
            rob = all(g > bb for g, bb in zip(g0, b))
            cls = None
            if rob:
                cls = 'fixable (witnessed)' if all(u <= bb for u, bb in zip(g1, b)) else 'candidate'
            cells.append({'cell': cell, 'seeds': [x['seed'] for x in xs], 'g_Y0_R': g0, 'U_g_Y1_R': g1, 'band': b,
                          'robust_Y0_gap': rob, 'class': cls})
        mass = {c['cell']: statistics.mean(c['g_Y0_R']) for c in cells if c['robust_Y0_gap']}
        dec = sum(m for c, m in mass.items() if next(x for x in cells if x['cell'] == c)['class'].startswith('fixable'))
        out[pair] = {'cells': cells, 'robust_Y0_gap_cells': len(mass), 'Y0_gap_mass': r4(sum(mass.values())),
                     'share_of_Y0_gap_mass_decided': r4(dec / sum(mass.values())) if mass else None}
    return out


def startup_ms(exp, startup_cell, state):
    rs = [r for r in load(exp) if timed(r) and r['cell'] == startup_cell and r['state'] == state]
    return {r['seed']: {'Y_ms': r4(med_s(r, 'Yd') * 1e3), 'R_ms': r4(med_s(r, 'Rd') * 1e3)} for r in rs}


def startup_shares(exp, startup_cell, state):
    """Arithmetic under an additive model (not a counterfactual): the startup cell's absolute Y-R difference as a share
    of each cell's absolute difference, and the log gap after subtracting each engine's startup time (unrounded medians)."""
    recs = [r for r in load(exp) if timed(r) and r['state'] == state]
    st = {r['seed']: (med_s(r, 'Yd'), med_s(r, 'Rd')) for r in recs if r['cell'] == startup_cell}
    by = {}
    for r in recs:
        if r['cell'] != startup_cell and r['seed'] in st:
            by.setdefault(r['cell'], []).append(r)
    share, adj = {}, {}
    for c, rs in sorted(by.items()):
        d = [med_s(r, 'Yd') - med_s(r, 'Rd') for r in rs]; d0 = [st[r['seed']][0] - st[r['seed']][1] for r in rs]
        if statistics.mean(d) > 0:
            share[c] = r4(statistics.mean(d0) / statistics.mean(d))
        adj[c] = [r4(math.log((med_s(r, 'Yd') - st[r['seed']][0]) / (med_s(r, 'Rd') - st[r['seed']][1])))
                  if med_s(r, 'Yd') > st[r['seed']][0] and med_s(r, 'Rd') > st[r['seed']][1] else None for r in rs]
    return share, adj


OPERATOR_DIFF = {'distinct': 'SQLite: ordered skip-ahead (SeekGT) on the index; Turso: full index scan with HashDistinct',
                 'order_limit': 'SQLite: bounded top-k ephemeral index; Turso: full sort (SorterInsert for every row), limit after sorting'}


def posthoc(S):
    """Exploratory and post hoc analyses (DEVIATIONS.md #6, #7); never replace a registered verdict."""
    out = {}
    if 'A' in S and 'A1' in S['claims']:
        cells = S['claims']['A1']['cells']
        tot = sum(c['g_mean'] for c in cells)
        ident = sum(c['g_mean'] for c in cells if c['same_plan'] and c['cell'][2:] not in OPERATOR_DIFF)
        out['A1_operator_level'] = {'share_plan_identical': r4(ident / tot), 'operator_different': OPERATOR_DIFF,
                                    'note': 'registered (access path) share: %s' % S['claims']['A1']['share_of_slower_gap_mass_in_plan_identical_cells']}
        PL = S['plans']; rows = S['A'].get('timesplit', [])
        m_id = m_diff = 0.0
        for x in rows:
            q = x['cell'][2:]
            if x['g_Y0_R'] <= x['band']:
                continue
            same = True if q in ('insert_txn', 'startup') else PL.get(f'2|S1|{q}', {}).get('same_plan_R_Y0')
            if same:
                m_id += x['g_Y0_R']
            else:
                m_diff += x['g_Y0_R']
        out['A1_on_Y0_Turso_0.5.0'] = {'share_plan_identical': r4(m_id / (m_id + m_diff)) if m_id + m_diff else None,
                                       'note': 'the claim was made for Turso 0.5.0; seed 2, S1, time split'}
        out['A_startup_share_of_time_difference'], _ = startup_shares('A_SURVEY', 'A_startup', 'S1')
    if 'B' in S:
        out['B_startup_share_of_time_difference'], out['B_startup_adjusted_log_gap'] = startup_shares('B_SURVEY', 'B_true', 'C')
        out['startup_ms'] = {k: v for k, v in (('A', startup_ms('A_SURVEY', 'A_startup', 'S1')), ('B', startup_ms('B_SURVEY', 'B_true', 'C')))}
        if 'base64_mechanism' in S:
            bm = S['base64_mechanism']
            out['B_base64_mechanism'] = {k: {'read': v['strace'].get('read'), 'write': v['strace'].get('write'),
                                             'max_rss_kB': v['time_v'].get('Maximum resident set size (kbytes)'),
                                             'minor_faults': v['time_v'].get('Minor (reclaiming a frame) page faults')} for k, v in bm.items()}
            ci = {k: v for k, v in S['captures'].get('B', {}).get('base64', {}).items()}
            out['B_base64_mechanism']['instr_log_ratio_4MiB'] = ci
    ch = S.get('captures_heldout', {})
    if ch:
        rows = {}
        sw = {x['seed']: x for x in S.get('C', {}).get('swaps', [])}
        for seg, m in sorted(ch.items()):
            seed = int(seg[1:])
            rows[seg] = {'C2_rust_share': m['C2_rust_share_instr'], 'C3_max_single_share': m['C3_max_single_share'],
                         'C3_top1': m['C3_top'][0], 'C3_top5_share': m['C3_top5_share'],
                         'PR1400_profile_share_mv': m['cg2_profile_share_mv_P1400p_vs_R0'], 'PR1400_profile_predicted_log_gain': m['cg2_predicted_log_gain'],
                         'PR1397_profile_predicted_log_gain': m['cg3_predicted_log_gain'],
                         'PR1400_instr_change': m['C6_instr_change_P1400'], 'PR1400_time_effect': sw.get(seed, {}).get('e1400'),
                         'PR1397_profile_share_cdef': m['cg3_profile_share_cdef_P1397p_vs_R0'],
                         'PR1397_instr_change': m['C5_instr_change_P1397'], 'PR1397_time_effect': sw.get(seed, {}).get('e1397'),
                         'instr_log_ratio_Y1_R1': m['instr_log_ratio_Y1_R1'], 'anchor_equal': m['anchor_equal']}
        out['C_profiles_by_segment'] = rows
    ro = load('A_RO')
    if ro:
        bA = S['A']['bands'] if 'A' in S else {}
        out['A_startup_config_witness_readonly'] = [
            {'cell': r['cell'], 'seed': r['seed'], 'g_default': r4(est(r, 'Yd', 'Rd')), 'U_readonly': r4(est(r, 'Yro', 'Rd')),
             'effect_of_readonly': r4(est(r, 'Yro', 'Yd')), 'band': r4(b_for(bA, r, 'Rd')) if bA else None,
             'class_by_RQ4_rule': ('configuration-fixable' if est(r, 'Yro', 'Rd') <= b_for(bA, r, 'Rd') else 'candidate') if bA else None}
            for r in ro if timed(r)]
    nf = os.path.join(RES, 'natural_floors.json')
    if os.path.exists(nf):
        out['natural_floors'] = json.load(open(nf))
    for pair in ('A', 'B', 'C'):
        R = S.get('rq4', {}).get(pair)
        if R and R['cells']:
            bm_ = S[pair]['matched_null_p95']
            mass = {c['cell']: statistics.mean(c['g_Y0_R']) for c in R['cells'] if c['robust_Y0_gap']}
            dec = sum(m for c, m in mass.items() if all(u <= bm_ for u in next(x for x in R['cells'] if x['cell'] == c)['U_g_Y1_R']))
            out[f'rq4_{pair}_decided_share_with_matched_null'] = r4(dec / sum(mass.values())) if mass else None
    return out


def planted_classes(S):
    """DEVIATIONS.md #8: classification of planted gaps under the main contract (F removable) and under V_F (F frozen)."""
    arch, env = load('B_ARCH'), load('B_ENV')
    if not arch or not env:
        return {}
    b = S['B']['bands']['<0.1s'] if 'B' in S else 0.236
    bm = S['B']['matched_null_p95'] if 'B' in S else None
    e = env[0]; ra_e = rounds_by_arm(e)
    def w_of(cell, size):
        arm = f"E_{cell}_{size}"
        diffs = [statistics.mean(x) - statistics.mean(y) for x, y in zip(ra_e[arm], ra_e['E0'])]
        return min(diffs) / 1e9, int(e['arms'][arm]['env']['GAPCR_PLANT_US']) / 1e6
    rows = []
    for r in arch:
        if not timed(r):
            continue
        cell = r['cell'][2:]
        ra = rounds_by_arm(r)
        t_r_upper = max(statistics.mean(x) for a in ('Rd', 'Ra') for x in ra[a]) / 1e9
        u = est(r, 'Yd', 'Rd')
        for arm, size in (('P2', '2'), ('P05', '05')):
            g = est(r, arm, 'Rd')
            w, planted = w_of(cell, size)
            l_delta = math.log(min(w, planted)) - math.log(t_r_upper)   # the smaller of the measured and the source guarantee
            gap = g > b
            if not gap:
                lab_f = lab_m = 'no robust slower gap'
            else:
                lab_f = 'architectural' if l_delta > b else 'candidate'
                lab_m = 'fixable (witnessed)' if u <= b else 'candidate'
            truth_f = 'architectural' if arm == 'P2' else 'unknown'
            truth_m = 'fixable' if cell == 'sort' else 'unknown'
            mislabel = ('architectural, contradicted by the witness: violation flagged' if (gap and l_delta > b and u <= b)
                        else ('architectural (no contradicting witness)' if gap and l_delta > b else '-'))
            rows.append({'cell': cell, 'arm': arm, 'planted_ms': r4(planted * 1e3), 'w_measured_ms': r4(w * 1e3),
                         'T_R_upper_ms': r4(t_r_upper * 1e3), 'g': r4(g), 'L_delta': r4(l_delta), 'U_witness_main': r4(u),
                         'label_under_V_F': lab_f, 'truth_under_V_F': truth_f, 'label_under_main': lab_m, 'truth_under_main': truth_m,
                         'mislabelled_frozen_under_main': mislabel,
                         'label_under_V_F_with_b_m': ('architectural' if g > bm and l_delta > bm else ('candidate' if g > bm else 'no gap')) if bm else None})
    return {'band': b, 'b_m': bm, 'rows': rows}


def wasi_classes(S):
    """DEVIATIONS.md #10: uutils under its wasm32-wasip1 contract W, on XFS with reflink. Certificate from the envelope
    of the frozen WASI copy path (kernel read into a user buffer plus write from it, measured natively)."""
    recs, envp = load('W_ARCH'), os.path.join(RES, 'envelope_xfs.jsonl')
    if not recs or not os.path.exists(envp):
        return {}
    env = {e['bytes']: e for e in map(json.loads, open(envp))}
    bands = S['B']['bands'] if 'B' in S else {'<0.1s': 0.236, '0.1-1s': 0.177}
    rows = []
    for r in recs:
        if not timed(r):
            continue
        ra = rounds_by_arm(r)
        n = r['factors']['bytes']; e = env[n]
        copy = r['family'] == 'cp'
        ws = [e['read_min_s']] + ([e['write_min_s']] if copy else [])
        L_seq = sum(ws)                                  # single-threaded guest: the copies cannot overlap
        L = max(sum(ws) / os.cpu_count(), max(ws))       # Theorem 1 literally: work law over P cores, span law with p_o = 1
        t_r_upper = max(statistics.mean(x) for a in ('Rd', 'Ra') for x in ra[a]) / 1e9
        b = bands.get(stratum(med_s(r, 'Rd')), max(bands.values()))
        g_w, g_n = est(r, 'Yw', 'Rd'), est(r, 'Yn', 'Rd')
        l_delta = math.log(L) - math.log(t_r_upper)
        row = {'cell': r['cell'], 'bytes': n, 'T_R_ms': r4(med_s(r, 'Rd') * 1e3), 'T_R_upper_ms': r4(t_r_upper * 1e3),
               'T_Yw_ms': r4(med_s(r, 'Yw') * 1e3), 'T_Yn_ms': r4(med_s(r, 'Yn') * 1e3), 'band': b,
               'g_wasi': r4(g_w), 'g_native': r4(g_n), 'aa_R': r4(est(r, 'Ra', 'Rd')),
               'floor_L_ms': r4(L * 1e3), 'L_delta': r4(l_delta), 'floor_L_seq_ms': r4(L_seq * 1e3),
               'L_delta_seq': r4(math.log(L_seq) - math.log(t_r_upper)), 'write_only_L_delta': r4(math.log(ws[-1]) - math.log(t_r_upper)) if copy else None,
               'class_under_W': ('architectural' if g_w > b and l_delta > b else ('candidate' if g_w > b else 'no robust slower gap')),
               'class_native': ('candidate (startup)' if g_n > b else 'no robust slower gap')}
        if 'Rk' in ra:
            row.update({'T_Rk_ms': r4(med_s(r, 'Rk') * 1e3), 'knockout_reflink_never_on_R': r4(est(r, 'Rk', 'Rd')),
                        'g_wasi_vs_R_without_reflink': r4(est(r, 'Yw', 'Rk')),
                        'L_delta_vs_R_without_reflink': r4(math.log(L) - math.log(max(statistics.mean(x) for x in ra['Rk']) / 1e9))})
        rows.append(row)
    return {'rows': rows, 'envelope': env}


def excess_share(cap, sys_key, ref_key, pattern):
    """Profile share (correlational): the system's excess instructions over the reference in functions matching
    `pattern`, as a share of the total excess; and the implied predicted log-instruction gain of removing it."""
    ys = resolve(cap[f'C|{sys_key}|-1']['funcs'], OBJ.get(sys_key)); rs = resolve(cap[f'C|{ref_key}|-1']['funcs'], OBJ.get(ref_key))
    rx = re.compile(pattern, re.I)
    ey = sum(v for k, v in ys.items() if rx.search(k)); er = sum(v for k, v in rs.items() if rx.search(k))
    ty, tr = cap[f'C|{sys_key}|-1']['total'], cap[f'C|{ref_key}|-1']['total']
    share = (ey - er) / (ty - tr)
    return {'excess_instr': ey - er, 'share_of_excess': r4(share), 'predicted_log_gain': r4(math.log((ty - (ey - er)) / ty))}


def cg_comparisons(S, cap):
    """RQ3: correlational gap graph (passive data) against counterfactual measurement (DEVIATIONS.md #5)."""
    out = {}
    if 'C' in S:
        rows = {x['cell']: x for x in S['C']['survey']}
        n, d = rows.get('C_t1_mnone'), rows.get('C_t1_m-1')
        if n and d:
            meas = [r4(n['g'][n['seeds'].index(s)] - d['g'][d['seeds'].index(s)]) for s in HELD['C'] if s in n['seeds']]
            out['C-cg1'] = {'cg_claim': 'shared asm carries no excess (anchors equal), so the asm configuration does not move the gap',
                            'cg_predicted_change': 0.0, 'measured_change_g_none_minus_g_default': meas,
                            'abs_error': [abs(m) for m in meas]}
        if cap:
            p1400 = excess_share(cap, 'P1400p', 'R0', MV)
            p1397 = excess_share(cap, 'P1397p', 'R0', r'cdef')
            sw = S['C'].get('swaps', [])
            e1400 = [x['e1400'] for x in sw if x['seed'] in HELD['C']]; e1397 = [x['e1397'] for x in sw if x['seed'] in HELD['C']]
            ci = S['captures'].get('C', {})
            out['C-cg2'] = {'cg_profile': p1400, 'measured_instr_change': ci.get('C6_instr_change_P1400'), 'measured_time_effect': e1400}
            out['C-cg3'] = {'cg_profile': p1397, 'measured_instr_change': ci.get('C5_instr_change_P1397'), 'measured_time_effect': e1397}
    if 'B' in S and S['B'].get('ko'):
        hw = set(S.get('markers', {}).get('gnu_accelerated_cells', ['B_cksum', 'B_wc_l']))
        ko = S['B']['ko']
        def mean(xs):
            return statistics.mean(xs) if xs else None
        for ver, gk, gkk in (('Y1', 'g_Y1_R', 'g_Y1_Rk'), ('Y0', 'g_Y0_R', 'g_Y0_Rk')):
            hw_g = [x[gk] for x in ko if x['cell'] in hw]; other = [x[gk] for x in ko if x['cell'] not in hw]
            contrast = mean(hw_g) - mean(other) if hw_g and other else None
            effect = [x[gk] - x[gkk] for x in ko if x['cell'] in hw]
            out[f'B-cg1-{ver}'] = {'cg_signature_contrast': r4(contrast), 'measured_knockout_effect_on_gap_mean': r4(mean(effect)),
                                   'per_cell': [(x['cell'], x['seed'], r4(x[gk] - x[gkk])) for x in ko if x['cell'] in hw]}
        b64 = [x for x in ko if x['cell'] == 'B_base64']; ck = [x for x in ko if x['cell'] == 'B_cksum']
        out['B-cg2'] = {'cg_claim': 'the Y0 base64 and cksum gaps were caused by missing SIMD (they were fixed by SIMD crates)',
                        'base64_knockout_on_R': [x['e_KO_on_R'] for x in b64], 'base64_g_Y0_R': [x['g_Y0_R'] for x in b64],
                        'cksum_g_Y0_R': [x['g_Y0_R'] for x in ck], 'cksum_g_Y0_Rk': [x['g_Y0_Rk'] for x in ck]}
    if 'A' in S and S['A'].get('ko'):
        PL = S['plans']; rows = [x for x in S['A']['survey'] if x['state'] == 'S1']
        same, diff = [], []
        for x in rows:
            q = x['cell'][2:]
            if q in ('insert_txn', 'startup'):
                continue
            ident = all(PL.get(f'{s}|S1|{q}', {}).get('same_plan_R_Y1') for s in (1, 2))
            (same if ident else diff).append(statistics.mean(x['g']))
        contrast = statistics.mean(diff) - statistics.mean(same) if same and diff else None
        parts = []
        for k in S['A']['ko']:
            if k['cell'] == 'A_in_subquery':
                parts.append({'cell': 'in_subquery (Y1; SQLite without Bloom runs Turso\'s plan)', 'seed': k['seed'], 'gap': k['g_default'],
                              'plan_part': k['plan_part'], 'execution_part': k['g_equalized']})
            if k['cell'] == 'A_join3_star':
                parts.append({'cell': 'join3_star (Y0 = Turso 0.5.0; SQLite without Bloom runs its plan)', 'seed': k['seed'], 'gap': k['g_default_Y0'],
                              'plan_part': r4(k['g_default_Y0'] - k['g_equalized_Y0']), 'execution_part': k['g_equalized_Y0']})
            if k['cell'] == 'A_join2':
                a = r4(k['g_S1_default'] - k['exec_plan_customers_first'])      # common plan = Turso's (customers first)
                b = r4(k['g_S1_default'] - k['exec_plan_orders_first'])         # common plan = SQLite's (orders first)
                parts.append({'cell': 'join2 S1 (crossed statistics states)', 'seed': k['seed'], 'gap': k['g_S1_default'],
                              'plan_part': r4((a + b) / 2), 'execution_part': r4(k['g_S1_default'] - (a + b) / 2),
                              'plan_part_if_common_plan_is_Turso_s': a, 'plan_part_if_common_plan_is_SQLite_s': b,
                              'note': 'interaction: the execution gap is +0.25 under one plan and -0.05 under the other; '
                                      'plan_part is the Shapley average of the two switching orders'})
        for k in load('A_KO2'):
            if timed(k):
                g, ge = est(k, 'Yp', 'Rp'), est(k, 'Yp', 'Rk')
                parts.append({'cell': 'distinct (Y1; SQLite without DistinctOpt runs Turso\'s operator; exploratory, DEVIATIONS #7)', 'seed': k['seed'],
                              'gap': r4(g), 'plan_part': r4(g - ge), 'execution_part': r4(ge), 'Y_aa': r4(est(k, 'Ya', 'Yp'))})
        out['A-cg1'] = {'cg_signature_contrast_plan_diff_minus_same': r4(contrast), 'mean_gap_plan_identical': r4(statistics.mean(same)) if same else None,
                        'mean_gap_plan_different': r4(statistics.mean(diff)) if diff else None,
                        'measured_decompositions': parts}
        j2 = [k for k in S['A']['ko'] if k['cell'] == 'A_join2']
        out['A-cg2'] = {'join2_per_state': [(k['seed'], k['g_S1_default'], k['g_S0_default'], k['exec_plan_customers_first'], k['exec_plan_orders_first']) for k in j2],
                        'columns': 'seed, gap S1, gap S0, execution gap with customers-first plan (Y in S1 vs R in S0), with orders-first plan (Y in S0 vs R in S1)'}
    return out


if __name__ == '__main__':
    main()
