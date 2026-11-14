"""Audit v2, registered before any frontier-model output exists (DEVIATIONS.md #12). It is applied identically to every
builder, so models are compared under one set of rules.

  python3 audit_v2.py outputs outputs_frontier      writes audit_v2_<dir>.csv and audit_v2_summary.json

Changes from v1 (audit.py), all fixed before the frontier run:
  (ii)/(iv) are checked independently of the unit the builder uses. A frozen operator's claimed least work above the
            time bound of the work the cell forces on it (forced amount x per-unit upper bound, x1.5) is an overestimate;
            it is (ii) if the claimed amount converts and exceeds the forced amount by more than 10%, otherwise (iv).
            The #11b checks are kept: least work above the system's own run on the cell (iv), and cksum's fd_write (ii).
  (v)       is computed over frozen and platform premises only. Sums are allowed where the contract makes execution
            sequential (wasip1 is single-threaded), and otherwise Theorem 1's floor is recomputed with P = 4 and the
            true per-operator cores.
  valid     an architectural label is a valid certificate if no premise has an error and the gap is architectural.
(i) and (iii) are as in v1. Hand-review findings are reported separately, never merged into these counts."""
import csv, glob, json, math, os, re, sys

import audit as A

HERE = os.path.dirname(os.path.abspath(__file__))


def audit_dir(d, truth):
    rows, outs = [], []
    for f in sorted(glob.glob(os.path.join(HERE, d, '*.json'))):
        if os.path.basename(f).startswith('_'):
            continue
        o = json.load(open(f)); tr = truth[o['gap']]
        js = A.parse(o['text'])
        rec = {'gap': o['gap'], 'seed': o['seed'], 'parsed': js is not None, 'truth_class': tr['klass']}
        if js is None:
            outs.append(rec); continue
        klass = str(js.get('class', '')).lower().strip(); rec['class'] = klass
        T_R_up = tr.get('T_R_upper_s') or max(tr.get('T_R_s', [0])) * 1.1
        errs, prem = set(), []
        for op in [x for x in (js.get('chokepoint') or []) if isinstance(x, dict)]:
            lw = op.get('least_work') or {}
            def num(v):
                try:
                    return float(v)
                except Exception:
                    return None
            total = num(lw.get('total_ms')) or 0.0
            amount = num(lw.get('amount'))
            kind, comp = A.match_component(op.get('component'), tr)
            e = {k: False for k in ('i', 'ii', 'iii', 'iv')}
            text = f"{op.get('operator', '')} {lw.get('calling_context', '')}".lower()
            if total > 0 and kind == 'mutable':
                e['iii'] = True
            if kind == 'frozen' and tr['avoidable'] and o['gap'] != 'A_insert_txn' and any(re.search(p, text, re.I) for p in tr['avoidable']):
                e['i'] = True
            forced = tr['forced'].get(comp) if kind == 'frozen' else None
            if forced and total > 0:
                bound_ms = forced['amount_upper'] * forced['per_unit_upper_us'] / 1e3
                a = A.amount_in(lw.get('unit'), amount, forced['unit']) if amount is not None else None
                if a is not None and a > 1.1 * forced['amount_upper'] + 1:
                    e['ii'] = True
                elif total > 1.5 * bound_ms + 1e-3:
                    e['iv'] = True
            if kind == 'frozen' and total > 1e3 * A.SYSTEM_TIME.get(o['gap'], float('inf')) and not e['ii']:
                e['iv'] = True
            if kind == 'frozen' and o['gap'] == 'W_cksum32' and 'write' in (comp or '').lower():
                a = A.amount_in(lw.get('unit'), amount, 'bytes') if amount is not None else None
                if a is None or a > 64:
                    e['ii'] = True; e['iv'] = False
            if kind == 'platform' and total > 1e3 * T_R_up:
                e['ii'] = True
            prem.append((total, comp, kind))
            rows.append({'gap': o['gap'], 'seed': o['seed'], 'class': klass, 'operator': op.get('operator'), 'component': op.get('component'),
                         'kind': kind, 'total_ms': total, 'amount': amount, 'unit': lw.get('unit'), **{f'err_{k}': v for k, v in e.items()}})
            errs |= {k for k, v in e.items() if v}
        floor = 0.0
        try:
            floor = float(js.get('floor_ms') or 0)
        except Exception:
            pass
        fp = [(t, c, k) for t, c, k in prem if t > 0 and k != 'mutable']
        if fp and floor > 0:
            if tr['contract'] == 'wasi':
                L = sum(t for t, _, _ in fp)
            else:
                cores = lambda c, k: tr['cores'].get(c, 1) if k == 'frozen' else 4
                L = max(sum(t for t, _, _ in fp) / 4, max(t / cores(c, k) for t, c, k in fp))
            if floor > 1.2 * L and not ('iii' in errs and floor <= 1.2 * sum(t for t, _, _ in prem)):
                errs.add('v')
        rec.update({'errors': sorted(errs), 'n_premises': len(prem),
                    'unsupported_architectural': klass == 'architectural' and tr['klass'] != 'architectural',
                    'architectural_found': klass == 'architectural' and tr['klass'] == 'architectural',
                    'valid_certificate': klass == 'architectural' and tr['klass'] == 'architectural' and not errs})
        outs.append(rec)
    return rows, outs


def summarize(rows, outs):
    parsed = [o for o in outs if o['parsed']]; n = len(rows)
    s = {'outputs': len(outs), 'parsed': len(parsed), 'premises': n,
         'classes': {c: sum(o.get('class') == c for o in parsed) for c in ('architectural', 'candidate', 'fixable')}}
    for k in ('i', 'ii', 'iii', 'iv'):
        kp = sum(r[f'err_{k}'] for r in rows)
        s[f'type_{k}'] = {'premises': kp, 'rate': round(kp / n, 3) if n else None, 'ci95': A.cp_interval(kp, n) if n else None}
    kv = sum('v' in o['errors'] for o in parsed)
    s['type_v_outputs'] = {'outputs': kv, 'rate': round(kv / len(parsed), 3) if parsed else None}
    non = [o for o in parsed if o['truth_class'] != 'architectural']; arch = [o for o in parsed if o['truth_class'] == 'architectural']
    ua = sum(o['unsupported_architectural'] for o in non)
    s['unsupported_architectural'] = {'k': ua, 'n': len(non), 'rate': round(ua / len(non), 3) if non else None,
                                      'ci95': A.cp_interval(ua, len(non)) if non else None,
                                      'with_a_premise_error': sum(1 for o in non if o['unsupported_architectural'] and o['errors'])}
    s['architectural_found'] = {'k': sum(o['architectural_found'] for o in arch), 'n': len(arch)}
    s['valid_certificates'] = {'k': sum(o['valid_certificate'] for o in arch), 'n': len(arch)}
    return s


def main(dirs):
    truth = json.load(open(os.path.join(HERE, 'ground_truth.json')))
    allsum = {}
    for d in dirs:
        rows, outs = audit_dir(d, truth)
        with open(os.path.join(HERE, f'audit_v2_{d}.csv'), 'w', newline='') as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        allsum[d] = {'summary': summarize(rows, outs), 'outputs': outs}
    json.dump(allsum, open(os.path.join(HERE, 'audit_v2_summary.json'), 'w'), indent=1)
    print(json.dumps({d: v['summary'] for d, v in allsum.items()}, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:] or ['outputs', 'outputs_frontier'])
