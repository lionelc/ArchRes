# gapCR pilot on three reimplementation pairs: results and insights

> **Update of 13 Nov 2026 (paper revision).**
>
> **Scope.** The paper now reports Pairs A and B only. Pair C (rav1d/dav1d) is less deterministic and was dropped from
> the paper; its data stay in this artifact and in the sections below.
>
> **New results in the paper** (summarized in §6b):
> - a natural architectural gap: uutils' `cp` under its WebAssembly contract (DEVIATIONS #10);
> - the profiler-misdirection example on Turso's `distinct`;
> - the final classes of all Turso and uutils gaps.

**Status.** This is a pilot on one shared 4-vCPU VM (Xeon 2.1 GHz, AVX-512; no CPU isolation). It exercises every instrument and
every research question of Sec. V at small scale, without new repairs. The registration (`REGISTRATION.md`) was frozen at
09:10:04Z on 11 Nov 2026 (sha256 in `registration.json`). The registered timing ran from 09:21Z to 10:43Z that day.
Ten deviations and addenda are logged in `DEVIATIONS.md`; each was logged before the data it concerns, except #7, which
is labelled post hoc. #8 and #9 were added on 12 Nov and #10 on 13 Nov, for the classification examples in §6a and §6b.
Every number below comes from `results/summary.json` (made by `analyze.py`) or `results/tables.md` (made by
`report.py`).

**Notation.**
- g = median over rounds of log(mean Y block / mean R block). Here g > 0 means the reimplementation Y is slower, and a
  ratio is e^g.
- b = the registered band: the p95 of single-block A/A |log ratios| per latency stratum.
- b_m = the matched null: the p95 of |g| between two identical arms.
- "Robust" means |g| > b with the same sign in every seed.

| Pair | Y (system) | R (reference) | Y0 (earlier version, time split) |
|---|---|---|---|
| A | Turso 0.8.3 CLI | SQLite 3.50.4 CLI | Turso 0.5.0 |
| B | uutils coreutils 0.12.0 | GNU coreutils 9.12 | uutils 0.2.0 |
| C | rav1d HEAD 2e7216c2 | dav1d (same checkout) | rav1d v1.1.0 against dav1d 1.5.1 (= R0) |

---

## 0. Main findings

1. **The correlational gap graph went wrong in all five ways Sec. IV predicts, on real gaps, in one study.**
   - Shared assembly with no excess masks a 1.5–1.9× Rust-versus-C gap (masking).
   - Profile shares over-predict a fix's effect by about 10×, with the sign depending on the input (location is not effect).
   - The signature contrast for hardware acceleration changes threefold between system versions, while the
     counterfactual effect does not (confounding across cells).
   - The SIMD "fix" of uutils base64 does not reveal the cause of the gap (a fix is not a cause).
   - A plan effect changes sign with the statistics state, and its size depends on the order in which mechanisms are
     switched (state dependence and interaction).
2. **Enberg's planner claim (A1).**
   - *Correlational test:* refuted, and in the opposite direction. Cells whose plans differ have *smaller* gaps
     (contrast −0.39).
   - *Counterfactual test:* the plan part is about 0 in one plan-different cell (`in_subquery`), but 74% of the gap in a
     cell whose EXPLAIN QUERY PLAN is *identical* (`distinct`). There, SQLite's skip-ahead DISTINCT, once knocked out,
     accounts for a factor of 13.
   - *Overall:* passive plan identity misclassifies cells in both directions.
3. **rav1d.** The default-configuration gap (+2% to +16%) is below this host's registered resolution. With assembly disabled,
   the gap is robust: 1.5–1.9× in all segments and thread counts (C8 confirmed). The anchors confirm that the shared
   assembly is identical work: 125/126, 337/338 and 319/320 common symbols are equal, and in total rav1d executes
   98.5–99.7% of dav1d's assembly instructions. This dav1d build reaches the entropy-decoder (msac) assembly through
   small C wrappers, which callgrind books under the wrapper names. So the default gap hides a large gap in the fallback
   code.
4. **An x86-inert commit is a natural negative control.** PR #1397 changes 0 instructions in all three segments. Yet its
   time effect is −1.0%, −1.3% and −1.6%: the same sign every time, and as large as the 0.7% and 1.6% effects claimed for
   the two PRs. Code-change claims at the 1% level need a rebuild (layout) null, not only an A/A null.
5. **uutils.**
   - cksum's 16× gap (B3 confirmed) is about half GNU's hardware acceleration. The knock-out removes 1.41 of 2.79 log
     units; B4 for cksum is confirmed, just at the registered 50% threshold.
   - base64's gap has nothing to do with GNU's SIMD, since GNU base64 has no hardware path (B4 refuted for base64).
     uutils 0.2.0 even executes 27% *fewer* user-space instructions than GNU. Instead, it holds the whole input in memory:
     23× GNU's resident set and 94× its page faults.
6. **Gaps and witnesses.**
   - Most remaining Turso and uutils gaps in short cells are partly or wholly process-startup gaps: Turso CLI +4.5 ms and
     uutils multicall +1.2 ms per process. For wc -l, cat, sha256sum and cksum, startup accounts for 64–100% of the
     absolute difference.
   - Natural witnesses decide 19% of Turso 0.5.0's robust gap mass as fixable (11% with b_m), none of uutils 0.2.0's, and
     nothing for rav1d.
7. **Instruments.**
   - Zero robust pseudo-gaps (A/A) in 49 logical cells.
   - The layout spread (≤ 0.06; 0.15 for base64) removes no robust gap.
   - Null plants and shams: 0 false detections out of 16.
   - 15% plants: 100% detected in B and C, but only 1 of 2 in A, where that session drifted (its A/A arm exceeded b_m).
8. **Classes (§6a).** No natural gap in the three pairs can be certified architectural under their contracts.
   - *rav1d:* the frozen assembly is shared, about half of dav1d's own work.
   - *uutils:* its contract freezes only constraints on code (pure Rust, one binary), not costly operators.
   - *Turso:* the frozen I/O layer's work per page is far too small in warm cells; a certificate would need at least
     27–29 µs per page, against at most 8.9 µs.

   A *planted* architectural gap on real binaries (a frozen 84 ms constructor in uutils, against GNU's sort at
   ≤ 49.5 ms) is certified (L_Δ = 0.53 > b). The same data under the main contract are fixable, and a mislabelled
   frozen operator is caught by the witness. The certificate abstains on a planted architectural gap with too little
   margin (L_Δ = 0.22 < b): it loses recall, never soundness.

---

## 1. What ran

