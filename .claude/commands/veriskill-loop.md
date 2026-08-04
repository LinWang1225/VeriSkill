---
description: "VeriSkill v6：current_batch → G 候选技能 → D 静态审查/打回 → Oracle 同题对比 → D 学规则 → 候选提交"
argument-hint: "rounds=12 batch=24 oracle_frac=0.25 max_gd_revisions=2 revise_audit=1 min_oracle_scored=2 min_improvements=1 max_regressions=0 replay_K=3 train_ratio=0.8 split_seed=0 edit_budget_g=6 edit_budget_d=4 eval_every=3 final_test_max=20 eval_baseline=true"
allowed-tools: Task, Read, Write, Edit, Bash, Glob, Grep
---

你是 VeriSkill v6 的流程编排者。你只负责数据隔离、候选版本、调用顺序、门控、回滚和记账；技能内容由 G/D 子 Agent 决定。

## 唯一正确的算法流程

评估对象是 G 生成的**候选 skill library**，不是旧轨迹答案。

```text
current_batch 训练轨迹
        ↓
G 读取整批轨迹，提炼 candidate skills
        ↓
D 同时读取轨迹、baseline skills、candidate skills 和 manifest
        ├─ REVISE  → 把具体反馈退回 G，最多修订 max_gd_revisions 次
        ├─ PASS    → 进入 Oracle
        └─ ABSTAIN → 进入 Oracle
                         ↓
Oracle 在同一批条目上分别运行 baseline 与同一 candidate fingerprint
                         ↓
baseline-candidate 配对真值
        ├─ 给 D：更新候选审查规则库
        ├─ 给 G：保存 regression / unresolved failure，下一轮使用
        └─ 门控：只有真实净提升且无超限 regression 才提交 candidate
```

另外，每轮最多抽查 `revise_audit` 个 D=REVISE 候选条目，用于发现 D 过度打回。REVISE 候选无论抽查结果如何都不在该轮直接提交；抽查只校准 D。

## 核心不变量

1. G 只编辑 `rounds/r<N>/candidate/iter<K>/`，绝不直接编辑 `workspace/actor_skills/`。
2. D 的 `review_candidate` 模式只读；只有 `learn_from_oracle` 模式可编辑 `workspace/critics/`。
3. Oracle 的 baseline 和 candidate 必须针对相同 item、相同 checker/truth，并记录同一 candidate fingerprint。
4. `pool/traj/` 与 `pool/traj.full/` 是只读训练数据。Oracle 新轨迹单独保存，绝不替换原始池。
5. 没有 `pool/checkers/<id>.sh` 或 `pool/truth/<id>.md` 的条目可以供 G/D 静态阅读，但不能进入 Oracle 门控真值。
6. `truth_source=redo`、环境故障、缺少配对或指纹不一致的记录不进入候选接受判断，也不训练 D。
7. test split 只用于 checkpoint/final evaluation，绝不进入 G、D 或 Oracle 反馈记忆。
8. D PASS 只表示“值得进入 Oracle”，不表示候选应被提交。
9. candidate 只有通过 baseline-candidate 真值门控后才能原子提交为正式 G。
10. 旧版 `verify.sh` 可保留作轨迹诊断，但不得再作为主循环第一步，也不得把它的 pass/fail 直接喂 G。

## 参数

```text
rounds=12              总轮数；续跑时从 ledger.round+1 到 rounds
batch=24               current_batch 大小
oracle_frac=0.25        PASS/ABSTAIN 候选进入 Oracle 的配对样本比例
max_gd_revisions=2      D=REVISE 后允许 G 修改的最大次数，不含首稿
revise_audit=1          每轮抽查多少个 REVISE 条目以校准 D
min_oracle_scored=2     候选门控所需可靠 baseline-candidate 配对下限
min_improvements=1      接受候选至少需要多少个 baseline fail→candidate pass
max_regressions=0       接受候选允许的 baseline pass→candidate fail 上限
replay_K=3              同一训练条目最多进入多少个 current_batch
train_ratio=0.8         train/test 划分比例
split_seed=0            划分种子
edit_budget_g=6         G 单次候选生成/修订编辑预算
edit_budget_d=4         D 每轮 learn_from_oracle 编辑预算
final_test_max=20       checkpoint/final 最多评估 test 条目数
eval_every=3            每 N 轮评估正式 G；0 表示只做 final
eval_baseline=true      是否在 r0 评估正式 G
```

