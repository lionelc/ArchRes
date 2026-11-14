# Soundness review of the classification theory, and how to validate it on open-source projects

*Review of `theory/classification_theory.md` at commit 3c8d6ec, 7 Nov 2026, for CauSE 2027 (ICSE 2027 workshop, Dublin). The submission deadline is 13 Nov 2026 (AoE). Full papers are at most 8 pages and position/short papers at most 5, references included, and review is double-anonymous [V]. The numbers in §2 come from `python3 theory/review_checks.py` (standard library, about 12 s), which reuses `sim_certificates.py`. Source tags follow `workflow/scout.py`: [V] verified on a fetched page, [S] search result, [M] memory.*

---

## 0. Verdict

**The theory is worth submitting.**
- **The core is sound.** "Architectural" is a universally quantified counterfactual over a declared set of admissible interventions. A witness bounds the residual $\Delta^\ast$ from above and a certificate bounds it from below; every result follows from one of those two directions.
- **Every proof is correct under its stated premises.**

**Three things must change before submission:**
1. **The cost model hides an assumption that real systems break (major).**
   - Thm 3 and Thm 7 assume that no admissible intervention can change a frozen operator's cost, and that operator times add up under every intervention.
   - But mutable code decides *how* frozen code is called: on how many threads, in which batches, in which order, with which options.
   - With a correct graph, the certificate labels 7.9% of fixable gaps architectural once 30% of frozen operators may be called on 4 threads (check C).
   - Thm 7's "exactly two ways" to break soundness become five. §2.1 gives a corrected certificate (Thm 3′).
2. **Dominance cannot come from enumerating plans (major in practice).** Admissible code changes are open-ended. Dominance must therefore come from the contract (a *chokepoint*), and the least work from what any correct implementation must do (§2.2).
3. **Statistical and scope details (medium).** §2.3–2.4 cover:
   - selecting the witness after trying many interventions (Thm 1);
   - an unnecessary Holm correction (Thm 4);
   - inference with a discrete running variable (Thm 2);
   - the band as a registered margin;
   - transportability (Thm 5), an exclusion restriction (Thm 6), and plan sufficiency (Thm 4).

**The simulation needs two corrections (§2.5):**
- Zero false architectural labels with a correct graph holds *by construction*.
- The comparison with today's `classify()` omits its configuration branch. The fair false-architectural rate is **19%, not 30%** (check A).
- The robustness claim holds: the largest difference between seeds 7 and 11 is 0.013 (check B).

**Positioning.**
- **The proofs are short because the hard part is upstream:** deciding what is admissible (the contract), and establishing the chokepoint and the cost envelope. Reviewers will judge whether those premises can be established on real systems; §4 is about that.
- **Theorem names:**
  - Present Thms 1, 4, 5 and 6 as propositions.
  - Keep as the main results: Thm 2 (with 2′), Thm 3′, Thm 7′ and Prop 8, framed as partial identification of $\Delta^\ast$ (§3).

## 1. What holds

| Result | Verdict | Note |
|---|---|---|
| Def. 1, the residual and the classes | Sound | Close $\mathcal I$ under composition (a code change plus a knob setting), or a combined fix falls outside $\Delta^\ast$ |
| Remark: narrowing $\mathcal I$ | Correct | A certificate for a wider set stays valid for any narrower one |
| Thm 1, witness | Correct for one pre-specified intervention | Selection among many: §2.3(a) |
| Thm 2, difference-in-discontinuities | Correct | The algebra checks: $\Delta-\delta_m$ equals the difference of the engines' first differences of $\mu_E$. Inference: §2.3(c). Shared thresholds: §2.4(a) |
| Thm 3, certificate | Correct as stated | Premise (C2) is not what the procedure measures: §2.1 |
| Thm 4, exhaustion | Correct, conservative | The Holm correction is unnecessary (§2.3(b)); plan sufficiency fails for knobs inside operators (§2.4(b)) |
| Thm 5, reference knock-out | Main statement correct | "The system lacks $\varphi$'s effect" overclaims: §2.4(c) |
| Thm 6, knob-following boundary | Correct with an exclusion restriction | §2.4(d) |
| Counterexample 1 | Correct | Co-switching is common in real systems: a spill threshold often starts an I/O path and a merge together |
| Thm 7, soundness | Correct within the draft's model ($t_o=\kappa_o u_o$, $\kappa_o$ a constant of the operator) | Incomplete outside it: §2.1 |
| Prop 8, passive data | Correct | Stronger framing as a positivity violation: §3 |

