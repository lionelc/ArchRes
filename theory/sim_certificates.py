"""Synthetic check of the classification certificates in theory/classification_theory.md.

Model of one robust gap (a cell in a state):
  - operators o with a cost; each is frozen (the architecture contract) or mutable;
  - plans = sets of operators. Plan 0 is the system's default. Every plan is admissible: reachable by configuration,
    or, for a 'bypass' plan, only through a code change in a mutable layer;
  - latency of a plan = sum of its operators' costs. An admissible code change can make a mutable operator up to
    1/RHO times cheaper; a frozen operator keeps its cost;
  - the reference's latency is set so that the default gap log(T_sys / T_ref) is a robust slower gap.
Ground truth: Delta* = min over admissible plans of log(minimal latency) - log(T_ref); architectural iff Delta* > band.

Classifiers compared (each sees only what its graph contains):
  certificate        Theorem 3: the operators labelled frozen that lie on EVERY known plan (the frozen dominators)
                     give a floor; architectural iff log(floor) - log(T_ref) > band;
  classify_today     workflow/boundary.py classify() with unit-cost evidence: the boundary track locates the default
                     plan's costliest operator (all default operators switch on together in the gap's cells);
                     architectural iff that operator is labelled frozen (a deep layer);
  config_exhaustion  Theorem 4's exhaustion read as a certificate: architectural iff every configuration-reachable
                     plan, as it runs today, stays beyond the band.
Graph errors injected into what the classifiers know. Common random numbers: every grid point sees the same instances
and the same error draws, so a plan missing at p_miss = 0.1 is also missing at 0.3.
  floor-inflating (Theorem 7: only these can produce a false architectural label from the certificate)
    p_miss      each bypass plan is missing from the known plan space with this probability;
    q_lab       each mutable operator is labelled frozen with this probability;
  floor-deflating (Theorem 7: these cost completeness only)
    p_extra     a spurious plan (not admissible) is added to the known plan space with this probability;
    q_unfreeze  each frozen operator is labelled mutable (or left out of the graph) with this probability.
Standard library only; deterministic for a seed: python3 theory/sim_certificates.py [--n 20000] [--seed 7] [--out F]"""
import argparse, json, math, random

RHO = 0.1        # a mutable operator can be made at most 10x cheaper by a code change
BAND = 0.10      # A/A band on the log scale (about 10%)
GRID = [         # (p_miss, q_lab, p_extra, q_unfreeze)
    (0.0, 0.0, 0.0, 0.0),
    (0.1, 0.0, 0.0, 0.0), (0.3, 0.0, 0.0, 0.0), (0.5, 0.0, 0.0, 0.0),
    (0.0, 0.1, 0.0, 0.0), (0.0, 0.3, 0.0, 0.0), (0.3, 0.1, 0.0, 0.0),
    (0.0, 0.0, 0.3, 0.0), (0.0, 0.0, 0.0, 0.3), (0.0, 0.0, 0.5, 0.5),
]
CLASSIFIERS = ('certificate', 'classify_today', 'config_exhaustion')


def instance(rng):
    n_ops = rng.randint(3, 8)
    ops = [{'frozen': rng.random() < 0.5, 'cost': math.exp(rng.uniform(math.log(0.1), math.log(10.0)))} for _ in range(n_ops)]
    plans = [{'ops': sorted(rng.sample(range(n_ops), rng.randint(1, n_ops))), 'bypass': False}]
    for _ in range(rng.randint(0, 3)):
        plans.append({'ops': sorted(rng.sample(range(n_ops), rng.randint(1, n_ops))), 'bypass': rng.random() < 0.5})
    t_default = sum(ops[o]['cost'] for o in plans[0]['ops'])
    t_ref = t_default / math.exp(rng.uniform(2 * BAND, 3.0))      # a robust slower gap
    return ops, plans, t_ref


def error_draws(rng, ops, plans):
    """Every draw is made whatever the error rates, so all grid points share them."""
    n = len(ops)
    return {'plan_u': [rng.random() for _ in plans], 'op_u': [rng.random() for _ in ops],
            'extra_u': rng.random(), 'extra_ops': sorted(rng.sample(range(n), rng.randint(1, n)))}


def min_latency(ops, plan_ops):
    return sum(ops[o]['cost'] * (1.0 if ops[o]['frozen'] else RHO) for o in plan_ops)


def truth(ops, plans, t_ref):
    return min(math.log(min_latency(ops, p['ops'])) for p in plans) - math.log(t_ref) > BAND


