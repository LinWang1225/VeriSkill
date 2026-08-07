# CADRE: Calibrated Audit-Driven Refinement of Expertise — Skill Evolution under Scarce Ground Truth

> **草稿说明（写给作者，投稿前删除）**
> 1. 名字 `CADRE` 是占位。不能再用 `VeriSkill` —— 已被 Jia et al. 2026
>    (arXiv:2607.27733) 占用。备选：BACE (Budgeted-Audit Co-Evolution)、ARBITER、CALIBRA。
> 2. 所有标 `[TBD]` 的表格与数字是**尚未跑的实验**，留空待补。已有数字全部来自
>    2026-08-04 ~ 08-06 的 29 轮实跑，可追溯到仓库 `birfy/matscibench-coevolution` 分支。
> 3. 实验计划见文末「实验计划与待补数据」一节。

---

## Abstract

Skill self-evolution lets an LLM agent turn its own failures into reusable procedural
knowledge. Existing methods obtain the failure signal for free and at every step:
self-play agents know the answer they posed, and program-verification agents query a
formal verifier. Neither holds in scientific problem solving, where correctness is decided
by a held-out answer key — a resource that exists but is costly, and whose unrestricted
use makes the resulting system impossible to deploy. The question is therefore not how to
evolve skills with *no* ground truth, but how to evolve them when ground truth is a
**scarce, budgeted resource**.

We present **CADRE**, which splits the signal by cost. A *learned critic* library `D`
supplies dense, answer-free verdicts on every trajectory; a deterministic oracle supplies
sparse ground truth on a stratified sample under a fixed **audit budget**. Audited
outcomes drive two distinct repairs: misjudgments sharpen `D`, and confirmed failures
become new skills in the solver library `G`. Three admission gates (smoke, regression,
promotion) guard each round's edits. The oracle acts as a calibration instrument for the
critic rather than as a reward channel for the solver.

We also identify a measurement pitfall specific to this design. Because the audit queue
is stratified *by the critic's own verdict*, pooling the strata yields a recall figure
that moves with the critic's fail rate rather than its discriminative power. We give the
reweighting that corrects it, and show it changes the conclusion: on MatSciBench, the
naive estimate reports critic recall improving 0.32→0.58, while the corrected estimate is
0.11→0.46 and reveals that *all* of the gain comes from the critic firing more often —
its accuracy conditional on passing a trajectory is unchanged (0.55→0.55).

Over 29 rounds on the MatSciBench metals subset, CADRE raises held-out accuracy from
50.0% to 66.7% (paired: 9 improved, 1 regressed, McNemar exact *p* = 0.0215) using
116 oracle calls. We further report an honest negative result: gains concentrate in the
first ~28 skills and then plateau, with later skills beginning to break problems earlier
skills had solved. We trace this to the critic's flat pass-side discrimination, which
starves the skill generator of learnable failures.

---

## 1 Introduction

An LLM agent that keeps a library of reusable *skills* — task-specific workflows, tool-use
recipes, error-handling procedures — can outperform the same backbone without them
(Li et al. 2026; Zhou et al. 2026). Writing those skills by hand does not scale, so a line
of work has the agent write them itself, distilling lessons from its own execution traces
(Ni et al. 2026; Yang et al. 2026a; Alzubi et al. 2026; Shen, Li, and Zhang 2026).

Every such system needs to know *which* trajectories were wrong. Existing work obtains
this cheaply because of where it sits:

- **Self-play** (Lu et al. 2026; Fu et al. 2026): a proposer generates the problem
  *together with its answer*, so the reward is verifiable by construction.
- **Program verification** (Jia et al. 2026): a formal verifier decides correctness at no
  cost and with no ambiguity.
- **Code / math with executable checks**: unit tests or exact-match answers are available
  at training time.

Scientific problem solving has none of these properties. Correctness is decided by a
benchmark answer key: the resource exists, but consulting it is metered, and consulting it
densely is not merely expensive — it is *the wrong experimental posture*. A system that
reads the key on every rollout cannot be deployed, and a skill library tuned against
unrestricted key access will not transfer to the setting it is meant for. The realistic
regime is therefore neither "ground truth everywhere" nor "no ground truth at all", but a
**budget**: a fixed, small number of authoritative judgments per unit of learning.

This motivates a different decomposition. We keep a second, **learned** library `D` whose
job is to judge trajectories *without the answer*, and we treat `D` itself as an object
to be improved. Ground truth enters only through a **bounded audit**: each round, a small
stratified sample of the batch is sent to a deterministic oracle. Audited outcomes are
used twice — to repair `D` where it misjudged, and to hand `G` a set of *confirmed*
failures to learn from. The oracle is a calibration instrument, not a reward channel.

Two consequences follow, and both are central to this paper.

First, the design makes the critic's quality the binding constraint on skill learning.
`G` only ever sees failures that `D` surfaced; if `D` cannot tell a wrong derivation from
a right one, `G` receives a biased and shrinking supply of learnable material. Our
experiments show exactly this failure mode.

