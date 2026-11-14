# gapCR pilot on three reimplementation pairs: registration

Written before any timing run. The UTC time and the sha256 of this file are recorded in `registration.json`, made when the file was frozen.
Later changes go in `DEVIATIONS.md`, never in this file.

This is a pilot on a single shared host. It exercises every instrument and every research question of Sec. V at small scale.
Its numbers are not the study's results.

## Host

- 4 vCPU Intel Xeon @ 2.10 GHz (AVX-512, SHA-NI, PCLMULQDQ), 15 GB RAM.
- Ubuntu 24.04.5, glibc 2.39.
- A shared VM without CPU isolation.
- Timing runs are sequential. Builds and deterministic captures never overlap a timing run.

## Engines

Binaries are pinned by sha256 in `manifest.json`, which is written before the first timing run.

| Pair | System Y | Reference R | Versions for the time split |
|---|---|---|---|
| A | Turso CLI 0.8.3 (release binary), `tursodb -q -m list` | SQLite 3.50.4 CLI, built from the amalgamation with gcc 13.3 `-O2` (scan status and explain comments on) | Y0 = Turso 0.5.0, the version of the vendor's claim A1 |
| B | uutils coreutils 0.12.0 (release binary, multicall) | GNU coreutils 9.12, built from source with the default configure (links OpenSSL libcrypto) | Y0 = uutils 0.2.0, before the base64 fix of 0.2.2 |
| C | rav1d at commit 2e7216c2 (27 Oct 2026; rustc nightly-2026-02-05; release profile, fat LTO) | dav1d from the same checkout (meson release; gcc 13.3) | Y0/R0 = both at tag v1.1.0 (6 May 2025, the bounty baseline; rustc nightly-2025-05-01) |

**Pair C natural experiments.** rav1d is also built at the parent and the merge commit of two pull requests:
- PR #1400: an optimized `PartialEq` for `Mv` (3e104b91 → 1be76ea9);
- PR #1397: on Arm, no initialization of `tmp_buf` (b6d77c44 → a95574f8).

**Compiler.** dav1d is built with the project's default compiler (gcc). Prossimo reports that the C compiler backend shifts dav1d by about 3%, so the compiler is a registered state of Pair C. The pilot uses the default only.

## Cells, states and seeds

### Pair A

**Databases.** Generated from a seed:
- `orders`: 300,000 rows, with integer columns id, cust, item, qty, price_cents and day, and a text note;
- `customers`: 30,000 rows; `items`: 5,000 rows;
- indexes on orders(cust), orders(day) and customers(region);
- WAL mode.

Each engine gets its own byte-identical copy.

**States.**
- S1: statistics present (ANALYZE run by SQLite before copying).
- S0: no statistics.

**Seeds.** Seed 1 (discovery) and seed 2 (held out). S0 is measured only with seed 1.

**Cells.** Each script repeats its statement so that SQLite needs about 0.1–0.5 s:
- `point_rowid`, `point_index`, `range_index`;
- `scan_agg`, `count_star`, `group_by`;
- `join2`, `join3_star`;
- `order_limit`, `like`, `in_subquery`, `distinct`;
- `insert_txn` (inside BEGIN … ROLLBACK);
- `startup` (`SELECT 1`).

### Pair B

**Inputs.** Generated from a seed:
- 64 MiB of random bytes, and its base64 encoding;
- 64 MiB of ASCII text lines;
- 8 MiB of text lines for sorting, and a sorted copy;
- 4 MiB of integers;
- 32 MiB of CSV.

**Seeds.** Seed 1 (discovery) and seed 2 (held out).

**Cells.**
- `base64`, `base64 -d`, `cksum`, `sha256sum`, `md5sum`, `b2sum`;
- `wc -l`, `wc -w`, `wc -m`;
- `sort`, `sort -n`, `sort -u`;
- `cut -d, -f2`, `cat`, `head -n 1000000`, `tail -n 1000000`, `uniq`;
- `seq 1 5000000`;
- `basename /a/b/c` and `true` (dominated by process startup).

**States.**
- C: `LC_ALL=C` (all cells).
- U: `LC_ALL=C.UTF-8` (`wc -m`, `sort`).
- KO (knock-out arms only): `GLIBC_TUNABLES=glibc.cpu.hwcaps=-AVX512F,-AVX2,-AVX,-PMULL,-VPCLMULQDQ` and `OPENSSL_ia32cap=0x0`.

### Pair C

**Input.** The Netflix Chimera clip, 720p, 8-bit: the input of rav1d's official benchmark harness.

