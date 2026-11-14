# Classifying gaps before repair: theory and proofs

*Working draft for the CauSE 2027 paper (paper 1), 5 Nov 2026. The vocabulary is gapCR's: cells, states, seeds, the A/A band, gap/mechanism/work_component/state_variable/fix nodes, verification types (I-same … X-inf), evidence classes E1–E6, the boundary track (`workflow/boundary.py`) and the residual classes (`gapgraph/vocab.py`). The question is how to decide, before any repair is attempted, whether a robust gap is* fixable *or* architectural*, and to prove the decision sound.*

---

## 0. Results in brief

1. **Definition.** Let $\Delta^\ast$ be a gap's **residual**: the smallest gap any admissible change to the system can reach. The gap is *architectural* when $\Delta^\ast$ exceeds the A/A band. The admissible changes are fixed by a declared **architecture contract**, a set $F$ of frozen mechanisms (§2).
2. **Identification without intervention (Thm 2).** Frozen mechanisms cannot be toggled, but they often switch at an input threshold. The boundary track's estimand is the system's jump minus the reference's jump at that threshold, which is a **difference-in-discontinuities**. Under stated continuity assumptions it identifies the causal effect of the mechanism switch on the system. *Intervene where you can; use discontinuities where you can't.*
3. **Architectural certificate (Thm 3, sound).** The gap is provably architectural if a frozen mechanism
   - is identified as a cause,
   - **dominates** every admissible plan (it runs on all of them), and
   - has a **cost floor**, from unit-cost dose-response, that alone exceeds the reference's time by more than the band.

   This decides the class without trying a repair.
4. **Where the existing evidence fits (Thms 4–6).**
   - *Exhaustion* is complete only over **configuration plan classes**, and says nothing about code-level fixes.
   - A *reference knock-out* identifies a missing feature but not whether adding it is admissible.
   - *A boundary that follows a knob* is evidence of **configurability** inside the knob's range.
5. **The current `classify()` has a hole (Counterexample 1).** When a frozen and a mutable mechanism switch at the same boundary, "boundary test + deep layer" certifies architectural although clamping the mutable one closes the gap. §6 proposes five amendments.
6. **Soundness and which accuracy matters (Thm 7).**
   - A certificate fails only by **overestimating the floor**, and the graph can cause that in exactly two ways:
     - an **under-enumerated admissible space**: a missing bypass plan, or a missing way to route less work to a frozen operator;
     - **mutable cost counted as frozen**: a mechanism mislabelled frozen, or a co-switching mutable mechanism's cost attributed to a frozen one.
   - The false-architectural probability is bounded by the probability of those errors plus the error levels of the floor's confidence bounds.
   - Every other graph error (spurious plans, missing frozen operators, frozen mechanisms labelled mutable, extra edges) costs completeness, never soundness.
   - The synthetic check in §7 behaves exactly so. False architectural labels:
     - 0 with a correct graph or with floor-deflating errors;
     - rising with the floor-inflating errors;
     - 30% of fixable gaps under today's `classify()` rule, even with a correct graph.
7. **Why causal (§8).**
   - The class is defined by what would happen under every admissible intervention.
   - Passive data cannot determine it. Prop 8 gives two systems with identical observational behaviour, one architectural and one fixable.
   - An admissible bypass that the default planner never chooses *never appears in passive data*, so correlational evidence cannot establish dominance.
   - Correlation is enough for ranking suspects, not for certifying architecture.

---

## 1. Setting (gapCR objects)

- **System and reference.** A case compares a system $Y$ (`sys_key`) with a reference $R$ (`ref_key`) implementing the same interface, over cells $c$ (queries or commands on fixed data), states $s$ (for example statistics states S/T) and seeds.
- **Execution model.** For engine $E$ and an admissible intervention $\iota$:
  - the engine runs a plan $\pi_E(c,s,\iota)$, a set of operators reflecting the *work components* that actually execute;
  - latency is $T_E=\sum_{o\in\pi} t_o$;
  - a measurement is $T_E\,e^{\varepsilon}$, with median-zero multiplicative noise $\varepsilon$ whose spread the A/A band $b$ captures (p95 of within-engine A/A pairs, stratified by reference latency);
  - for parallel branches, replace the sum on that branch by a max. Every result below holds with "sum" replaced by any monotone, non-negative combination, provided the floor in Thm 3 uses the same combination.