## 2. Issues, with corrected statements

### 2.1 Frozen code is not frozen cost (major)

**Where.**
- §1 of the draft fixes $t_o=\kappa_o u_o$ with $\kappa_o$ a constant of the operator.
- (C2) adds "frozen, so no $\iota$ changes it".
- Step 2 of Thm 3's proof assumes the operators' times add up under every $\iota$.

Freezing a mechanism fixes its *code*, not the context it is called in. Mutable callers set that context:
- **Parallelism.** A thread-safe frozen operator can be called on several threads by a mutable executor.
- **Batching.** One call per batch instead of one per row amortizes per-call cost.
- **Order and layout.** These affect cache and branch behaviour.
- **The frozen component's options.** RocksDB's options, for example, are set by its embedder.
- **Overlap of frozen operators with each other.** Pipelining changes how their times combine.

E3 dose-response measures $\kappa_o$ in the *default* context only. It also measures a marginal slope over the measured range, which overstates the average cost at a smaller work level when cost per unit grows with volume (cache spills).

**Counterexample (correct graph, false architectural label).**
- **Setup.**
  - A frozen decoder $f$ handles $u=10^6$ rows at $\kappa=1\,\mu$s per row: $t_f=1.0$ s on the default, sequential plan.
  - The reference takes 0.5 s, and $b=0.1$.
  - Every admissible plan calls $f$, so (C1) holds, and the labels are right.
- **The certificate's verdict.** The floor is 1.0 s, and $\log(1.0/0.5)=0.69>b$, so it labels the gap architectural.
- **Why that is wrong.** $f$ is thread-safe, so a change to the mutable executor can partition the rows and call $f$ on 4 threads. Then $t_f\approx 0.25$ s. If the rest of the plan takes at most 0.30 s, then $g\le\log(0.55/0.5)=0.095\le b$, and the gap is fixable.

**Check C.**
- **Setup.**
  - Same instances as Table B of the draft, correct graph.
  - Each frozen operator can be parallelized 4 ways by mutable code with probability 0.3.
  - Mutable operators keep the draft's 10× code-change speedup.
  - 1,368 gaps that were architectural become fixable.
- **Results.**

| Floor | False architectural (rate among fixable) | Recall among architectural |
|---|---|---|
| The draft's (sequential cost of the frozen dominators) | **894 (0.079)** | 0.69 |
| Envelope: each frozen dominator at its best admissible context | 0 (0.000) | 0.66 |
| Work law only: frozen dominators' work divided by the 4 threads | 0 (0.000) | 0.32 |

**Corrected model.** For operator $o$ under intervention $\iota$, $t_o^\iota=f_o(z_o^\iota)$.
- **The calling context $z_o^\iota$.** This is the work routed to $o$ and how it is presented: batches, order, layout, threads, options and cache state. The cell and the mutable mechanisms set it.
- **What freezing fixes.** Freezing fixes $f_o$ for $o\in F$, so $f_o$ is autonomous under every $\iota\in\mathcal I$. It does not fix $z_o$.
- **Notation.**
  - $Z_o=\{z_o^\iota:\iota\in\mathcal I\}$ is the set of admissible contexts.
  - $W_o(z)$ is $o$'s CPU work in context $z$.
  - $p_o$ is the most cores any $z\in Z_o$ lets $o$ use; $p_o=1$ when $o$ is sequential by nature or by contract.
  - $P$ is the machine's number of cores.