**Seeds.** 240 frames from three segments: `--skip 0` (discovery; the sanity checks used it), `--skip 3000` and `--skip 6000` (held out).

**Settings.** `--threads` ∈ {1, 4} × `--cpumask` ∈ {default (all, i.e. AVX-512 ICL), `avx2`, `none`}.

**Output.** `-o /dev/null` during timing. The MD5 of the frames is compared separately, for every arm and setting.

## Measurement

- **Design.** One celltest design per experiment. Every arm runs two blocks per round, in rotation orders (`celltest.orders.rotation`), which are counterbalanced.
- **Blocks.** One run per block with no warm-up for cells of at least 1 s; otherwise 3 runs per block and 1 warm-up.
- **Verification.** Outputs are checked before timing: the sha256 of stdout and the exit status. Pair A compares the list output.
- **Gap.** `g = celltest.noise.estimator(cell, Y, R)`, the median over rounds of the log ratio of block means.
- **Band b.** The p95 of single-block A/A |log ratios| per pair and latency stratum (< 0.1 s, 0.1–1 s, > 1 s).
- **Robust gap.** |g| > b, with the same sign in every seed of the cell.
- **Matched null b_m.** The p95 of |estimator(Ya, Yd)| and |estimator(Ra, Rd)| over the pair's cells.
- **Effect of an intervention arm X against its base arm.** `e = estimator(X, base)`.

### Verdicts (pilot)

- **Confirmed:** the predicted sign with |e| > b_m in every held-out seed, and inside the predicted range if one is given.
- **Refuted:** either
  - the opposite sign with |e| > b_m in every held-out seed; or
  - |e| ≤ b_m in every held-out seed, when the claim predicts an effect larger than 2 b_m. The pilot's equivalence margin is b_m.
- **Inconclusive:** anything else.
- **Descriptive or deterministic claims:** decided by the stated deterministic measurement.

## Registered claims

These are published claims, with sources in the paper's bibliography, plus the post hoc hypothesis C8. "pp" means percentage points.

### Pair C

**C1** (Prossimo bounty page, May 2025): rav1d is about 5% slower than dav1d.
- *Prediction:* at V0 (v1.1.0 pair) with threads 1 and the default mask, the gap is robust and slower, and g lies in [0.03, 0.07].
- *Evidence:* timing.

**C2** (Crane & Sen 2024): Rust accounts for almost exactly half of total run time with all assembly enabled.
- *Proxy:* the share of rav1d's executed instructions outside assembly symbols, at HEAD, threads 1, default mask.
- *Prediction:* the share lies in [0.40, 0.60].
- *Evidence:* deterministic (instructions, not time; a proxy).

**C3** (Crane & Sen 2024): the remaining overhead is spread roughly evenly across the largest, most complex functions.
- *Operationalization:* rav1d's excess instructions over dav1d, attributed to functions matched by name.
- *Prediction:* no single function carries more than 20% of the excess.
- *Evidence:* deterministic.

**C4** (Crane & Sen 2024): bounds checks account for less than 1% of the transpiled code's overhead.
- Not testable in the pilot, because it needs a modified rustc. Recorded as untestable without repair.

