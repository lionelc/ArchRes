# The Architectural Residual: artifact

This is the artifact for the paper "The Architectural Residual: Causal Bounds for Software Performance Gaps". It contains the registered pilot on two reimplementation pairs, the audit of LLM-proposed certificates, and the synthetic check of the certificates.

## Contents

| Folder | What it holds | Paper |
|---|---|---|
| `experiments/pilot/` | The registration (`REGISTRATION.md`), its deviations and addenda (`DEVIATIONS.md`, #1–#13), the scripts, raw logs and results, and the full report (`REPORT.md`) | Secs. V–VI |
| `experiments/agent/` | Prompts, ground truth, the raw outputs of GPT-6.1 Sol, Claude Opus 5.5 and Qwen3-8B, the audit scripts, the replication and the diagnostic (`README.md`) | Sec. VI-C, Table III |
| `experiments/SETUP.md` | How to rebuild the engines and rerun the pilot on another host | — |
| `theory/` | The synthetic check: `sim_certificates.py`, `sim_breakdown.py` and `review_checks.py`, with recorded results; also notes on the theory | Sec. III-F |

## Quick checks (standard library Python, under 10 s each)

From this folder:

```
python3 theory/sim_certificates.py --n 20000 --seed 7 --out /tmp/sim.json   # byte-identical to theory/sim_certificates_results.json
python3 theory/review_checks.py --n 20000 --seed 7                           # the 19.3% and 7.9% of Sec. III-F
python3 theory/sim_breakdown.py --seed 7                                     # ground-truth composition
cd experiments/agent && python3 audit_v2.py outputs outputs_frontier outputs_opus outputs_frontier_rep outputs_opus_rep && python3 replication.py
```

The audit can be rerun from the recorded outputs. Generating new outputs needs your own API keys (see `experiments/agent/README.md`).

## Numbering

`REPORT.md`, `experiments/agent/README.md` and the theory notes were written against a longer draft of the paper. In the submitted paper:

| Long draft | Submitted paper |
|---|---|
| Sec. III-G (synthetic check) | Sec. III-F |
| Theorem 5 (soundness: the five premise errors) | Corollary 1 |
| Table VIII (audit of LLM certificates) | Table III |

`DEVIATIONS.md` is a timestamped log and is left as written.

## Registration order

Each addendum in `DEVIATIONS.md` records when it was logged and whether outputs existed at that time. The ground truth of the planted gap was corrected after the first GPT-6.1 Sol run (#12b); the version as registered is `experiments/agent/ground_truth_v1_as_registered.json`.

## License

Apache 2.0 (`LICENSE`).
