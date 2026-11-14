"""Ground-truth composition of the synthetic check (theory/sim_certificates.py), for the paper's description of its setup.

  python3 theory/sim_breakdown.py [--n 20000] [--seed 7]

For every instance (one robust gap), with b = sim_certificates.BAND:
  default gap g          log(T_default) - log(T_ref), drawn uniform on [2b, 3]
  residual Delta*        min over admissible plans of log(frozen costs + RHO * mutable costs) - log(T_ref)
  classes                configuration-fixable: some configuration-reachable plan, at today's costs, is within b
                         code-fixable:          fixable (Delta* <= b), but only through a bypass or cheaper mutable operators
                         mixed architectural:   b < Delta* < g
                         pure architectural:    Delta* = g (no admissible intervention lowers the gap at all)
  certifiable            the frozen operators on every plan (the frozen dominators) alone exceed T_ref by more than b,
                         i.e. what the certificate of Theorem 1 can prove with a correct graph"""
import argparse, math, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim_certificates as S  # noqa: E402


def breakdown(n, seed):
    rng = random.Random(seed)
    c = {'configuration-fixable': 0, 'code-fixable': 0, 'mixed architectural': 0, 'pure architectural': 0,
         'certifiable': 0, 'architectural, not certifiable': 0}
    why = {'mutable floors only': 0, 'frozen costs spread over plans': 0}
    n_ops = n_plans = n_bypass = n_frozen = 0
    for _ in range(n):
        ops, plans, t_ref = S.instance(rng)
        n_ops += len(ops); n_plans += len(plans); n_bypass += sum(p['bypass'] for p in plans); n_frozen += sum(o['frozen'] for o in ops)
        g = math.log(sum(ops[o]['cost'] for o in plans[0]['ops'])) - math.log(t_ref)
        res = min(math.log(S.min_latency(ops, p['ops'])) for p in plans) - math.log(t_ref)
        if res <= S.BAND:
            cfg = any(math.log(sum(ops[o]['cost'] for o in p['ops'])) - math.log(t_ref) <= S.BAND for p in plans if not p['bypass'])
            c['configuration-fixable' if cfg else 'code-fixable'] += 1
            continue
        c['pure architectural' if res >= g - 1e-12 else 'mixed architectural'] += 1
        label = [o['frozen'] for o in ops]
        if S.certificate(ops, plans, t_ref, label):
            c['certifiable'] += 1
        else:
            c['architectural, not certifiable'] += 1
            # would the residual exceed b if only frozen costs counted (mutable operators free)?
            frozen_only = min(sum(ops[o]['cost'] for o in p['ops'] if ops[o]['frozen']) for p in plans)
            if frozen_only > 0 and math.log(frozen_only) - math.log(t_ref) > S.BAND:
                why['frozen costs spread over plans'] += 1
            else:
                why['mutable floors only'] += 1
    return {'n': n, 'seed': seed, 'classes': c, 'architectural, not certifiable, because': why,
            'mean operators': round(n_ops / n, 2), 'mean frozen share': round(n_frozen / n_ops, 3),
            'mean plans (incl. default)': round(n_plans / n, 2), 'bypass share of alternative plans': round(n_bypass / (n_plans - n), 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    r = breakdown(a.n, a.seed)
    for k, v in r.items():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