Second, the stratified audit that makes the budget affordable also makes the obvious
metrics wrong. The audit queue draws from `D`'s *fail* set and its *pass* set separately.
Pooling the strata and computing recall as TP/(TP+FN) produces a number that rises
whenever `D` becomes more trigger-happy, independent of whether it discriminates better.
We give the correction and show it reverses the reading of our own results.

Our contributions:

- **Skill evolution under a ground-truth budget.** We formulate skill self-evolution for
  the setting where correctness is observable but rationed, and give a loop that splits
  the signal by cost: a learned critic supplies dense answer-free judgment, a bounded
  oracle audit supplies sparse truth that keeps the critic calibrated.
- **Dual-library co-evolution with admission gates.** Audited outcomes drive separate
  repairs to the critic and the solver library; smoke, regression, and promotion gates
  admit each round's edits, with a regression set built from confirmed true positives.
- **A reweighted critic metric.** We show that verdict-stratified audits make pooled
  recall a sampling artifact, give the reweighting, and demonstrate that it changes the
  conclusion on our own data.
- **An honest account of the plateau.** We report where the method stops working and
  attribute it to a measurable property of the learned critic, rather than reporting only
  the segment where the curve rises.

---

## 2 Related Work

### 2.1 Skill Self-Evolution

Trace2Skill distills trajectory-local lessons into transferable instructions (Ni et al.
2026). SkillOpt and SkillOpt-Lite refine skill text from rollout feedback with validation
gating (Yang et al. 2026a; Shen, Li, and Zhang 2026). EvoSkill analyzes execution failures
and preserves effective skill folders through validation (Alzubi et al. 2026). SkillCAT
contrasts successful and failed trajectories before replaying candidate revisions
(Chen et al. 2026). CoEvoSkills co-evolves a surrogate verifier to provide revision
signals (Zhang et al. 2026), and AutoSkill derives skills from dialogue and interaction
traces (Yang et al. 2026b).

CoEvoSkills is closest to us in spirit — it also learns a verifier — but the surrogate is
used to *supply revision signals*, not as a first-class artifact whose own error profile
is measured and repaired against sparse ground truth. CADRE differs in treating the critic
as a co-equal evolving library with an explicit, audited error budget.

### 2.2 Verification Signals for Agent Learning

Where a sound verifier exists, it can be used directly. VeriSkill (Jia et al. 2026)
attributes program-verification failures to skill deficiencies and admits only revisions
that improve verifier PASS rate; the verifier is free and definitive, so the hard problem
is *attribution*, not *observation*. Self-play systems (Lu et al. 2026; Chen et al. 2025;
Fu et al. 2026) sidestep the issue by generating problems with known targets. SESA
(Fu et al. 2026) additionally couples an evolving skill memory to the self-play frontier.

Our setting removes the assumption these methods share: no free verifier, no
self-generated answer. The signal must be learned, and its learning must be paid for.

### 2.3 Learned Verifiers, Critics, and Judges

LLM-as-judge and process reward models supply scalar feedback where ground truth is
absent, but are typically trained offline and then frozen. Work on self-verification
reports that models are substantially better at recognizing their own errors when given
the answer than without it. CADRE is consistent with that finding and quantifies it in the
evolution setting: our learned critic carries real signal when it *rejects* a trajectory
(precision 0.71 against a 0.55 base rate) and essentially none when it *accepts* one
(0.55, indistinguishable from chance).

---

## 3 Problem Formulation

Let `x` be a task drawn from a distribution `𝒟`, and let `π(· | x, G)` be the agent's
solution policy conditioned on a skill library `G`. A deterministic oracle
`O(x, a) ∈ {0, 1}` decides whether solution `a` is correct, but each call has cost and the
total number of calls is bounded by a budget `B`.

The objective is the usual one,

> `J(G) = E_{x∼𝒟} E_{a∼π(·|x,G)} [ O(x, a) ]`,  and  `G* = arg max_G J(G)`.  (1)

What differs is the information constraint: skill evolution may consult `O` at most `B`
times, and `B ≪ |𝒟| × rounds`.

We therefore introduce a critic library `D` inducing an answer-free verdict

> `v(x, a; D) ∈ {pass, fail}`,  (2)

and use `v` as the dense signal that decides which trajectories are candidates for skill
repair. `D` is itself evolved. Writing `f = P(v = fail)` for the critic's fail rate,
`p = P(O = 0 | v = fail)` for its precision and `m = P(O = 0 | v = pass)` for its pass-side
miss rate, the critic's true recall is

> `Recall(D) = f·p / ( f·p + (1−f)·m )`.  (3)

Equation (3) is the object we care about, and — as Section 4.6 shows — it is *not* what a
pooled count over a verdict-stratified audit estimates.

---

## 4 CADRE

