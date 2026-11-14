"""The sufficiency rule for a fix's effect, from replications (generic form of cu1's analysis/sufficiency.py, amendment 2c).

Question: is a fix's effect on a cell-setting SUFFICIENTLY VERIFIED? There is no minimum effect size (a consistent 2% win
counts); what is required is enough evidence, in three independent legs:
  D  deterministic mechanism: with the fix's switch ON the mechanism's marker leaves the deterministic profile and the
     instruction total falls, on the same input (capture of the same cell-setting, else of the same cell's base setting);
  S  sign consistency: the effect is negative in at least sign_needed(K) of the K replication seeds;
  M  magnitude beyond the matched null: the mean effect lies below the null distribution of the mean of K draws from the
     stratum's pool of the system's own A/A estimates (same estimator, switch OFF twice); one-sided resampled p; Holm
     across the fix's precondition cell-settings at the look's alpha. A pool below min_pool borrows its neighbours.
Controls: the upper tail (Holm at alpha_controls) with the effect positive in sign_needed(K) seeds is a regression.
Calibration: leg M applied to the reference's own A/A estimate on every cell-setting (should reject at the nominal rate).
Looks: combine() keeps a look-1 SV and gives look-2 verdicts only to cell-settings with D true but not SV at look 1.

Input: replication runs in celltest's rep format: {'meta': ..., 'cells': {'<state>|<cell>|<setting>': {'role': 'P' or
'control', '<ref_equal_key>': bool, '<arms_equal_key>': bool, 'timing': {'rounds': [[{'w': conn, 'med': ns}, ...]]}}}}
and a capture file {'cells': {key: {'off': {'marker_in_top'}, 'on': {'marker_in_top'}, 'ir_ratio_on_off'}}}.
The order of computation (and of random draws) is fixed, so a case's recorded verdict regenerates byte for byte."""
import bisect, math, random, statistics
from dataclasses import dataclass, field

DEFAULT_STRATA = [(0, 40e6, '<40ms'), (40e6, 120e6, '40-120ms'), (120e6, float('inf'), '>120ms')]
DEFAULT_NEIGHBOURS = {'<40ms': ['40-120ms'], '>120ms': ['40-120ms'], '40-120ms': ['<40ms', '>120ms']}


@dataclass
class Rule:
    connections: tuple = ('gd', 'ga', 'ud', 'ua', 'ub')
    effect: tuple = ('ua', 'ud')        # log(effect[0] / effect[1]): the fix's effect
    null: tuple = ('ub', 'ud')          # the system's own A/A, same estimator: the matched null
    ref_aa: tuple = ('ga', 'gd')        # the reference's A/A (calibration)
    gap: tuple = ('ud', 'gd')           # the base gap to the reference
    ref_conn: str = 'gd'                # the stratum is read on this connection's blocks
    ref_label: str = 'gnu'              # names output fields: <ref>_ms, <ref>_aa, equal_to_<ref>_all_seeds
    ref_equal_key: str = 'equal_to_gnu'
    arms_equal_key: str = 'uu_arms_equal'
    strata: list = field(default_factory=lambda: list(DEFAULT_STRATA))
    neighbours: dict = field(default_factory=lambda: dict(DEFAULT_NEIGHBOURS))
    alpha_look: dict = field(default_factory=lambda: {1: 0.025, 2: 0.025})
    alpha_controls: float = 0.05
    min_pool: int = 20
    B: int = 200_000
    rng_seed: int = 20261022
    edges: dict = field(default_factory=dict)       # edge id -> [(state, cell, setting), ...]
    verdict_label: str = 'verdict'                  # the edge verdict's field name (cu1: 'verdict_2c')

    def sign_needed(self, k):
        return k - k // 8


def stratum(ns, strata):
    for lo, hi, name in strata:
        if lo <= ns < hi:
            return name