def certificate(ops, known_plans, t_ref, label):
    dominators = set.intersection(*(set(p['ops']) for p in known_plans))
    floor = sum(ops[o]['cost'] for o in dominators if label[o])
    return floor > 0 and math.log(floor) - math.log(t_ref) > BAND


def classify_today(ops, plans, label):
    located = max(plans[0]['ops'], key=lambda o: ops[o]['cost'])
    return label[located]


def config_exhaustion(ops, plans, t_ref):
    return all(math.log(sum(ops[o]['cost'] for o in p['ops'])) - math.log(t_ref) > BAND for p in plans if not p['bypass'])


def run(n, seed, p_miss=0.0, q_lab=0.0, p_extra=0.0, q_unfreeze=0.0):
    rng, erng = random.Random(seed), random.Random(f'{seed}/errors')
    tally = {k: {'labels': 0, 'false': 0, 'true': 0} for k in CLASSIFIERS}
    n_arch = 0
    for _ in range(n):
        ops, plans, t_ref = instance(rng)
        d = error_draws(erng, ops, plans)
        arch = truth(ops, plans, t_ref)
        n_arch += arch
        known = [p for p, u in zip(plans, d['plan_u']) if not (p['bypass'] and u < p_miss)]
        if d['extra_u'] < p_extra:
            known.append({'ops': d['extra_ops'], 'bypass': True})
        label = [(u >= q_unfreeze) if o['frozen'] else (u < q_lab) for o, u in zip(ops, d['op_u'])]
        verdicts = {'certificate': certificate(ops, known, t_ref, label),
                    'classify_today': classify_today(ops, plans, label),
                    'config_exhaustion': config_exhaustion(ops, plans, t_ref)}
        for k, v in verdicts.items():
            tally[k]['labels'] += v
            tally[k]['false'] += v and not arch
            tally[k]['true'] += v and arch
    n_fix = n - n_arch
    out = {'n': n, 'seed': seed, 'p_miss': p_miss, 'q_lab': q_lab, 'p_extra': p_extra, 'q_unfreeze': q_unfreeze,
           'true_architectural': n_arch, 'fixable': n_fix}
    for k, t in tally.items():
        out[k] = {'architectural_labels': t['labels'], 'false_architectural': t['false'],
                  'false_arch_rate_among_fixable': round(t['false'] / n_fix, 4) if n_fix else None,
                  'recall_among_architectural': round(t['true'] / n_arch, 4) if n_arch else None,
                  'precision': round(t['true'] / t['labels'], 4) if t['labels'] else None}
    return out


def tables(runs):
    r0 = runs[0]
    lines = [f"n = {r0['n']}, seed = {r0['seed']}: {r0['true_architectural']} truly architectural, {r0['fixable']} fixable "
             f"(the same instances at every grid point).", '',
             'Table 1. The certificate under graph errors', '',
             '| p_miss | q_lab | p_extra | q_unfreeze | false architectural (rate among fixable) | completeness (recall among architectural) | precision |',
             '|---|---|---|---|---|---|---|']
    for r in runs:
        c = r['certificate']
        lines.append(f"| {r['p_miss']} | {r['q_lab']} | {r['p_extra']} | {r['q_unfreeze']} | {c['false_architectural']} "
                     f"({c['false_arch_rate_among_fixable']}) | {c['recall_among_architectural']} | {c['precision']} |")
    lines += ['', 'Table 2. The three classifiers with a correct graph (first grid point)', '',
              '| classifier | architectural labels | false architectural (rate among fixable) | recall among architectural | precision |',
              '|---|---|---|---|---|']
    for k in CLASSIFIERS:
        c = r0[k]
        lines.append(f"| {k} | {c['architectural_labels']} | {c['false_architectural']} ({c['false_arch_rate_among_fixable']}) | "
                     f"{c['recall_among_architectural']} | {c['precision']} |")
    lines += ['', 'Table 3. False architectural rate among fixable gaps, every classifier at every grid point', '',
              '| p_miss | q_lab | p_extra | q_unfreeze | ' + ' | '.join(CLASSIFIERS) + ' |', '|---|---|---|---|' + '---|' * len(CLASSIFIERS)]
    for r in runs:
        lines.append(f"| {r['p_miss']} | {r['q_lab']} | {r['p_extra']} | {r['q_unfreeze']} | "
                     + ' | '.join(str(r[k]['false_arch_rate_among_fixable']) for k in CLASSIFIERS) + ' |')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', default=None, help='write all runs as JSON here')
    a = ap.parse_args()
    runs = [run(a.n, a.seed, *g) for g in GRID]
    print(tables(runs))
    if a.out:
        with open(a.out, 'w') as fh:
            json.dump(runs, fh, indent=1)


if __name__ == '__main__':
    main()
