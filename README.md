# VeriSkill v6

VeriSkill 让生成器技能库 G 与判别器规则库 D 共同演进，但两者的职责严格分开：

- **G** 从一批训练轨迹中提炼一版隔离的候选 skill library；
- **D** 同时阅读训练轨迹、正式技能、候选技能和 G 的 coverage manifest，判断候选是否应修改、可以进入 Oracle，或仅凭文本无法判断；
- **Oracle** 在相同训练条目上分别运行正式技能和冻结的候选技能，用 checker/truth 做 baseline-candidate 配对比较；
- Oracle 结果用于校准 D，并决定候选是否原子提交为新的正式 G。

主循环不再是“D 判旧轨迹 → fail 喂 G”。正确流程是：

```text
current_batch
    ↓
G 生成 candidate skills
    ↓
D review_candidate
    ├─ REVISE  → G 修订，最多若干次
    ├─ PASS    → Oracle
    └─ ABSTAIN → Oracle
                     ↓
       baseline 与 candidate 同题执行
                     ↓
       improvement / regression / retained / unresolved
             ├─ D learn_from_oracle
             ├─ 失败经验进入下一轮 G
             └─ 通过门控才提交 candidate
```

## 关键约束

1. G 只编辑 `rounds/r<N>/candidate/iter<K>/`，不能直接改正式技能库。
2. D 的 `review_candidate` 模式只读；`learn_from_oracle` 模式才允许修改 critics。
3. 原始 `pool/traj/` 和 `pool/traj.full/` 保持只读，Oracle 新轨迹不再覆盖训练池。
4. 没有 checker/truth 的条目不进入候选接受门控。
5. D=REVISE 的候选每轮可抽查少量条目，用于发现 D 的错误拒绝，但该候选不在当轮直接提交。
6. 候选只有在相同条目上比 baseline 产生正净增益、且 regression 不超过阈值时才能提交。
7. test split 只做 checkpoint/final evaluation，不进入 G/D 反馈。

## 目录布局

```text
<repo>/
├── .claude/
│   ├── commands/veriskill-loop.md
│   └── agents/
│       ├── g-improve.md
│       └── d-improve.md
├── lib/
│   └── candidate_flow.py          # 候选准备、校验、Oracle 配对、门控、提交、报告
├── tools/
│   └── start_v6_experiment.py     # 归档旧实验并初始化干净 v6 状态
├── workspace/
│   ├── actor_skills/              # 当前正式 G
│   └── critics/                   # D 的候选审查规则库
├── pool/
│   ├── traj/                      # 原始训练轨迹，只读
│   ├── traj.full/                 # 原始完整版轨迹，只读
│   ├── checkers/                  # 可靠真值来源
│   ├── truth/                     # 可靠真值来源
│   └── meta.json                  # train/test split 与 replay 计数
├── rounds/r<N>/
│   ├── current_batch.list
│   ├── current_batch/
│   ├── baseline_skills/
│   ├── candidate/iter<K>/
│   ├── manifests/iter<K>.json
│   ├── reviews/iter<K>.json
│   ├── oracle/{baseline,candidate}/
│   ├── comparison.jsonl
│   ├── decision.json
│   └── feedback/{oracle_to_d,oracle_to_g}.jsonl
├── experience/
│   ├── oracle_to_d/
│   └── oracle_to_g/
└── stats/
    ├── candidate_eval.jsonl       # G/D 共演进主指标
    └── test_eval.jsonl            # 正式 G 的 held-out 指标
```


## 从 v4/v5 安全开始新实验

旧 ledger、used_count、rounds、旧式 critics 和被 Oracle 滚动替换过的轨迹不能直接续训。补丁提供安全迁移工具：

```bash
# 先只看计划，不修改文件
python3 tools/start_v6_experiment.py --label before_v6

# 归档旧实验并冷启动 v6；存在 pool/traj_orig 时自动恢复原始轨迹
python3 tools/start_v6_experiment.py --label before_v6 --apply \
  --recompute-split --split-seed 0 --train-ratio 0.8
```

默认行为：

- 把旧 `rounds/`、`stats/`、`history/`、`experience/`、`ledger.json` 和 `report.md` 移到 `archive/before_v6/`；
- 归档并清空旧 G/D；
- 将 `pool/meta.json` 的 `used_count`、`g_version` 重置为 0；
- 若存在 `pool/traj_orig/`，归档当前轨迹后恢复原始只读轨迹；
- 初始化 `flow_version=6` 的 ledger。

需要以旧 G 作为 warm start 时加 `--preserve-actor`。不建议使用 `--preserve-critics`，因为 v5 critics 检查的是答案轨迹，而 v6 critics 检查的是候选 skill。

## 三个 prompt 的职责

### `g-improve.md`