兼容旧 launcher：

- 只传 `audit_frac` 时，把它当作 `oracle_frac`；
- 只传 `edit_budget` 时，同时作为 `edit_budget_g` 和 `edit_budget_d`；
- `rubric_threshold` 参数在 v6 主流程中忽略并记录说明。

本次参数：

```text
$ARGUMENTS
```

## 固定目录

| 对象 | 路径 |
|---|---|
| 正式 G | `workspace/actor_skills/` |
| D 规则库 | `workspace/critics/` |
| 原始训练轨迹 | `pool/traj/`、`pool/traj.full/` |
| 数据划分 | `pool/meta.json` |
| 候选流程工具 | `lib/candidate_flow.py` |
| 本轮 batch | `rounds/r<N>/current_batch.list` |
| 本轮轨迹只读副本 | `rounds/r<N>/current_batch/` |
| baseline 快照 | `rounds/r<N>/baseline_skills/` |
| 候选版本 | `rounds/r<N>/candidate/iter<K>/` |
| G manifest | `rounds/r<N>/manifests/iter<K>.json` |
| D review | `rounds/r<N>/reviews/iter<K>.json` |
| Oracle 队列 | `rounds/r<N>/oracle_queue.jsonl` |
| baseline 新轨迹/结果 | `rounds/r<N>/oracle/baseline/`、`baseline.jsonl` |
| candidate 新轨迹/结果 | `rounds/r<N>/oracle/candidate/`、`candidate.jsonl` |
| 配对比较与门控 | `rounds/r<N>/comparison.jsonl`、`decision.json` |
| Oracle→D | `rounds/r<N>/feedback/oracle_to_d.jsonl` |
| Oracle→G | `rounds/r<N>/feedback/oracle_to_g.jsonl` |
| 跨轮 G 经验 | `experience/oracle_to_g/` |
| D 校准历史 | `experience/oracle_to_d/` |
| 候选指标 | `stats/candidate_eval.jsonl` |
| 正式 G test 时间序列 | `stats/test_eval.jsonl` |
| 状态 | `ledger.json` |

## Setup

### 1. 预检

必须存在：

- `pool/traj/`
- `pool/meta.json`
- `oracle_run.sh`
- `eval_test.sh`
- `lib/pool.py`
- `lib/candidate_flow.py`
- `tools/start_v6_experiment.py`
- `.claude/agents/g-improve.md`
- `.claude/agents/d-improve.md`

缺失即停止，不自造替代实现。

若 `ledger.json` 已存在但 `flow_version != 6`，立即停止。不要在旧轮次上续训，提示先执行：

```bash
python3 tools/start_v6_experiment.py --label before_v6
python3 tools/start_v6_experiment.py --label before_v6 --apply \
  --recompute-split --split-seed "$split_seed" --train-ratio "$train_ratio"
```

第一条只显示归档与重置计划，第二条才执行。默认会归档旧 rounds/stats/history/ledger、清空旧 G/D，并在存在 `pool/traj_orig/` 时恢复不可变原始轨迹。需要用旧 G 做 warm start 时显式加 `--preserve-actor`；不建议保留旧 critics。

创建缺失目录：

```bash
mkdir -p workspace/actor_skills workspace/critics rounds history stats \
  experience/oracle_to_g experience/oracle_to_d
: > /dev/null
[ -f stats/candidate_eval.jsonl ] || : > stats/candidate_eval.jsonl
[ -f stats/test_eval.jsonl ] || : > stats/test_eval.jsonl
```

检查：

```bash
python3 -m py_compile lib/candidate_flow.py
bash -n oracle_run.sh
bash oracle_run.sh --fingerprint
python3 lib/extract.py --check pool/traj
```

### 2. 登记 train/test

```bash
python3 lib/pool.py register \
  --meta pool/meta.json \
  --traj-dir pool/traj \
  --seed $split_seed \
  --train-ratio $train_ratio
```

只允许 `split=train` 进入 current_batch。容量不足时先报告可运行轮数。

### 3. 初始化 ledger

不存在时写：

```json
{
  "flow_version": 6,
  "round": 0,
  "g_version": 0,
  "d_version": 0,
  "candidate_attempts": 0,
  "accepted_candidates": 0,
  "rejected_candidates": 0,
  "oracle_attempts": 0,
  "oracle_failures": 0
}
```

这些字段必须实际维护：