- **Gap.** $g(c,s)=\log T_Y-\log T_R$, defined on noise-free latencies.
  - It is estimated by the digest's median over rounds of the log ratio of block means.
  - The gap is **robust slower** when the estimate exceeds $b$ with the same sign in every seed (`digest.classify_state`).
  - The band therefore plays two roles: a noise threshold for measurements, and the practical-equivalence margin in the class definitions below.
- **Unit costs.** An operator $o$ does $u_o(c,s)$ units of work (rows, bytes, calls) at unit cost $\kappa_o$, so $t_o=\kappa_o u_o$. Deterministic counters (E1) measure $u_o$, and dose-response (E3) estimates $\kappa_o$.

## 2. Admissible interventions, the residual, and the classes

**Architecture contract.** Partition the system's mechanisms into frozen ($F$) and mutable ($M$).
- $F$ is a declaration, for example the storage or file format (L3) and anything the project rules out. It is stated per case before any classification and registered with a hash, like every other gapCR registration.
- **Admissible interventions** $\mathcal I$:
  - $\mathcal I_{cfg}$: settings of existing system knobs (configuration);
  - $\mathcal I_{code}$: code changes to mechanisms in $M$, including new plans or operators inserted at extension points owned by $M$.
- **Query rewrites are excluded.** They change the workload, not the system; they are workarounds, not fixes.

**Definition 1 (residual and classes).** For a robust slower gap,
$$\Delta^\ast(c,s)=\inf_{\iota\in\mathcal I} g_\iota(c,s).$$
| gapCR class | Condition |
|---|---|
| `configuration` | Some $\iota\in\mathcal I_{cfg}$ gives $g_\iota\le b$ |
| `fixable_next` | Not configuration, but some $\iota\in\mathcal I_{code}$ gives $g_\iota\le b$ |
| `architectural` | $\Delta^\ast > b$ |
| *(mixed)* | $b<\Delta^\ast<g$: part of the gap is fixable, the residual is architectural |
| `architectural_candidate` | Evidence is consistent with architectural but no certificate (§5) |
| `unexplained` | No identified mechanism |

"Structural" or "fixable" in earlier notes means `configuration` ∪ `fixable_next`.

"Architectural" is a **universal statement over $\mathcal I$**. It can be proved only by an argument that covers all admissible interventions without enumerating them: a *certificate*.

**Remark (restricting admissibility).**
- A project may narrow $\mathcal I$, for example to changes that cause no regression beyond the band on registered control cells.
- Narrowing $\mathcal I$ can only raise $\Delta^\ast$, and can only enlarge the set of operators that every admissible plan contains.
- So a certificate computed for the wider set stays valid for any narrower one, and no-regression constraints never cost soundness.

## 3. Identification

### Theorem 1 (witnesses: proving a gap is *not* architectural)