读取整个 current_batch，对轨迹模式聚类，编辑候选技能目录，并写出：

- 轨迹簇；
- 技能改动；
- 每条轨迹的 expected coverage；
- 未覆盖项；
- 对 D 反馈的逐条回应。

### `d-improve.md mode=review_candidate`

不修改规则库。逐条检查候选 skill 是否覆盖轨迹模式，输出：

- `PASS`：静态结构充分，可以进入 Oracle；
- `REVISE`：存在明确、可操作的候选缺陷，返回 G；
- `ABSTAIN`：文本不足以判断真实效果，进入 Oracle。

### `d-improve.md mode=learn_from_oracle`

读取冻结候选上的 baseline-candidate 真值结果，更新候选审查规则。D 主要学习：

- `false_accept`：放行了无效或退化候选；
- `false_reject_evidence`：打回的候选在抽查中出现真实改善；
- 哪些效果必须交给 Oracle，应写成 abstain 规则而不是 hard reject。

## 候选工具

```bash
python3 lib/candidate_flow.py --help
```

常用命令：

```bash
# 准备本轮 baseline 与 candidate/iter0
python3 lib/candidate_flow.py prepare \
  --actor workspace/actor_skills \
  --round-dir rounds/r1

# 校验 G manifest
python3 lib/candidate_flow.py validate-manifest \
  --manifest rounds/r1/manifests/iter0.json \
  --batch rounds/r1/current_batch.list \
  --candidate-dir rounds/r1/candidate/iter0 \
  --base-fingerprint <fingerprint>

# 校验 D review
python3 lib/candidate_flow.py validate-review \
  --review rounds/r1/reviews/iter0.json \
  --batch rounds/r1/current_batch.list \
  --candidate-fingerprint <fingerprint>

# 汇总演进结果
python3 lib/candidate_flow.py report \
  --metrics stats/candidate_eval.jsonl \
  --out-json results/candidate_summary.json \
  --out-md results/candidate_summary.md
```

## 推荐实验参数

快速检查流程：

```text
rounds=2 batch=12 oracle_frac=0.25 max_gd_revisions=1
revise_audit=1 min_oracle_scored=2 min_improvements=1 max_regressions=0
```

中等 pilot：

```text
rounds=6 batch=24 oracle_frac=0.25 max_gd_revisions=2
revise_audit=1 min_oracle_scored=2 min_improvements=1 max_regressions=0
eval_every=3
```

正式实验：

```text
rounds=12 batch=24 oracle_frac=0.25 max_gd_revisions=2
revise_audit=1 min_oracle_scored=2 min_improvements=1 max_regressions=0
replay_K=3 train_ratio=0.8 split_seed=0 eval_every=3 eval_baseline=true
```

旧 launcher 的第三个参数仍可传 `audit_frac`；v6 prompt 会把它映射为 `oracle_frac`。

## 如何判断 G 是否演进正确

主要看：

- accepted candidate 数量和接受率；
- baseline fail→candidate pass 的 `improvement`；
- baseline pass→candidate fail 的 `regression`；
- `net_gain = improvement - regression`；
- 正式 G 在固定 test 子集上的成功率和逐题翻转。

技能文件变多、D 更容易 PASS、训练批次通过率上升，都不能单独证明 G 有效。

## 如何判断 D 是否演进正确

主要看：

- PASS / REVISE / ABSTAIN 分布；
- `false_accept` 是否下降；
- `false_reject_evidence` 是否下降；
- ABSTAIN 是否集中在确实需要真实执行的问题；
- D 打回后，下一候选的 uncovered/partial 数量是否减少；
- 平均 G-D 修订次数是否稳定，而不是持续达到上限。

v6 不再把“D 判轨迹的 TP/FP/FN/TN”作为主指标，因为 D 的直接评估对象已经变成候选 skill。

## OfficeQA 运行

原有 setup、backend、watchdog 和 `oracle_run.sh` 接线可以继续使用。`oracle_run.sh` 已支持通过环境变量切换技能目录：

```bash
VERISKILL_ACTOR_SKILLS=rounds/r1/baseline_skills \
  bash oracle_run.sh pool/traj/q001.md --new-traj-out rounds/r1/oracle/baseline/q001.md

VERISKILL_ACTOR_SKILLS=rounds/r1/candidate/iter0 \
  bash oracle_run.sh pool/traj/q001.md --new-traj-out rounds/r1/oracle/candidate/q001.md
```

点火方式保持不变：

```bash
bash adapters/setup_officeqa_101.sh
bash adapters/launch_loop_101.sh 6 24 0.25
```

运行前建议从空 G、空 D 和干净 ledger 开始新的实验目录；旧 v4/v5 结果可作为历史记录，但不应续训，因为旧监督流程与 v6 的候选审查定义不同。
