# Deviations from REGISTRATION.md

1. **R0 for Pair C** (logged 09:12Z, before any timing run). The C sources in rav1d's repository at tag v1.1.0 do not
   compile on x86 with gcc 13.3 (`src/x86/mc.h`: 'ssse3' undeclared). R0 is therefore upstream dav1d 1.5.1, the version
   rav1d 1.1.0 was synchronized with (Prossimo, AV1 initiative page), built with meson release and gcc 13.3.

2. **Scale cuts** (logged 09:17Z, before any timing run), to fit the pilot into one session. None changes an estimator or a verdict rule.
   - Cells under 1 s: 2 runs and 1 warm-up per block (registered: 3 and 1).
   - Pair B inputs: 32 MiB (registered: 64 MiB).
   - Pair A: the time split uses the held-out seed only; S0 uses six plan-sensitive cells of seed 1.
   - Pair C: the time split and the swaps use the default mask; the swaps run 8 rounds.
3. **Survey arms.** Each survey uses four arms (Yd, Ya, Rd, Ra). The earlier versions (Y0) run in separate four-arm
   time-split experiments, so that every design stays position-balanced with few rounds.

4. **Registered follow-up for claim A1** (09:19Z, before any timing run). This makes the A1 follow-up concrete; it is an
   addendum, not a change. Deterministic plan captures (`results/plans.json`) and checks show three equalizations:
   - `in_subquery`: SQLite with only its Bloom filter knocked out runs Turso 0.8.3's plan.
   - `join3_star`: SQLite with only its Bloom filter knocked out runs Turso 0.5.0's nested-loop plan. Turso 0.8.3 uses a
     hash join instead.
   - `join2`: SQLite without statistics (S0) runs Turso 0.8.3's with-statistics (S1) plan, and the reverse.

   Experiment A_KO times these plan-equalized contrasts on both seeds. Every arm uses the same `cat prefix | engine`
   pipe structure. The SQLite optimization mask is 0x00080000 (Bloom filter).
   - The plan part of a gap is g(default) − g(equalized).
   - The execution part is g(equalized).