def measures(rec, rule):
    """The per-seed estimators of one cell-setting (per round: the mean of each connection's two blocks; then the median
    over rounds of the log ratio, as in gapgraph.rebuild.paired_measures)."""
    per = {c: [] for c in rule.connections}
    ref_blocks = []
    for rd in rec['timing']['rounds']:
        m = {}
        for b in rd:
            m.setdefault(b['w'], []).append(b['med'])
        for c in per:
            per[c].append(statistics.mean(m[c]))
        ref_blocks += m[rule.ref_conn]
    L = lambda pair: statistics.median(math.log(x / y) for x, y in zip(per[pair[0]], per[pair[1]]))
    a, b = rule.effect
    return {'e': L(rule.effect), 'n': L(rule.null), 'g': L(rule.ref_aa), 'gap': L(rule.gap),
            'ref_ms': statistics.median(ref_blocks) / 1e6, 'base_ms': statistics.median(per[b]) / 1e6,
            'fix_ms': statistics.median(per[a]) / 1e6, 'stratum': stratum(statistics.median(ref_blocks), rule.strata)}


def holm(pvals, alpha):
    order = sorted(pvals, key=lambda k: pvals[k]); m = len(order); rej = {}
    stop = False
    for i, k in enumerate(order):
        if not stop and pvals[k] <= alpha / (m - i):
            rej[k] = True
        else:
            stop = True; rej[k] = False
    return rej


def verdict(runs, capture_cells, rule, look=1):
    """runs: the replication runs (in seed order); capture_cells: the capture's 'cells'. Returns {'summary', 'cells'}."""
    R = rule.ref_label; b_name, a_name = rule.effect[1], rule.effect[0]
    per = {}
    for run in runs:
        for key, rec in run['cells'].items():
            row = per.setdefault(key, {'role': rec['role'], 'ref_eq': [], 'arms_eq': [], 'seeds': []})
            row['ref_eq'].append(rec[rule.ref_equal_key]); row['arms_eq'].append(rec[rule.arms_equal_key])
            if rec[rule.arms_equal_key] and rec['timing']['rounds']:
                row['seeds'].append(measures(rec, rule))
    pool = {}
    for row in per.values():
        for s in row['seeds']:
            pool.setdefault(s['stratum'], []).append(s['n'])
    rng = random.Random(rule.rng_seed)
    sims = {}

    def pool_for(st):
        p = list(pool.get(st, []))
        if len(p) < rule.min_pool:
            for nb in rule.neighbours[st]:
                p += pool.get(nb, [])
        return p

    def null_means(st, k):
        if (st, k) not in sims:
            p = pool_for(st); sims[(st, k)] = sorted(statistics.mean(rng.choice(p) for _ in range(k)) for _ in range(rule.B))
        return sims[(st, k)]

    def p_lower(st, k, x):
        return (bisect.bisect_right(null_means(st, k), x) + 1) / (rule.B + 1)

    def p_upper(st, k, x):
        s = null_means(st, k)
        return (len(s) - bisect.bisect_left(s, x) + 1) / (rule.B + 1)

    out = {}
    for key, row in per.items():
        st, cell, setting = key.split('|')
        ss = row['seeds']; k = len(ss)
        if k == 0:
            out[key] = {'role': row['role'], 'status': 'not measured'}; continue
        strat = statistics.mode(s['stratum'] for s in ss)
        es = [s['e'] for s in ss]; mean_e = statistics.mean(es)
        sim = null_means(strat, k)
        lo_q, hi_q = sim[int(0.025 * rule.B)], sim[int(0.975 * rule.B)]
        ckey = key if key in capture_cells else f'{st}|{cell}|base'
        c = capture_cells.get(ckey)
        D = bool(c and c['off']['marker_in_top'] and not c['on']['marker_in_top'] and c['ir_ratio_on_off'] < 1)
        gap_mean = statistics.mean(s['gap'] for s in ss)
        need = rule.sign_needed(k)
        out[key] = {'role': row['role'], 'stratum': strat, 'k': k, 'effects': [round(x, 4) for x in es], 'mean_effect': round(mean_e, 4),
                    'pct_change_time': round(100 * (math.exp(mean_e) - 1), 2),
                    'null_interval_95': [round(mean_e - hi_q, 4), round(mean_e - lo_q, 4)],
                    'null_n': [round(s['n'], 4) for s in ss], f'{R}_aa': [round(s['g'], 4) for s in ss],
                    'gap_base': round(gap_mean, 4),
                    'share_of_gap': round(-mean_e / gap_mean, 3) if gap_mean > 0 else None,
                    f'{R}_ms': round(statistics.median(s['ref_ms'] for s in ss), 1), f'{b_name}_ms': round(statistics.median(s['base_ms'] for s in ss), 1),
                    f'{a_name}_ms': round(statistics.median(s['fix_ms'] for s in ss), 1),
                    f'equal_to_{R}_all_seeds': all(row['ref_eq']),
                    'D': D, 'D_source': ckey if c else None, 'ir_ratio_on_off': round(c['ir_ratio_on_off'], 4) if c else None,
                    'S': sum(x < 0 for x in es) >= need, 'S_pos': sum(x > 0 for x in es) >= need,
                    'null_pool_size': len(pool_for(strat)),
                    'p_lower': p_lower(strat, k, mean_e), 'p_upper': p_upper(strat, k, mean_e)}
    P = {k: v['p_lower'] for k, v in out.items() if v.get('role') == 'P' and 'p_lower' in v}
    CTRL_lo = {k: v['p_lower'] for k, v in out.items() if v.get('role') == 'control' and 'p_lower' in v}
    CTRL_hi = {k: v['p_upper'] for k, v in out.items() if v.get('role') == 'control' and 'p_upper' in v}
    alpha = rule.alpha_look[look]
    hp, hcl, hch = holm(P, alpha), holm(CTRL_lo, rule.alpha_controls), holm(CTRL_hi, rule.alpha_controls)
    for k, v in out.items():
        if 'p_lower' not in v:
            continue
        if v['role'] == 'P':
            v['M'] = hp[k]; v['SV'] = v['D'] and v['S'] and v['M']
        else:
            v['regression'] = hch[k] and v['S_pos']; v['improvement_on_control'] = hcl[k] and v['S']
    calib = {}
    for k, v in out.items():
        if f'{R}_aa' in v:
            calib[k] = p_lower(v['stratum'], v['k'], statistics.mean(v[f'{R}_aa']))
    hcal = holm(calib, alpha)
    edges = {}
    for e, cells in rule.edges.items():
        keys = ['|'.join(c) for c in cells]
        sv = [out.get(k, {}).get('SV') for k in keys]
        edges[e] = {'cells': keys, 'SV': sv, rule.verdict_label: 'retired' if sv and all(sv) else 'partly' if any(sv) else 'not_removed'}
    summary = {'look': look, 'alpha_P': alpha, 'n_seeds': len(runs), 'P_cell_settings': len(P), 'SV': sum(1 for v in out.values() if v.get('SV')),
               'controls': len(CTRL_hi), 'regressions': [k for k, v in out.items() if v.get('regression')],
               'improvements_on_controls': [k for k, v in out.items() if v.get('improvement_on_control')],
               f'calibration_false_rejections_{R}_aa_raw': sum(1 for p in calib.values() if p <= alpha),
               f'calibration_false_rejections_{R}_aa_holm': sum(hcal.values()), 'calibration_tests': len(calib),
               'null_pool_sizes': {s: len(v) for s, v in pool.items()}, 'edges': edges,
               'runs': [r['meta'] for r in runs]}
    return {'summary': summary, 'cells': out}


