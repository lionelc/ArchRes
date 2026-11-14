"""Mechanical audit of the builder's certificate premises against ground_truth.json, by Theorem 3's error types.
Fixed before any builder output exists (DEVIATIONS.md #11).

  python3 audit.py          writes audit.csv (one row per chokepoint premise) and audit_summary.json

Per premise (an operator the builder lists in its chokepoint and counts in its floor):
  (iii) mutable counted as frozen: its component is neither frozen by the contract nor platform (kernel, CPU hardware);
  (i)   bypass: a frozen operation that an admissible setting avoids (ground truth `avoidable`);
  (ii)  overestimated least work: the amount exceeds the cell's forced amount by more than 10%, or, for platform work,
        the claimed least work exceeds T_R_upper (the reference does that work, and more, in less time);
  (iv)  costlier calling context than an admissible one: per-unit cost above 1.5x the ground truth's upper bound;
  (v)   less parallelism or overlap than admissible: the builder's floor exceeds, by more than 20%, the floor of Theorem 1
        recomputed from its own least works with P = 4 and the true per-operator cores.
Per output: the class claimed; an architectural label is unsupported if the truth is not architectural.
Exact (Clopper-Pearson) 95% intervals."""
import csv, glob, json, math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = ('operating system kernel', 'cpu hardware')
UNIT_BYTES = {'b': 1, 'byte': 1, 'bytes': 1, 'kb': 1e3, 'kib': 1024, 'mb': 1e6, 'mib': 1 << 20, 'gb': 1e9, 'gib': 1 << 30}


def parse(text):
    t = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    i, depth = t.find('{'), 0
    if i < 0:
        return None
    for j in range(i, len(t)):
        depth += {'{': 1, '}': -1}.get(t[j], 0)
        if depth == 0:
            try:
                return json.loads(t[i:j + 1])
            except Exception:
                return None
    return None


def match_component(comp, truth):
    c = (comp or '').lower()
    for f in truth['frozen']:
        if f.lower() in c or c in f.lower():
            return 'frozen', f
    if any(p in c for p in PLATFORM) or c in ('kernel', 'hardware', 'cpu'):
        return 'platform', c
    return 'mutable', c


def amount_in(unit, amount, forced_unit):
    u = (unit or '').lower().strip().rstrip('s') if unit else ''
    if forced_unit == 'pages':
        if 'page' in u:
            return amount
        return None
    if forced_unit == 'bytes':
        for k, f in UNIT_BYTES.items():
            if u == k or u == k.rstrip('s'):
                return amount * f
        return None
    if forced_unit == 'runs':
        return amount if re.search(r'run|call|invocation|time', u) else None
    return None