The draft's model is the special case $W_o(z)=\kappa_o u(z)$ and $p_o=P=1$.

**Theorem 3′ (certificate with calling contexts).** For a robust slower gap at $(c,s)$, suppose:
- **(C1′) Chokepoint:** every $\iota\in\mathcal I$ executes every $o\in D\subseteq F$ (see §2.2 for how to establish this);
- **(C2′) Envelope:** $w_o\le\inf_{z\in Z_o}W_o(z)$ for each $o\in D$;
- **(C3′) The floor beats the band:** $\log L-\log\overline T_R>b$, where $L=\max\big(\tfrac1P\sum_{o\in D}w_o,\ \max_{o\in D}w_o/p_o\big)$.

Then $\Delta^\ast>b$. With confidence bounds, this holds with probability at least $1-\alpha_w-\alpha_R$, where $\alpha_w$ is familywise over $D$.

*Proof.* Fix $\iota$.
1. By (C1′) and (C2′), the run does at least $\sum_{o\in D}w_o$ CPU work on at most $P$ cores, so $T^\iota_Y\ge\frac1P\sum_{o\in D}w_o$ (the work law).
2. Each $o\in D$ uses at most $p_o$ cores, so it takes at least $w_o/p_o$ wall-clock time, and the run cannot finish before it does (the span law).
3. Hence $T^\iota_Y\ge L$, and $g_\iota\ge\log L-\log\overline T_R>b$ for every $\iota$. So the infimum $\Delta^\ast$ exceeds $b$ too. ∎

**Remarks.**
- With $P=p_o=1$, $L=\sum_o w_o$: this is the draft's floor, now with its envelope condition stated.
- If the contract or data dependences force some operators of $D$ to run one after another, then the sum of their $w_o/p_o$ along that chain is also a lower bound (the critical path). Check C's envelope floor uses this, because its model runs operators in sequence.
- **Measuring $w_o$.** Call the frozen operator directly in a harness:
  - at the least work the output requires (§2.2);
  - under the most favourable admissible context: largest batches, best order, warm caches, best options;
  - taking a lower confidence bound on CPU time.

  *Frozen* means unchangeable, not unmeasurable. This is an I-same measurement on the operator itself, which is stronger than a dose-response slope read off default plans.

**Theorem 7′ (which errors break soundness).** Under the model above, the computed $L$ can exceed $\inf_\iota T^\iota_Y$ only through one of these routes, or through a coverage failure of a confidence bound:

| # | Route | In the draft? |
|---|---|---|
| 1 | A bypass exists: the chokepoint is false | yes: a missing plan |
| 2 | The least work is overestimated | yes: a missing work reduction |
| 3 | Mutable cost is counted as frozen | yes: a mislabel or a co-switch |
| 4 | An admissible context is cheaper than the one measured: batching, order, options, caching | **no** |
| 5 | More parallelism or overlap is admissible than $P$ and $p_o$ allow | **no** |

- **Every other error lowers $L$** and costs completeness only, as the draft says.
- **Routes 4 and 5 are invisible to the graph.** They concern how a frozen operator is called, not which operators run. So a perfect graph does not protect against them; only the envelope measurement does.

### 2.2 Dominance and least work come from the contract (major in practice)

**Dominance.** (C1) quantifies over $\Pi_{\mathcal I}$, which the draft derives "from code".
- **The problem.** $\mathcal I_{code}$ includes new plans and operators written in $M$. That space is open-ended, and enumerating existing code never covers it. So (A1) cannot be established by enumeration.
- **What closes the space is the contract.** (C1′) holds when the contract says a resource can only be reached through $o$, for example:
  - "the on-disk format is read only through the frozen reader";
  - "every read and write goes through the storage engine".
- **Establishing it** then takes two steps: register that clause with the contract, and check from the source code (S-src) that $o$ is the only access path.