- `flow_version`：固定为 6，用于阻止旧流程状态续训；
- `round`：完成到第几轮；
- `g_version`：正式 G 成功提交次数；
- `d_version`：D 规则编辑通过门控次数；
- `candidate_attempts`：产生候选首稿次数；
- `accepted_candidates` / `rejected_candidates`；
- `oracle_attempts` / `oracle_failures`：baseline 和 candidate 调用分别计数。

### 4. r0 快照与可选基线

```bash
cp -a workspace/actor_skills history/r0_G_initial
cp -a workspace/critics history/r0_D_initial
```

`eval_baseline=true` 时：

```bash
bash eval_test.sh --meta pool/meta.json --out-dir rounds/r0_test_eval \
  --max $final_test_max --seed 0 --round 0 --g-version 0 \
  --series stats/test_eval.jsonl
```

该评估只读 test，不产生任何 G/D 反馈。


## 断点续跑与幂等

watchdog 可能在一轮中途重启编排者。续跑时必须先检查现有产物，不能重复抽样、重复提交或重复累计指标：

1. `$R/current_batch.list` 已存在时，不再调用 `pool.py sample`，直接使用原 batch。
2. `$R/candidate_state.json`、baseline 和 candidate 已存在时，`candidate_flow.py prepare` 会返回 `resumed=true`；不得使用 `--force`，除非该轮已明确废弃并人工确认。
3. 已存在且通过校验的 manifest/review 直接复用；只有文件缺失、JSON 非法或指纹不匹配时才重派对应 Agent。
4. Oracle JSONL 按 item 去重。重启后只运行 baseline/candidate 中缺失的一侧，不重复调用已成功的一侧。
5. `decision.json` 已存在且 baseline/candidate 内容指纹仍匹配时，不重复 compare。确需重跑 compare 时，`stats/candidate_eval.jsonl` 会按 round+candidate_version 覆盖，不重复追加。
6. `candidate_flow.py commit` 是幂等的：正式 G 已等于已接受候选时返回 `already_committed=true`。ledger 的 g_version/accepted_candidates 只能在本轮首次提交后增加一次。
7. 每个阶段完成后写空 marker：`sample.done`、`g_iter<K>.done`、`review_iter<K>.done`、`oracle.done`、`d_learn.done`、`commit.done`、`round.done`。marker 只能在对应输出校验通过后创建。
8. ledger.round 只在 `round.done` 写好后推进。
9. **resume 时按 marker 判断入口**：若 `$R/commit.done` 已存在但 `$R/round.done` 不存在，说明 commit 完成但 checkpoint eval（step 11）未跑或中断——必须先补跑 step 11 的 eval 和记账，写 `round.done`，再推进 ledger.round。不得跳过 checkpoint 直接进入下一轮。

# 每轮流程

设当前轮为 `r`，轮目录为 `R=rounds/r$r`。

## 1. 抽取 current_batch

```bash
mkdir -p "$R/current_batch"
python3 lib/pool.py sample \
  --meta pool/meta.json \
  --round "$r" \
  --batch "$batch" \
  --replay-k "$replay_K" \
  --out-batch "$R/current_batch.list"
```

把轨迹复制成只读本轮输入，不移动、不覆盖原池：

```bash
while IFS= read -r id; do
  [ -n "$id" ] || continue
  cp "pool/traj/$id.md" "$R/current_batch/$id.md"
  [ -f "pool/traj.full/$id.md" ] && \
    cp "pool/traj.full/$id.md" "$R/current_batch/$id.full.md"
done < "$R/current_batch.list"
chmod -R a-w "$R/current_batch"
```

```bash
touch "$R/sample.done"
echo "[$(date +%H:%M:%S)] r$r: sample done ($(wc -l < "$R/current_batch.list" 2>/dev/null || echo 0) items)" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 2. 准备 baseline 与候选 iter0

```bash
python3 lib/candidate_flow.py prepare \
  --actor workspace/actor_skills \
  --round-dir "$R"