Let $\iota\in\mathcal I$ be applied, with its deterministic marker confirming that it took effect (leg D of gapCR's sufficiency rule). Let $U_\iota$ be a $(1-\alpha)$ upper confidence bound on $g_\iota$. If $U_\iota\le b$, then declaring $\Delta^\ast\le b$ errs with probability at most $\alpha$.

*Proof.* By the definition of the infimum, $\Delta^\ast\le g_\iota$. If $\Delta^\ast>b$, then $g_\iota>b\ge U_\iota$, so the bound failed to cover $g_\iota$. That happens with probability at most $\alpha$. ∎

The logic is a single witness: one admissible change that closes the gap refutes "architectural". The rest of the sufficiency rule attributes the closure to $\iota$:
- S: the same sign in nearly every seed;
- M: beyond a matched A/A null, with Holm correction.

That attribution matters for naming the fix, not for the class.

### Theorem 2 (boundary identification: a difference-in-discontinuities)

**Setup.** A cell family $c(x)$ indexed by an integer running variable $x$ (fields, rows, bytes …). A deterministic witness $w(x)$ (a plan token, opcode or counter: O-det) shows mechanism $m$ switching on in the system at $x^\ast$; bisection finds $x^\ast$ exactly (`boundary.locate`). Write the log of a measurement of engine $E$ as
$$\mu_E(x)+\beta_E\,\mathbb 1[x\ge x^\ast]+\varepsilon_E ,$$
with $\mu_E$ smooth and $\varepsilon_E$ median-zero noise, so that $\log T_E(x)=\mu_E(x)+\beta_E\,\mathbb 1[x\ge x^\ast]$.

**Assumptions.**
- **(B1) Reference stability:** no reference mechanism switches at $x^\ast$. Check it by comparing the reference's plans and deterministic counters at $x^\ast-1$ and $x^\ast$.
- **(B2) Smoothness:** each $\mu_E$ is twice differentiable near $x^\ast$, with $|\mu_E''|\le K_E$.
- **(B3) Common shocks:** any discontinuity at $x^\ast$ other than a mechanism switch moves both engines' log time equally. Examples are the data or the environment crossing a size threshold. In other words, the non-mechanism parts of $\beta_Y$ and $\beta_R$ coincide.
- **(B4) Exclusivity:** no other system mechanism switches at $x^\ast$. The certificate checks "witness flips exactly at $x^\ast$" and "same plan elsewhere" cover mechanisms that show in the plan. Mechanisms that switch inside an operator do not show there; Counterexample 1 shows why *mutable* ones must be clamped.

**Claim.** Let $\delta_m$ be the causal effect on $\log T_Y$ of switching $m$ on at $x^\ast$, that is $do(m{=}\text{on})$ vs $do(m{=}\text{off})$ with $x$ held fixed. The boundary track's estimand (`boundary.jump`)
$$\Delta=[\log T_Y(x^\ast)-\log T_Y(x^\ast{-}1)]-[\log T_R(x^\ast)-\log T_R(x^\ast{-}1)]$$
satisfies
$$\Delta-\delta_m=[\mu_Y(x^\ast)-\mu_Y(x^\ast{-}1)]-[\mu_R(x^\ast)-\mu_R(x^\ast{-}1)].$$
The bias is the difference in the two engines' local slopes.
- The ladder's local linear fit on each side (`boundary.local_linear_jump`) removes the first-order slope difference, leaving bias $O\big((K_Y+K_R)h^2\big)$ for ladder spacing $h$.
- Placebo pairs off the boundary check (B2) and (B3) away from $x^\ast$: they should show $\Delta\approx 0$.

*Proof.*
1. By (B1) and (B4), the only mechanism switch at $x^\ast$ in either engine is $m$'s, in the system; its contribution to $\beta_Y$ is $\delta_m$.
2. By (B3), the common shocks cancel in the difference.
3. Subtracting the two engines' first differences leaves $\delta_m$ plus the slope terms.
4. A Taylor expansion of $\mu_E$ on each side bounds the slope terms after the local linear correction. This is the standard regression-discontinuity argument (Hahn, Todd & van der Klaauw 2001), applied to a difference of two units (difference-in-discontinuities; Grembi, Nannicini & Troiano 2016). ∎

**Why it matters.** $\delta_m$ is an *interventional* quantity (Rung 2), identified **without intervening on $m$**. For frozen mechanisms, which cannot be toggled, thresholds are the main route to causal identification. This closes the identifiability gap on the frozen side.

## 4. Certificates

### Theorem 3 (architectural certificate)

For a robust slower gap at $(c,s)$, let $\Pi_{\mathcal I}(c,s)$ be the set of plans the system can run under some $\iota\in\mathcal I$. It is derived from code: the planner's alternatives, knobs, and extension points owned by $M$. Suppose:
- **(C1) Dominance:** a set $D\subseteq F$ of frozen operators appears in every plan of $\Pi_{\mathcal I}(c,s)$.
- **(C2) Floor:** for each $o\in D$, $t_o\ge \underline\kappa_o\,\underline u_o$ under every $\iota$, where:
  - $\underline\kappa_o$ is a lower confidence bound on the frozen unit cost (E3 dose-response; frozen, so no $\iota$ changes it);
  - $\underline u_o$ is the fewest units of work $o$ can receive under any $\iota$ (upstream mutable mechanisms may reduce it, for example by projection; take the minimum over $\Pi_{\mathcal I}$).
- **(C3) The floor beats the band:** $\log\sum_{o\in D}\underline\kappa_o\underline u_o-\log \overline T_R(c,s)>b$, where $\overline T_R$ is an upper confidence bound on the reference's latency.

Then $\Delta^\ast(c,s)>b$: the gap is architectural. With confidence bounds, the conclusion holds whenever the bounds cover; by a union bound, that is with probability at least $1-\alpha_\kappa-\alpha_R$.

*Proof.* Take any $\iota\in\mathcal I$, with plan $\pi_\iota\in\Pi_{\mathcal I}$.
1. By (C1), $D\subseteq\pi_\iota$.
2. Operator times are non-negative and add up, so $T^\iota_Y\ge\sum_{o\in D}t_o\ge\sum_{o\in D}\underline\kappa_o\underline u_o$ by (C2).
3. System interventions do not change $T_R$, and $T_R\le\overline T_R$.
4. Therefore $g_\iota\ge\log\sum_{o\in D}\underline\kappa_o\underline u_o-\log \overline T_R>b$ by (C3).
5. Every $g_\iota$ is at least the same constant, which exceeds $b$, so the infimum does too. ∎

**What each premise needs from gapCR.**
- (C1): a code-derived plan space (S-src) cross-checked by O-det plans. Observation alone cannot establish (C1); see §8.
- (C2):
  - E1 counters for $u_o$, and E3 dose-response for $\kappa_o$;
  - identification that the cost is $o$'s own: Thm 2 with mutable co-switchers clamped, or E2 clamping where possible;
  - the plan space, for $\underline u_o$: the least work any admissible plan routes to $o$ (for example after a mutable filter pushdown), not the default plan's work.
- (C3): the digest's reference latency.

**Mixed gaps.** If (C1)–(C2) hold but (C3) fails, the floor still lower-bounds the residual: $\Delta^\ast\ge\log(\text{floor}/\overline T_R)$. The surplus $g-\log(\text{floor}/\overline T_R)$ upper-bounds what any fix can remove.

### Theorem 4 (exhaustion is complete only over configuration plan classes)

Assume **plan sufficiency for configuration**: for $\iota\in\mathcal I_{cfg}$, $g_\iota=G(\pi_\iota)$ up to noise. Knobs act only through the plan, and operator code is unchanged. Let $\Pi_{cfg}$ be the finite set of plans reachable by configuration, enumerated from code. Suppose every $\pi\in\Pi_{cfg}$ was run, and its gap's lower confidence bound exceeds $b$, with simultaneous Holm correction over $|\Pi_{cfg}|$ plans. Then the gap is not configuration-fixable.

*Proof.* $\min_{\iota\in\mathcal I_{cfg}}g_\iota=\min_{\pi\in\Pi_{cfg}}G(\pi)$, and every term was shown to exceed $b$. ∎

**Limits.** Exhaustion says nothing about $\mathcal I_{code}$. A mutable operator can be made cheaper without changing the plan. So **exhaustion alone never certifies architectural** (§7: 79% of fixable gaps labelled architectural); it rules out only `configuration`.

### Theorem 5 (reference knock-out identifies a feature, not a class)

If disabling a reference feature $\varphi$ brings the gap within the band ($\log T_Y-\log T_{R^{-\varphi}}\le b$), the gap is *explained* by $\varphi$: the system lacks $\varphi$'s effect. The gap is architectural **only if** adding $\varphi$ to the system requires a change in $F$.

*Proof and counterexample.* The knock-out is an intervention on the reference, so it identifies the cause. Whether the system can gain $\varphi$ depends on whether $\varphi$'s insertion point lies in $F$, which the contract decides, not the knock-out. If the insertion point lies in $M$, the gap is `fixable_next` despite a successful knock-out. ∎

### Theorem 6 (a boundary that follows a knob points to configurability)

Suppose the switch point moves with a system knob $k$ over its admissible range $K$, as $x^\ast(k)$. Suppose also that $m$ carries the gap (Thm 2): with $m$ off, the gap at $x$ is within the band. Then any cell with $x<\sup_{k\in K}x^\ast(k)$ is configuration-fixable. If $m$ carries only part of the gap, the knob removes that part and the rest is classified on its own.

*Proof.* Choose $k\in K$ with $x^\ast(k)>x$; then $m$ is off at $x$, and the gap is within the band by assumption. Setting $k$ is in $\mathcal I_{cfg}$, so it is a witness; Thm 1 turns its measurement into a statistical guarantee. ∎

So "follows the knob" supports **identification**, and supports **architectural** only for cells beyond the knob's reach. A compile-time constant counts as a knob only if changing it is admissible, that is, the constant lies in $M$.

### Counterexample 1 (co-switching mechanisms)

A frozen operator $f$ (cheap) and a mutable operator $m'$ (expensive) both switch on at $x^\ast$. The boundary test passes, $f$ sits in a deep layer, and $f$'s witness flips exactly at $x^\ast$. "Boundary test + deep layer" therefore certifies architectural. But a code change that makes $m'$ cheaper, or a clamp of $m'$, closes the gap. The gap is `fixable_next`.

Theorem 2's (B4) fails here, and the jump is not $f$'s effect. **Repair:** clamp every *mutable* co-switcher (E2, mediator by clamping) and require the jump to persist. Mutable mechanisms *can* be clamped, which is exactly the "intervene where you can" half of the method.

## 5. The decision procedure and its soundness

**Procedure** (per robust gap, before any repair; every step uses only pre-repair evidence):
1. **`configuration`:** a configuration witness, that is an $\iota\in\mathcal I_{cfg}$ whose upper confidence bound on the gap is within the band (Thm 1).
2. **`fixable_next`:** the identified cause set (I-same/E4, O-det/E1, E2 clamp, or Thm 2) contains a mutable mechanism whose removal or emulation blocks the gap (a mutable vertex cut between the divergence and the gap node), or a feature-absence cause with an insertion point in $M$ (Thm 5).
   - This label is a prediction that the repair then tests (rebuild-and-disappear); it is not a certificate.
   - If step 3 would also fire, the evidence is inconsistent: audit the graph before labelling.
3. **`architectural`:** Theorem 3's (C1)–(C3) hold. Where the culprit was identified at a boundary, (B1)–(B4) hold, with mutable co-switchers clamped.
4. **`architectural_candidate`:** an identified frozen cause, but dominance or the floor is not established, or exhaustion only (Thm 4).
5. **`unexplained`:** otherwise.

### Theorem 7 (soundness, and which accuracy matters)

**Assumptions.**
- (A1) **Complete admissible space:** the known plan space contains every admissible plan, and $\underline u_o$ is the least work any of them routes to $o$.
- (A2) **Frozen cost only:**
  - every mechanism labelled frozen is in $F$;
  - the cost attributed to it is its own, so the identification assumptions of the evidence used hold: (B1)–(B4) for boundaries, with mutable co-switchers clamped, and determinism for O-det.
- (A3) Costs are non-negative, and the floor combines them as the system does (sum, or max over parallel branches).

**Claim (soundness).** Under (A1)–(A3), the procedure labels a fixable gap `architectural` with probability at most $\alpha_\kappa+\alpha_R$, the error levels of the floor's and the reference's confidence bounds. With exact costs it never does.

*Proof.* The label requires (C1)–(C3).
1. (A1) makes the computed $D$ a subset of every admissible plan, so (C1) holds.
2. (A2) and (A3) make the computed floor a lower bound on the time $D$ takes under any $\iota$. So (C2) holds whenever the confidence bounds cover.
3. Thm 3 then gives $\Delta^\ast>b$. ∎

**Claim (error bound).** Without the assumptions, by a union bound,
$$P(\text{false architectural})\le P(\neg\text{A1 for this gap})+P(\neg\text{A2 on }D)+P(\neg\text{A3})+\alpha_{\kappa}+\alpha_R .$$

**Which graph accuracy matters.** The certificate fails only by **overestimating the floor**: the computed floor exceeds the least time the system can reach. The graph can cause that in exactly two ways:
1. **An under-enumerated admissible space** (¬A1):
   - a missing bypass plan, which leaves operators in the dominator set that some admissible plan avoids;
   - a missing work reduction, which keeps $\underline u_o$ at the default plan's work.
2. **Mutable cost counted as frozen** (¬A2):
   - a mutable mechanism labelled frozen;
   - a co-switching mutable mechanism's cost attributed to a frozen one (Counterexample 1).

Every other error lowers the floor, so it costs completeness, never soundness:
- spurious plans in the known space, which shrink the dominator set;
- frozen mechanisms labelled mutable, or missing from the graph;
- extra edges.

This is the precise sense in which "accuracy matters". It tells the graph builder where to spend verification effort:
- enumerate admissible plans and work reductions from code;
- audit the frozen/mutable partition, and the attribution of cost at each boundary.

**Not complete.** Gaps with $\Delta^\ast>b$ exist that the procedure leaves as candidates, for example when no single frozen dominator set reaches the floor, or under non-additive costs. Soundness, not completeness, is the property the downstream decision needs: skipping repairs.

## 6. Proposed amendments to `classify()` (for discussion; code unchanged)

| Current rule | Issue | Amendment |
|---|---|---|
| `boundary_test and (exhaustion or reference_knockout or unit_cost or follows_knob)` and deep layer → architectural | Co-switching mutable mechanisms (Counterexample 1). Exhaustion, knock-out and follows-knob do not establish dominance or a floor (Thms 4–6) | Architectural only with dominance (C1, plan space from code) and a floor (C2–C3, from `unit_cost` evidence); boundary attribution requires mutable co-switchers clamped (E2) |
| `follows_knob` counts toward architectural | Evidence of configurability within the knob's range (Thm 6) | Record the knob's admissible range. Cells within reach → `configuration`, once a witness passes; beyond reach → may support architectural |
| `reference_knockout` counts toward architectural | Identifies a missing feature; class depends on the insertion point (Thm 5) | Record the insertion point's layer or owner. In $M$ → `fixable_next` |
| `deep_layers=('L3','L4')` with L4 = configuration | Configuration mechanisms are the *most* admissible to change; declaring them frozen inflates false architectural labels (A2) | Replace layer depth with the registered frozen set $F$. If L4 means build-time configuration that the project rules out, say so in the contract |
| `exhaustion` | Complete only over configuration plan classes | Use it to rule out `configuration`, not to certify `architectural` |

## 7. Synthetic check of the theorems (`theory/sim_certificates.py`)

**Model.**
- Random operators: frozen or mutable, with log-uniform costs.
- Random plans: the default plus up to three alternatives, about half of them reachable only through mutable code (the "bypasses").
- A code change can make a mutable operator up to 10× cheaper.
- The reference latency is set so that the default gap is robust slower.
- **Ground truth** is $\Delta^\ast$, by enumeration.

**Classifiers.**
- `certificate`: Thm 3, computed from what the graph knows.
- `classify_today`: `boundary.classify()` with unit-cost evidence.
  - The boundary track locates the default plan's costliest operator, and the label is architectural iff that operator is labelled frozen (a deep layer).
  - This reading is generous to the rule: it locates the operator that carries most of the time.
- `config_exhaustion`: Thm 4's exhaustion read as a certificate. The label is architectural iff every configuration-reachable plan, as it runs today, stays beyond the band.

**Graph errors**, injected only into what the classifiers know:
- floor-inflating: missing bypasses ($p_{miss}$), and mutable operators labelled frozen ($q_{lab}$);
- floor-deflating: a spurious plan added to the known space ($p_{extra}$), and frozen operators labelled mutable or missing ($q_{unfreeze}$);
- every grid point uses the same instances and the same error draws (common random numbers).

**Run.** 20,000 instances, seed 7: `python3 theory/sim_certificates.py --n 20000 --seed 7`, about 5 s. Raw output is in `sim_certificates_results.{md,json}`. Of the instances, 10,058 are truly architectural and 9,942 fixable.

**Table A. The certificate under graph errors**

| $p_{miss}$ | $q_{lab}$ | $p_{extra}$ | $q_{unfreeze}$ | False architectural (rate among fixable) | Completeness | Precision |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | **0 (0.000)** | 0.69 | 1.00 |
| 0.1 | 0 | 0 | 0 | 129 (0.013) | 0.70 | 0.98 |
| 0.3 | 0 | 0 | 0 | 393 (0.040) | 0.71 | 0.95 |
| 0.5 | 0 | 0 | 0 | 646 (0.065) | 0.73 | 0.92 |
| 0 | 0.1 | 0 | 0 | 434 (0.044) | 0.71 | 0.94 |
| 0 | 0.3 | 0 | 0 | 1258 (0.127) | 0.74 | 0.86 |
| 0.3 | 0.1 | 0 | 0 | 884 (0.089) | 0.73 | 0.89 |
| 0 | 0 | 0.3 | 0 | **0 (0.000)** | 0.61 | 1.00 |
| 0 | 0 | 0 | 0.3 | **0 (0.000)** | 0.50 | 1.00 |
| 0 | 0 | 0.5 | 0.5 | **0 (0.000)** | 0.29 | 1.00 |

**Table B. The three classifiers with a correct graph**

| Classifier | Architectural labels | False architectural (rate among fixable) | Recall among architectural | Precision |
|---|---|---|---|---|
| `certificate` | 6,927 | **0 (0.000)** | 0.69 | 1.00 |
| `classify_today` | 9,828 | 2,963 (0.298) | 0.68 | 0.70 |
| `config_exhaustion` | 17,894 | 7,836 (0.788) | 1.00 | 0.56 |

**Reading.**
- **Sound with a correct graph.** The certificate makes **zero** false architectural labels among 9,942 fixable gaps, and certifies 69% of the truly architectural ones. The rest stay candidates (Thm 7).
- **Only the floor-inflating errors matter.** False labels appear only with those errors, and grow with them. The floor-deflating errors leave soundness intact and cost only completeness, which falls to 29% when both are at 0.5. This is the asymmetry Thm 7 predicts.
- **Today's rule is unsound with a perfect graph.** It has about the same recall as the certificate (0.68 vs 0.69), but labels 30% of fixable gaps architectural. At $q_{lab}=0.3$ that rises to 51% (Table 3 of the results file).
- **Exhaustion is the mirror image.** It is complete (recall 1.00) but unsound, labelling 79% of fixable gaps architectural, because it cannot see code-level fixes (Thm 4).
- **Robustness.** A second seed (11) gives the same pattern; no rate in the three tables differs by more than 0.014.
- **Caveats.**
  - Absolute rates depend on the synthetic distribution and should not be quoted as properties of real systems; the qualitative pattern is the result.
  - Completeness rising with floor-inflating errors is an artefact: more labels, not better ones.
  - The simulation injects one form of each floor-inflating error: missing plans and mislabelled operators. Missing work reductions and misattributed co-switch costs are covered by the theory only.

## 8. Why causal evidence is necessary for this classification

**Proposition 8 (passive data cannot determine the class).** Passive data are any number of measurements of the system as it is built and configured, across any cells and states. Two systems can have identical passive data and different classes: one architectural, one fixable.

*Proof (a concrete pair).*
1. Take two systems that differ only in a capability nobody exercises. In both, every default plan decodes whole rows through a frozen decoder $f$ whose floor exceeds the band.
   - In the first system, $f$ offers no other way to read the data.
   - In the second, $f$ also exposes a per-column read that no default plan calls, and that is cheap enough to bring the gap within the band.
2. Both systems run the same plans at the same costs on every passive run, so their passive data are identical.
3. In the first system every admissible plan decodes whole rows, so the gap is architectural (Thm 3).
4. In the second, a change to the mutable executor can call the per-column read, which brings the gap within the band, so $\Delta^\ast\le b$. ∎

**Consequence.** A classifier that uses passive data alone gives both systems the same label and errs on one of them. So it is either unsound, or it never certifies such gaps. The missing information is structural (the plan space and the components' interfaces, from code) or interventional (forcing a plan), which is what the certificate's premise (C1) asks for.

- **In gapCR's terms.** Timing associations and default-plan observations (O-timed, and even O-det on default plans) cannot establish (C1). Only code (S-src: the plan space and extension points) or an intervention that forces the plan (I-same) can. A correlational classifier is blind to precisely the error that Thm 7 shows breaks soundness.
- **Co-switching makes association ambiguous.** In Counterexample 1 every mechanism that switches at $x^\ast$ correlates perfectly with the gap. Only clamping (E2, an intervention on the mutable side) separates them.
- **gapCR's verification hierarchy is Pearl's ladder,** and the certificate draws only on its causal rungs:

  | gapCR evidence | Rung |
  |---|---|
  | O-timed, X-inf | association |
  | O-det on content-identical twins | a controlled comparison: deterministic, all else equal |
  | I-same, E2 clamps | intervention |
  | Boundary jumps | natural experiments |

  The theory explains *why* the admission rule needs I-same or O-det: they are the evidence types that satisfy the certificate's premises.
- **Where correlation is enough:** ranking suspects for investigation, and single-cause gaps whose cells are distinctive. Never for certifying "architectural".

## 9. Making it empirical ("prove it" on real cases)

1. **Retrospective soundness test with human fixes (`workflow/humanfix.py`).** For each case:
   - build the graph blind on the parent commit, as the human-fix track already does;
   - run the procedure;
   - register the later human fixes.

   Scoring:
   - A **soundness violation** is a gap certified architectural on the parent commit that is within the band on the fix commit, re-measured on the same cells.
   - Report $v$ violations among $n$ human-closed gaps, with an exact one-sided bound (Clopper–Pearson; with $v=0$, the rule of three gives at most $3/n$ at 95%).
   - Fixes that change a declared-frozen mechanism test the contract, not the certificate: report them separately.
   - Prefer fixes merged after the agents' training cutoff, as the track already does.
   - Threat: human-closed gaps are a selected sample (the fixes people chose to make), so the bound applies to gaps like them.
2. **Planted ground truth.** Gaps created by toggling known mutable mechanisms (fixable by construction), against gaps that cross a frozen mechanism declared in the contract.
3. **Boundary studies on frozen thresholds.** Thm 2 estimates with placebos, plus clamps of mutable co-switchers, on at least one threshold per case.
4. **Ablations matching Thm 7.** Remove code-derived bypass enumeration, or swap the audited partition for layer depth, and show the false-architectural rate move as predicted.

## 10. References (✓ confident; *verify* before citing)

- Hahn, Todd & van der Klaauw, "Identification and estimation of treatment effects with a regression-discontinuity design", *Econometrica* 69(1), 2001 ✓
- Imbens & Lemieux, "Regression discontinuity designs: a guide to practice", *J. Econometrics* 142(2), 2008 ✓
- Grembi, Nannicini & Troiano, "Do fiscal rules matter?", *AEJ: Applied Economics* 8(3), 2016 (difference-in-discontinuities) ✓
- Pearl, *Causality*, 2nd ed., 2009 ✓; Pearl & Bareinboim, transportability, *Statistical Science* 29(4), 2014 ✓
- Lengauer & Tarjan, dominators, *TOPLAS* 1(1), 1979 ✓
- Clopper & Pearson, *Biometrika* 26(4), 1934 ✓; Hanley & Lippman-Hand, "If nothing goes wrong, is everything all right?", *JAMA* 249(13), 1983 (rule of three) ✓
- Holm, *Scand. J. Statistics* 6(2), 1979 ✓
- Lee, Binkley, Feldt, Gold & Yoo, Causal Program Dependence Analysis — *verify venue*
- Foster et al., "Using causal inference to test systems with hidden and interacting variables", EASE 2025 — *verify*
- Siebert, statistical causal inference in SE, *IST* 2023 — *verify*