def cp_interval(k, n, a=0.05):
    from statistics import NormalDist  # noqa: F401 (stdlib only; beta quantiles by bisection)
    def beta_cdf(x, aa, bb, steps=4000):
        if x <= 0: return 0.0
        if x >= 1: return 1.0
        h = x / steps; s = 0.0
        for i in range(steps):
            t = (i + 0.5) * h
            s += t ** (aa - 1) * (1 - t) ** (bb - 1)
        return s * h / math.exp(math.lgamma(aa) + math.lgamma(bb) - math.lgamma(aa + bb))
    def quant(p, aa, bb):
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            if beta_cdf(mid, aa, bb) < p: lo = mid
            else: hi = mid
        return (lo + hi) / 2
    lo = 0.0 if k == 0 else quant(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else quant(1 - a / 2, k + 1, n - k)
    return round(lo, 3), round(hi, 3)


def bands():
    S = json.load(open(os.path.join(HERE, '..', 'pilot', 'results', 'summary.json')))
    out = {}
    for x in S['A']['survey']:
        if x['state'] == 'S1':
            out[x['cell']] = S['A']['bands']['<0.1s'] if x['R_s'][0] < 0.1 else S['A']['bands']['0.1-1s']
    for x in S['B']['survey']:
        if x['state'] == 'C':
            out[x['cell']] = S['B']['bands']['<0.1s'] if x['R_s'][0] < 0.1 else S['B']['bands']['0.1-1s']
    return out


BANDS = bands()


def system_times():
    """The system's own measured time on each cell (an admissible run, so an upper bound on any frozen least work)."""
    t = json.load(open(os.path.join(HERE, 'ground_truth.json')))
    out = {g: max(v['T_Y_s']) for g, v in t.items() if v.get('T_Y_s')}
    out['P_sort_frozen_plant'] = 0.1131            # uutils sort with F, B_ARCH (prompt)
    return out


SYSTEM_TIME = system_times()


def main():
    truth = json.load(open(os.path.join(HERE, 'ground_truth.json')))
    rows, outs = [], []
    for f in sorted(glob.glob(os.path.join(HERE, 'outputs', '*.json'))):
        o = json.load(open(f)); tr = truth[o['gap']]
        js = parse(o['text'])
        rec = {'gap': o['gap'], 'seed': o['seed'], 'parsed': js is not None, 'truth_class': tr['klass']}
        if js is None:
            outs.append(rec); continue
        klass = str(js.get('class', '')).lower().strip()
        rec['class'] = klass
        ops = [op for op in (js.get('chokepoint') or []) if isinstance(op, dict)]
        T_R_up = tr.get('T_R_upper_s') or max(tr.get('T_R_s', [0])) * 1.1
        b = None
        lw_list, errs_out, errs_supp = [], set(), set()
        for op in ops:
            lw = op.get('least_work') or {}
            try:
                total = float(lw.get('total_ms') or 0)
            except Exception:
                total = 0.0
            kind, comp = match_component(op.get('component'), tr)
            e = {k: False for k in ('i', 'ii', 'iii', 'iv', 'v')}
            text = f"{op.get('operator', '')} {lw.get('calling_context', '')}".lower()
            if total > 0 and kind == 'mutable':
                e['iii'] = True
            if kind == 'frozen' and tr['avoidable'] and not (o['gap'] == 'A_insert_txn' and tr['pair'] == 'A') \
                    and any(re.search(p, text, re.I) for p in tr['avoidable']):
                e['i'] = True
            forced = tr['forced'].get(comp) if kind == 'frozen' else None
            try:
                amount = float(lw.get('amount')) if lw.get('amount') is not None else None
            except Exception:
                amount = None
            try:
                per_unit = float(lw.get('per_unit_cost_us')) if lw.get('per_unit_cost_us') is not None else None
            except Exception:
                per_unit = None
            if forced and amount is not None:
                a = amount_in(lw.get('unit'), amount, forced['unit'])
                if a is not None and a > 1.1 * forced['amount_upper'] + 1:
                    e['ii'] = True
                if a is not None and a > 0 and total > 0:
                    unit_cost = total * 1e3 / a          # us per unit, from the builder's own totals
                    if unit_cost > 1.5 * forced['per_unit_upper_us']:
                        e['iv'] = True
            if kind == 'platform' and total > 1e3 * T_R_up:
                e['ii'] = True
            lw_list.append((total, comp, kind))
            # supplementary (DEVIATIONS #11b): least work above an actual admissible run of the system, and cksum's output
            s_iv = kind == 'frozen' and total > 1e3 * SYSTEM_TIME.get(o['gap'], float('inf'))
            s_ii = False
            if kind == 'frozen' and o['gap'] == 'W_cksum32' and 'write' in (comp or '').lower() and amount is not None:
                a = amount_in(lw.get('unit'), amount, 'bytes')
                s_ii = a is None or a > 64
            rows.append({'gap': o['gap'], 'seed': o['seed'], 'class': klass, 'operator': op.get('operator'),
                         'component': op.get('component'), 'kind': kind, 'total_ms': total, 'amount': amount,
                         'unit': lw.get('unit'), 'per_unit_us': per_unit, 'cores': op.get('max_cores'),
                         **{f'err_{k}': v for k, v in e.items()}, 'supp_ii': s_ii, 'supp_iv': s_iv})
            if s_ii or s_iv:
                errs_supp.update({'ii'} if s_ii else set()); errs_supp.update({'iv'} if s_iv else set())
            errs_out |= {k for k, v in e.items() if v}
        # (v): recompute Theorem 1's floor from the builder's own least works
        try:
            floor = float(js.get('floor_ms') or 0)
        except Exception:
            floor = 0.0
        counted = [(t, c, k) for t, c, k in lw_list if t > 0]
        if counted and floor > 0:
            true_cores = lambda c, k: tr['cores'].get(c, 1) if k == 'frozen' else (1 if tr['contract'] == 'wasi' else 4)
            L = max(sum(t for t, _, _ in counted) / 4, max(t / true_cores(c, k) for t, c, k in counted))
            if floor > 1.2 * L:
                errs_out.add('v')
                for r in rows[-len(lw_list):]:
                    r['err_v'] = True
        # supplementary (DEVIATIONS #11a): (C3) by the builder's own numbers, and (v) over frozen or platform premises only
        b_cell = BANDS.get(o['gap'], 0.236)
        own_ok = floor > 0 and math.log(floor / 1e3) - math.log(T_R_up) > b_cell
        fp = [(t, c, k) for t, c, k in counted if k != 'mutable'] if (counted and floor > 0) else []
        v_fp = False
        if fp:
            tc = lambda c, k: tr['cores'].get(c, 1) if k == 'frozen' else (1 if tr['contract'] == 'wasi' else 4)
            L_fp = max(sum(t for t, _, _ in fp) / 4, max(t / tc(c, k) for t, c, k in fp))
            v_fp = sum(t for t, _, _ in fp) > 0 and floor > 1.2 * L_fp and floor <= 1.2 * sum(t for t, _, _ in fp)
        rec.update({'n_premises': len(ops), 'errors': sorted(errs_out), 'floor_ms': floor,
                    'unsupported_architectural': klass == 'architectural' and tr['klass'] != 'architectural',
                    'architectural_found': klass == 'architectural' and tr['klass'] == 'architectural',
                    'self_inconsistent_architectural': klass == 'architectural' and not own_ok,
                    'v_frozen_or_platform_only': v_fp,
                    'errors_with_supplementary': sorted(errs_out | errs_supp | ({'v'} if v_fp else set()))})
        outs.append(rec)
    with open(os.path.join(HERE, 'audit.csv'), 'w', newline='') as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    parsed = [o for o in outs if o['parsed']]
    n_prem = len(rows)
    summ = {'outputs': len(outs), 'parsed': len(parsed), 'premises': n_prem}
    for k in ('i', 'ii', 'iii', 'iv', 'v'):
        kp = sum(r[f'err_{k}'] for r in rows); ko = sum(k in o['errors'] for o in parsed)
        summ[f'type_{k}'] = {'premises_with_error': kp, 'rate_per_premise': round(kp / n_prem, 3) if n_prem else None,
                             'ci95_premise': cp_interval(kp, n_prem) if n_prem else None,
                             'outputs_with_error': ko, 'rate_per_output': round(ko / len(parsed), 3) if parsed else None,
                             'ci95_output': cp_interval(ko, len(parsed)) if parsed else None}
    arch_truth = [o for o in parsed if o['truth_class'] == 'architectural']
    non_arch = [o for o in parsed if o['truth_class'] != 'architectural']
    ua = sum(o['unsupported_architectural'] for o in non_arch); found = sum(o['architectural_found'] for o in arch_truth)
    summ['unsupported_architectural'] = {'k': ua, 'n': len(non_arch), 'rate': round(ua / len(non_arch), 3) if non_arch else None,
                                         'ci95': cp_interval(ua, len(non_arch)) if non_arch else None}
    summ['recall_architectural'] = {'k': found, 'n': len(arch_truth), 'rate': round(found / len(arch_truth), 3) if arch_truth else None}
    summ['any_error_in_unsupported_architectural'] = sum(1 for o in non_arch if o['unsupported_architectural'] and o['errors'])
    arch_claims = [o for o in parsed if o.get('class') == 'architectural']
    summ['supplementary_11a'] = {
        'architectural_claims': len(arch_claims),
        'self_inconsistent_architectural': sum(o['self_inconsistent_architectural'] for o in arch_claims),
        'v_frozen_or_platform_only_outputs': sum(o['v_frozen_or_platform_only'] for o in parsed),
        'unsupported_caught_by_contract_check_iii': sum(1 for o in non_arch if o['unsupported_architectural'] and 'iii' in o['errors']),
        'unsupported_caught_by_iii_or_own_C3': sum(1 for o in non_arch if o['unsupported_architectural']
                                                    and ('iii' in o['errors'] or o['self_inconsistent_architectural']))}
    supp = {}
    for k in ('i', 'ii', 'iii', 'iv', 'v'):
        kp = sum(r[f'err_{k}'] or r.get(f'supp_{k}', False) or (k == 'v' and False) for r in rows)
        ko = sum(k in o.get('errors_with_supplementary', []) for o in parsed)
        supp[f'type_{k}'] = {'premises': kp, 'rate_premise': round(kp / n_prem, 3) if n_prem else None,
                             'ci95_premise': cp_interval(kp, n_prem) if n_prem else None,
                             'outputs': ko, 'rate_output': round(ko / len(parsed), 3) if parsed else None,
                             'ci95_output': cp_interval(ko, len(parsed)) if parsed else None}
    supp['unsupported_architectural_with_any_error'] = sum(1 for o in non_arch if o['unsupported_architectural'] and o.get('errors_with_supplementary'))
    supp['architectural_found_with_premise_errors'] = sum(1 for o in arch_truth if o['architectural_found'] and o.get('errors_with_supplementary'))
    summ['supplementary_11b'] = supp
    summ['classes'] = {c: sum(o.get('class') == c for o in parsed) for c in ('architectural', 'candidate', 'fixable')}
    summ['by_pair'] = {}
    for grp, sel in (('A', lambda g: g.startswith('A_')), ('B native', lambda g: g.startswith('B_')),
                     ('B WebAssembly', lambda g: g.startswith('W_')), ('planted', lambda g: g.startswith('P_'))):
        os_ = [o for o in parsed if sel(o['gap'])]
        summ['by_pair'][grp] = {'outputs': len(os_), 'classes': {c: sum(o.get('class') == c for o in os_) for c in ('architectural', 'candidate', 'fixable')},
                                'with_any_error': sum(bool(o['errors']) for o in os_)}
    json.dump({'summary': summ, 'outputs': outs}, open(os.path.join(HERE, 'audit_summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