DEFAULT_LABELS = {
    'title': '# Sufficiency verdict',
    'rule_sentence': 'SV = D (deterministic mechanism) and S (sign in every seed) and M (mean effect beyond the matched null, Holm). No minimum effect size.',
    'edges_heading': '## Edges',
    'calibration_line': "- leg M applied to the reference's own A/A estimator on all {n} cell-settings: {raw} raw rejections at {alpha}, {holm} after Holm;",
}


def render_md(result, rule, labels=None):
    """The verdict's Markdown (labels: the case's title and wording; cu1's reproduce its recorded file exactly)."""
    lab = dict(DEFAULT_LABELS, **(labels or {})); R = rule.ref_label
    summary, out = result['summary'], result['cells']
    L = [lab['title'], '',
         f"{summary['n_seeds']} replication seeds; {summary['P_cell_settings']} precondition cell-settings; {summary['controls']} controls. "
         + lab['rule_sentence'], '',
         '| cell-setting | role | stratum | effects per seed | mean | time change | 95% null interval | D (Ir on/off) | S | p (one-sided) | M | SV / regression | gap | share |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for k, v in sorted(out.items(), key=lambda kv: (kv[1].get('role', ''), kv[0])):
        if 'effects' not in v:
            L.append(f"| {k} | {v['role']} | not measured | | | | | | | | | | | |"); continue
        tag = ('SV' if v.get('SV') else 'not SV') if v['role'] == 'P' else ('REGRESSION' if v.get('regression') else 'improvement?' if v.get('improvement_on_control') else 'none')
        p = v['p_lower'] if v['role'] == 'P' else min(v['p_lower'], v['p_upper'])
        L.append(f"| {k} | {v['role']} | {v['stratum']} | {v['effects']} | {v['mean_effect']} | {v['pct_change_time']}% | {v['null_interval_95']} | "
                 f"{v['D']} ({v['ir_ratio_on_off']}{'' if v['D_source'] == k else ' from ' + str(v['D_source'])}) | {v['S'] if v['role'] == 'P' else v['S_pos']} | "
                 f"{p:.2g} | {v.get('M', '')} | {tag} | {v['gap_base']} | {v['share_of_gap']} |")
    edges = summary['edges']
    L += ['', lab['edges_heading'], '', '| edge | cells | SV | verdict |', '|---|---|---|---|']
    L += [f"| {e} | {', '.join(d['cells'])} | {d['SV']} | {d[rule.verdict_label]} |" for e, d in edges.items()]
    L += ['', '## Calibration and controls', '',
          lab['calibration_line'].format(n=summary['calibration_tests'], raw=summary[f'calibration_false_rejections_{R}_aa_raw'],
                                         alpha=summary['alpha_P'], holm=summary[f'calibration_false_rejections_{R}_aa_holm']),
          f"- regressions on controls: {summary['regressions'] or 'none'}; verified improvements on controls: {summary['improvements_on_controls'] or 'none'};",
          f"- null pool sizes per stratum: {summary['null_pool_sizes']}."]
    return '\n'.join(L) + '\n'


def combine(look1_cells, look2_cells, rule):
    """The registered two-look combination: SV at look 1 stands; cell-settings with D but not SV at look 1 take their
    look-2 verdict; others keep look 1; controls report a regression or improvement from either look; edges recomputed."""
    final = {}
    for k, v1 in look1_cells.items():
        v2 = look2_cells.get(k, {})
        if v1.get('role') == 'P':
            if v1.get('SV'):
                final[k] = {'role': 'P', 'SV': True, 'decided_at': 'look 1', 'mean_effect': v1['mean_effect'], 'pct': v1['pct_change_time'], 'p': v1['p_lower'], 'k': v1['k']}
            elif v1.get('D'):
                final[k] = {'role': 'P', 'SV': bool(v2.get('SV')), 'decided_at': 'look 2', 'mean_effect': v2.get('mean_effect'), 'pct': v2.get('pct_change_time'),
                            'p': v2.get('p_lower'), 'k': v2.get('k'), 'S': v2.get('S'), 'M': v2.get('M'),
                            'look1': {'mean_effect': v1['mean_effect'], 'p': v1['p_lower'], 'S': v1['S']}}
            else:
                final[k] = {'role': 'P', 'SV': False, 'decided_at': 'look 1 (D false: not eligible for look 2)'}
        else:
            final[k] = {'role': 'control', 'regression': bool(v1.get('regression') or v2.get('regression')),
                        'improvement_on_control': bool(v1.get('improvement_on_control') or v2.get('improvement_on_control')),
                        'mean_effect_look1': v1.get('mean_effect'), 'mean_effect_look2': v2.get('mean_effect')}
    edges = {e: {'cells': ['|'.join(c) for c in cs]} for e, cs in rule.edges.items()}
    for d in edges.values():
        d['SV'] = [final.get(c, {}).get('SV') for c in d['cells']]
        d[rule.verdict_label] = 'retired' if all(d['SV']) else 'partly' if any(d['SV']) else 'not_removed'
    summary = {'SV_total': sum(1 for v in final.values() if v.get('SV')), 'P_total': sum(1 for v in final.values() if v['role'] == 'P'),
               'SV_look1': sum(1 for v in final.values() if v.get('SV') and v['decided_at'] == 'look 1'),
               'SV_look2': sum(1 for v in final.values() if v.get('SV') and v['decided_at'] == 'look 2'),
               'regressions': [k for k, v in final.items() if v.get('regression')],
               'improvements_on_controls': [k for k, v in final.items() if v.get('improvement_on_control')], 'edges': edges}
    return {'summary': summary, 'cells': final}


def render_combined_md(result, rule, title='# Sufficiency: final verdict over both looks'):
    s = result['summary']
    L = [title, '',
         f"SV {s['SV_total']} of {s['P_total']} precondition cell-settings ({s['SV_look1']} at look 1, {s['SV_look2']} at look 2). "
         f"Regressions on controls: {s['regressions'] or 'none'}.", '',
         '| cell-setting | SV | decided at | seeds | mean effect | time change | p (one-sided) |', '|---|---|---|---|---|---|---|']
    for k, v in sorted(result['cells'].items()):
        if v['role'] == 'P':
            p = '' if v.get('p') is None else f"{v['p']:.2g}"
            L.append(f"| {k} | {v['SV']} | {v['decided_at']} | {v.get('k', '')} | {v.get('mean_effect', '')} | {v.get('pct', '')}% | {p} |")
    L += ['', f"| edge | cells | SV | {rule.verdict_label.replace('verdict_', 'verdict under ') if rule.verdict_label != 'verdict' else 'verdict'} |", '|---|---|---|---|']
    L += [f"| {e} | {', '.join(d['cells'])} | {d['SV']} | {d[rule.verdict_label]} |" for e, d in s['edges'].items()]
    return '\n'.join(L) + '\n'


def load_attr(spec):
    """'package.module:NAME' (importable) or 'path/to/file.py:NAME' -> that object (a case adapter's Rule, labels, title)."""
    import importlib, importlib.util
    from pathlib import Path
    mod, _, name = spec.rpartition(':')
    if not mod or not name:
        raise ValueError(f'expected MODULE:NAME or FILE.py:NAME, got {spec!r}')
    if mod.endswith('.py'):
        sp = importlib.util.spec_from_file_location(Path(mod).stem, mod)
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    else:
        m = importlib.import_module(mod)
    return getattr(m, name)


def main(argv=None):
    """python3 -m celltest.sufficiency verdict --rule R --capture CAP.json [--look 1|2] [--labels L] --out PREFIX RUN.json...
       python3 -m celltest.sufficiency combine --rule R [--title T] --out PREFIX LOOK1.json LOOK2.json
    R, L, T: MODULE:NAME or FILE.py:NAME (e.g. adapters/cu1/cu1_adapter.py:RULE). Writes PREFIX.json and PREFIX.md in
    exactly the form the tests check against a case's recorded files."""
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(prog='python3 -m celltest.sufficiency', description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('verdict'); v.add_argument('runs', nargs='+'); v.add_argument('--capture', required=True)
    v.add_argument('--look', type=int, default=1); v.add_argument('--labels')
    c = sub.add_parser('combine'); c.add_argument('looks', nargs=2); c.add_argument('--title')
    for p in (v, c):
        p.add_argument('--rule', required=True); p.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    rule = load_attr(a.rule)
    if a.cmd == 'verdict':
        res = verdict([json.loads(Path(p).read_text()) for p in a.runs], json.loads(Path(a.capture).read_text())['cells'], rule, look=a.look)
        Path(a.out + '.json').write_text(json.dumps(res, indent=1, default=str))
        Path(a.out + '.md').write_text(render_md(res, rule, load_attr(a.labels) if a.labels else None))
        s = res['summary']
        print('SUFFICIENCY_OK', f"{s['SV']} / {s['P_cell_settings']}", 'regressions', s['regressions'],
              'edges', {e: d[rule.verdict_label] for e, d in s['edges'].items()})
    else:
        l1, l2 = (json.loads(Path(p).read_text())['cells'] for p in a.looks)
        comb = combine(l1, l2, rule)
        Path(a.out + '.json').write_text(json.dumps(comb, indent=1))
        Path(a.out + '.md').write_text(render_combined_md(comb, rule, load_attr(a.title)) if a.title else render_combined_md(comb, rule))
        s = comb['summary']
        print('COMBINE_OK', f"{s['SV_total']} / {s['P_total']}", {e: d[rule.verdict_label] for e, d in s['edges'].items()}, 'regressions', s['regressions'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
