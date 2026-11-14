"""Numerical checks behind theory/soundness_review.md. Standard library only; reuses theory/sim_certificates.py.

  A  fairness: sim_certificates.classify_today skips classify()'s config_closes branch (a configuration-reachable plan
     that already closes the gap returns 'configuration'). With that branch, how many false architectural labels remain?
  B  robustness: seed 11 against seed 7, every rate of the three tables in sim_certificates_results.md.
  C  calling context: a frozen operator that mutable code may run on P threads. The certificate's floor uses the
     operator's sequential cost, so it can exceed the least reachable latency although the graph is correct. Compared:
       floor_seq       the draft's floor (sequential cost of the frozen dominators);
       floor_envelope  each frozen dominator at its best admissible calling context (cost / P if parallelizable);
       floor_worklaw   every frozen dominator divided by P (needs no knowledge of which ones parallelize).
python3 theory/review_checks.py [--n 20000] [--seed 7] [--p-par 0.3] [--threads 4]"""
import argparse, math, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_certificates as S  # noqa: E402


def config_closes(ops, plans, t_ref):
    """classify()'s first branch: some configuration-reachable plan, with today's costs, is within the band."""
    return any(math.log(sum(ops[o]['cost'] for o in p['ops'])) - math.log(t_ref) <= S.BAND for p in plans if not p['bypass'])


def check_a(n, seed):
    rows = []
    for g in S.GRID:
        p_miss, q_lab, p_extra, q_unfreeze = g
        rng, erng = random.Random(seed), random.Random(f'{seed}/errors')
        n_fix = false_today = false_fair = 0
        for _ in range(n):
            ops, plans, t_ref = S.instance(rng)
            d = S.error_draws(erng, ops, plans)
            label = [(u >= q_unfreeze) if o['frozen'] else (u < q_lab) for o, u in zip(ops, d['op_u'])]
            if S.truth(ops, plans, t_ref):
                continue
            n_fix += 1
            today = S.classify_today(ops, plans, label)
            false_today += today
            false_fair += today and not config_closes(ops, plans, t_ref)
        rows.append((g, round(false_today / n_fix, 4), round(false_fair / n_fix, 4)))
    return rows


def check_b(n):
    worst = 0.0
    for g in S.GRID:
        r7, r11 = S.run(n, 7, *g), S.run(n, 11, *g)
        for k in S.CLASSIFIERS:
            for m in ('false_arch_rate_among_fixable', 'recall_among_architectural', 'precision'):
                worst = max(worst, abs(r7[k][m] - r11[k][m]))
    return round(worst, 4)


def check_c(n, seed, p_par, threads):
    rng, crng = random.Random(seed), random.Random(f'{seed}/context')
    floors = ('floor_seq', 'floor_envelope', 'floor_worklaw')
    t = {f: {'labels': 0, 'false': 0, 'true': 0} for f in floors}
    n_arch_ctx = flipped = 0
    for _ in range(n):
        ops, plans, t_ref = S.instance(rng)
        par = [o['frozen'] and u < p_par for o, u in zip(ops, [crng.random() for _ in ops])]
        factor = [S.RHO if not o['frozen'] else (1.0 / threads if pa else 1.0) for o, pa in zip(ops, par)]
        reach = min(sum(ops[o]['cost'] * factor[o] for o in p['ops']) for p in plans)
        arch = math.log(reach) - math.log(t_ref) > S.BAND
        n_arch_ctx += arch
        flipped += S.truth(ops, plans, t_ref) and not arch
        dom = [o for o in set.intersection(*(set(p['ops']) for p in plans)) if ops[o]['frozen']]
        vals = {'floor_seq': sum(ops[o]['cost'] for o in dom),
                'floor_envelope': sum(ops[o]['cost'] * factor[o] for o in dom),
                'floor_worklaw': sum(ops[o]['cost'] for o in dom) / threads}
        for f, v in vals.items():
            lab = v > 0 and math.log(v) - math.log(t_ref) > S.BAND
            t[f]['labels'] += lab; t[f]['false'] += lab and not arch; t[f]['true'] += lab and arch
    n_fix = n - n_arch_ctx
    out = {'n': n, 'seed': seed, 'p_par': p_par, 'threads': threads, 'true_architectural': n_arch_ctx, 'fixable': n_fix,
           'architectural_without_context_now_fixable': flipped}
    for f in floors:
        out[f] = {'false_architectural': t[f]['false'], 'false_arch_rate_among_fixable': round(t[f]['false'] / n_fix, 4),
                  'recall_among_architectural': round(t[f]['true'] / n_arch_ctx, 4)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--p-par', type=float, default=0.3)
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    print('A. classify_today, false architectural rate among fixable: as simulated / with the config_closes branch')
    print('| p_miss | q_lab | p_extra | q_unfreeze | as simulated | with config_closes |\n|---|---|---|---|---|---|')
    for g, x, y in check_a(a.n, a.seed):
        print(f'| {" | ".join(str(v) for v in g)} | {x} | {y} |')
    print(f'\nB. largest absolute difference between seeds 7 and 11 over every rate of the three tables: {check_b(a.n)}')
    c = check_c(a.n, a.seed, a.p_par, a.threads)
    print(f"\nC. calling context: each frozen operator parallelizable on {c['threads']} threads with probability {c['p_par']}; "
          f"correct graph; {c['true_architectural']} architectural, {c['fixable']} fixable "
          f"({c['architectural_without_context_now_fixable']} were architectural before parallel calls were admissible)")
    print('| floor | false architectural (rate among fixable) | recall among architectural |\n|---|---|---|')
    for f in ('floor_seq', 'floor_envelope', 'floor_worklaw'):
        print(f"| {f} | {c[f]['false_architectural']} ({c[f]['false_arch_rate_among_fixable']}) | {c[f]['recall_among_architectural']} |")


if __name__ == '__main__':
    main()
