"""Registered analysis for DEVIATIONS #13 (written before any replication or diagnostic output exists).

  python3 replication.py        reads outputs_{frontier,opus}{,_rep,_diag}/, writes replication_summary.json

Arm R (exact replication, samples 3-6, audit v2, corrected ground truth). The split is CONFIRMED if all three hold:
  C-R1  WebAssembly cp (W_cp512, W_cp128; 8 outputs per model): Claude architectural >= 6/8 and GPT architectural <= 2/8.
  C-R2  planted gap (4 outputs per model): Claude architectural >= 3/4 and GPT fixable >= 3/4.
  C-R3  "fixable" labels on the 17 gaps whose truth is candidate (68 outputs per model): Claude >= 17/68, GPT <= 3/68.
  Secondary, reported but not part of the decision: C-R4 false architectural labels outside the planted gap <= 2/64.
Arm D (diagnostic, samples 1-4): a builder follows a stated premise if >= 3 of its 4 outputs have the expected class.
  The explanation (the split is how each builder fills a premise the prompt leaves implicit) is supported if both
  builders follow all four premises. In D_cp512_noceiling an architectural label matches only if its per-byte cost is
  not the stated 8 GB/s rate (an independent bound, flagged for hand review)."""
import json, os

import audit as A
import audit_v2 as V

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDERS = {'GPT-6.1 Sol': 'outputs_frontier', 'Claude Opus 5.5': 'outputs_opus'}
EXPECTED = {'D_plant_mutable': 'fixable', 'D_plant_frozen': 'architectural',
            'D_cp512_ceiling': 'architectural', 'D_cp512_noceiling': 'candidate'}
STATED_RATE_US_PER_BYTE = 1 / 8000.0   # 8 GB/s


def count(outs, gaps, klass):
    sel = [o for o in outs if o['gap'] in gaps and o['parsed']]
    return sum(o.get('class') == klass for o in sel), len(sel)


def arm_r(truth):
    res = {}
    cand = sorted(g for g, t in truth.items() if t['klass'] == 'candidate')
    for name, d in BUILDERS.items():
        rows, outs = V.audit_dir(d + '_rep', truth)
        rows1, outs1 = V.audit_dir(d, truth)
        cp = count(outs, {'W_cp512', 'W_cp128'}, 'architectural')
        pl_arch = count(outs, {'P_sort_frozen_plant'}, 'architectural')
        pl_fix = count(outs, {'P_sort_frozen_plant'}, 'fixable')
        fx = count(outs, set(cand), 'fixable')
        fa = sum(o.get('unsupported_architectural', False) for o in outs if o['gap'] != 'P_sort_frozen_plant')
        n_fa = sum(1 for o in outs if o['parsed'] and o['gap'] != 'P_sort_frozen_plant' and o['truth_class'] != 'architectural')
        stab = {}
        for g in sorted({o['gap'] for o in outs1 + outs}):
            stab[g] = [o.get('class') for o in sorted(outs1 + outs, key=lambda o: o['seed']) if o['gap'] == g]
        res[name] = {'new_samples': V.summarize(rows, outs), 'pooled_6': V.summarize(rows1 + rows, outs1 + outs),
                     'cp_architectural': cp, 'planted_architectural': pl_arch, 'planted_fixable': pl_fix,
                     'fixable_on_candidate_gaps': fx, 'false_architectural_outside_planted': (fa, n_fa),
                     'classes_by_gap_all_samples': stab}
    g, c = res['GPT-6.1 Sol'], res['Claude Opus 5.5']
    crit = {'C-R1': c['cp_architectural'][0] >= 6 and g['cp_architectural'][0] <= 2,
            'C-R2': c['planted_architectural'][0] >= 3 and g['planted_fixable'][0] >= 3,
            'C-R3': c['fixable_on_candidate_gaps'][0] >= 17 and g['fixable_on_candidate_gaps'][0] <= 3,
            'C-R4 (secondary)': all(r['false_architectural_outside_planted'][0] <= 2 for r in res.values())}
    return res, crit, all(crit[k] for k in ('C-R1', 'C-R2', 'C-R3'))


def arm_d():
    res = {}
    for name, d in BUILDERS.items():
        per = {}
        for v, exp in EXPECTED.items():
            outs = []
            for s in range(1, 5):
                f = os.path.join(HERE, d + '_diag', f'{v}__s{s}.json')
                if not os.path.exists(f):
                    continue
                js = A.parse(json.load(open(f))['text']) or {}
                klass = str(js.get('class', '')).lower().strip()
                rates = [((op.get('least_work') or {}).get('per_unit_cost_us')) for op in (js.get('chokepoint') or []) if isinstance(op, dict)]
                stated = bool(rates) and all(isinstance(r, (int, float)) and abs(r - STATED_RATE_US_PER_BYTE) <= 0.1 * STATED_RATE_US_PER_BYTE for r in rates)
                match = klass == exp or (v == 'D_cp512_noceiling' and klass == 'architectural' and not stated)
                outs.append({'sample': s, 'class': klass, 'L_delta': js.get('L_delta'), 'uses_stated_rate': stated,
                             'match': match, 'independent_bound_for_review': v == 'D_cp512_noceiling' and klass == 'architectural' and not stated})
            per[v] = {'expected': exp, 'outputs': outs, 'matches': sum(o['match'] for o in outs), 'n': len(outs),
                      'follows': sum(o['match'] for o in outs) >= 3}
        res[name] = per
    supported = all(p['follows'] for per in res.values() for p in per.values())
    return res, supported


def main():
    truth = json.load(open(os.path.join(HERE, 'ground_truth.json')))
    r, crit, confirmed = arm_r(truth)
    d, supported = arm_d()
    out = {'arm_R': r, 'criteria': crit, 'split_confirmed': confirmed, 'arm_D': d, 'explanation_supported': supported}
    json.dump(out, open(os.path.join(HERE, 'replication_summary.json'), 'w'), indent=1)
    for name in BUILDERS:
        x = r[name]
        print(f"{name}: cp arch {x['cp_architectural']}, planted arch {x['planted_architectural']} fixable {x['planted_fixable']}, "
              f"fixable on candidate {x['fixable_on_candidate_gaps']}, false arch outside planted {x['false_architectural_outside_planted']}")
    print('criteria', crit, 'CONFIRMED' if confirmed else 'NOT CONFIRMED')
    for name in BUILDERS:
        print(name, {v: f"{p['matches']}/{p['n']} {[o['class'][:4] for o in p['outputs']]}" for v, p in d[name].items()})
    print('explanation supported' if supported else 'explanation NOT supported')


if __name__ == '__main__':
    main()