### 4.1 Overview

Each round processes a batch of `N` trajectories through four stages:

```
sample batch  →  ① critic verdicts (answer-free, dense)
              →  ② stratified oracle audit (B/rounds calls)
              →  ③ dual improvement: D-improve (fix misjudgments)
                                     G-improve (fix confirmed failures)
              →  ④ admission gates: smoke | regression | promotion
              →  commit (or roll back), replace audited trajectories in the pool
```

### 4.2 Stage 1: Critic-Scored Batch Verification

`D` reads a trajectory without the reference answer and emits a structured verdict:
a rubric score, the critic rules it fired, a list of *concerns*, and a self-reported
confidence. Rules carry a soft/hard designation; only hard rules flip a verdict directly.

We found the raw rubric score to be effectively binary in practice — of 28 false negatives
in an early phase, 26 carried the maximum score, placing them on top of the true negatives
and making the score useless as a ranking signal. We therefore convert the auxiliary
channels into a penalty on the pass side:

> `adjusted = score − w_s·|rules_fired| − w_c·|concerns| − w_f·(1 − confidence)`,  (4)

and flip `pass → fail` when `adjusted` falls below a threshold. The justification is
empirical: in 27 of those 28 false negatives, `D` had already written the correct doubt
into its `concerns` field and then passed the trajectory anyway. Equation (4) simply stops
discarding that text.

### 4.3 Stage 2: Stratified Oracle Audit under a Budget

`B/rounds` items per round go to the oracle, drawn from three strata:

- **suspected-overkill**: items `D` marked `fail` — estimates precision `p`;
- **random**: uniform over items `D` marked `pass` — estimates miss rate `m`;
- **low-confidence**: `pass` items with the lowest confidence — enriches for likely misses.

The oracle is the benchmark's own deterministic judge, involving no model call. Audited
items are then re-solved under the current library and the fresh trajectories are returned
to the pool, so the pool tracks the evolving solver rather than freezing at round 0.

### 4.4 Stage 3: Dual-Library Improvement

**D-improve** consumes the audit's disagreements. A false positive (critic said fail,
oracle says pass) narrows the offending rule or adds an exclusion. A false negative
(critic said pass, oracle says fail) adds a rule or sub-case naming the missed error
signature, attached to evidence item ids.