**Least work.** $u_o$ should be the work that *any* correct implementation must route through $o$, given the format and the required output, not the least work among the plans we know. Examples:
- a full decompression must decode every input byte;
- a point lookup must read the pages from the root to the leaf;
- a scan must decode the blocks that contain its rows.

With both clauses registered, Thm 7′ routes 1 and 2 become contract-audit questions instead of graph-completeness questions.

### 2.3 Statistical details (medium)

**(a) Selecting a witness after trying many interventions (Thm 1).**
- **The problem.** Thm 1 holds for one pre-specified $\iota$. Suppose agents try $J$ interventions and declare the first with $U_\iota\le b$. Under $\Delta^\ast>b$ every $g_\iota>b$, so $P(\exists\iota:U_\iota\le b)\le J\alpha$: a false "fixable" rate of up to $J\alpha$.
- **Remedy.** Either use level $\alpha/J$, or select on one set of seeds and confirm on held-out seeds. gapCR's look-1/look-2 design gives the second option if the witness is fixed before look 2.

**(b) Thm 4 needs no Holm correction.** The conclusion "every configuration plan stays beyond the band" is an intersection–union test (Berger 1982).
- *Proposition 4′.* Let each $L_\pi$ be a level-$\alpha$ lower confidence bound for $G(\pi)$, with no adjustment. Declare "not configuration-fixable" iff $L_\pi>b$ for all $\pi\in\Pi_{cfg}$. This rule has level $\alpha$.
- *Proof.* Under $H_0:\min_\pi G(\pi)\le b$, pick $\pi_0$ with $G(\pi_0)\le b$. Rejection requires $L_{\pi_0}>b\ge G(\pi_0)$, which has probability at most $\alpha$. ∎
- Holm keeps the conclusion valid but only costs power.

**(c) Inference for Thm 2.**
- With an integer running variable, the jump is identified only up to the smoothness bound. After the local linear fit, the bias is at most $C(K_Y+K_R)h^2$, where $C$ is a constant of the ladder design.
- **Report a bias-aware ("honest") interval:** estimate ± (bias bound + $z\cdot$se), as in Kolesár & Rothe (2018) and Armstrong & Kolesár (2018).
- **Register $K$ before the run.** It cannot be learned at $x^\ast$; a ladder's curvature away from the threshold is a reasonable source.
- **Placebos test only part of the design.** They test (B2) and (B3) away from $x^\ast$. (B3) at $x^\ast$ itself remains an assumption, so say so.

**(d) The band.**
- **The problem.** The class definitions use $b$ as an equivalence margin, but the digest re-estimates $b$ in every run (the p95 of A/A pairs). The class therefore becomes a random target.
- **Remedy.** Register $b$ from a calibration run, or state that the classes are conditional on the run's band.
- In Thm 3, $\alpha_\kappa$ (now $\alpha_w$) must be familywise across the operators in $D$.

### 2.4 Scope and wording (medium)

**(a) Theorem 2′ (shared thresholds).** Reimplementations often share the reference's thresholds; Turso and SQLite, for example, share a file format.
- **Setup.** Suppose both engines switch at $x^\ast$, with (B2), (B3), and exclusivity *within each engine*. Then (B1) fails, but the same algebra gives
$$\Delta-(\delta_Y-\delta_R)=[\mu_Y(x^\ast)-\mu_Y(x^\ast{-}1)]-[\mu_R(x^\ast)-\mu_R(x^\ast{-}1)].$$
- **Interpretation.**
  - $\Delta$ measures how much more the system pays for the *same* format-imposed event, as a relative (log-scale) effect.
  - A shared format event cannot by itself create a gap. Only a costlier handling can, and if that handling lies in $M$, it is a fix target.
- **Units.** Each $\delta$ is relative to its own engine's baseline. For absolute cost, $t_m(x^\ast)\approx T_Y(x^\ast{-}1)(e^{\delta_m}-1)$. This is net of whatever $m$ replaces, hence a lower bound on $m$'s own cost.