```

读取 `candidate_state.json`，记录 `baseline_fingerprint`。从此到候选决策完成前，正式 G 不得变化。

## 3. G 生成候选

派发 `g-improve`，明确给出：

- `current_batch.list=$R/current_batch.list`
- `current_batch=$R/current_batch/`
- `baseline_skills=$R/baseline_skills/`
- `candidate_skills=$R/candidate/iter0/`
- `manifest_out=$R/manifests/iter0.json`
- `candidate_version=r$r-i0`
- `base_fingerprint`
- 最近若干 `experience/oracle_to_g/*.jsonl`
- `edit_budget_g`

G 返回的 JSON 原样保存为 `$R/g-result-iter0.json`。manifest 必须由 G 写到指定路径。

验证：

```bash
python3 lib/candidate_flow.py validate-manifest \
  --manifest "$R/manifests/iter0.json" \
  --batch "$R/current_batch.list" \
  --candidate-dir "$R/candidate/iter0" \
  --base-fingerprint "<baseline_fingerprint>" \
  --out "$R/manifests/iter0.validated.json"
```

验证失败：该轮候选无效，不调用 Oracle，记录 rejected，进入记账。

```bash
touch "$R/g_iter$k.done"
echo "[$(date +%H:%M:%S)] r$r: G iter$k done" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 4. D 审查候选，必要时打回 G

令 `k=0`。**review 前先快照 critics**，用于事后校验 D 在只读模式没有篡改规则库：

```bash
cp -a workspace/critics "$R/critics_before_review"
critics_fp_before="$(python3 lib/candidate_flow.py fingerprint --skills-dir workspace/critics)"
```

派发 `d-improve mode=review_candidate`，明确给出：

- current_batch、baseline、candidate iterK；
- validated manifest；
- `workspace/critics/` 只读；
- `candidate_version=r$r-i$k`；
- 实际 candidate fingerprint。

保存为 `$R/reviews/iter$k.json`。

**review 后校验 critics 未被篡改**：

```bash
critics_fp_after="$(python3 lib/candidate_flow.py fingerprint --skills-dir workspace/critics)"
if [ "$critics_fp_before" != "$critics_fp_after" ]; then
  echo "[r$r] 警告：D 在 review_candidate 模式修改了 critics，从快照回滚" >&2
  rm -rf workspace/critics && cp -a "$R/critics_before_review" workspace/critics
fi
```

若指纹不一致：D 违反了只读约束，从快照恢复 critics，记录违规，该轮 D review 结果仍可用但标记 `critics_tampered=true`。

然后验证 review：

```bash
python3 lib/candidate_flow.py validate-review \
  --review "$R/reviews/iter$k.json" \
  --batch "$R/current_batch.list" \
  --candidate-fingerprint "<candidate_fingerprint>" \
  --out "$R/reviews/iter$k.validated.json"
```

### D=REVISE 且 k < max_gd_revisions

```bash
python3 lib/candidate_flow.py clone-iteration \
  --round-dir "$R" --from-iter "$k" --to-iter "$((k+1))"
```

再次派发 G，额外提供：

- `previous_manifest=$R/manifests/iter$k.validated.json`
- `d_feedback=$R/reviews/iter$k.validated.json`
- 新 candidate 目录、manifest 路径和 candidate_version。

验证新 manifest，再让 D review。最多修订 `max_gd_revisions` 次。

### 防止无效争论

若 D 连续两次给出本质相同的 REVISE 反馈，而 G manifest 已逐条回应，下一次 review 应优先 ABSTAIN，交给 Oracle；编排者不得让两个 Agent 无限循环。

达到最大修订次数仍为 REVISE：不再打回，进入”REVISE 抽查”，本轮候选不能提交。

```bash
touch "$R/review_iter$k.done"
_dv=$(python3 -c "import json;print(json.load(open('$R/reviews/iter$k.validated.json')).get('verdict','?'))" 2>/dev/null || echo "?")
echo "[$(date +%H:%M:%S)] r$r: D review iter$k = $_dv" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 5. 构建 Oracle 队列

预算：

```text
B = ceil(oracle_frac × 实际 current_batch 大小)
```

调用：

```bash
python3 lib/candidate_flow.py build-oracle-queue \
  --batch "$R/current_batch.list" \
  --review "$R/reviews/iter$k.validated.json" \
  --checker-dir pool/checkers \
  --truth-dir pool/truth \
  --budget "$B" \
  --revise-audit "$revise_audit" \
  --round "$r" \
  --out "$R/oracle_queue.jsonl"
```

队列规则由工具确定：

- PASS/ABSTAIN：优先 `unjudgeable`、`partial`，再覆盖样本；
- REVISE：最多抽查 `revise_audit` 个；
- 没有 checker/truth 的条目排除；
- 按轮次确定性选择。

队列为空时：候选不能提交；记录“无可靠 Oracle 覆盖”。

## 6. Oracle 同题运行 baseline 与 candidate

先从 queue 提取 ID，每个 ID 必须运行两次，且两个结果都成功才形成配对。

baseline：

```bash
VERISKILL_ACTOR_SKILLS="$R/baseline_skills" \
  bash oracle_run.sh "pool/traj/$id.md" \
  --new-traj-out "$R/oracle/baseline/$id.md"
```

candidate：

```bash
VERISKILL_ACTOR_SKILLS="$R/candidate/iter$k" \
  bash oracle_run.sh "pool/traj/$id.md" \
  --new-traj-out "$R/oracle/candidate/$id.md"
```

stdout 分别逐行写：

- `$R/oracle/baseline.jsonl`
- `$R/oracle/candidate.jsonl`

每跑完一个 item 的 baseline+candidate 两侧，往 loop 日志记一行：

```bash
echo "[$(date +%H:%M:%S)] r$r: Oracle $id done" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

规则：

- 每次调用最多原样重试一次；
- baseline/candidate 任一环境失败，该 item 不形成配对；
- 不覆盖 `pool/traj`；
- 新轨迹只保存在本轮 Oracle 目录；
- Oracle 前后重新计算 candidate 目录内容指纹，必须保持不变；同一批 candidate Oracle 结果中的 `skill_hash` 必须唯一。该 `skill_hash` 是原脚本运行指纹，不要求与 `candidate_flow.py` 的内容指纹字符串相等；
- Oracle 不加载 critics。

```bash
touch "$R/oracle.done"
echo "[$(date +%H:%M:%S)] r$r: Oracle done" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 7. 配对比较与候选门控

```bash
python3 lib/candidate_flow.py compare \
  --review "$R/reviews/iter$k.validated.json" \
  --baseline "$R/oracle/baseline.jsonl" \
  --candidate "$R/oracle/candidate.jsonl" \
  --baseline-dir "$R/baseline_skills" \
  --candidate-dir "$R/candidate/iter$k" \
  --round "$r" \
  --candidate-version "r$r-i$k" \
  --gd-revisions "$k" \
  --min-scored "$min_oracle_scored" \
  --min-improvements "$min_improvements" \
  --max-regressions "$max_regressions" \
  --out-comparison "$R/comparison.jsonl" \
  --out-decision "$R/decision.json" \
  --out-to-d "$R/feedback/oracle_to_d.jsonl" \
  --out-to-g "$R/feedback/oracle_to_g.jsonl" \
  --metrics stats/candidate_eval.jsonl
```

四种 paired outcome：

- `improvement`：baseline fail → candidate pass；
- `regression`：baseline pass → candidate fail；
- `retained_pass`：两者都 pass；
- `unresolved_fail`：两者都 fail。

默认接受条件全部成立：

- D 最终不是 REVISE；
- scored pairs ≥ `min_oracle_scored`；
- improvement ≥ `min_improvements`；
- regression ≤ `max_regressions`；
- `net_gain=improvement-regression > 0`；
- candidate pass count 不低于 baseline。

不得人工改写 `decision.json` 绕过门控。

## 8. Oracle 反馈给 D 更新规则库

只要有可靠配对，就派发 `d-improve mode=learn_from_oracle`，给出：

- review、manifest、冻结 candidate；
- `$R/feedback/oracle_to_d.jsonl`；
- baseline/candidate 新轨迹；
- `workspace/critics/`；
- 最近的 `experience/oracle_to_d/`；
- `edit_budget_d`。

调用前快照：

```bash
cp -a workspace/critics "history/r${r}_D_before"
```

D 返回保存为 `$R/d-learn-result.json`。检查：

- 只修改 critics；
- frontmatter 合法；
- R ID 全库唯一；
- 没有具体答案、题面、test ID；
- 新 hard 规则有足够跨样本证据；
- 单文件改动不超过 40%；
- 旧的明显反例仍不会被新规则误杀。

失败则整体回滚 critics。通过则：

- `d_version += 1`；
- 复制 `$R/feedback/oracle_to_d.jsonl` 到 `experience/oracle_to_d/r$r.jsonl`。

D 的规则更新不影响本轮已经冻结的 candidate decision。

```bash
touch "$R/d_learn.done"
echo "[$(date +%H:%M:%S)] r$r: D learn done" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 9. Oracle 反馈给 G

无论候选是否接受，只要 `$R/feedback/oracle_to_g.jsonl` 非空，就复制到：

```text
experience/oracle_to_g/r<r>.jsonl
```

该文件只来自 train 条目，只保存 regression 与 unresolved failure。下一轮 G 可读取；本轮不在 Oracle 后再次无限修订，避免重复烧预算和选择性过拟合。

## 10. 提交或拒绝候选

### decision.accepted=true

```bash
python3 lib/candidate_flow.py commit \
  --actor workspace/actor_skills \
  --candidate "$R/candidate/iter$k" \
  --decision "$R/decision.json" \
  --backup "history/r${r}_G_before_commit"
```

提交成功后：

- `g_version += 1`
- `accepted_candidates += 1`
- 保存 `history/r${r}_G_accepted/`

### decision.accepted=false

正式 G 保持不变：

- `rejected_candidates += 1`
- 候选目录和 decision 保留供分析；
- 不把 candidate 内容复制进 workspace。

`candidate_attempts` 每轮首稿成功产生后加 1，不按 revision 次数增加。

```bash
touch "$R/commit.done"
_acc=$(python3 -c "import json;d=json.load(open('$R/decision.json'));print('accept' if d.get('accepted') else 'reject')" 2>/dev/null || echo "?")
echo "[$(date +%H:%M:%S)] r$r: commit done ($_acc)" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

## 11. checkpoint 与记账

当 `eval_every > 0` 且 `r % eval_every == 0`，只评估正式 G：

```bash
bash eval_test.sh --meta pool/meta.json \
  --out-dir "$R/test_eval" \
  --max "$final_test_max" \
  --seed 0 \
  --round "$r" \
  --g-version "<ledger.g_version>" \
  --series stats/test_eval.jsonl
```

更新 ledger 的 `round=r` 和调用计数，原子写回。

每轮在 `report.md` 追加一行，至少包含：

```text
round | candidate | final D verdict | gd revisions | scored pairs |
improvement | regression | retained | unresolved | net gain |
accepted | g_version | d_version | Oracle failures
```

checkpoint eval 完成且 ledger 原子写回后：

```bash
touch "$R/round.done"
echo "[$(date +%H:%M:%S)] r$r: round done" >> "${VERISKILL_LOOP_LOG:-/dev/null}"
```

只有 `round.done` 存在时，ledger.round 才推进到 `r`。resume 时若 `commit.done` 存在但 `round.done` 不存在，必须补跑 checkpoint eval 再写 `round.done`。

## 停止条件

满足任一条件停止：

- 跑满 rounds；
- train 池按 replay_K 耗尽；
- 累计 Oracle 最终环境故障率超过 30%，且 attempts ≥ 10；
- 连续 3 轮没有候选被接受、D 没有新增有效校准，并且 current_batch 的主要未覆盖簇不再变化；
- 用户明确停止。

“D 连续 PASS”不是收敛；“G 技能文件数量不变”也不是收敛。

## 最终评估与报告

结束时：

1. 用正式 G 在固定 test 子集运行 `eval_final_same_sample.sh`（同时测 G 成功率和 D 判别准确率）：

```bash
bash eval_final_same_sample.sh --meta pool/meta.json \
  --out-dir rounds/final_test \
  --max "$final_test_max" \
  --seed 0 \
  --round "<ledger.round>" \
  --g-version "<ledger.g_version>" \
  --series stats/test_eval.jsonl
```

2. 画 `stats/test_eval.jsonl` 的 G success-rate 曲线；
3. 汇总 `stats/candidate_eval.jsonl`。

必须分别报告：

### G 演进

- 提议候选数与接受数；
- candidate accept rate；
- 每轮 improvement / regression / net_gain；
- baseline 与 candidate paired pass rate；
- 正式 G 的 held-out test success rate；
- test 的 fail→pass 与 pass→fail 配对变化。

### D 演进

- PASS / REVISE / ABSTAIN 数量；
- `correct_accept`；
- `false_accept`；
- `supported_revise`；
- `false_reject_evidence`；
- `useful_abstain`；
- 平均 G-D revision 次数；
- 因 D 打回后 uncovered/partial 是否下降。

### 成本与可靠性

- baseline 与 candidate Oracle 调用总数；
- 可靠 scored pairs；
- unscored 排除数；
- 环境失败数；
- 每个 accepted candidate 的 Oracle 成本。

禁止继续报告旧定义的“D 判轨迹 TP/FP/FN/TN”作为主指标。v6 的 D 评估对象是候选 skill 的审查决策。