| Experiment | Cells × seeds | Arms | Purpose |
|---|---|---|---|
| captures | C: 8 builds, 60 frames, plus held-out segments (#6); B: 6 utilities × 3 engines, 4 MiB; A: 3 queries × 3 engines | callgrind | deterministic counterparts, anchors, profiles |
| plans | 12 queries × 2 states × 2 seeds × 3 engines | EXPLAIN QUERY PLAN | plan identity |
| C_SURVEY | 3 segments × threads {1, 4} × masks {default, avx2, none} | Yd, Ya, Rd, Ra | gaps, bands, C8, C-cg1 |
| C_TIMESPLIT | 3 segments × threads {1, 4} | Y0d, Y0a, R0d, Y1d | C1, C7, RQ4 |
| C_SWAPS | 3 segments, threads 1 | P1400p, P1400, P1397p, P1397 (8 rounds) | C5, C6, C-cg2, C-cg3 |
| B_SURVEY | 20 utilities × 2 seeds (LC_ALL=C) + 3 × 2 (UTF-8) | Yd, Ya, Rd, Ra | gaps |
| B_TIMESPLIT | 11 utilities × 2 seeds | Y0d, Y0a, Rd, Yd | B1–B3, RQ4 |
| B_KO | 7 utilities × 2 seeds | Y0d, Yd, Rd, Rk (GNU without hardware acceleration) | B4, B-cg1, B-cg2 |
| A_SURVEY | 14 queries × 2 seeds (S1) + 6 queries (S0) | Yd, Ya, Rd, Ra | gaps, A1, A2 |
| A_TIMESPLIT | 14 queries, held-out seed | Y0d, Y0a, Rd, Yd | A3, RQ4 |
| A_KO | `in_subquery`, `join3_star`, `join2` × 2 seeds | plan-equalized arms (#4) | A1 follow-up, A-cg1, A-cg2 |
| A_KO2 (#7, exploratory) | `distinct` × 2 seeds | Turso, Turso A/A, SQLite, SQLite without DistinctOpt | operator-level plan part |
| *_PLANTS | B: 4, C: 2, A: 2 cells (held-out seeds) | plants of 2%, 5% and 15%, null plant, sham | RQ2 |
| B_ARCH, B_ENV (#8, 12 Nov) | `cksum`, `sort`, seed 2; GNU `true` | GNU ×2, uutils ×2, uutils with F = 2 T̂_R and 0.5 T̂_R; F called directly | planted classes under a contract variant (§6a) |
| A_RO (#9, 12 Nov) | `startup`, `point_index` × 2 seeds | Turso, Turso `--readonly`, SQLite ×2 | configuration witness for the startup gap (§6a) |
| natural_floors (deterministic) | A: page counts; B: loader work; C: shared asm share | — | where a certificate could exist (§6a) |
| *_LAYOUT | 3 cells per pair | environment padding of 0–3 KiB | RQ1 |

The outputs of every arm agreed before timing in every cell (sha256 of stdout and exit status). The C frames are
bit-identical across engines and masks.

**Deviations**:
1. R0 is upstream dav1d 1.5.1, because the C code in rav1d v1.1.0 does not build.
2. Scale cuts: 2+1 runs per short block, 32 MiB Pair B inputs, a held-out-only time split for A, 8 swap rounds for C.
3. Four-arm surveys.
4. Plan-equalization follow-up for A1.
5. The correlational baseline.
6. Exploratory deterministic checks: profiles of the held-out segments, the base64 mechanism, and the B5 markers.
7. Post hoc: operator-level plans and the DistinctOpt knock-out.
8. Planted classes under a contract variant that freezes a planted operator (12 Nov).
9. `--readonly` as a configuration witness for Turso's startup gap (12 Nov).

---

## 2. RQ1: can gaps be measured reliably? (funnel)

| Pair | Logical cells | b (by stratum) | b_m | Robust gaps | Robust pseudo-gaps | Layout spread (max) | Robust after layout | Instruction sign agrees |
|---|---|---|---|---|---|---|---|---|
| A | 20 | <0.1 s: 0.321; 0.1–1 s: 0.165 | 0.070 | 14 | 0 | 0.062 | 14 | 2/3 |
| B | 23 | <0.1 s: 0.236; 0.1–1 s: 0.177 | 0.073 | 15 | 0 | 0.151 | 15 | 5/6 |
| C | 6 | 0.1–1 s: 0.162; >1 s: 0.151 | 0.054 | 2 (no-asm only) | 0 | 0.055 | 2 | 2/2 |

The alternative estimator (ratio of medians over all blocks) agrees in sign with g in every cell.

**Insights.**

- **Resolution is set by the band, not by a single comparison's noise.** The registered band is 3–5× the matched null.
  - With b, the rav1d default gap (+0.04 to +0.15) and the 5% claim C1 cannot be resolved on this host.
  - With b_m, C1's held-out estimates (0.063, 0.089) exceed the null.
  - Sec. V should report both, and treat b as the closure tolerance for classes (Sec. 6 below).
- **Natural negative control.** The x86 build of PR #1397 differs in 466,862 bytes but executes 25, 391 and 457 fewer
  instructions out of 0.17–5.1 billion: zero work.
  - Its time effect is −0.010, −0.013 and −0.016 in all three segments. That is below b_m, but the sign is the same each
    time, and the size equals the claimed effects of both PRs (0.7%, 1.6%).
  - A layout or rebuild null (here, padding spread up to 0.055 on C) is the right null for code-change claims.
- **Deterministic counterparts disagree in two cells, and both disagreements are informative.**
  - uutils `sort` executes 33% *more* instructions but is 1.6× *faster*: it sorts in parallel, so wall time is not work.
  - Turso `join2` executes 11% fewer instructions but is 15–23% slower. This is not explained here: memory behaviour is
    a candidate.
- **Valgrind caveat.** Valgrind lacks AVX-512, so the C captures follow the AVX2 path while timing follows AVX-512. The
  anchor check holds on the captured path only.
- **Process startup is a gap mechanism of its own, and it confounds short cells.** Under an additive model (arithmetic,
  not a counterfactual), the startup difference is the following share of the absolute time difference:

  | Pair | Cell | Startup share |
  |---|---|---|
  | B | `cat` | 99% |
  | B | `wc -l` | 100% |
  | B | `sha256sum` | 71% |
  | B | `cksum` | 64% |
  | A | `point_index` | 52% |
  | A | `point_rowid` | 22% |
  | A | `scan_agg` | 15% |
  | A | `distinct` | 4% |

  The startup times are Turso 6.9–7.1 ms against SQLite 2.5–2.7 ms, and uutils 2.1 ms against GNU 0.9 ms. Startup-adjusted
  gaps for B: `wc -l` −0.03 to +0.03, `cksum` +0.19, `sha256sum` +0.01 to +0.02. The main study needs
  larger inputs or in-process timing, and a startup cell as a design factor.

---

## 3. RQ2: known-truth plants (held-out seeds)

| Pair | 2% plant | 5% plant | 15% plant | Null plant | Sham | A/A arm |
|---|---|---|---|---|---|---|
| C (2 cells) | 0/2 (+0.007, +0.035) | 2/2 (+0.069, +0.059) | 2/2 (+0.161, +0.142) | 0/2 | 0/2 | 0/2 |
| B (4 cells) | 1/4 (noise: `cut` +0.10) | 0/4 | 4/4 (+0.08 to +0.14) | 0/4 | 0/4 | 0/4 |
| A (2 cells) | 0/2 | 0/2 | 1/2 (+0.051, +0.091) | 0/2 | 0/2 | **1/2 (+0.087)** |

Expected log effects are +0.020, +0.049 and +0.140. "Detected" means e > b_m.

- **Sensitivity.** The detection limit is about b_m (5–7%). A 15% plant is recovered accurately on C (+0.16, +0.14).
- **Specificity.** 0 false detections out of 16 null plants and shams.
- **Pair A's plant session drifted.** Its own A/A arm read +0.087 on `scan_agg`, and the 15% plants were attenuated.
  Per Sec. IV, Pair A's confirmation rates in this session should be corrected, or the session rerun. This is exactly why
  plants are run *inside* the study rather than once.
- **Class of these plants.** Every plant here is removable, so every planted gap is fixable by construction; none is
  architectural. Planted architectural gaps need a contract variant that freezes the plant (§6a (iii)).

---

## 4. Registered claims

| Claim | Prediction | Measured (held-out unless noted) | Verdict |
|---|---|---|---|
| **C1** rav1d ≈ 5% slower (Prossimo) | V0 gap robust, in [0.03, 0.07] | g(Y0, R0) = 0.063, 0.089, against b = 0.162 and 0.151 (discovery segment 0.041); instructions +13% (log 0.126, discovery segment) | **inconclusive** (not robust at this host's resolution; above b_m) |
| **C2** Rust ≈ half of run time | Rust share of instructions in [0.40, 0.60] | 0.44 (discovery); held-out 0.60, 0.63 (#6) | **confirmed** (registered); content-dependent |
| **C3** overhead spread evenly | no function > 20% of the excess | memset 31% (discovery); held-out: `create_lf_mask_inter` 26%, `cdef_brow` 17%; top 5 = 83%, 70%, 66% | **refuted** (2 of 3 segments); the top function differs in every segment |
| **C4** bounds checks < 1% | — | needs a modified rustc | untestable without repair |
| **C5** PR #1397 (Arm only) | x86: no instruction change, \|e\| ≤ b_m | Δinstructions = 0 in all segments; e = −0.013, −0.016 | **confirmed** (scope) |
| **C6** PR #1400 saves 0.7% | x86: e < 0 and fewer instructions | instructions +0.15% (discovery, registered capture); held-out −0.12%, −0.19% (#6); e = +0.027, −0.009 | **refuted** on the registered capture; the sign depends on content; time null-consistent |
| **C7** fixable by Rust-only changes (time split) | e(Y1 vs Y0) < 0 | e = +0.051, −0.021; instructions +0.9% | **null-consistent** (no measurable x86 progress from v1.1.0 to HEAD) |
| **C8** (post hoc, registered before held-out) asm masks the gap | g(none) − g(default) > b | +0.437, +0.304 | **confirmed** |
| **B1** uutils base64 ≈ 8× slower | Y0 ratio ≥ 4 | 1.37× (g = 0.318, robust) | **refuted at 32 MiB** (the claim says "large files"; transport by size untested) |
| **B2** base64 fixed, faster than GNU | Y1 g ≤ 0 | g = −0.718 (2.05× faster) | **confirmed** |
| **B3** cksum up to 17× slower | Y0 ratio ≥ 4 | **16.0×** (g = 2.776); Y1 still +0.264 | **confirmed**; Y1 not within b in seed 2 |
| **B4** gaps closed by adopting SIMD (causal reading) | cksum: knock-out removes ≥ ½ of the Y0 gap; base64: no hardware path | cksum: g(Y0, R) = 2.792 → g(Y0, R_KO) = 1.385 (removes 50.4%); base64: knock-out effect −0.035 | **cksum confirmed** (at the threshold); **base64 refuted** |
| **B5** the KO switches markers | markers off under KO | GNU: `cksum` and `wc -l` switched; uutils: `cksum` switched (uutils `wc` uses other wording, also switched by inspection) | **confirmed** |
| **A1** gaps almost entirely due to the planner (Enberg) | ≤ 20% of the slower gap mass in plan-identical cells | **90%** (access-path identity, registered); 43% at operator level (#7); 64% for Turso 0.5.0 | **refuted** on this workload (the claim was made on TPC-H) |
| **A2** Turso 4–6× slower on scans, 1.5–2× on points and joins (0.7.1) | 0.8.3: scan ≥ 2×; point, join ≥ 1.3× | `scan_agg` 1.28×, `point_rowid` 2.37×, `join2` 1.15–1.23× | **partly** (only point meets it) |
| **A3** 0.8 "performance release" shrinks gaps | most robust Y0 gaps shrink | 11 of 14 shrank beyond b_m | **confirmed** |

---

## 5. RQ3: correlation versus causation (the main result)

**Design.** The correlational gap graph (CG; `DEVIATIONS.md` #5) uses only passive data:
- default-run timings, profiles, plans and markers;
- three estimators: *profile share*, *signature contrast*, and the fix as cause.

The counterfactual graph uses replayed interventions on the same cells: masks, knock-outs, plan equalization, commit
swaps and crossed states.

| # | Question | Correlational answer | Counterfactual answer | Divergence (Sec. IV) | CG error |
|---|---|---|---|---|---|
| C-cg1 | Does the shared assembly affect the rav1d gap? | No. Asm symbols carry 0 excess (anchors equal); predicted change 0 | Turning asm off raises g by **+0.44, +0.30**. The no-asm gap is 1.5–1.9× (robust, all segments and threads) | masking (positivity) | error 0.30–0.44, larger than the gap itself; wrong transport conclusion for asm-less targets |
| C-cg2 | What does PR #1400 (Mv `PartialEq`) gain? | Profile share of the motion-vector functions: 7.7–9.4% of the excess. Predicted −0.009, −0.016, −0.016 (log instructions) | Measured **+0.0015, −0.0012, −0.0019**; time +0.027, −0.009 (null) | location is not effect | about 10× over-prediction; sign wrong on 1 of 3 segments |
| C-cg3 | PR #1397 on x86 | `cdef` share 9–17%; predicted −0.017 to −0.020 | **0 instructions**; time −0.010 to −0.016 (layout) | scope (negative control) | a reader aware of the scope would not predict a gain; shown for the layout lesson |
| B-cg1 | How much does GNU's hardware acceleration add to the gap in the cells where it is active? | Signature contrast **+1.42 (Y0)**, **+0.42 (Y1)** | Knock-out: **+1.33** for both versions (it is a property of R: log R_KO/R) | confounding across cells | Y0: error 0.09 (by luck); Y1: error 0.91 (3× under) |
| B-cg2 | Was the Y0 base64 gap caused by GNU's SIMD (the fix's mechanism)? | Yes: "fixed by adopting SIMD" | GNU knock-out effect **−0.035 / +0.009** (no hardware path). Y0 executes 27% fewer instructions than GNU, has RSS 39.8 MB vs 1.7 MB, and 8,534 vs 91 page faults. The Y1 fix overshoots (2× faster than GNU) | a fix is not a cause | wrong mechanism (and wrong target if R's speed were to be matched) |
| B-cg2′ | cksum: same reading | Yes | The knock-out removes 50.4% of the Y0 gap. The rest (4.0×) is not hardware | a fix is not a cause (partly) | half the gap misattributed |
| A-cg1 | How much of the Turso gap is due to plans? | Contrast (plan-different minus plan-identical) **−0.39**: plans are associated with *smaller* gaps | Plan parts: `in_subquery` **−0.03, +0.08** of 0.43–0.45 (all execution); `join3_star` (Turso 0.5.0) **0.80, 0.77** of 1.94, 1.91 (41%); `join2` (S1) Shapley **0.09, 0.02** of 0.18, 0.13; `distinct` (EQP-identical!) **2.62, 2.54** of 3.44, 3.57 (74%) | confounding plus masking (EQP hides operators) | wrong sign; misclassifies cells in both directions |
| A-cg2 | Does the statistics state matter? | Pooled `join2` gap ≈ 0.09 | S1 +0.13 to +0.18; S0 0.00 to +0.07; `join3_star` S1 +0.60, +0.74 against S0 **−0.50** (the sign flips) | state dependence | pooling hides a sign flip |
| A-cg2′ | `join2`: plan or execution? | — | The execution gap is **+0.25** under Turso's plan and **−0.04 to −0.07** under SQLite's plan. The plan part is −0.07 or +0.25 depending on which engine's plan is held fixed | interaction | a single "plan share" is undefined without an order; Shapley needed |

**What the comparison shows.**

1. **Masking (positivity) is not hypothetical.**
   - *rav1d:* default runs never execute the fallback kernels, so no profile of them can say that rav1d's fallback is
     1.5–1.9× slower than dav1d's. A whole layer of the gap graph is invisible until the mask is switched.
   - *SQLite:* EXPLAIN QUERY PLAN never shows the skip-ahead DISTINCT. Bytecode shows it (`SeekGT` against Turso's
     `HashDistinct`), and only a knock-out sizes it.
2. **Location is not effect, even deterministically.**
   - The profile share of the motion-vector code is stable (8–9%). The effect of an actual change to that code is about
     10× smaller, and its sign depends on the segment.
   - The profile ranking itself is content-dependent: the top function is memset, `create_lf_mask_inter` or `cdef_brow`,
     depending on the segment.
3. **A signature contrast measures what the *system* does in the signature cells, not what the mechanism does.**
   - The effect of GNU's acceleration on the gap is log(R_KO/R), the same for every uutils version (+1.33).
   - The contrast fell from 1.42 to 0.42 because uutils 0.12 adopted SIMD in exactly those cells, and its residual gap
     there is largely startup (64% of cksum's absolute difference and all of `wc -l`'s).
   - Conversely, the marker misses an active mechanism. GNU `sha256sum` loses 1.35–1.43 log units under the knock-out
     (OpenSSL SHA-NI), but has no `--debug` marker.
4. **A fix is not a cause.**
   - The base64 fix and the base64 gap involve different mechanisms. GNU has no SIMD path; uutils 0.2.0 does less
     computation but buffers the whole file.
   - For cksum, SIMD is half the story.
5. **State dependence and interaction are the norm.** Sign flips by statistics state (`join3_star`), by locale (`wc -m`:
   +1.34 to +1.48 in C, −2.75 to −2.88 in UTF-8) and by assembly mask (rav1d). A plan part that depends on the switching
   order (`join2`) is why Sec. IV's 2^k design and Shapley attribution are needed.

**Tally.** Excluding the negative control C-cg3, the comparisons pose six questions; B-cg1 is asked for two versions.
- **Right (1 case):** the correlational answer is quantitatively right only for B-cg1 on Y0, within 0.09. That is because
  Y0 had no hardware path in the signature cells.
- **Partly right (1 case):** B-cg2′, cksum. SIMD is a cause, but it explains half the gap.
- **Wrong mechanism, size, target or state (6 cases):**
  - C-cg1: no effect predicted, +0.30 to +0.44 measured.
  - C-cg2: 8–13× over-predicted, with the sign wrong in 1 of 3 segments.
  - B-cg1 on Y1: 3× under-estimated.
  - B-cg2 for base64: wrong mechanism.
  - A-cg1: wrong sign; cells misclassified in both directions.
  - A-cg2: pooling hides a sign flip.

**Caveat on the comparison.** The CG estimators are the ones practitioners use, applied to the same cells; they are not
straw men. C-cg3 is shown as a negative control, not counted as a CG failure. The base64 *mechanism* (memory) is supported
by deterministic counts only. The counterfactual result is the null knock-out on GNU, which rules out GNU's SIMD; the
memory explanation would itself need an intervention.

---

## 6. RQ4: witnesses and classes (natural witnesses only, no certificates)

Corollary 1 is applied with L_Δ = −∞: a robust Y0 gap is **fixable (witnessed)** if U = g(Y1, R) ≤ b in every seed;
otherwise it remains a **candidate**.

| Pair | Robust Y0 gaps | Decided as fixable | Share of Y0 gap mass decided | With b_m as tolerance |
|---|---|---|---|---|
| A (Turso 0.5.0 → 0.8.3) | 14 | `count_star` (U = −0.85), `group_by` (−0.09), `join2` (0.14), `range_index` (0.31 ≤ 0.32) | **18.8%** | 11.0% |
| B (uutils 0.2.0 → 0.12.0) | 3 (`cksum`, `wc -l`, `cat`) | none (`cksum` U = 0.235, 0.264 against b = 0.236) | **0%** | 0% |
| C (rav1d v1.1.0 → HEAD) | 0 (default gap not robust) | — | — | — |

**Insights.**
- Natural witnesses decide only a minority, and they can decide only "fixable". Every other robust gap stays a candidate
  until a certificate (a lower bound) or a repair exists. This is the gap between upper and lower bounds that Sec. III
  formalizes.
- The class depends on the closure tolerance (18.8% against 11.0%). The paper should state b as a declared tolerance,
  separate from detection noise.
- **Contract admissibility matters.** For C, the bounty contract (assembly frozen; Rust, rustc and std changes allowed)
  makes HEAD an admissible witness: no asm changed, and the anchors are equal against R0 (132/132). For B, uutils 0.12.0
  links only libc (pure Rust), so it is admissible under a pure-Rust contract.
- uutils 0.12.0's cksum reports avx512, avx2 and pclmul hardware support itself (`--debug`). About half of its residual
  log gap (+0.24 to +0.28 in the time split, +0.36 to +0.38 in the survey) is startup: +0.19 remains after adjustment. A
  witness that removes the startup cost could decide it.

---

## 6a. Gap classes: synthetic check, planted controls, and the three real pairs

**The classes.** All three settings use the same classes. Each one is a decision about repair effort.

| Class | Evidence | Repair decision |
|---|---|---|
| configuration-fixable | a setting closes the gap (a witness in I_cfg) | change the setting |
| fixable | an admissible change closes it (a witness) | a repair exists, and the witness shows which |
| architectural | a certificate: L_Δ = log L − log T̄_R > b (Theorem 1) | no repair toward parity is attempted |
| mixed | architectural, and some witness lowers the gap (U < g) | repair the part above the floor only |
| candidate | neither bound decides | stays in the repair queue; nothing is claimed |

"Architectural" is never established by failed repairs, which is why the evaluation needs no repairs.

### (i) The synthetic check (paper Sec. III-G; `theory/sim_certificates.py`, `theory/sim_breakdown.py`)

**These are not programs.** Each of the 20,000 instances is a cost model of one robust gap:
- 3–8 operators, each frozen with probability ½, with log-uniform costs in [0.1, 10];
- a default plan and 0–3 alternative plans (operator subsets), each reachable by configuration or, with probability ½,
  only by a code change (a bypass);
- a code change can make a mutable operator at most 10× cheaper;
- T_R is set so that the default gap is uniform in [0.2, 3] log units, with b = 0.1.

The admissible interventions are finite, so Δ* is computed exactly. That is the only reason synthetic gaps are needed:
on real systems Δ* is unknowable.

**The synthetic set contains architectural gaps, about half.** Ground truth at seed 7:

| Class | Count |
|---|---|
| fixable: configuration-fixable | 2,106 |
| fixable: needs a code change | 7,836 |
| architectural: mixed | 7,742 |
| architectural: pure (no admissible intervention lowers the gap) | 2,316 |
| **total** | 9,942 fixable, 10,058 architectural |

**The classifiers.** Each answers "architectural or not"; the certificate may abstain, leaving a candidate.
- **Certificate (Theorem 1).** False architectural rate among fixable gaps 0.000; recall 0.69. It misses 3,131
  architectural gaps:
  - 1,723 whose residual rests on the 10× limit on mutable speed-ups, which no real contract states;
  - 1,408 whose plans each pay frozen cost but share no frozen operator.
- **The earlier gapCR rule (frozen culprit).** False rate 0.193.
- **Exhaustion over configuration plans.** False rate 0.788, exactly the 7,836 gaps that need a code change.

### (ii) The pilot's registered plants are fixable by construction

A removable plant is closed by switching it off, which is admissible under every contract. So the registered plants (RQ2)
contain **no architectural gap**. They measure edge confirmation (Se and Sp) and the soundness of fixable labels, never
recall.

### (iii) Planted classes under a contract variant (DEVIATIONS #8, 12 Nov)

**Setup.**
- **Contract variant V_F.** The preloaded constructor F is frozen and runs once per invocation of uutils.
- **Envelope (C2).** F is called directly in GNU `true` (B_ENV). Its loop exits only after w µs of wall time, so its least
  work is w by construction; the measurement confirms it.
- **Certificate.** D = {F} and p_F = 1, so L = w. T̄_R is the largest per-round GNU block mean in the same cell.

| Cell | Arm | Planted w | w measured | T̄_R | g | L_Δ | U (switch-off witness) | Label under V_F (truth) | Label under main contract (truth) |
|---|---|---|---|---|---|---|---|---|---|
| sort | P2 | 84.28 ms | 84.36 ms | 49.55 ms | +0.950 | **+0.531** | −0.424 | **architectural** (architectural ✓) | **fixable** (fixable ✓) |
| sort | P05 | 21.07 ms | 20.92 ms | 49.55 ms | +0.138 | −0.863 | −0.424 | no robust slower gap (unknown) | no robust slower gap (fixable) |
| cksum | P2 | 8.64 ms | 8.46 ms | 6.79 ms | +1.083 | +0.220 | +0.318 | candidate (**architectural**: recall miss) | candidate (unknown) |
| cksum | P05 | 2.16 ms | 1.88 ms | 6.79 ms | +0.553 | −1.284 | +0.318 | candidate (unknown) | candidate (unknown) |

b = 0.236 (registered band for Pair B, < 0.1 s).

**Reading.**
- **Identification.** The architectural gap on `sort` is certified with every premise checkable:
  - (C1) the contract clause plus the constructor attribute in `plant.c`;
  - (C2) the source guarantee plus the direct measurement;
  - (C3) arithmetic.

  The label means that no admissible change can bring uutils within the band, so no repair toward parity is attempted.
  The 0.42 by which g exceeds the floor is not covered by the certificate and remains a target.
- **Contract relativity.** The same measurements under the main contract, where F is removable, give "fixable": the
  switch-off arm is a witness with U = −0.42.
- **A mislabel is caught.** If an agent labels the removable F as frozen, which is Theorem 3's error (iii), the
  certificate says "architectural" on `sort`. The admissible switch-off witness contradicts it (U ≤ b), so the
  soundness check flags the violation.
- **Sound but incomplete.** On `cksum`, the frozen plant is architectural by construction, but L_Δ = 0.22 < b. GNU's
  conservative upper bound (6.79 ms, against a median of 5.2 ms) and a plant sized from the previous day's GNU time
  (4.3 ms) leave too little margin. The certificate abstains: it loses recall and keeps soundness, as in the synthetic
  check.

### (iv) Where an architectural gap can come from in the three real pairs

Condition (C3) compares the least work of *frozen* operators with the reference's *whole* time. A certificate therefore
needs a frozen component that only the system runs, or runs more expensively, and whose least work alone exceeds T_R by
more than b.

Clauses that constrain *how* mutable code is written (pure Rust, one binary, no new unsafe) can only raise Δ*. They name
no operator whose cost could be measured, so they yield no floor.

| Pair | Frozen part (main contract) | Can a certificate exist? | Pilot evidence | Consequence |
|---|---|---|---|---|
| A (Turso) | asynchronous I/O layer (Turso only); file format | only where the layer's least work for the pages the format forces exceeds SQLite's whole time | `scan_agg` must read 4,390 pages. A certificate needs ≥ 26.7–29.3 µs of frozen work per page (b_m or b), but Turso's whole count(*) run (800 index pages through the same layer) implies ≤ 8.86 µs per page beyond startup. The startup gap shrinks only from 2.6–2.7× to 2.3–2.6× under `--readonly`, which removes 3 fsyncs and 1 ftruncate (DEVIATIONS #9) | scan: candidate. Startup: not configuration-fixable, so a candidate. A certificate would need the layer's initialization alone to exceed SQLite's whole startup (2.3–2.7 ms) by e^b |
| B (uutils) | constraints only: pure Rust, multicall binary | no | startup +1.2 ms per process (2.07–2.15 ms against 0.90–0.92 ms). The 19.2 MB PIE binary has 50,833 relative relocations, 1.78 MB of relocated read-only data and 486 page faults, against GNU true's 16 relocations, 88 B and 66 faults. These are set by how the binary is built (mutable) | startup gap: candidate. A build without runtime relocations would be its witness |
| C (rav1d) | shared assembly (also run by dav1d) | no: the floor ≤ dav1d's own asm time < T_R | rav1d runs 98.5–99.7% of dav1d's asm instructions, which are 45–64% of dav1d's instructions | every rav1d gap, including the 1.5–1.9× no-asm gap, is fixable or a candidate under the bounty's contract |

**Upshot.** In the pilot, no natural gap can be certified architectural, and the evidence says why for each pair. This is
the expected outcome for reimplementations whose contracts admit almost any change to their own code. It is the correct
answer, not a failure of the method. A rule that labels a gap architectural whenever a frozen or design-level element is
on its path ("the multicall architecture" for uutils' startup, "the frozen I/O layer" for Turso's scan) would have
labelled both architectural without any floor. In the synthetic check, that kind of rule labels about one fixable gap in
five architectural.

---

## 6b. A natural architectural gap, a profiler's misdirection, and final classes (13 Nov)

### (i) A natural architectural gap: uutils' `cp` under its WebAssembly contract (DEVIATIONS #10)

**Setup.**
- uutils 0.12.0 builds for `wasm32-wasip1` in its own CI (`--no-default-features --features feat_wasm`). We built it,
  precompiled it, and ran it under wasmtime 50.0.1.
- The file system is XFS with reflink, on a RAM-backed loop image. GNU `cp` 9.12 clones extents by default (FICLONE;
  coreutils ≥ 9.0), and so does native uutils.
- Under WASI preview1, the only data-moving calls are fd_read and fd_write into and out of linear memory, with no clone.
  strace shows 65,536 `pread64` and 65,536 `pwrite64` calls for 512 MiB.

| Cell | GNU | uutils WASI | g | Floor L (Thm 1, P = 4) | T̄_R | L_Δ | Class under W | GNU `--reflink=never` | uutils native |
|---|---|---|---|---|---|---|---|---|---|
| cp 512 MiB | 3.7 ms | 332 ms | +4.47 (88×) | 66.7 ms | 4.8 ms | **+2.63** | **architectural** | removes 3.71 (gap vs it: +0.74) | +0.42 (FICLONE; start-up) |
| cp 128 MiB | 3.7 ms | 87.6 ms | +3.19 (24×) | 18.9 ms | 5.0 ms | **+1.33** | **architectural** | removes 2.51 (gap vs it: +0.69) | +0.52 |
| cksum 32 MiB | 8.4 ms | 33.5 ms | +1.37 (3.9×) | 4.7 ms | 9.6 ms | −0.72 | candidate (abstains) | — | +0.16 |

**Envelope (C2).** Measured natively (`envelope.c`): read 66.7 ms and write 63.9 ms for 512 MiB on the same file
system. These are minima over buffers of 64 KiB to 16 MiB and 5 repetitions.
- Theorem 1's floor, L = max(Σw/P, max w), does not even need the copies to be sequential.
- Under the single-thread premise of wasip1, L = 130.6 ms and L_Δ = 3.30.
- Even if a runtime could map the source into linear memory, the write alone gives L_Δ = 2.59.

**Reading.**
- The gap is the price of the WebAssembly design commitment, not of uutils' code. The same engine natively clones and
  has only its start-up gap.
- The knock-out identifies the reference mechanism the contract puts out of reach: the extent clone.
- The compute-bound `cksum`, 3.9× slower under WASI, has a frozen floor of only one read. The certificate abstains, so
  the method discriminates.

### (ii) How a profiler misdirects on Turso's `distinct` (37× slower)

**What the profiler shows.** callgrind on Turso 0.8.3 attributes:
- 66% of its 1.40 G instructions to the hash-distinct path (SipHash, `op_hash_distinct`, hash-table probes, key
  comparisons);
- 13% to B-tree cursors and column fetches;
- 14% to VDBE stepping.

**What a profile-guided fix can achieve.** Knocking out SQLite's DistinctOpt makes SQLite run the same operator, a full
index scan with a distinct table, in 47–50 ms. A profile-guided fix that matches SQLite on that operator removes at most
0.82–1.03 log units and leaves Turso about 13× slower.

**What the counterfactual graph isolates.** The knock-out identifies SQLite's skip-ahead DISTINCT (`SeekGT` over 531
distinct keys instead of 300,000 entries). It carries 2.54–2.62 log units (71–76%), and it is visible in neither profile
nor EXPLAIN QUERY PLAN.

### (iii) Final classes (Pairs A and B)

| Pair | Class | Cells |
|---|---|---|
| Turso | candidate | all 10 robust slower gaps of 0.8.3; no certificate exists (§6a (iv)) |
| Turso | candidate with an isolated mechanism | `distinct` (skip-ahead DISTINCT, 71–76%); `join3_star` (SQLite's Bloom filter, all of it) |
| Turso | candidate, execution gap | `in_subquery` (plan part ≈ 0) |
| Turso | candidate, not configuration-fixable | `startup` (`--readonly` leaves 2.3–2.6×) |
| Turso | fixable (witnessed by 0.8.3) | 4 of 0.5.0's 14 robust gaps |
| uutils native | candidate | 6 robust slower gaps (mostly start-up; `wc -m` because GNU answers from `fstat`, which strace confirms) |
| uutils WASI | architectural | `cp` |
| uutils WASI | candidate | `cksum` |

The paper's Table VII lists these per cell, and Table VI quantifies the correlational errors on Pairs A and B (§5 above
also includes Pair C).

---

## 6c. Theory completeness (13 Nov; paper Sec. III)

1. **Operator clauses and constraint clauses.**
   - **Contract.** The architecture contract is now C = (F, K). Operator clauses freeze operators and their cost
     functions. Constraint clauses are predicates on programs: language, `unsafe`, single binary, platform.
   - **Resource certificate (Theorem 2).** A constraint-only contract gives Theorem 1 nothing to work with (D = ∅).
     Constraints restrict the capabilities C_K ⊆ C that a program may use, so they need a machine model: if every
     program using only C_K must consume A_r units of a resource that C_K supplies at rate ≤ ρ_r, then T ≥ A_r/ρ_r.
     Examples of resources are bytes through a channel and instructions of a class.
   - **Constraints the reference satisfies cannot certify (Proposition 2).** If the reference itself uses only C_K on
     the cell, then A_r/ρ_r ≤ T_R. A constraint can therefore certify only by removing a capability that the reference
     uses. "Pure Rust" removes none, so native uutils can never be certified; the WASI interface removes the clone, and
     both theorems give the same floor.
2. **Transport (Theorem 4).**
   - **Model.** Selection diagram M → W → T ← S: the work W is shared, and S marks the engines' cost functions.
   - **Formula.** By total probability, then S-separation of W (Tr1), then rules 3 and 2 of the do-calculus (Tr2):
     P*(t | do(m)) = Σ_w P(w | do(m)) · P*(t | do(w)). The first factor is read from R's counters and the second
     identified (or bounded) from Y's own interventions (Tr3).
   - **Example (paper Sec. VI).** SQLite's skip-ahead DISTINCT gives w¹ = 4 × 531 seeks. Turso's own point lookups
     bound its per-seek cost at 10.7–12.0 µs, and its start-up is 6.9–7.1 ms. So adding the feature would take Turso's
     `distinct` from 32–37× to between 2.0× and 10.8× (δ_Y ∈ [−2.77, −1.22]). The naive transport (−2.58) lies inside
     the interval, but nothing guaranteed it.
3. **Bounded exploration (Proposition 4).** I_B is the set of interventions tried within a budget B, and U_B the best
   upper bound among them.
   - (a) U_B is nonincreasing and valid.
   - (b) No finite exploration raises the lower bound: two systems can agree on I_B and differ in class.
   - (c) A certificate with L_Δ > b is a sound stop signal for every budget.
   - (d) Under independent attempts with success probability p, an undecided gap survives n attempts with probability
     (1−p)^n, which gives a Bayesian budget rule. The gap graph sets p, which is how its accuracy turns into budget.

## 6d. Builder-agent error rates (13 Nov; DEVIATIONS #11, #11a–c; `experiments/agent/`)

**Setup.**
- A real LLM builder (Qwen3-8B, run locally by llama.cpp) was blinded to every intervention. It proposed a class and
  certificate premises for 20 gaps from passive evidence only, twice each: 40 outputs, 51 premises.
- An audit registered before the run checked every premise against the ground truth. Every premise was also reviewed
  by hand.

**Results.**
- **Unsupported architectural labels: 22/34 = 65% [47, 80].** These include all 20 Turso outputs and both WebAssembly
  `cksum` outputs. Every one rested on a premise error of the five kinds the soundness theorem lists.
- **The dominant error is (iii), mutable counted as frozen: 63% of premises [48, 76], or 71% after the hand review.**
  The VDBE, B-tree code and planner were labelled frozen although the contract names them mutable.
  - Checking each premise against the contract rejects 20 of the 22 false labels.
  - The builder's own (C3) arithmetic rejects the other 2: floor 6.4 ms against T_R 9.6 ms.
- **Other error types:** (iv) 18% [8, 31]; (ii) 4% [0, 14]; (i) 0/51. (iv) and (ii) rest on supplementary checks.
- **(v) is not a real error here.** The builder always summed least works as if they ran in sequence. Every such sum
  was either over mutable premises, so already (iii), or over WebAssembly calls, where the single-thread clause
  justifies it.
- **Recall: 6/6 architectural gaps labelled architectural, but only 2/6 with valid premises.** The WebAssembly `cp`
  certificates invented 100 µs per 8 KiB call.
- **Constraint-only contract (native uutils):** 0 architectural claims, but 10/12 "fixable" claims without a named
  witness.

**Lesson.** A small model's premises cannot be trusted. The audit the soundness theorem prescribes (contract check,
envelope, arithmetic) rejected every false architectural label. This one small model bounds builder quality from below;
it does not estimate frontier agents.

## 6e. Frontier builder (14 Nov; DEVIATIONS #12, #12a, #12b)

**Setup.** GPT-6.1 Sol, reasoning effort high, on the same 20 blinded prompts with two samples each. Both builders are
scored by the same registered audit v2.

**Results.**
- **No false labels, no certificates.** 0/36 false architectural labels [0, 0.10]. It stated no certificate at all
  (0 premises).
- **WebAssembly `cp`.** It named the forced fd_read and fd_write work as the chokepoint, then declined. Its reason: the
  achieved native copy rates are not ceilings over every admissible context. That is a stricter reading of (C2) than
  our envelope.
- **Native uutils.** All candidate; it never claimed "fixable" without a witness.
- **The planted gap.** Classed fixable by a setting (`GAPCR_PLANT_US=0`). This exposed error (iv) in our own planted
  certificate: we had frozen the constructor but not its duration. The certificate holds only if the contract also
  freezes the duration. Ground truth corrected (#12b).

**Under the corrected truth, Qwen3-8B** has 24/36 false architectural labels, all on premise errors and all rejected
by the audit, and 4/4 WebAssembly `cp` labels, none with valid premises.

**Upshot.**
- The small model over-claims and the audit catches it. The frontier model is sound but certifies only what a
  context-independent cost bound supports.
- The "right label for the wrong reasons" finding does not carry over to the frontier model.
- Completeness needs better bounds (direct envelope measurements, resource ceilings), not a stronger model.

## 6f. Second frontier builder: Claude Opus 5.5 (14 Nov; DEVIATIONS #12c, #12d)

**Setup.** `claude-opus-5-5` with adaptive thinking at effort "high" (the model rejects a fixed thinking budget), on the
same 20 blinded prompts with two samples each. It was scored by the same audit v2 against the corrected ground truth
(#12b). This run came after the GPT-6.1 Sol run and the correction it caused. The prompts did not change.

| Measure (audit v2, corrected truth) | GPT-6.1 Sol | Claude Opus 5.5 |
|---|---|---|
| premises stated | 0 | 29 |
| (iii) mutable counted as frozen | — | 0/29 [0, 0.12] |
| (iv) costlier context | — | 2/29 [0.01, 0.23] (planted s1; `A_startup` s1, 5 µs) |
| (ii) overestimated work | — | 3/29 [0.02, 0.27] (`A_distinct` s2: 730 index pages against 44 with skip-ahead; `A_point_rowid` s1: 2,000 pages against 1,622; planted s2, by a unit artifact, in substance (iv)) |
| (i) bypass | — | 0/29 |
| (v) floor above Theorem 1's | — | 17/40 outputs: Turso page reads put on one core where the ground truth allows four; all have L_Δ ≤ −1.68, so no label changes |
| false architectural | 0/36 [0, 0.10] | 2/36 [0.01, 0.19]: both planted, both on premise error (iv) |
| architectural found (WASI `cp`) | 0/4 | 4/4, valid premises 4/4 (L_Δ 2.64 and 1.21, against our 2.63 and 1.33) |
| WASI `cksum` | candidate 2/2 | candidate 2/2 (L_Δ −0.83, against our −0.72) |
| "fixable" without a witness | 0 | 21 outputs on 12 candidate gaps |
| fixable with a valid named witness | 2 (planted) | 0 |

**Findings.**
- **Opposite failure modes.** GPT-6.1 Sol is sound but incomplete. Claude Opus 5.5 is complete on the natural
  architectural gap but not sound.
- **Opus repeated our planted-certificate error, to the digit.** It froze the constructor, read
  `GAPCR_PLANT_US=84284` as fixed by the cell, and reported L_Δ = 0.532, our original certificate. Against the
  registered ground truth (`ground_truth_v1_as_registered.json`), audit v2 accepts sample 1 and rejects sample 2 only by
  a unit artifact. So error (iv) passed a premise-by-premise audit and was caught only because a second builder searched
  for a cheaper calling context.
- **WASI `cp`.** Opus used the prompt's native rate of about 8 GB/s as a per-byte cost lower bound, the same premise as
  our certificate. GPT-6.1 Sol refused that premise: an achieved rate is not a ceiling. Our certificate survives an 11×
  error in that rate.
- **"Fixable" without a witness.** Opus names a concrete, plausible repair each time: a static non-PIE build for the
  uutils start-up gap, a bounded top-N sorter for `order_limit`, a memmem search for `like`, an ordered distinct for
  `distinct`. None is measured. They are hypotheses for the witness search, not classes.

**Upshot.** No false architectural label survived the audit. One survived until a second builder looked for a cheaper
calling context. Error (iv) needs adversarial review (a second builder, or an explicit search for calling contexts) in
addition to the mechanical audit.

## 6g. Replication and premise diagnostic (14 Nov; DEVIATIONS #13, #13a; `experiments/agent/replication.py`)

**Arm R: exact replication.** Both builders were run with unchanged configuration on samples 3–6 (80 new outputs each).
The split is **confirmed**: every registered criterion holds.

| Criterion (new samples 3–6) | GPT-6.1 Sol | Claude Opus 5.5 | Holds |
|---|---|---|---|
| C-R1: WASI `cp` labelled architectural | 0/8 | 8/8 | yes |
| C-R2: planted gap (GPT fixable, Claude architectural) | fixable 4/4 | architectural 4/4 | yes |
| C-R3: "fixable" on the 17 candidate gaps | 2/68 | 37/68 | yes |
| C-R4 (secondary): false architectural outside the planted gap | 0/68 | 0/68 | yes |

**Pooled over six samples per gap** (120 outputs per builder; audit v2, corrected truth):

| Measure | GPT-6.1 Sol | Claude Opus 5.5 |
|---|---|---|
| premises stated | 0 | 79 |
| (iii) | — | 0/79 [0, 0.05] |
| (iv) | — | 8/79 [0.05, 0.19]: 4 planted, 4 `A_startup` of ≤ 10 µs |
| (ii) | — | 11/79 [0.07, 0.24]: 9 Turso page overcounts, 2 planted by a unit artifact |
| (i) | — | 3/79 registered; 0 by hand (#13a) |
| (v), per output | — | 43/120, all Turso, L_Δ ≤ −1.64, no label changed |
| false architectural | 0/108 [0, 0.03] | 6/108 [0.02, 0.12], all planted, all (iv) |
| WASI `cp` architectural | 0/12 | 12/12; valid 9/12 registered, 12/12 by hand |
| "fixable" without a witness | 2/102 [0.00, 0.07] | 58/102 [0.47, 0.67] |
| fixable with a valid witness | 6/6 (planted, `GAPCR_PLANT_US=0`) | 0 |

Each builder is stable across its own samples. Every GPT output on every gap is candidate, except the planted gap
(fixable 6/6) and two "fixable" labels. Claude's class on the key gaps is the same in all six samples: WASI `cp`
architectural, planted architectural, `cksum` candidate.

Against the registered (v1) ground truth, audit v2 would have accepted 4 of Claude's 6 planted certificates. It
rejects the other 2 only by the unit artifact.

**Arm D: premise diagnostic.** One sentence was added to the planted and `cp512` prompts to state the premise either
way. Both builders matched the expected class in **16/16** outputs. The explanation is **supported**.

| Variant | Expected | GPT-6.1 Sol | Claude Opus 5.5 |
|---|---|---|---|
| `D_plant_mutable`: the duration is a setting | fixable | 4/4 | 4/4 |
| `D_plant_frozen`: the duration is frozen | architectural | 4/4 (L_Δ 0.532) | 4/4 (L_Δ 0.532) |
| `D_cp512_ceiling`: 8 GB/s is a ceiling (hypothetical) | architectural | 4/4 (L_Δ 2.636) | 4/4 (L_Δ 2.636) |
| `D_cp512_noceiling`: the rates are achieved only | candidate | 4/4 | 4/4 |

**Interpretation.**
- On certificates, the two builders do not differ in reasoning. They differ in how they fill a premise the contract
  leaves implicit: the scope of (C2)'s "any admissible calling context".
  - GPT reads that scope literally: the duration is a setting, and an achieved rate is no ceiling.
  - Claude takes stated facts as given: the duration is part of the cell, and the rate bounds the cost.
- Once the premise is stated, they agree exactly.
- The "fixable" difference has the same shape. The prompt asks for "fixable" whenever "an admissible change you can
  name would close the gap". Claude names plausible repairs and believes them. GPT almost always asks for evidence.
  The diagnostic did not test this.

**Consequences for the method.**
- A contract must state the scope of every premise: which inputs of a frozen operator are frozen with it, and whether
  an envelope is a ceiling or an achieved rate.
- Error (iv) needs an adversarial search for cheaper calling contexts, in addition to the mechanical audit.
- A regex-based check of (i) needs a hand review. Here "precompiled" matched the pattern for compilation work.

---

## 7. What this means for the paper

**Applied on 12 Nov.**
- Sec. III-G: the synthetic check's setup, classes and composition, classifiers and metrics.
- Sec. IV-D: the class of planted controls, and planted architectural gaps.
- Sec. V-D: the gap classes in the three pairs, where an architectural gap can come from, and the worked identification
  example.

The items below are still proposals.

**Sec. V (design).** Each pilot lesson maps to a concrete change:
1. Report both b and b_m. Declare the closure tolerance separately.
2. Add a rebuild or layout null for code-change effects (C5 as the template).
3. Add startup cells as a design factor, and inputs sized so that startup is below 10% of R's time; or use in-process
   timing.
4. Define plan identity on bytecode or operators, not on EXPLAIN QUERY PLAN.
5. Capture profiles on every seed or segment.
6. Run 2^k interaction cells wherever two switches exist (`join2`).
7. Run plant sessions per pair, with the A/A arm as a drift alarm.

**Sec. VI (results).** A pilot paragraph and a compact RQ3 table, for example the C-cg1, B-cg1, B-cg2 and A-cg1 rows.
Suggested text:

> On a pilot of three pairs on one shared host, the correlational gap graph failed in each of the five ways of Sec. IV.
> - rav1d's shared assembly carries no excess, yet switching it off raises the gap from 2–16% to 1.5–1.9×.
> - Profile shares over-predicted a merged fix by about 10×.
> - A hardware-acceleration signature contrast fell threefold between uutils versions, while the knock-out effect stayed
>   at 1.33 log units.
> - The SIMD fix of uutils base64 did not identify its cause.
> - On Turso, plan-different cells had *smaller* gaps, yet a knock-out attributed 74% of the largest gap to an optimizer
>   decision invisible in EXPLAIN QUERY PLAN.

---

## 8. Limitations

- **Host.** One shared VM without isolation. Bands are wide (0.15–0.32). The rav1d default gap and C1 are below the
  registered resolution.
- **Scale cuts** (#2). B inputs are 32 MiB. For cksum, `wc -l` and cat, B cells are startup-dominated.
- **Profiles.** Valgrind follows the AVX2 path, not AVX-512. Captures cover 60 frames per segment.
- **External validity.** Pair A is a 14-query micro-workload, not TPC-H, so A1 and A2 are tested outside their original
  contexts. B1 says "large files". C6 was measured on Apple M3.
- **Exploratory analyses.** #6 and #7 are exploratory, and A_KO2 (`distinct`) is post hoc. None replaces a registered
  verdict.
- **Not exercised:** certificates, agent-built gap graphs, and cross-host transport.

---

## 9. Reproduce

```
cd experiments/pilot
python3 capture.py results/captures.json            # deterministic (callgrind)
python3 plans.py                                    # EXPLAIN QUERY PLAN
python3 run.py C_SURVEY C_TIMESPLIT C_SWAPS B_TIMESPLIT B_KO A_SURVEY A_KO A_TIMESPLIT B_SURVEY \
               C_PLANTS B_PLANTS A_PLANTS C_LAYOUT B_LAYOUT A_LAYOUT A_KO2
python3 markers.py; python3 sqlite_ops.py; python3 capture_extra.py   # deterministic checks (#6, #7)
python3 run.py B_ARCH B_ENV A_RO; python3 natural_floors.py           # classification examples (#8, #9)
python3 analyze.py; python3 report.py               # results/summary.json, results/tables.md
```

Binaries are pinned by sha256 in `manifest.json`. The raw per-block timings are in `results/<EXP>.json`, and the log in
`logs/run.log`.