**(b) Plan sufficiency (Thm 4).**
- **The problem.** Many knobs act *inside* operators: buffer sizes, batch sizes, thread counts, feature switches. Exhaustion over plans misses them.
- **A real example.** Dolt made a feature opt-in to remove hot-path overhead without changing any plan (§4.3).
- **Remedy.** Exhaustion must range over knob settings. Continuous knobs need a monotonicity argument, such as "more memory never hurts", to be covered by their extremes.

**(c) Knock-outs (Thm 5).** Disabling $\varphi$ in the reference identifies $\varphi$'s effect *in the reference*.
- **The overclaim.** That the gap closes when $\varphi$ is off is a magnitude match, not evidence that the system lacks $\varphi$.
- **What it needs.** Require O-det evidence that the system lacks $\varphi$'s signature.
- **What a fix prediction needs.** Predicting that adding $\varphi$ to the system closes the gap needs transportability of $\varphi$'s effect across engines (Pearl & Bareinboim 2014); the draft cites this but does not use it.

**(d) Knob-following boundaries (Thm 6).**
- **The gap in the proof.** The proof needs an exclusion restriction: $k$ affects the gap at $x$ only through $x^\ast(k)$. Otherwise, setting $k$ may change other mechanisms.
- **In practice,** rely on a measured witness at the chosen $k$ (Thm 1).

**(e) Wording.**
- "This closes the identifiability gap on the frozen side" overclaims. Better: "gives a route to identification at thresholds".
- Frozen operators that can be called in isolation are identifiable by direct intervention anyway (§2.1).

### 2.5 The simulation

1. **Zero false architectural labels with a correct graph holds by construction.**
   - The model satisfies (A1)–(A3) exactly and has no measurement noise. So for every plan $p$, $\sum_{o\in p}$cost·factor $\ge\sum_{o\in D\cap F}$cost, which is the floor.
   - That row checks the code, not the theorem.
   - The informative results are the error sweeps and the comparison between rules. Present them that way, or reviewers will call the zero circular.
2. **The comparison with today's rule omits a branch.**
   - `classify_today` skips `classify()`'s `config_closes` branch. In the real rule, a configuration-reachable plan that already closes the gap returns `configuration` first.
   - With that branch (check A), today's rule labels **19.3%** of fixable gaps architectural with a correct graph (1,914 of 9,942), not 29.8% (2,963). At $q_{lab}=0.3$ the rate is 37.2%, not 51.1%.
   - The qualitative conclusion stands; quote the fair numbers.
3. **The robustness claim holds.** The largest difference between seeds 7 and 11 over every rate of the three tables is 0.0133 (the draft says "at most 0.014").
4. **A row to add.** Add check C to Table A as the route-4/5 row: the draft's floor fails, and the envelope floor restores soundness.

## 3. Framing for the CauSE audience

**Partial identification.**
- Let $U$ be the smallest upper confidence bound over measured witnesses, so $\Delta^\ast\le U$. Let $L_\Delta=\log L-\log\overline T_R$ be the certificate's lower bound, so $\Delta^\ast\ge L_\Delta$.
- Then $\Delta^\ast\in[L_\Delta,U]$ with probability at least $1-\alpha$, and the classes read off the interval:
  - **architectural** if $L_\Delta>b$;
  - **fixable** if $U\le b$;
  - **candidate** if $L_\Delta\le b<U$;
  - **mixed** if $b<L_\Delta$ and $U<g$.
- This is Manski-style partial identification. Interventions bound the residual from above; the contract plus interventional cost measurements bound it from below. It unifies Thms 1 and 3 and gives the paper one central picture.