5. **Addendum: the correlational baseline** (09:41Z, before any Pair A or Pair B timing run; the Pair C default-mask
   survey and the captures already exist). This makes RQ3's within-study comparison explicit.

   A *correlational gap graph* (CG) is built from passive data only:
   - default-configuration timings across cells and seeds;
   - deterministic profiles of default runs (per-function instruction excess of Y over R);
   - query plans;
   - `--debug` acceleration markers.

   CG estimates each mechanism's effect in the way practitioners do:
   - **profile share:** the mechanism's share of the excess cost;
   - **signature contrast:** the mean gap of cells that show the mechanism's signature minus that of cells that do not;
   - **predicted gain:** for a fix of a mechanism, its profile share of the gap.

   Every CG claim below is compared with the counterfactual measurement on the same cells. The metrics are sign agreement,
   the absolute error of the estimate, and whether the CG answer would pick a wrong fix target or class.

   - **C-cg1 (shared assembly):** asm symbols carry no excess (anchor check), so CG predicts that the gap does not depend
     on the assembly configuration: g(none) ≈ g(default). Measured: the `--cpumask none` arms (C_SURVEY).
   - **C-cg2 (PR #1400):** CG predicts the fix gains the parent's excess share in the motion-vector functions. Measured:
     the commit swap, in instructions and time.
   - **C-cg3 (PR #1397):** CG predicts the fix gains the parent's excess share in `cdef_brow`. Measured: the commit swap.
   - **B-cg1 (hardware acceleration):** CG estimates the effect of GNU's hardware acceleration on the gap as the signature
     contrast (cells where GNU's `--debug` reports acceleration minus the others; Y1 and Y0). Measured: the B_KO
     knock-out on GNU, g(Y,R) − g(Y,R_KO).
   - **B-cg2 (the Y0 → Y1 fixes):** CG attributes the base64 and cksum improvements to SIMD (the published reading).
     Measured: B_KO for the cause, and the time split for the fix.
   - **A-cg1 (plans):** CG estimates the effect of plan differences as the signature contrast (plan-different minus
     plan-identical cells, S1, both seeds). Measured: the plan part in A_KO.
   - **A-cg2 (statistics state):** CG pools the two statistics states. Measured: the gaps per state and under crossed
     states (A_KO, join2).

6. **Addendum: exploratory deterministic checks** (09:59Z, before any Pair A or Pair B timing run; the Pair C survey,
   time split and part of the swaps exist). These are labelled exploratory in the report. They run after the timing
   chain and never overlap a timing run.
   - **Segment dependence of the Pair C profile.** The captures used the first 60 frames of the discovery segment, the
     only segment captured. C2, C3 and the profile shares of C-cg2 and C-cg3 are recomputed on 60 frames of the two
     held-out segments (`--skip 3000`, `--skip 6000`), for Y1, R1, P1400p, P1400, P1397p and P1397, default mask.
   - **Mechanism of the base64 gap (B1, B4, B-cg2).** The captures show that uutils 0.2.0 executes fewer user-space
     instructions than GNU on base64 (log ratio −0.31). If B1's gap is robust in time, its mechanism is outside
     user-space instructions. `strace -c -f` (system calls by type) and `/usr/bin/time -v` (maximum resident set,
     page faults) are recorded for base64 encode under R, Y0 and Y1 on the 32 MiB input of seed 2.
   - **Claim B5** uses `markers.py` (its rules are in its docstring, fixed before it runs).

7. **Addendum: operator-level plan differences (exploratory, post hoc)** (10:25Z, after the Pair A survey, A_KO and
   the Pair A time split; labelled post hoc in the report). EXPLAIN QUERY PLAN is identical at the access-path level
   for `distinct` and `order_limit`, yet these cells carry the largest Pair A gaps. Turso's plan for `distinct` shows
   a hash table for count(DISTINCT), which SQLite's does not. Two checks:
   - **Sensitivity of A1:** the plan-identical share recomputed with operator-level identity, where a step that only
     one engine shows (a hash table for DISTINCT) makes the plans different. Reported next to the registered value,
     never instead of it.
   - **Knock-out follow-up:** SQLite's bytecode (EXPLAIN) for `distinct` and `order_limit` under the default and under
     single optimization knock-outs. If a knock-out makes SQLite use the operator Turso uses, a four-arm cell
     (Turso, Turso A/A, SQLite, SQLite with the knock-out) is timed on both seeds with the A_KO pipe wrappers, and its
     plan part and execution part are reported as exploratory.

8. **Addendum: planted classes under a contract variant (exploratory)** (12 Nov 2026, 11:08Z, logged before it runs; the other entries are from 11 Nov). The pilot's plants are
   removable, so they are fixable by construction. They test edge confirmation and the soundness of fixable labels,
   but never an architectural label. This experiment adds known-truth architectural gaps on real binaries, so that the
   classification pipeline (certificate, witness, partial identification) is exercised end to end.
   - **Contract variant V_F.** Pair B's contract plus one clause: the planted operator F, a constructor preloaded into
     the system's process (`plant.c`), is frozen and runs once in every invocation.
   - **Cells.** Held-out seed 2, LC_ALL=C:
     - `cksum`, where the system is slower than the reference (g ≈ +0.36);
     - `sort`, where it is faster (g ≈ −0.5).
   - **Arms.** Rd, Ra (GNU 9.12) and Yd, Ya (uutils 0.12.0), plus:
     - P2: uutils with F of w = 2 × T̂_R;
     - P05: uutils with F of w = 0.5 × T̂_R.

     T̂_R is GNU's median time in B_SURVEY, seed 2.
   - **Envelope (C2).** F is called directly in the cheapest host, GNU `true`, with and without the preload, for each
     planted size (experiment B_ENV). w is the smallest per-round difference of block means. The source guarantees
     w ≥ the planted µs, because the loop exits only after that much wall time.
   - **Certificate (Theorem 1).**
     - D = {F}, p_F = 1, so L = w.
     - T̄_R is the largest per-round block mean of the two GNU arms in the same cell.
     - L_Δ = log w − log T̄_R; architectural iff L_Δ > b, with b = 0.236 (Pair B, < 0.1 s stratum); b_m is reported
       too.
   - **Witness under the main contract,** where F is removable: the switch-off arm Yd, with U = g(Yd, R).
   - **Truth.**
     - Under V_F, P2 is architectural, since every admissible run pays w ≥ 2 T̂_R. P05's class is unknown, because it
       depends on how fast the rest of uutils could become.
     - Under the main contract, `sort`'s planted gaps are fixable (the witness Yd), and `cksum`'s are unknown.
   - **Expected labels.** P2 under V_F: architectural. P05 under V_F: candidate. `sort` under the main contract:
     fixable. `cksum` under the main contract: candidate.
   - **Mislabel demonstration.** Theorem 3's error (iii) is a removable F labelled frozen. It must produce an
     architectural label that the witness Yd contradicts on `sort`, which flags the soundness violation.

9. **Addendum: a configuration witness for Turso's startup gap (exploratory)** (12 Nov 2026, about 11:12Z,
   logged immediately before it ran at 11:12:47Z).
   - **What strace shows.** Turso's CLI issues 3 fsync calls and 1 ftruncate even for `SELECT 1`, and spawns 2 threads.
     With the existing `--readonly` flag, the fsync and ftruncate calls disappear and the output is unchanged.
   - **Why it matters.** `--readonly` is a setting, admissible under every contract. If it closes the startup gap to
     within b, the gap is configuration-fixable.
   - **Experiment A_RO.**
     - Cells: `startup` and `point_index`, seeds 1 and 2, S1.
     - Arms: Yd (`wrap_t1`), Yro (the same with `--readonly`), Rd and Ra (SQLite).
     - Witness bound U = g(Yro, R). The class follows the registered RQ4 rule (U ≤ b).

10. **Addendum: a natural architectural gap under uutils' WebAssembly contract (exploratory)** (13 Nov 2026, 07:07Z,
    logged before it runs).

    **Why.** Under the registered native contracts no natural gap can be certified (REPORT §6a). This addendum tests the
    same engine, uutils 0.12.0, under a second contract that its project supports: the `wasm32-wasip1` target that
    uutils' CI builds with `--no-default-features --features feat_wasm`.
    - **System Y_W.** uutils 0.12.0, built from the tag with that command (stable rustc), precompiled with and run by
      wasmtime 50.0.1. The `.cwasm` and wasmtime sha256 are in `logs/run.log`.
    - **Contract W.**
      - Frozen: WASI preview1 as implemented by wasmtime 50.0.1. Data moves between a file and the module only through
        `fd_read`/`fd_pread` into linear memory and `fd_write`/`fd_pwrite` out of it. preview1 has no clone, splice or
        copy call, and a hard link is not a copy.
      - Mutable: uutils' Rust code, its build for this target, and runtime settings such as precompilation.

    **Cells.** On an XFS file system with reflink (a loop image in RAM):
    - `cp` of a 512 MiB and a 128 MiB file (wrappers remove the previous destination first);
    - `cksum` of a 32 MiB file, the discrimination cell.

    **Arms.**
    - GNU 9.12, twice (A/A).
    - GNU with `--reflink=never` (a reference knock-out; `cp` only).
    - uutils native 0.12.0, which is the same engine under the registered native contract.
    - Y_W.

    **Certificate (Theorem 1).**
    - (C1) D = {fd_read of all n bytes, fd_write of all n bytes} for `cp`, and {fd_read of n bytes} for `cksum`.
    - (C2) w = the least wall time of `read()` of the file into a user buffer, plus `write()` of n bytes into a new file
      on the same file system. These are measured natively by `envelope.c`, minimized over buffers of 64 KiB to 16 MiB
      and 5 repetitions. Any fd_read/fd_write implementation does at least these kernel copies.
    - (C3) wasip1 has no threads, so p = 1 and L = sum of w.
    - T̄_R is the largest per-round block mean of the two GNU arms.
    - b is the registered Pair B band of the cell's stratum.

    **Predictions,** written before the run.
    - `cp`: L_Δ > b, so architectural under W. Under the native contract, uutils' own cp clones (FICLONE), so there is no
      robust slower gap.
    - The knock-out `--reflink=never` removes most of the W gap. This is the mechanism: R's extent clone, which W cannot
      reach.
    - `cksum`: a large measured gap but L_Δ < b, so a candidate. The certificate must abstain.

11. **Addendum: the error rates of a real builder agent, by Theorem 3's error types** (13 Nov 2026, 08:58Z, logged
    before any builder output exists). Files are in `experiments/agent/`.

    **Builder.** Qwen3-8B (Q4_K_M GGUF, sha256 d98cdcbd…5785), an open-weight LLM, served locally by llama.cpp (commit
    68598133). It runs in non-thinking mode with the model card's sampling (temperature 0.7, top-p 0.8, top-k 20), with
    seeds 1 and 2 (seed 3 if time allows).

    **Input.** The builder is blinded to all intervention results. For each of 20 gaps it sees only passive evidence:
    - 10 Turso cells, 6 uutils native cells, 3 uutils WebAssembly cells and 1 planted frozen operator;
    - default-run timings, start-up cells, query plans, callgrind profiles, `--debug` markers, system-call summaries;
    - data facts, the contract, and a list of components.

    It must claim a class and, for an architectural claim, the premises of Theorem 1, as JSON.

    **Audit.** `audit.py` checks every premise against `ground_truth.json`, written from the pilot before any output:
    - (iii) a component neither frozen nor platform;
    - (i) avoidable frozen work (Turso's fsync calls, which `--readonly` removes; JIT compilation under WASI);
    - (ii) an amount above the forced amount (SQLite's own page reads; the file's bytes), or platform work above T_R_upper;
    - (iv) a per-unit cost above 1.5× the upper bound (8.86 µs per page; the WebAssembly run's own cost per byte);
    - (v) a floor more than 20% above Theorem 1's floor recomputed from the builder's own least works with P = 4.

    Outcomes: unsupported architectural labels, and recall on the 3 gaps that are architectural by certificate.

    **Hashes (sha256, first 16 hex).** ground_truth.json b20181571c8545c3; audit.py b67efa75377eeb21; run_builder.py
    77745367bc7160a0; build_prompts.py 3bd52837a6e14dbe; ground_truth.py 873663bece7db026; prompts (concatenated)
    5dfe9938235a98a1.

    **Scope.** One small open-weight model is a floor for builder quality, not an estimate for frontier agents.

    **11a. Supplementary measures** (09:06Z, after viewing three outputs: A_distinct, A_in_subquery and A_insert_txn,
    seed 1). The registered measures are unchanged and are reported first. Two descriptive measures are added:
    - architectural labels that fail (C3) by the builder's own floor and the T_R_upper and b given in the prompt;
    - error (v) recomputed over frozen and platform premises only, because mutable premises already count as (iii).

    **11b. Supplementary checks** (09:26Z, after viewing seed 1's WebAssembly and planted outputs). The registered rules
    for (ii) and (iv) need an amount in the forced unit, so they miss least works stated in other units, such as
    "65,536 calls at 100 µs". Two checks are reported next to the registered ones, never instead of them:
    - (iv) a frozen operator's claimed least work exceeds the system's own measured run on the cell. That run is an
      admissible context, so its time bounds any frozen least work.
    - (ii) for `W_cksum32`, `fd_write` of more than 64 bytes. The cell writes only a checksum line; the ground truth
      omitted that operator's forced amount.

    **11c. Prompt error, corrected** (09:48Z, found during the manual review of the audit).
    - **The error.** The `W_cp128` prompt reused the 512 MiB cell's system-call count: it said 65,536 calls of 8 KiB
      instead of 16,384.
    - **The fix.** The prompt was corrected and only that cell was rerun with seeds 1 and 2. The two affected outputs
      are kept in `outputs_superseded/` and excluded from the analysis.
    - **Unchanged.** No other prompt and no audit rule changed.

12. **Addendum: a frontier reasoning builder, and audit v2** (14 Nov 2026, 05:02Z, registered before any frontier
    output exists).
    - **Why.** A review objected that one small model run without reasoning does not match the paper's motivation, and
      that its errors barely exercise the checks that need measurements.
    - **Builder 2.** A frontier reasoning model, Claude Opus (the newest Opus model available to the provided API key;
      the id is logged in `outputs_frontier/_model_choice.json`), with extended thinking enabled (budget 16,000
      tokens). It sees the same 20 blinded prompts, minus Qwen's `/no_think` switch, two samples each.
      Script: `run_builder_anthropic.py`.
    - **Audit v2** (`audit_v2.py`) is applied identically to both builders:
      - (ii)/(iv) are checked against a time bound on the forced work, independent of the builder's units;
      - (v) is computed over frozen and platform premises only, with sums allowed where the contract makes execution
        sequential;
      - valid certificates are counted.

      v1 and the #11 numbers stay as reported. Applied to the Qwen outputs before the frontier run, v2 gives: (iii)
      32/51; (iv) 12/51; (ii) 2/51; (i) 0/51; (v) 0/40; unsupported architectural 22/34, all with a premise error;
      architectural found 6/6, valid certificates 2/6.
    - **Hashes (sha256, first 16 hex).** run_builder_anthropic.py 34c10aea2308536e; audit_v2.py b94eec32980f60ed;
      audit.py d0cb9fdbfd3e7072; ground_truth.json b20181571c8545c3; prompts (concatenated, after #11c)
      db7ecc66cd6be114.

    **12a. Frontier builder changed to OpenAI GPT-6.1 Sol** (05:16Z, before any frontier output exists). Only an
    OpenAI key is available.
    - **Runner.** `run_builder_openai.py` (sha256 c659906a2441eff7). It uses the Responses API with reasoning effort
      "high" and a logged fallback chain.
    - **Model id.** Looked up in the models list, never guessed, and logged in `outputs_frontier/_model_choice.json`.
    - **Unchanged.** Prompts, samples (two per gap), audit v2 and the ground truth.

    **12b. Ground-truth correction found by the frontier builder** (05:23Z, after the frontier run).

    - **What the builder found.** GPT-6.1 Sol (`gpt-6.1-sol`, Responses API, reasoning effort high, no fallbacks) classed
      the planted gap "fixable" in both samples, with a concrete witness: set `GAPCR_PLANT_US=0`.
    - **Why it is right.** Contract V_F (#8) froze the constructor F, but not its duration, which is an environment
      setting. Under our own definition of a frozen operator, only its implementation is fixed and its calling
      context may change. F's least work is therefore 0, not 84.3 ms.
    - **What was wrong.** Our planted "architectural" certificate (#8, paper Sec. V-D and VI) had error (iv), a
      cheaper admissible calling context. That is the error the soundness theorem calls invisible in the graph.
    - **Corrections.**
      - Ground truth for `P_sort_frozen_plant`: class fixable (by a setting), with F's least work 0. The registered
        version is kept as `ground_truth_v1_as_registered.json`.
      - The planted certificate holds only under a contract that freezes F together with its duration. The paper
        says so.
    - **Audit v2 under the corrected truth** (both builders scored identically):
      - Qwen3-8B: 24/36 false architectural labels, all with a premise error. Architectural gaps found 4/4, with
        valid premises 0/4.
      - GPT-6.1 Sol: 0/36 false architectural labels and 0 premises (it never stated a certificate). WebAssembly `cp`
        found 0/4: it declined because the achieved native copy rates are not ceilings over every admissible context
        (C2). Planted gap correctly classed fixable 2/2.

    **12c. Builder 3: Claude Opus 5.5** (05:40Z, before any Opus output exists). An Anthropic key became available, so
    the builder registered in #12 is run as well.
    - **Model.** `claude-opus-5-5` (display name "Claude Opus 5.5"), taken from the models list, never guessed, and
      logged in `outputs_opus/_model_choice.json`. Extended thinking with budget 16,000 tokens; if the model rejects
      that, adaptive thinking. The mode actually used is recorded with every output.
    - **Runner.** `run_builder_anthropic.py` (sha256 afda71714f3fc48f). The only change from #12 is that the output
      directory is read from `GAPCR_OUT_DIR` (here `outputs_opus/`), so the GPT outputs are not overwritten.
    - **Unchanged.** Prompts (db7ecc66cd6be114), samples (two per gap), audit v2 (b94eec32980f60ed).
    - **Ground truth.** The corrected version from #12b (ground_truth.json 3d137c899a467be4). This run therefore comes
      after the GPT-6.1 Sol outputs and the correction they caused. Opus sees only the prompts, which did not change.

    **12d. Thinking configuration** (05:47Z, before any Opus output exists). The first launch stopped before any
    output: the model rejects `thinking.type = enabled` with a budget and asks for adaptive thinking with an effort
    level, and the four parallel threads each advanced the fallback index past the end of the list.
    - **Fix.** The mode is chosen once, before the parallel calls. The fallback is adaptive thinking with
      `output_config.effort = "high"`, which matches GPT-6.1 Sol's reasoning effort "high".
    - **Runner.** sha256 eabcb7b4f0b65449. Nothing else changed.

13. **Addendum: replication of the two frontier builders, and a diagnostic** (14 Nov 2026, 06:29Z, registered before
    any output of this addendum exists).
    - **Why.** The two builders split in opposite directions (#12b, #12c), each consistently across its two samples. A
      review asked for confirmation. Both reasoned for similar lengths: median reasoning tokens 623 (GPT) and 497
      (Claude). So depth of reasoning does not explain the split.
    - **Candidate explanation, stated before the new runs.** Both key disagreements turn on clause (C2) of the shared
      system prompt: least work "under ANY admissible calling context (... options, settings)".
      - On the planted gap, GPT treats `GAPCR_PLANT_US` as a setting. Claude treats it as part of the fixed cell, as
        `LC_ALL=C` is.
      - On WebAssembly `cp`, GPT does not accept an achieved rate as a cost bound. Claude does.
      - The prompt also asks for "fixable" whenever "an admissible change you can name would close the gap". So
        Claude's unmeasured "fixable" labels follow the prompt's wording; they are unverified claims, not violations.
    - **Arm R, exact replication.** Both builders, configuration unchanged: GPT-6.1 Sol with Responses API reasoning
      effort high; Claude Opus 5.5 with adaptive thinking, effort high. The 20 original prompts, samples 3–6 (80 new
      outputs per builder), written to `outputs_frontier_rep/` and `outputs_opus_rep/`. Scored by audit v2 against the
      corrected ground truth. The split is **confirmed** if all of the following hold on the new samples:
      - C-R1. WebAssembly `cp` (8 outputs per builder): Claude labels it architectural in ≥ 6, GPT in ≤ 2.
      - C-R2. The planted gap (4 outputs): Claude labels it architectural in ≥ 3, GPT labels it fixable in ≥ 3.
      - C-R3. "Fixable" on the 17 gaps whose truth is candidate (68 outputs): Claude ≥ 17, GPT ≤ 3.

      C-R4 is secondary: at most 2 of 64 false architectural labels outside the planted gap, per builder. Pooled
      six-sample rates are reported as well.
    - **Arm D, diagnostic (exploratory).** There are four prompts (`build_diag_prompts.py`, `prompts_diag/`). Each copies
      an original prompt and adds one sentence that states the implicit premise. Samples 1–4, written to
      `outputs_frontier_diag/` and `outputs_opus_diag/`. Expected classes:
      - `D_plant_mutable`: fixable. The duration is declared a setting.
      - `D_plant_frozen`: architectural. The duration is declared frozen.
      - `D_cp512_ceiling`: architectural. 8 GB/s is given as a ceiling; this premise is hypothetical and not measured.
      - `D_cp512_noceiling`: candidate. The rates are declared achieved only. An architectural label counts as a match
        only on an independent bound, which is flagged for hand review.

      A builder follows a premise if at least 3 of its 4 outputs match. The explanation is supported if both builders
      follow all four premises.
    - **Analysis.** `replication.py`, written and dry-run on copies of the existing outputs before this registration.
    - **Hashes (sha256, first 16 hex).** run_builder_openai.py 986392f64d10460e; run_builder_anthropic.py
      c4aa5f56375f953b. The only change to either runner is that `GAPCR_OUT_DIR` and `GAPCR_PROMPTS_DIR` are read from
      the environment. build_diag_prompts.py 808335783b08bfbd; replication.py b0ce325f06483ad1; audit_v2.py
      b94eec32980f60ed; ground_truth.json 3d137c899a467be4; prompts db7ecc66cd6be114; prompts_diag ec7102174f611723.

    **13a. Audit false positive found in hand review** (06:38Z, after the #13 runs).
    - **What happened.** The registered (i) check matches the regex `compil`, which is meant to catch compilation work
      listed as frozen. It also matched the phrase "precompiled module" in 3 of Claude's WASI `cp` certificates (rep
      samples: `W_cp128` s5 and s6, `W_cp512` s3). In those certificates the phrase names the cheaper context, which
      excludes compilation, so it is not error (i).
    - **What is reported.** The registered numbers are reported unchanged, with the hand-review correction next to
      them: (i) 3/79 registered and 0 by hand; valid WASI `cp` certificates 9/12 registered and 12/12 by hand. The audit
      code is not changed.
    - **Result of #13, recorded at 06:40Z.** Arm R: C-R1 to C-R4 all hold, so the split is confirmed. Arm D: both
      builders 16/16, so the explanation is supported. Details are in pilot report §6g and
      `agent/replication_summary.json`.