**G-improve** consumes *confirmed* failures, clustered by error mechanism rather than by
item, so that a skill generalizes beyond the instance that produced it. Actions are
`new_skill`, `patch`, or `description` (widening a skill's activation triggers).

Both improvers operate under a per-round edit budget.

### 4.5 Stage 4: Admission Gates

- **Smoke gate**: re-run `D` on known-correct trajectories; a flip to `fail` signals the
  round's critic edits introduced an overkill.
- **Regression gate**: a set pinned from *confirmed true-positive* trajectories is re-run
  every round; any flip to `pass` means the library forgot a lesson it had learned. This
  gate exists because pass-side smoke tests do not catch forgetting — in our run, the same
  item was caught at round 6 and missed again at round 15, and another was caught at
  round 3 and missed at rounds 11 and 12.
- **Promotion gate**: a soft rule becomes hard only with sufficient distinct supporting
  evidence and zero attributed false positives.

Failing a gate rolls the round's edits back.

### 4.6 Reweighted Critic Metrics

Because the audit strata are defined *by the critic's verdict*, true positives and false
positives can only arise in the suspected-overkill stratum, and false negatives and true
negatives only in the other two. Pooling them and computing `TP/(TP+FN)` therefore
estimates a quantity that depends on how many audit slots each stratum received — which is
itself a function of `f`. As `f` rises, the pooled figure rises even if `p` and `m` are
unchanged.

The correct estimator combines the stratum-wise quantities with the *full-batch* fail rate
`f` (which is observed for every item, not just audited ones) through Equation (3).
Section 6.5 shows the two estimators disagreeing on our data by a factor of roughly three
and, more importantly, disagreeing about the *mechanism* of improvement.

---

## 5 Experimental Setup

**Benchmarks.** We run the full CADRE loop independently on each of three scientific
benchmarks, chosen to vary the domain, the answer format, and — deliberately — the
*quality of the oracle itself*.

| Benchmark | Domain | Answer form | Oracle | Base rate |
|---|---|---|---|---|
| MatSciBench, `Materials: Metals` (Zhang et al. 2026) | materials science | numeric / closed form | official `rule_judge`: sympy equivalence + 5% relative tolerance, **no model call** | 50.0% |
| SciBench, statistics subset (Wang et al. 2024) | physics / statistics | numeric | deterministic numeric checker with tolerance, **no model call** | `[TBD]` |
| HLE, math subset (Phan et al. 2025) | research-level mixed | open-answer exact match | official HLE judge prompt, **model-based** | `[TBD]` |
| OfficeQA | document / spreadsheet QA | numeric, string, date | deterministic checker over extracted answer | 50.0% |

Two rows are chosen deliberately rather than for convenience. **HLE**'s official judge is
itself an LLM: our claim concerns a *budgeted* oracle, not a perfect one, so this row tests
whether the loop survives when the scarce ground truth is also noisy. **OfficeQA** is not a
scientific reasoning task at all — it requires locating evidence in office documents,
aggregating tabular data, and formatting extracted values — so it tests whether the loop is
specific to closed-form derivation or applies wherever failures have recurring structure.
OfficeQA additionally exhibits genuine *environment* failures (a chart's data points lost
during PDF-to-text extraction, for instance), which we must separate from reasoning
failures; §6.1 shows why that distinction is not cosmetic.

We considered and excluded **GPQA-diamond**: its oracle is ideal (exact letter match, no
model), but an agentic solver is already near ceiling on it, leaving no headroom for skill
evolution to demonstrate anything. We report its measured base rate in the appendix rather
than running the loop.

**Pool construction.** For each benchmark, from a no-skill probe we build a **1:1 balanced
pool**: every incorrectly-solved item plus an equal, difficulty-stratified sample of
correctly-solved items, so that a critic which passes everything scores exactly 50%. Each
pool is split 80/20 train/test by exact quota over a hash ordering with a fixed seed. For
MatSciBench this yields 238 items, 190 train / 48 test; sizes for the other two are in
Table 1.

**Harness alignment.** The solver prompt replicates the benchmark's official protocol
(system prompt, question assembly, answer convention) so that measured accuracy is
comparable to published numbers and so that the no-skill baseline differs from the evolved
system *only* by the skill library.

**Configuration.** Backbone GLM-5.2 for solver, critic, and improvers. Batch 16 per round,
audit 4 per round (25%), edit budget 15, consolidation every 6 rounds. On MatSciBench:
29 rounds, ≈41 hours wall clock, 116 oracle calls over 77 distinct items. The other two
benchmarks use the identical configuration; no per-benchmark tuning is performed.

**Metric.** Accuracy on the held-out split of each benchmark. Held-out splits of this size
carry roughly ±7 points of binomial noise, so we report **paired** comparisons on identical
items and test significance with McNemar's exact test rather than comparing rates alone.

---

## 6 Experimental Results

### 6.1 Main Result

CADRE is run independently on each benchmark under the identical configuration of §5.
Each cell is accuracy on that benchmark's held-out split; the paired columns compare the
evolved library against the no-skill baseline on identical items.

| Benchmark | Skills | No skill | CADRE | Δ | Improved / Regressed | McNemar *p* |
|---|---|---|---|---|---|---|
| MatSciBench (metals) | 37 | 24/48 = 50.0% | **32/48 = 66.7%** | **+16.7** | 9 / 1 | **0.0215** |
| SciBench (statistics) | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` |
| HLE (math) | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` |
| OfficeQA | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` |
| **Average** | — | `[TBD]` | `[TBD]` | `[TBD]` | — | — |

*Table 1: Held-out accuracy per benchmark. Each row is an independent CADRE run; no
skill library is shared across rows.*

On MatSciBench the evolved library improves 9 items and breaks 1, a paired gain that is
significant at *p* = 0.0215 despite the small split. An intermediate checkpoint (round 21,
28 skills) already reaches 66.0%, which we return to in §6.6.

Because each row is a separate run with its own pool, oracle, and skill library, Table 1
measures whether the *loop* works across settings — not whether a library learned in one
domain transfers to another. We make no transfer claim.

**Why the paired columns carry the claim.** An earlier pilot on OfficeQA, run under a
different loop variant (§6.11), illustrates the hazard of reading the rate columns alone.
Its accuracy rose from 8/16 = 50.0% to 11/18 = 61.1% over 11 rounds — an apparent +11.1
points. But the two evaluations lost *different* items to environment failures, and on the
15 items judged in both, the result is 8/15 → 9/15: **one item improved, none regressed,
McNemar *p* = 1.0**. Most of the headline gain was a change in which items happened to
execute, not in how many were solved. We therefore report paired columns everywhere and
treat unpaired rate deltas as uninterpretable.

### 6.2 Harness Control

To rule out that the gain comes from prompt differences rather than skills, we re-ran the
same skill library under the benchmark's official harness and under our solver harness:
66.0% vs 63.8% on the same 47 items — a one-item difference. The skill effect is therefore
not a harness artifact.

### 6.3 Comparison with Baselines `[TBD]`

| Method | Held-out accuracy | Δ vs No-Skill | Oracle calls |
|---|---|---|---|
| No Skill | 50.0% | — | 0 |
| One-pass LLM Skill | | | |
| Human-written Skill | | | |
| Skill-Creator | | | |
| EvoSkill | | | |
| SkillOpt-Lite | | | |
| CoEvoSkills | | | |
| **CADRE (ours)** | **66.7%** | **+16.7** | **116** |

> 未跑。这是投稿的硬缺口——目前只有 No-Skill 一个对照。

### 6.4 Oracle Budget Sweep `[TBD]`

The audit fraction is the central knob: it trades ground-truth cost against critic
calibration quality.

| Audit fraction | Oracle calls | Held-out accuracy | Critic recall (reweighted) |
|---|---|---|---|
| 0.0 (no audit) | 0 | | |
| 0.125 | | | |
| **0.25 (default)** | **116** | **66.7%** | **0.46** |
| 0.50 | | | |
| 1.00 (dense oracle) | | | |

> 未跑。`0.0` 与 `1.00` 两端最关键：前者证明审计不可省，后者给出上界。

### 6.5 Critic Quality Over Time

The mechanism changes described in Section 4.2 were introduced between rounds 17 and 18,
giving a natural before/after split over 116 audits.

| | rounds 1–17 | rounds 18–29 |
|---|---|---|
| Fail rate `f` (full batch) | 0.074 | 0.359 |
| Precision `p` = P(wrong \| fail) | 0.74 | 0.71 |
| Pass-side accuracy = 1 − `m` | 0.55 | **0.55** |
| **Reweighted recall (Eq. 3)** | **0.11** | **0.46** |
| *Naive pooled recall* | *0.32* | *0.58* |

Two readings of the same data. The naive pooled figure suggests the critic became
substantially better at finding failures. The reweighted figure shows recall did rise —
but decomposes it: `f` grew by a factor of 4.9 while `p` fell slightly and pass-side
accuracy did not move at all. The critic did not learn to discriminate; it learned to cast
a wider net. Its signal is real when it rejects (0.71 against a 0.55 base rate) and absent
when it accepts.

### 6.6 Evolution Dynamics and the Plateau

Accuracy does not improve monotonically with library size. Paired on identical items, the
step from a 28-skill library to a 37-skill library yields **4 improved, 3 regressed**,
net +1 item, McNemar **p = 1.0**: statistically indistinguishable from no change, while the
step from 0 to 28 skills carries essentially all of the +16.7 points.

Three of the later-round regressions are items that an earlier library had solved. In one,
the solver's answer became wrong by a factor of ≈4π after a newly added skill redirected
its formula choice. New skills had begun to interfere with old ones.

Additionally, **15 of 48 test items (31%) were never solved in any configuration**, and the
regression gate fired **3 rollbacks** across 29 rounds.

We connect this to Section 6.5: `G` is fed only failures that `D` surfaced. With pass-side
accuracy pinned at chance, roughly half of all real failures never enter the improvement
queue at all, and the ones that do are increasingly the same ones.

### 6.7 Component Ablation `[TBD]`

| Variant | Held-out accuracy | Δ vs Full |
|---|---|---|
| Full CADRE | 66.7% | — |
| w/o critic (audit-only, same oracle budget) | | |
| w/o concern penalty (Eq. 4) | | |
| w/o regression gate | | |
| w/o smoke gate | | |
| w/o promotion gate | | |
| w/o consolidation | | |
| w/o failure clustering (per-item skills) | | |

> 未跑。`w/o critic` 是最重要的一行——它直接回答「学一个判别器是否值得，还是把
> 同样的 oracle 预算直接花在随机抽样上更好」。

### 6.8 Cross-Model Transferability `[TBD]`

Skills evolved with GLM-5.2, deployed unchanged on other backbones.

| Deployment backbone | No Skill | + CADRE skills | Δ |
|---|---|---|---|
| GLM-5.2 (evolution backbone) | 50.0% | 66.7% | +16.7 |
| Qwen3-Max | | | |
| DeepSeek-V4 | | | |
| Claude Opus 4.8 | | | |
| GPT-5.6 | | | |

> 未跑。这条决定技能是「可移植的程序性知识」还是「特定模型的提示词伪影」。

### 6.9 Critic Behaviour Across Benchmarks `[TBD]`

Table 1 reports whether the loop *works*; this table reports whether it works for the same
reason. We repeat the reweighted critic analysis of §6.5 on each benchmark.

| Benchmark | Fail rate *f* | Precision | Pass-side accuracy | Reweighted recall |
|---|---|---|---|---|
| MatSciBench (metals) | 0.074 → 0.359 | 0.74 → 0.71 | 0.55 → 0.54 | 0.11 → 0.46 |
| SciBench (statistics) | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` |
| HLE (math) | `[TBD]` | `[TBD]` | `[TBD]` | `[TBD]` |

The HLE row carries additional weight: its oracle is model-based, so any degradation in
critic calibration there separates "the critic is hard to train" from "the critic was
calibrated against a noisy target".

### 6.10 Variance `[TBD]`

| Seed | Held-out accuracy | Skills | Rounds to plateau |
|---|---|---|---|
| 0 (reported) | 66.7% | 37 | ≈21 |
| 1 | | | |
| 2 | | | |

> 未跑。单次运行无法区分方法效应与运气。

### 6.11 A Prior Loop Variant on OfficeQA

Before the loop described in §4, we ran an earlier variant on OfficeQA for 11 rounds with
55 oracle calls. That variant is *candidate-review* rather than *audit-calibrated*: the
solver library first proposes candidate skills, the critic reviews each candidate
(`REVISE` / `PASS` / `ABSTAIN`), and the oracle then runs a paired baseline-vs-candidate
comparison on the same items to decide admission. The critic never issues verdicts on
ordinary trajectories, so there is no stratified audit and no reweighted-recall question.

| | Rounds | Oracle calls | Accepted / rejected candidates | Paired result |
|---|---|---|---|---|
| Candidate-review variant | 11 | 55 | 9 / 2 | 1 improved, 0 regressed (n = 15), *p* = 1.0 |

We report it for two reasons. First, it is where the environment-failure confound in §6.1
was found. Second, it isolates what the audit contributes: the candidate-review variant
spends its oracle budget confirming skills the solver already proposed, whereas CADRE
spends it discovering failures the solver did not know it had. A controlled comparison of
the two on the same pool is the cleanest available test of that distinction, and is listed
as future work rather than claimed here — the OfficeQA pilot used a different pool, backbone
and budget, so it does not support a like-for-like conclusion.

---

## 7 Case Studies

**Skills that transfer vs. skills that overfit.** Of the items the evolved library newly
solved, several correspond to genuinely reusable conventions — e.g. reporting the
diffraction angle 2θ rather than the Bragg angle θ; applying addition-rule significant
figures (decimal places) rather than multiplication-rule ones to an additive expression.
Others were narrower.

**A dirty benchmark item corrupts a rule.** One pool item carried an empty reference
answer, so the oracle judged it incorrect regardless of the solver's output. It was
audited three times, counted twice as a critic false negative, and — before we caught it —
was written into the supporting evidence of a rule that had been promoted to *hard*.
Automatic quarantine of unjudgeable items is a prerequisite, not a convenience.

**A gate that punishes the fix.** At round 21 the smoke gate flipped a known-correct item
and, per the all-or-nothing rollback policy, discarded all three of that round's critic
edits — two of which were precisely the edits repairing that round's false positives. The
gate's granularity, not its existence, was the defect.

**A measurement artifact that inverts a reading.** Evaluating the held-out split in pool
order shows 28.6% at the halfway point and 66.7% at completion, because the balanced pool
is stored with all originally-failed items first. Any mid-run reading, or any run truncated
early, is systematically pessimistic.

---

## 8 Limitations

- Filled results currently come from **one benchmark, one run, one backbone**. The other
  two rows of Table 1, and §§6.3, 6.4, 6.7, 6.8, 6.10, are unfilled; until they are, the
  claim is existence, not generality.
- Each benchmark is evolved **independently**. We therefore say nothing about whether a
  library learned in one domain transfers to another — that is a different question and we
  do not test it.
- The held-out split has **48 items** (≈±7 points of binomial noise). We mitigate with
  paired testing but cannot escape the sample size.
- The pool is **1:1 balanced by construction**, so absolute accuracies are not comparable
  to standard MatSciBench leaderboard numbers; only within-pool comparisons are meaningful.
- The **critic's pass-side signal is at chance**, which bounds what the loop can achieve.
  We diagnose this but do not fix it.
- The oracle is a **rule-based judge with known parsing behaviours** (LaTeX fractions are
  tokenized digit-wise; restating a quantity in a second unit changes the parsed arity).
  These affect all conditions equally but cap achievable accuracy.

---

## 9 Conclusion

CADRE evolves solver skills where ground truth is a scarce, budgeted resource rather than
a freely available signal, by pairing a dense answer-free critic with a bounded, stratified
oracle audit that keeps that critic calibrated. On MatSciBench metals, it raises held-out
accuracy from 50.0% to 66.7% using 116 oracle calls (paired, *p* = 0.0215).

The more durable contribution may be the negative one. We show that verdict-stratified
audits make pooled critic recall a sampling artifact, give the correction, and use it to
demonstrate that our critic's apparent improvement is entirely an increase in fail rate
rather than in discrimination. Because the skill generator consumes only what the critic
surfaces, that flat pass-side accuracy is a direct, measurable explanation for why skill
gains plateau after roughly 28 skills — and it identifies pass-side discrimination, not
skill generation, as the bottleneck when ground truth must be rationed.

---

## References

*（按投稿模板补齐；以下为已引用条目）*

- Alzubi, S.; Provenzano, N.; Bingham, J.; Chen, W.; Vu, T. 2026. EvoSkill: Automated skill discovery for multi-agent systems. arXiv:2603.02766.
- Chen, K.; Zhong, Q.; Liu, J.; Du, B. 2026. SkillCAT: Contrastive assessment and topology-aware skill self-evolution for LLM agents. arXiv:2606.13317.
- Chen, Y.; Wang, Y.; Zhu, S.; et al. 2025. Multi-agent evolve: LLM self-improve through co-evolution. arXiv:2510.23595.
- Fu, Z.; Li, Z.; Ai, Q.; et al. 2026. Self-Play Meets Skill Evolution: Self-Evolving Search Agents that Pose, Solve, and Remember. arXiv:2607.29468.
- Jia, C.; Zhao, T.; Xiao, Z.; Zhang, W.; Zhou, M. 2026. VeriSkill: A Self-Evolution Framework for Program Verification Skills. arXiv:2607.27733.
- Li, X.; Liu, Y.; Chen, W.; et al. 2026. SkillsBench: Benchmarking how well agent skills work across diverse tasks. arXiv:2602.12670.
- Lu, H.; Wen, Y.; Cheng, P.; et al. 2026. Search Self-Play: Pushing the Frontier of Agent Capability without Supervision. ICLR.
- Ni, J.; Liu, Y.; Liu, X.; et al. 2026. Trace2skill: Distill trajectory-local lessons into transferable agent skills. arXiv:2603.25158.
- Shen, Y.; Li, B.; Zhang, X. 2026. SkillOpt-Lite: Better and Faster Agent Self-evolution via One Line of Vibe. arXiv:2607.03451.
- Yang, Y.; Gong, Z.; Huang, W.; et al. 2026a. Skillopt: Executive strategy for self-evolving agent skills. arXiv:2605.23904.
- Yang, C.; et al. 2026b. AutoSkill. *(待补)*
- Zhang, Y.; et al. 2026. CoEvoSkills. *(待补)*
- Zhang, J.-K.; et al. 2026. MatSciBench. *(待补，见 https://huggingface.co/datasets/JunkaiZ/MatSciBench)*
- Zhou, M.; et al. 2026. *(待补)*

---
---

# 实验计划与待补数据

## 已有（可直接写进论文）

| 编号 | 实验 | 状态 | 位置 |
|---|---|---|---|
| E1 | 主结果：无技能 50.0% → r27 66.7%，配对 9/1，p=0.0215 | ✅ | §6.1 |
| E2 | harness 对照：同技能库两套 harness 差 1 题 | ✅ | §6.2 |
| E3 | 判别器指标（重加权 vs 汇总口径） | ✅ | §6.5 |
| E4 | 平台期：28→37 技能净 +1 题，p=1.0；3 条退步 | ✅ | §6.6 |
| E5 | 案例：脏题污染硬判据、门粒度误伤、池序造成的中途低估 | ✅ | §7 |
| E6 | OfficeQA 旧循环 pilot：11 轮 / 55 次 oracle / 生率 50.0%→61.1%，配对 1 进步 0 退步 p=1.0 | ✅ | §6.11、§6.1 |

## 待跑（按优先级）

### P0 —— 不做就无法投稿

**A′. 多数据集主结果（§6.1、§6.9）**
在 SciBench（统计子集）和 HLE（数学子集）上各跑一遍完整 CADRE，配置与 MatSciBench
完全一致、不做任何逐数据集调参。每个数据集独立建池、独立演进、独立评估，**不跨域复用
技能库**——Table 1 要证明的是「这个循环在不同设定下都成立」，不是「技能可迁移」。

两个 harness 仓库里已有（`benchmarks/hle/`、`adapters/run_rounds_stat.sh` +
`pool/checkers/checker_core_stat.py`），主要工作是建 1:1 平衡池和对齐各自的官方 harness。

选型说明：
- **SciBench 统计子集** —— 判分确定性、零模型调用，与 MatSciBench 同性质，是干净的重复验证
- **HLE 数学子集** —— 官方判分器本身是 LLM。这一条是**故意选的**：论文主张的是「预算内的
  oracle」而不是「完美的 oracle」，HLE 用来测循环在真值本身带噪时还成不成立
- **OfficeQA** —— 根本不是科学推理任务（文档定位、表格聚合、抽取值格式化），用来测这套循环
  是不是只对闭式推导有效。它还有真实的**环境故障**（PDF 转文本丢掉图表数据点等），正好逼我们
  把环境故障和推理失败分开计
- **GPQA-diamond 排除** —— 判分理想（精确字母匹配、零模型），但 agentic solver 已接近天花板，
  没有提升空间。测一下 base rate 写进附录即可，不跑循环

⚠️ **OfficeQA 必须重跑，不能直接用旧数据。** 仓库 main 分支上那 11 轮跑的是
`flow_version: 6` 的**候选审查流程**（G 提候选技能 → D 做 review_candidate → Oracle 做
baseline-vs-candidate 配对比较），和 §4 的审计校准循环是两套东西，直接当 Table 1 一行是错的。
旧数据已作为 §6.11 的对照写进论文，并贡献了 §6.1 里那个「生通过率 +11.1 点、配对后
1 进步 0 退步 p=1.0」的方法论例子。

*预估*：每数据集 建池 ~3 小时 + 29 轮 ≈ 41 小时 + 评估 ~1 小时。三个数据集 ≈ 6 天，可并行。
OfficeQA 单题成本实测约 $1，需单独核预算。

**A. 基线对照（§6.3）**
在同一 48 题 test 集、同一 harness、同一 backbone 下跑：
- One-pass LLM Skill：让模型一次性根据训练集写一版技能库
- Human Skill：人工写 5–10 条材料学技能
- EvoSkill / SkillOpt-Lite / Skill-Creator：开源实现直接跑
- CoEvoSkills：最相关的对照（也学 verifier）

*预估*：每个方法一次演进 + 一次评估。按当前单轮 88 分钟、评估 50 分钟估算，
每方法约 4–8 小时（视其轮数）。5 个方法 ≈ 1.5–2 天。

**B. Oracle 预算扫描（§6.4）**
`audit_frac ∈ {0, 0.125, 0.25, 0.5, 1.0}`，各跑 ~20 轮。
- `0.0` 证明「不审计会怎样」——预期判别器漂移、技能学错东西
- `1.0` 给出上界，同时暴露「密集用答案键」的不可部署性

*预估*：4 组新跑 × 20 轮 ≈ 4 × 30 小时 = 5 天。可并行（如果 #117 的并发能落地）。

**C. 消融（§6.7）**
最关键是 `w/o critic`：把同样的 116 次 oracle 调用直接花在随机抽样上，
不学判别器，看技能能长到什么程度。这一行直接回答「学判别器值不值」。
其余各去一个组件重跑 ~20 轮。

*预估*：7 个变体 × 20 轮 ≈ 8–9 天，可并行。

### P1 —— 决定论文强度

**D. 跨模型迁移（§6.8）**
技能库不变，换 Qwen3-Max / DeepSeek-V4 / Claude Opus 4.8 / GPT-5.6 各评估一次 48 题。
*预估*：4 × 50 分钟 ≈ 4 小时。**性价比最高的一项**，建议优先做。

**E. 多数据集主结果（§6.1、§6.9）** —— 已提到 P0，见下方 A′。

**F. 方差（§6.10）**
换 2 个 split seed 各重跑 29 轮。
*预估*：2 × 41 小时 ≈ 3.5 天。

### P2 —— 加分项

- **G. 技能检索规模实验**：技能库从 10 → 300 条时，全量注入 vs top-k 检索的准确率与
  token 成本曲线。与 ScienceAgent issue #116 直接呼应。
- **H. 判别器 pass 侧的补救**：试若干方案（多次采样投票、给判别器工具执行权、
  反向推导校验），看能否把 pass 侧准确率从 0.55 抬起来。这是论文指出的瓶颈，
  能给出哪怕部分的解法会显著加分。
- **I. 成本核算**：每个方法的 token / 费用 / 墙钟，做一张成本-收益表。

## 跑之前必须先修的三个坑

1. **脏题隔离** —— 参考答案为空的条目自动剔除（当前 `m164` 已污染过一条 hard 判据）
2. **评估集打散** —— `items.list` 固定种子 shuffle，否则中途读数系统性偏低
3. **超时与退避** —— `ROUND_TIMEOUT` 从 7200s 上调（近期单轮均值 88 分钟、最长 224
   分钟），并把网络中断与 429 分开退避（当前一律等 600 秒）

## 建议的最小可投稿集合

如果时间有限，按此顺序：

1. **D 跨模型迁移**（4 小时）—— 性价比最高，一次评估就能拿一行
2. **A′ 多数据集：先只加 SciBench**（2 天）—— 单数据集结论撑不起投稿，第二个数据集是
   从「一个案例」到「一个方法」的分水岭。若还有余力，**第三个优先 OfficeQA 而不是 HLE**：
   它是非科学推理任务，对「这套循环不只对闭式推导有效」这条主张的边际价值最大，而 HLE
   的模型判分器会引入一个需要额外解释的变量。HLE 留到 rebuttal
3. **C 的 `w/o critic` 一行**（1 天）—— 直接回答「学判别器值不值」
4. **B 的 `audit_frac = 0` 与 `= 1.0` 两端**（2 天）—— 标题主张「真值是有限资源」，
   这两端就是该主张的直接证据，缺了标题站不住
5. **A 的 EvoSkill + SkillOpt-Lite 两个基线**（1 天）

约 6–7 天，能撑起「方法在多个设定下有效 + 判别器必要 + 审计预算必要 + 技能可迁移」四条。

注意第 2 项与第 4 项的顺序取舍：如果只能二选一，选 **A′**。审计预算扫描证明的是方法内部
的设计合理性，而第二个数据集证明的是方法本身不是过拟合到一个窄域的偶然产物——审稿人更
在意后者。