**Positivity.**
- In passive operation the plan is a deterministic function of the cell, the state and the configuration. An admissible plan that the default policy never picks has probability zero.
- Positivity fails there, so $g_\iota$ for that plan, and hence the infimum, is not identified from passive data. Prop 8 is an instance.
- Foster et al. (EASE '25) stress positivity as the key limit of observational causal testing, so this framing connects directly to that line of work.

**Which graph errors matter.**
- Causal graphs in software analytics are known to be unstable (Hulse, Eisty & Menzies 2025). Thm 7′ answers the practical question for this decision: only floor-inflating errors matter.
- gapCR builds its graphs with LLM agents. The theorem therefore says which agent errors to audit, which matches the call's emphasis on agentic systems judged by correlational benchmarks [V].

**Related work to add.**
- **Coz**, causal profiling with virtual speedups (Curtsinger & Berger, SOSP '15). Its "what if this code were faster" is the counterfactual behind a mutable fix.
- **Unicorn**, causal performance debugging of configurable systems (Iqbal et al., EuroSys '22). This is the `configuration` class.
- **Further causal-SE work:**
  - Giamattei et al., the systematic review in IST 178 (2025);
  - Furia, Torkar & Feldt, causal analysis of programming-language effects (TOSEM 2023) [M for the authors];
  - Zhang et al., Rust's runtime performance and its sources (ASE '22) [M];
  - Jin et al., real-world performance bugs (PLDI '12) [M].

## 4. Validation on real open-source projects

### 4.1 What the validation must show

| Claim | Test | Ground truth | Statistic |
|---|---|---|---|
| Soundness of `architectural` (Thm 3′/7′) | Label each robust gap *before* repair, then compare with what later fixed it | Agent repairs with SV; human fixes that respect the contract (touch only $M$) | Violations $v$ among $n$ fixable gaps, with a one-sided Clopper–Pearson bound ($v=0$: at most $3/n$ at 95%) |
| The same, without a selected sample | Planted fixable gaps: put an existing optimization behind a switch, off | Fixable by construction | $v/n$ |
| Completeness | Planted architectural gaps: declare a component frozen in a synthetic contract and add known work to it | Architectural by construction | Recall |
| Falsification on certified gaps | Repair agents with a fixed budget under the contract (gate unchanged) | Any repair that passes the gate and the sufficiency rule is a violation | Count; zero is weak evidence, so report it as an attempt |
| Thm 2 identifies a causal effect | **Within-study comparison** (LaLonde 1986; Cook, Shadish & Wong 2008): at a threshold where a *mutable* mechanism switches and can be toggled, estimate the effect from the ladder (no intervention) and by toggling at $x^\ast$ on the same binary (I-same). Then apply Thm 2 where no toggle exists | The toggled estimate | Difference with an interval; placebos |
| Counterexample 1 occurs in practice | Find a real co-switch; compare `classify()` with the procedure after clamping | Clamped measurement | Case |
| Prop 8 occurs in practice | A knob or API path that no default plan uses and that removes a gap | Witness | Case |
| Contract-relativity | Same reference and cells, two systems with different contracts | Contracts | Class tables side by side |

### 4.2 First priority for 13 Nov: the cases already run (ts1, cu1)

These steps reuse the existing records. Whether each one works depends on what the ts1/cu1 folders contain, which I have not seen.
1. **Register a contract per case before recomputing any class**, with `workflow.records`: hash and real UTC time. It names:
   - the frozen set $F$, each item with a source;
   - the admissible classes (rewrites excluded);
   - the chokepoints;
   - the machine's $P$.
2. **Collect the witnesses already in the records:**
   - every cell-setting with SV in a sufficiency verdict;
   - every registered human fix that brings its precondition cells within the band;
   - any configuration change that closed a gap.

   Each gives fixable cells, with the selection caveat in §2.3(a).
3. **Recompute labels on the pre-repair graphs** with (a) `classify()` as used and (b) the corrected procedure, which certifies only with a chokepoint and an envelope floor.
4. **Count the fixable cells labelled architectural under each rule** and report $v/n$ with exact bounds. This is the paper's first real-system result: today's rule against the certificate on the same gaps.
   - The theory predicts violations for `classify()` where a fixable gap's boundary mechanism sits in L3 or L4, co-switching cases included, and none for the certificate.
   - A certificate that never fires on these cases is also a result: it marks where today's rule overreaches.
5. **Optional: one within-study boundary comparison per case**, if a mutable threshold with a switch exists. Turso and SQLite share the file format, so format thresholds fall under Thm 2′.
6. **Choose the paper type:**
   - **Full paper (8 pages):** if steps 1–4 work for at least one case, the paper is theory + simulation + a real retrospective test.
   - **Short/position paper (5 pages):** otherwise, the corrected theory + simulation + one worked real example.

   Either way, anonymize: the repository name, the case paths and the session links must not appear, and any artifact link must go to an anonymous mirror.

### 4.3 New candidate projects

**What the theory needs beyond `scout.py`'s criteria:**
- a contract that can be declared from public sources;
- ground truth for both classes;
- frozen operators that can be called in isolation, to measure the envelope;
- thresholds;
- a fix history.

| Pair | Contract (frozen set) | Fixable ground truth | Architectural angle | Thresholds | Complexity / statefulness | Main risk |
|---|---|---|---|---|---|---|
| **Kvrocks vs Redis/Valkey** | Data on disk in RocksDB, to cut memory cost [S]. The maintainers say direct comparison makes no sense because the storage and thread model differ [S] | Command- and encoding-level PRs [M] | **Natural chokepoint:** every read goes through RocksDB. Envelope from RocksDB's own `db_bench` and its perf counters [M]. A 2026 talk calls the wrong workload "a latency disaster" [S] | Reference side: Redis's encoding conversions, which are knob thresholds [M]. System side: memtable flush, block size [M] | high / high | Server noise; command-subset differences. Apache-2.0 [S] |
| **Dolt vs MySQL; Doltgres vs Postgres** | Versioned storage engine and Go SQL engine [M]. DoltHub states that Doltgres's best is bounded by Dolt's [S] | **Sysbench multiples published per release and nightly; optimizations documented with numbers** [S]: a hot-path feature made opt-in (multiple to 1.03); passing tree nodes as pointers (1.07); in Doltgres, flushing every 128 rows (over 200% on multi-row benchmarks) | Doltgres's "under 2x" claim is an informal certificate whose premises can be checked. A valid floor must be the *shared* engine's least cost, not Dolt's total | Fewer clean ones [M] | high / high | Server noise; MySQL/Postgres versions to pin |
| **rav1d vs dav1d** | **The bounty rules are a published contract:** the shared assembly may not be modified, and only Rust may be added [S] | Bounty-era PRs [S], e.g. avoiding a zero-initialization (−1.6%) and byte-wise equality for small structs (−0.7%), without new `unsafe` | The remaining gap of about 5% is spread across large functions [S], which tests that the certificate stays silent (candidate) on a diffuse gap. Bounds checks are the cleanest real case of a frozen policy with mutable cost (route 4) | Few [M] | high / medium | Gap near the band, so many replications are needed. rav1d passes all of dav1d's tests [S] |
| **Pebble vs RocksDB** | Go reimplementation that inherits RocksDB's file formats and is a subset by design [S] | Pebble performance PRs [M] | Go runtime and garbage collection as frozen [M] | LSM state: memtable flush, L0 compaction triggers [M] | high / high | Same interface only at the key-value API, so a harness is needed; Pebble v2 cannot open RocksDB databases [S] |
| **BusyBox or toybox vs GNU, on cu1's harness** | Size-first design [M] | Fix history [M] | With uutils on the same cells: **same reference, two contracts** | Buffer thresholds [M] | medium / low | Weaker on your complexity and statefulness criteria |

**Recommendation:**
- **The existing cases first** (§4.2). cu1 is also timely: uutils has shipped by default on Ubuntu since 25.10 [S], and Ubuntu's switch surfaced performance gaps that were then fixed, which are human-fix ground truth [S]. On 26.04 the GNU binaries stay installed alongside, as `gnucp`, `gnusha256sum` and so on [S].
- **Then Kvrocks**, if the goal is real architectural certificates.
- **Or Dolt/Doltgres**, if the goal is a long ground-truth series of closed gaps plus a published floor claim to test.
- **rav1d** gives the best published contract and the diffuse-gap and bounds-check story.

### 4.4 Threats to name in the paper

- Human fixes are a selected sample: the gaps people chose to close. The bound applies to gaps like them.
- Contracts change over time. Making a feature opt-in is itself a contract decision, so date-stamp the contract.
- Server systems are noisier than CLIs, which means larger bands and more replications.
- Agents may know a fix from training. The human-fix track already prefers fixes merged after the training cutoff.
- The simulation's absolute rates depend on its synthetic distribution; only the qualitative pattern transfers.

## 5. References checked

**The three marked "verify" in the draft (all verified [S]):**
- S. Lee, D. Binkley, R. Feldt, N. Gold, S. Yoo, "Causal program dependence analysis", *Science of Computer Programming* 240:103208, Feb 2025.
- M. Foster, R. M. Hierons, D. Shin, N. Walkinshaw, C. Wild, "Using causal inference to test systems with hidden and interacting variables: an evaluative case study", *EASE '25* (best paper on the first author's page).
- J. Siebert, "Applications of statistical causal inference in software engineering", *Information and Software Technology* 159:107198, 2023.

**Found while checking [S]:**
- Giamattei, Guerriero, Pietrantuono, Russo, "Causal reasoning in software quality assurance: a systematic review", *IST* 178, 2025.
- Hulse, Eisty, Menzies, "Shaky structures: the wobbly world of causal graphs in software analytics", *EMSE* 30(5):142, 2025.

**To add, from memory (confident; check page numbers):**
- Curtsinger & Berger, Coz, *SOSP '15*.
- Iqbal, Krishna, Javidian, Ray, Jamshidi, Unicorn, *EuroSys '22*.
- Berger, *Technometrics* 24(4), 1982 (intersection–union tests).
- Kolesár & Rothe, *AER* 108(8), 2018.
- Armstrong & Kolesár, *Econometrica* 86(2), 2018.
- Manski, *Partial Identification of Probability Distributions*, Springer, 2003.
- LaLonde, *AER* 76(4), 1986.
- Cook, Shadish & Wong, *J. Policy Analysis and Management* 27(4), 2008.
- Blumofe & Leiserson, *JACM* 46(5), 1999 (work and span).

## Sources for the project facts

- Workshop call: https://causality-software-engineering.github.io/cause-workshop-2027/ [V]
- rav1d bounty and its rules: https://www.memorysafety.org/blog/rav1d-perf-bounty/ [S]
- rav1d contest fixes: https://ohadravid.github.io/posts/2025-05-rav1d-faster/ [S]
- rav1d optimization report: https://www.memorysafety.org/blog/rav1d-performance-optimization/ [S]
- Dolt reaches sysbench parity with MySQL: https://www.dolthub.com/blog/2025-12-04-dolt-is-as-fast-as-mysql/ [S]
- How Dolt got there: https://www.dolthub.com/blog/2025-12-12-how-dolt-got-as-fast-as-mysql/ [S]
- Doltgres's optimizations and floor claim: https://www.dolthub.com/blog/2026-08-13-doltgres-as-fast-as-mysql-is-slow/ [S]
- Kvrocks: https://github.com/apache/kvrocks [S]
- Kvrocks maintainers on comparing with Redis: https://github.com/apache/kvrocks/discussions/389 [S]
- Kvrocks talk, Percona Live 2026: https://perconalive.com/2026-amsterdam/talks/on-disk-and-redis-compatible-when-kvrocks-beats-valkey-and-when-it-doe/ [S]
- uutils on Ubuntu: https://github.com/uutils/coreutils [S]
- Ubuntu's performance findings: https://www.phoronix.com/news/Ubuntu-Rust-Coreutils-Perf [S]
- Ubuntu 26.04 setup: https://computingforgeeks.com/ubuntu-2604-rust-coreutils-guide/ [S]
- Pebble: https://github.com/cockroachdb/pebble [S]
