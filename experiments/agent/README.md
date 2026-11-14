# Builder-agent error rates (paper Sec. VI, Table VIII; DEVIATIONS.md #11, #11a–c, #12, #12a–d)

**Question.** How often does a real builder agent make each of the five premise errors that the soundness theorem
(Theorem 5 in the paper) lists?

**Builder.** Qwen3-8B (Q4_K_M GGUF, sha256 d98cdcbd…5785), served locally by llama.cpp (commit 68598133). It runs in
non-thinking mode at temperature 0.7, top-p 0.8 and top-k 20, with seeds 1 and 2.

**Input.** The builder is blinded to every intervention result. `prompts/` holds one prompt per gap, with passive
evidence only:
- timings and start-up cells;
- query plans and callgrind profiles;
- `--debug` markers and system-call summaries;
- data facts, the contract and a list of components.

**Gaps (20).**
- 10 Turso cells;
- 6 uutils native cells;
- 3 uutils WebAssembly cells;
- 1 planted frozen operator.

**Audit.**
- `audit.py` applies the registered rules: ground truth in `ground_truth.json`, hashes in DEVIATIONS #11.
- It also applies two supplementary checks (#11a, #11b). These are reported separately.
- One prompt error was corrected (#11c): the superseded outputs are in `outputs_superseded/`.
- All 51 premises were also reviewed by hand. The review found 4 more premises that attribute mutable work to the
  frozen I/O layer, which is error (iii). All 4 are in outputs that were already flagged.

| Measure | Result |
|---|---|
| outputs, premises | 40, 51 |
| (iii) mutable counted as frozen | 32/51 premises = 0.63 [0.48, 0.76] (36/51 = 0.71 after the hand review) |
| (iv) costlier context (supplementary check) | 9/51 = 0.18 [0.08, 0.31] |
| (ii) overestimated least work (supplementary check) | 2/51 = 0.04 [0.00, 0.14] |
| (i) bypass | 0/51 [0, 0.07] |
| (v) floor above Theorem 1's | 26/40 outputs: all over mutable premises or over WASI sums that the single-thread clause justifies |
| architectural label on a non-architectural gap | 22/34 = 0.65 [0.47, 0.80]; every one has ≥ 1 premise error |
| rejected by the contract check for (iii) | 20/22; by (iii) or the builder's own (C3): 22/22 |
| architectural gaps labelled architectural | 6/6, but only 2/6 with valid premises (the planted ones) |
| native uutils (constraint-only contract) | 0 architectural; 10/12 "fixable" claims without a named witness |

**Reproduce.**
```
llama-server -m Qwen3-8B-Q4_K_M.gguf -c 8192 -t 4 --port 8088 --jinja
python3 ground_truth.py
python3 build_prompts.py
python3 run_builder.py 1 2
python3 audit.py
```
The profiles that the prompts quote come from `/work/agent/profile_cells.sh` (callgrind on seed 1).


## Frontier builders (DEVIATIONS #12, #12a–d, #13, #13a)

**Runs.** Both builders saw the same 20 prompts and are scored by the same registered `audit_v2.py`, against the ground
truth corrected per #12b. Each gap has six samples: two first runs, then four registered replications (#13).
- GPT-6.1 Sol (`gpt-6.1-sol`): OpenAI Responses API, reasoning effort high, no fallbacks. Runner
  `run_builder_openai.py`; outputs in `outputs_frontier/` (s1–2) and `outputs_frontier_rep/` (s3–6).
- Claude Opus 5.5 (`claude-opus-5-5`): Anthropic Messages API, adaptive thinking, effort high. Runner
  `run_builder_anthropic.py`; outputs in `outputs_opus/` (s1–2) and `outputs_opus_rep/` (s3–6). Its first run came after
  the #12b correction.

| Measure (six samples, 120 outputs per builder) | GPT-6.1 Sol | Claude Opus 5.5 | Qwen3-8B, 2 samples, no reasoning |
|---|---|---|---|
| premises stated | 0 | 79 | 51 |
| (iii) mutable counted as frozen | — | 0/79 [0, 0.05] | 0.63 [0.48, 0.76] |
| (iv) costlier context | — | 8/79 [0.05, 0.19] | 0.27 [0.16, 0.42] |
| (ii) overestimated work | — | 11/79 [0.07, 0.24] | 0.04 |
| (i) bypass | — | 3/79 registered, 0 by hand (#13a) | 0 |
| (v) floor above Theorem 1's (outputs) | — | 43/120, no label changes | 0 |
| false architectural labels | 0/108 [0, 0.03] | 6/108 [0.02, 0.12], all planted, error (iv) | 24/36 [0.49, 0.81], all on a premise error |
| WASI cp labelled architectural | 0/12 (declined: C2 not established) | 12/12; valid premises 9/12 registered, 12/12 by hand | 4/4, valid premises 0/4 |
| "fixable" without a witness | 2/102 | 58/102 | 10/34 |
| fixable with a valid named witness | 6/6 (planted: set GAPCR_PLANT_US=0) | 0 | 0 |

**Replication (#13, arm R).** The split is confirmed: all registered criteria hold on samples 3–6.
- WASI cp architectural: Claude 8/8, GPT 0/8.
- Planted gap: Claude architectural 4/4, GPT fixable 4/4.
- "Fixable" on candidate gaps: Claude 37/68, GPT 2/68.

**Diagnostic (#13, arm D; `build_diag_prompts.py`, `prompts_diag/`).** One added sentence states the premise the
original prompt leaves implicit:
- whether the plant's duration is a setting or is frozen;
- whether the 8 GB/s rate is a ceiling or only an achieved rate.

Both builders then gave the expected class in 16/16 outputs, with identical L_Δ wherever they certified. Outputs are
in `outputs_frontier_diag/` and `outputs_opus_diag/`. The two builders differ in how they fill an implicit premise,
not in how they reason about the certificate. `replication.py` writes `replication_summary.json`.

**What the builders found.**
- **GPT-6.1 Sol** found a calling-context error (iv) in our own planted certificate. The contract froze the
  constructor, not its duration setting. The ground truth was corrected (#12b); the registered version is
  `ground_truth_v1_as_registered.json`.
- **Claude Opus 5.5** repeated that error in all six samples, to the digit (L_Δ = 0.532). Against the registered ground
  truth, audit v2 would have accepted 4 of the 6. It certified both WASI `cp` cells in every sample (L_Δ 2.64 and
  1.21, against our 2.63 and 1.33).
- Pilot report §6f and §6g have the details.

**Reproduce.**
```
GAPCR_OPENAI_KEY_FILE=... python3 run_builder_openai.py 1 2
GAPCR_ANTHROPIC_KEY_FILE=... GAPCR_OUT_DIR=outputs_opus python3 run_builder_anthropic.py --model claude-opus-5-5 1 2
GAPCR_OPENAI_KEY_FILE=... GAPCR_OUT_DIR=outputs_frontier_rep python3 run_builder_openai.py --model gpt-6.1-sol 3 4 5 6
GAPCR_ANTHROPIC_KEY_FILE=... GAPCR_OUT_DIR=outputs_opus_rep python3 run_builder_anthropic.py --model claude-opus-5-5 3 4 5 6
python3 build_diag_prompts.py
GAPCR_OPENAI_KEY_FILE=... GAPCR_OUT_DIR=outputs_frontier_diag GAPCR_PROMPTS_DIR=prompts_diag python3 run_builder_openai.py --model gpt-6.1-sol 1 2 3 4
GAPCR_ANTHROPIC_KEY_FILE=... GAPCR_OUT_DIR=outputs_opus_diag GAPCR_PROMPTS_DIR=prompts_diag python3 run_builder_anthropic.py --model claude-opus-5-5 1 2 3 4
python3 audit_v2.py outputs outputs_frontier outputs_opus outputs_frontier_rep outputs_opus_rep
python3 replication.py
```
