# Synthetic check of the certificates: results

Reproduce (standard library only, about 5 s): `python3 theory/sim_certificates.py --n 20000 --seed 7 --out theory/sim_certificates_results.json`. The model, classifiers and error types are described in the script's docstring; the theory is `theory/classification_theory.md` (sections 5 and 7). A second seed (`--seed 11`) gives the same pattern: 0 false architectural with a correct graph, completeness 0.69, `classify_today` 0.30 and `config_exhaustion` 0.79 false architectural rate among fixable gaps.

Two numbers in the paper's Sec. III-F come from `theory/review_checks.py`, not from the tables below (reproduce: `python3 theory/review_checks.py --n 20000 --seed 7`, about 5 s). The 19.3% is check A: the frozen-culprit rule with its configuration branch. Table 2's `classify_today` omits that branch, hence its 29.8%. The 7.9% is check C: the sequential floor when mutable code may run frozen operators on 4 threads (probability 0.3 each); the envelope floor gives 0.

n = 20000, seed = 7: 10058 truly architectural, 9942 fixable (the same instances at every grid point).

Table 1. The certificate under graph errors

| p_miss | q_lab | p_extra | q_unfreeze | false architectural (rate among fixable) | completeness (recall among architectural) | precision |
|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 0.0 | 0.0 | 0 (0.0) | 0.6887 | 1.0 |
| 0.1 | 0.0 | 0.0 | 0.0 | 129 (0.013) | 0.6977 | 0.9819 |
| 0.3 | 0.0 | 0.0 | 0.0 | 393 (0.0395) | 0.7149 | 0.9482 |
| 0.5 | 0.0 | 0.0 | 0.0 | 646 (0.065) | 0.7322 | 0.9194 |
| 0.0 | 0.1 | 0.0 | 0.0 | 434 (0.0437) | 0.7056 | 0.9424 |
| 0.0 | 0.3 | 0.0 | 0.0 | 1258 (0.1265) | 0.7384 | 0.8552 |
| 0.3 | 0.1 | 0.0 | 0.0 | 884 (0.0889) | 0.7319 | 0.8928 |
| 0.0 | 0.0 | 0.3 | 0.0 | 0 (0.0) | 0.6086 | 1.0 |
| 0.0 | 0.0 | 0.0 | 0.3 | 0 (0.0) | 0.499 | 1.0 |
| 0.0 | 0.0 | 0.5 | 0.5 | 0 (0.0) | 0.2924 | 1.0 |

Table 2. The three classifiers with a correct graph (first grid point)

| classifier | architectural labels | false architectural (rate among fixable) | recall among architectural | precision |
|---|---|---|---|---|
| certificate | 6927 | 0 (0.0) | 0.6887 | 1.0 |
| classify_today | 9828 | 2963 (0.298) | 0.6825 | 0.6985 |
| config_exhaustion | 17894 | 7836 (0.7882) | 1.0 | 0.5621 |

Table 3. False architectural rate among fixable gaps, every classifier at every grid point

| p_miss | q_lab | p_extra | q_unfreeze | certificate | classify_today | config_exhaustion |
|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.298 | 0.7882 |
| 0.1 | 0.0 | 0.0 | 0.0 | 0.013 | 0.298 | 0.7882 |
| 0.3 | 0.0 | 0.0 | 0.0 | 0.0395 | 0.298 | 0.7882 |
| 0.5 | 0.0 | 0.0 | 0.0 | 0.065 | 0.298 | 0.7882 |
| 0.0 | 0.1 | 0.0 | 0.0 | 0.0437 | 0.3716 | 0.7882 |
| 0.0 | 0.3 | 0.0 | 0.0 | 0.1265 | 0.5106 | 0.7882 |
| 0.3 | 0.1 | 0.0 | 0.0 | 0.0889 | 0.3716 | 0.7882 |
| 0.0 | 0.0 | 0.3 | 0.0 | 0.0 | 0.298 | 0.7882 |
| 0.0 | 0.0 | 0.0 | 0.3 | 0.0 | 0.2083 | 0.7882 |
| 0.0 | 0.0 | 0.5 | 0.5 | 0.0 | 0.1486 | 0.7882 |

Ground-truth composition (`python3 theory/sim_breakdown.py --seed 7`; the paper's Sec. III-F):

| Class | Count |
|---|---|
| fixable, configuration-fixable | 2,106 |
| fixable, needs a code change | 7,836 |
| architectural, mixed (b < Δ* < g) | 7,742 |
| architectural, pure (Δ* = g) | 2,316 |
| architectural and certifiable with a correct graph | 6,927 |
| architectural, not certifiable: residual rests on the 10× limit on mutable speed-ups | 1,723 |
| architectural, not certifiable: frozen costs on every plan, but no common frozen operator | 1,408 |

Mean 5.5 operators per instance (50.1% frozen); 2.5 plans per instance including the default; 50.4% of alternative plans
are bypasses.