**C5** (Ravid 2025; PR #1397): skipping the initialization of `tmp_buf` in the Arm CDEF path saves 1.6%.
- The claim's scope is the Arm path.
- *Prediction on x86:* |e| ≤ b_m for P1397 against P1397p, and the instruction count unchanged to within 0.1%.
- *Evidence:* timing and deterministic.

**C6** (Ravid 2025; PR #1400): an optimized `PartialEq` for `Mv` saves 0.7%, measured on an Apple M3.
- *Prediction on x86:* P1400 is faster than P1400p (e < 0) and executes fewer instructions.
- *Evidence:* timing (possibly below this host's resolution) and deterministic.

**C7** (bounty premise): the gap is fixable by Rust-only changes.
- *Time split:* g(Y1 vs R0) < g(Y0 vs R0), that is, rav1d at HEAD against v1.1.0's dav1d, holding the reference fixed.
- *Admissibility:* no assembly file changed between v1.1.0 and HEAD (checked: none since May 2025).

**C8** (post hoc, from the discovery segment's sanity runs): with assembly disabled, the gap is larger than with assembly.
- *Prediction:* g(none) − g(default) > b, in both held-out seeds, threads 1.

### Pair B

**B1** (uutils issue #8574, 2025): uutils base64 is about 8× slower than GNU on large files.
- *Prediction:* at Y0 (0.2.0), the base64 encode gap is robust and slower, with ratio ≥ 4 (g ≥ 1.39).

**B2** (Phoronix 2025): base64 was fixed in 0.2.2 and became faster than GNU.
- *Prediction:* at Y1 (0.12.0), g ≤ 0, or |g| ≤ b.

**B3** (Phoronix 2025): cksum was up to 17× slower than GNU on large files.
- *Prediction:* at Y0, the cksum gap is robust and slower, with ratio ≥ 4. At Y1, |g| ≤ b, or faster.

**B4** (Lobsters commenter 2025): the base64 and cksum gaps were addressed by adopting SIMD implementations.
- *Causal reading:* the Y0 gaps exist because GNU uses SIMD hardware acceleration and uutils did not.
- *Test:* knock out GNU's acceleration (KO state on R).
  - cksum: the claim predicts that the knock-out removes most of the Y0 gap, |g(Y0, R_KO)| ≤ 0.5 |g(Y0, R)|.
  - base64: GNU base64 has no hardware path, so the knock-out has no effect, and the claim cannot explain that gap.
- *Verdict:* separate for each utility.

**B5** (instrument check, GNU manual): the KO environment switches GNU's and uutils 0.12.0's `--debug` markers to "not detected".
- *Evidence:* deterministic.

### Pair A

**A1** (Enberg, 7 Mar 2026, Turso 0.5.0 against SQLite 3.49.1 on TPC-H): where performance differs, the difference is almost entirely due to the query planner and optimizer.
- *Operationalization:* among robust slower gaps, the share of gap mass in cells whose normalized plans are identical (EXPLAIN QUERY PLAN: access order and access methods).
- *Prediction:* ≤ 20% of the gap mass is in plan-identical cells.
- *Evidence:* timing plus deterministic plans.
- *Follow-up:* where plans differ, registered SQLite knock-outs (optimization mask, `automatic_index`) are timed if they move SQLite's plan toward Turso's.

**A2** (third-party benchmark of Turso 0.7.1): Turso is 4–6× slower on scans and about 1.5–2× slower on point reads and joins.
- *Prediction for Y1 (0.8.3):* `scan_agg` g ≥ log 2; `point_rowid` and `join2` g ≥ log 1.3.

**A3** (Turso 0.8 release notes, "the performance release"): the Y0 gaps shrink in Y1.
- *Prediction:* g(Y1, R) < g(Y0, R) in most robust Y0 gap cells.

## Known-truth controls

**Plant mechanism.** `plant.c`, loaded with `LD_PRELOAD`. Its constructor busy-waits `GAPCR_PLANT_US` microseconds, then unsets the variable so that a wrapper's exec does not repeat it.

**Arms.**
- Plants of 2%, 5% and 15% of the cell's median Y time.
- A null plant: preloaded with 0 µs.
- A sham switch: `GAPCR_SHAM=1` without the preload.

**Cells.**
- Pair B: `cksum`, `wc -l`, `sort`, `cut`.
- Pair C: threads 1, default mask.
- Pair A: `scan_agg`, `join2`.

**Seeds.** The held-out seeds.

**Estimates.** Sensitivity by planted size, and specificity from the null plants and shams.

## RQ1 funnel

1. **Null:** the A/A estimator treated as a pseudo-gap; report the rate of robust pseudo-gaps.
2. **Layout spread:** Y with environment padding of 0, 1, 2 and 3 KiB on three cells per pair. A gap is credited only above max(b, spread).
3. **Deterministic counterparts:** callgrind instruction counts (Pairs B and C; Pair A for three queries). For Pair C, add the anchor check: the per-symbol counts of assembly functions must be equal across the engines.
4. **Transport:** not available on one host; reported as missing.
5. **Analysis variants:** the sign agreement of the ratio of medians over all blocks with g.

## RQ3 within-study comparisons

- **Pair C:** predict each PR's effect from the parent's per-function instruction excess in the functions the PR touches, and compare with its measured instruction and time effect.
- **Pair B:** the association between "GNU uses hardware acceleration in this cell" and gap size, against the measured effect of the knock-out on the gap.
- **Pair A:** the association between "plans differ" and gap size, against the measured effect of plan equalization.

## RQ4

**Witnesses.** Natural witnesses are later versions (Y1), admissible under the pair's contract:
- Pair C: Rust-only changes, assembly untouched;
- Pair B: pure Rust (the release binary links only libc);
- Pair A: same file format and SQL semantics.

**Certificates.** None in the pilot.

**Classes** (Corollary 1 with L_Δ = −∞): fixable if U ≤ b, otherwise candidate.

**Reported:** the share of the Y0 robust gap mass that the witnesses decide.
