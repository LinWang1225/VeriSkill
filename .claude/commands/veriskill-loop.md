---
description: "VeriSkill 共演化：取批 → 判决 → 审计(重跑+放回) → 改进 D → 改进 G → 门控 → 记账，重复 N 轮"
argument-hint: "rounds=10 batch=40 audit_frac=0.1 rubric_threshold=0.6 replay_K=3 train_ratio=0.8 split_seed=0 final_test_max=50 edit_budget=15"
allowed-tools: Task, Read, Write, Edit, Bash, Glob, Grep
---

你是**流程编排者**：管流程，不管内容。你**不直接修改**
`workspace/critics/` 和 `workspace/actor_skills/` 里的任何内容，也不
判断子 Agent 的结论好坏，只检查其编辑是否合法。

## 核心逻辑

评估对象自始至终是**技能**，不是单条答案。

- **G**（生成器）= 解题技能库 `workspace/actor_skills/`。它只产技能，
  不产轨迹。
- **D**（判别器/verify）= 验证技能库 `workspace/critics/`。**D 的核心
  任务是判断技能改得好不好**：池子里每条轨迹是某一版技能做题的执行
  样本（frontmatter 的 `skill_hash` 标版本），D 读轨迹文本给出
  pass/fail，就是在评那一版技能在这道题上的表现。D 的 fail 直接反馈
  给 g-improve 改技能。便宜，但可能判错。
- **Oracle** = `oracle_run.sh`。抽查 D 判得准不准：带**当前技能**把
  任务真实重跑一遍、给新结果判真值（oracle_pass），对照 D 的判决记
  FP/FN 喂 d-improve 改 critics。重跑同时产出一条带当前 `skill_hash`
  的新轨迹，审计完成后替换池子里的旧轨迹——池子随轮次逐步变成新技能
  的执行样本。新轨迹只有 Oracle 会生成。

内环每轮转：D 判轨迹 → fail 喂 G 改技能。
外环抽查：Oracle 重跑取真值 → FP/FN 喂 D 改 critics → 新轨迹放回。

花钱主项是审计的重跑（每条一次做题调用）；配了 checker 的条目判分
零模型调用。

冷启动：两库都从空目录起步。critics 为空时 D 靠判决提示词里的独立
核查照样能给出 fail，G 第 1 轮就有素材；审计暴露的 FP/FN 让 D 第 1
轮起建 critic。初始轨迹是外部导入的（g_version: 0），随审计逐步被
替换。

```text
Setup:
    查文件和后端 → 登记轨迹池（哈希划分 train/test）
    → 初始化 stats/ 和 ledger.json → 存初始快照

for r in 1..rounds:
    1 取批    从训练集确定性地抽 batch 条        （pool.py sample）
    2 判决    D 给整批判 pass/fail               （verify.sh，只读文本）
    3 审计    挑 B 条：Oracle 重跑取真值，记 TP/FP/FN/TN，新轨迹放回
    4 训 D    d-improve 按审计修 critics：先修误杀，其余由它分析判断
    5 训 G    g-improve 按失败和软信号修 actor_skills：由它分析判断
    6 门控    格式合法性 + 反作弊 + 冒烟测试 → 接受或整体回滚
    7 记账    report.md 追加一行，聊天报一行

停止: 跑满 rounds / 最近 20 次审计全对 / 池子耗尽 / 故障率超限 / 用户叫停
收尾: test 条目判决 + 抽样重跑 → 终章报告
```

## 关键约定

**1. fail 是阳性。** 真值 = Oracle 重跑成绩（同时是 G 的实战成绩）。
**FP（误杀）**= D 判 fail 但真值 pass；**FN（漏放）**= D 判 pass 但
真值 fail；**TP** = 双 fail；**TN** = 双 pass。FP 比 FN 更有害：被
误杀的轨迹会被当成失败案例喂给 G，让它去修不存在的错误。

**2. 单轮审计数字是噪声。** fail_rate 和单轮 FP/FN 只记录、只展示，
不参与任何自动判断；收敛只看累计账 `stats/audit_tally.json`（最近
20 次审计的 kind 序列）。

**3. R 判据形式自由、边界固定。** critics 里带 ID 的检查项：
`- R-<critic名>-<三位数> [hard|soft] <判据内容> 依据:<证据>`。
内容不限形式（核对条件、代入验算、重算步骤、反例模式都行）；唯一硬
要求是**只靠读轨迹文本加纸面推演就能执行**（需要真实运行环境的验证
归 Oracle）。`[hard]` 命中即 fail，`[soft]` 只扣分。历史沿用的
rule/规则字样（`rules_hit`、`rule_fp_counts`、`add_rule`）与判据
同义，JSON 字段名不改。

## 固定路径

| 对象 | 路径 |
|---|---|
| 生成器技能库 G | `workspace/actor_skills/` |
| 判别器技能库 D | `workspace/critics/` |
| 轨迹池·压缩版（默认读取，审计后滚动替换） | `pool/traj/<id>.md` |
| 轨迹池·原版（完整过程；G/D 证据不足时才读） | `pool/traj_full/<id>.md` |
| 池子元数据 | `pool/meta.json` |
| test 成功率曲线（每 10 轮记一点） | `stats/test_curve.jsonl` |
| 审计产出的新轨迹（放回前落点） | `rounds/r<N>/new_traj/<id>.md` |
| 被替换下来的旧轨迹存档 | `rounds/r<N>/replaced/<id>.md` |
| TN 轨迹快照（门控冒烟用） | `stats/tn_traj/<id>.md` |
| 规则误杀累计 | `stats/rule_fp_counts.json` |
| 已审计组合 | `stats/audited.json` |
| 未成簇的漏放暂存 | `stats/fn_pending.jsonl` |
| 纸面不可判出栏清单 | `stats/fn_out_of_scope.jsonl` |
| TN 累计清单 | `stats/tn_seen.list` |
| 审计累计账 | `stats/audit_tally.json` |
| 每轮输出 | `rounds/r<N>/` |
| 快照 | `history/` |
| 全局状态 | `ledger.json` |
| 汇总报告 | `report.md` |

外部脚本：`verify.sh <batch.list> <out.jsonl>` 文本判决（轨迹目录默认
`pool/traj`，`VERISKILL_TRAJ` 可临时指别处）；
`oracle_run.sh <轨迹路径> [--new-traj-out <路径>]` 重跑取真值并产新
轨迹；`lib/pool.py` 登记、取批、排审计队列。全部永不编辑。

## 参数

```text
rounds=10           总轮数
batch=40            每轮取多少条
audit_frac=0.1      审计预算占 batch 的比例
rubric_threshold=0.6  评分细则通过线（verify.sh 用）
replay_K=3          同一条目最多被取用几次
train_ratio=0.8     训练集比例
split_seed=0        划分随机种子
final_test_max=50   收尾最多重跑多少条测试条目
edit_budget=15      每个子 Agent 每轮的编辑预算（软上限，子 Agent 自行判断）
```

本次调用实际传入的参数：

```text
$ARGUMENTS
```

按 `key=value` 解析，没出现的键用默认值，解析不了的忽略并在开场说明。
`rounds` 是**总轮数**：`ledger.round > 0`（续跑）时从 `ledger.round+1`
跑到 `rounds`。

**环境接线**（Setup 时做一次）：

- 脚本假定位于项目根目录（与 `workspace/`、`pool/` 同级）；
- `export VERISKILL_RUBRIC_THRESHOLD=<rubric_threshold>`（不 export
  则 verify.sh 用自己的默认值）；
- `VERISKILL_BACKEND` 必须已设置（claude / codex / custom / stub）；
- 可选：`VERISKILL_JOBS`（并发，默认 4）、`VERISKILL_CHECK_SKILLS`、
  `VERISKILL_MODEL`、`VERISKILL_TIMEOUT`、`VERISKILL_TASK_DATA`、
  `VERISKILL_SOLVE_NOTE`。

**长命令放后台跑**：整批 `verify.sh` 和重跑的 `oracle_run.sh` 可能
超过 Bash 工具 10 分钟上限，用 `run_in_background`，通知到了再收结果。

**确定性**：登记、取批、审计队列一律用 `lib/pool.py` 子命令，不要
自己写等价的抽样代码。

## 数据隔离

- 只有 `split=train` 的条目能进 batch、作为改进 D/G 的依据。
- `split=test` 的条目在收尾前不判决、不审计、不作为改进依据。例外
  只有三个：Setup 的登记和格式体检（只做结构解析）、每 10 轮一次的
  周期性 test 评估（见第 7 步，结果只记录不反馈）。
- Oracle 重跑的做题工作区只有题目、技能库和任务数据——看不到旧轨迹
  的过程和答案，也看不到 gold/checker/truth。
- `verify.sh` 的工作区只有轨迹和 critics，看不到任何 Oracle 真值。
- Oracle 重跑加载当前解题技能库和可选校验工具技能，**绝不加载
  critics**——否则 FP/FN 全部失真。指纹里出现 critics 内容就是配错。
- `d-improve` 能看 `audit.jsonl` 全部行（真值是它的监督信号）。
- `g-improve` 只能看 `audit_g.jsonl`（kind 为 TN/FP 的行）。**不给它
  FN 的真值**：那会把"D 没抓到的错长什么样"直接教给 G。

## 子 Agent 派发

`d-improve` 和 `g-improve` 是 `.claude/agents/` 下的 subagent，用
Task 工具按名字调用。派发时把输入清单逐项写进 prompt，路径一律相对
项目根目录；子 Agent 只准读清单里的路径，外加一个固定例外：清单内
任一轨迹的**原版** `pool/traj_full/<id>.md`（默认派发的是压缩版，
证据被压缩截断、不足以定位根因时读原版）。

回复应当只有一个 JSON 块，原样存进 `rounds/r<N>/<名字>-result.json`。
不是合法 JSON 时，该侧按本轮无编辑处理（文件被改动则回滚到 before
快照），原因记进报告。

---

## Setup（round 1 之前做一次）

1. 确认存在（缺任何一个就停下报告，不要自建替代实现）：
   `pool/traj/`、`pool/meta.json`、`verify.sh`、`oracle_run.sh`。
   `workspace/actor_skills/`、`workspace/critics/` 不存在就建空目录
   （空库冷启动是常态，放了初始技能也接受）。
   预检，任一不过也停下报告：
   - **后端**：`bash verify.sh --selftest` 通过（一次最小调用）；
   - **成本预估**：花钱主项是审计重跑（每轮 B 次做题调用）；判分
     checker 条目零调用、truth 条目一次裁判。看 `pool/checkers/`、
     `pool/truth/` 覆盖多少条目，把每轮预估调用数报告给用户再继续；
   - **轨迹格式**（纯正则，不花钱）：

     ```bash
     python3 lib/extract.py --check pool/traj
     ```

     输出缺「题目」或「最终答案」节的条目清单。抽不出「题目」的条目
     没法重跑审计——报告给用户，让他们补转换或接受审不了，再继续。
2. 缺什么建什么：`rounds/`、`history/`、`stats/`、`report.md`；
   `stats/rule_fp_counts.json` = `{}`；`stats/audited.json` = `[]`；
   `stats/fn_pending.jsonl`、`stats/fn_out_of_scope.jsonl`、
   `stats/tn_seen.list` 空文件；`stats/tn_traj/` 空目录；
   `stats/audit_tally.json` = `{"recent":[]}`。
3. `ledger.json` 不存在则初始化：

```json
{"round": 0, "g_version": 0, "oracle_attempts": 0, "oracle_failures": 0}
```

| 字段 | 含义 | 写 | 读 |
|---|---|---|---|
| `round` | 已完成的轮号 | 第 6 步 | 续跑时定起点 |
| `g_version` | G 库版本计数 | 第 6 步（G 编辑存活时 +1） | 报表、快照命名、放回时写 meta |
| `oracle_attempts` / `oracle_failures` | Oracle 累计尝试/故障数 | 第 3 步 | 停止条件 |

这张表就是账本的全部，不要加没人读的字段。审计结果相关状态全记在
`stats/audit_tally.json`，账本只管流程状态。

4. 存初始快照 `history/r0_D_initial/`、`history/r0_G_initial/`。

5. **登记轨迹池**（登记一次；split 由只依赖 ID 的哈希决定，可复现）：

```bash
python3 lib/pool.py register --meta pool/meta.json --traj-dir pool/traj \
  --seed $split_seed --train-ratio $train_ratio
```

   核对容量：训练条目数 × `replay_K` < `rounds` × `batch` 时池子会
   中途耗尽，先报告预计能跑几轮再开始。

`pool/meta.json` 结构（`g_version` 只是记录，不参与选取）：

```json
{"items": [{"id": "<id>", "g_version": 0, "used_count": 0, "split": "train|test"}]}
```

---

## 每轮流程（r = 1..rounds）

### 1. 取批

建目录：`rounds/r<r>/`、`rounds/r<r>/new_traj/`、
`rounds/r<r>/replaced/`、`rounds/r<r>/g_fail_items/`、
`history/r<r>_D_before/`、`history/r<r>_G_before/`；两个技能库现状
复制进 before 快照。

```bash
python3 lib/pool.py sample --meta pool/meta.json --round $r --batch $batch \
  --replay-k $replay_K --out-batch rounds/r$r/batch.list
```

规则：`split=train` 且 `used_count < replay_K` 里随机抽 `batch` 条，
不足全取，选中的 `used_count+1` 原子写回。退出码 3 = 池子耗尽：停止
并报告。

**抽样规矩**（编排者自己做的随机操作也遵守）：先按 ID 排序，再
`random.seed(轮号)`，再抽；按 confidence 排序时并列按 ID 排。

### 2. 文本判决

D 判池子里的轨迹——即评产出各轨迹的那版技能：

```bash
bash verify.sh rounds/r<r>/batch.list rounds/r<r>/verdicts.jsonl
```

每行至少包含：

```json
{"item":"<id>", "verdict":"pass|fail", "rules_hit":[],
 "rubric_scores":{}, "confidence":0.0, "reason":"..."}
```

verify.sh 内部判决逻辑写死在它的提示词里，不用管也不许改。
`confidence` 的含义固定：标准化评分距 `rubric_threshold` 的远近
（越远越接近 1）；命中 `[hard]` 判据的固定 0.9。审计排序依赖它。

核对：行数、ID 与 batch.list 一一对应、JSON 合法。缺失的先重试一次
（缺失条目写 `rounds/r<r>/retry.list` 再跑一遍，结果并入）；仍缺的
补记：

```json
{"item":"<id>", "verdict":"fail", "rules_hit":[], "rubric_scores":{},
 "confidence":0, "reason":"verify 输出缺失或非法"}
```

算 **fail_rate** = 本轮判 fail 的比例。

### 3. Oracle 审计（重跑 + 放回）

审计一条 = 带**当前技能**把该任务真实重跑一遍（一次做题调用，全程
看不到旧轨迹的过程和答案），给新结果判真值得 **oracle_pass**；同时
产出带当前 `skill_hash` 的新轨迹，审计成功后替换池子里的旧轨迹。
oracle_pass 对照 D 判决记 FP/FN，也是 G 的实战成绩。

判分真值按序取第一个能用的：① `pool/checkers/<id>.sh`（零模型
调用）；② `pool/truth/<id>.md`（一次裁判调用）；③ 都没有 → 重跑
成功得出结果且没报错即 pass。

预算：

```text
B = ceil(audit_frac × 本轮实际取到的条数)
```

不设下限；单轮审计的作用是给 D 提供错例、给池子补新样本，收敛判断
只看累计账。

**技能指纹** = 重跑会加载的全部技能内容哈希 12 位，每轮开头取一次：

```bash
bash oracle_run.sh --fingerprint
```

**去重**：已审组合不再进队列（`pool.py audit-queue` 自动做）。键一律
`<条目ID>@<技能指纹>`——技能一变，同一条目就是新观测。指纹不含
critics，D 单独改动不影响它；D 改了、G 没动的轮次指纹不变，去重避免
同一观测重复烧预算。（历史遗留的 `@static` 键 pool.py 仍会查到并
跳过，不用清理。）

B 计 `oracle_run.sh` 成功调用次数。每次审计一次做题调用；判分
checker 零调用、truth 加一次裁判。

**排队列**（三段制,高效利用稀疏审计——误杀段 `floor(B/2)` 条取判
fail 里 confidence 最低的找 FP；pass 名额优先给**低置信段**（判 pass
但 confidence<0.8,D 不确定、最可能 FN）；余下留给**随机段**从高置信
pass 里随机抽,保无偏、防 G 学会"让 D 高信心放行"逃审。现在 confidence
是 D 的主观把握、有真实分布,低置信段才能精准命中 D 判错的地方）：

```bash
python3 lib/pool.py audit-queue --verdicts rounds/r$r/verdicts.jsonl \
  --audited stats/audited.json --fingerprint <本轮指纹> \
  --budget $B --round $r > rounds/r$r/audit_queue.jsonl
```

**执行**：逐条（放后台跑）

```bash
bash oracle_run.sh pool/traj/<id>.md --new-traj-out rounds/r<r>/new_traj/<id>.md
```

退出码非 0 时**先原样重试一次**（瞬时超时和输出解析失败占大头，一次
重试通常能救回）；仍非 0 才按环境故障处理：丢弃继续，不计入 B、不写
audited.json、不放回，队列不补位。重试成功的按成功计，重试本身不额外
占预算。环境故障率超 30% 停止循环（累计尝试满 10 次后才评估这条；
故障率按最终结果计，重试救回的不算故障）。

**记录**，每条写一行 `rounds/r<r>/audit.jsonl`：

```json
{"item":"<id>", "segment":"误杀|低置信|随机", "d_verdict":"pass|fail",
 "oracle_pass": true, "kind":"TP|FP|FN|TN", "skill_hash":"<12位>",
 "truth_source":"checker|truth|redo", "rules_hit":[],
 "normalized_score": 0.72, "confidence": 0.6, "oracle_evidence":"...",
 "skill_result":"重跑得出的答案"}
```

（`skill_hash`、`truth_source`、`skill_result` 抄 oracle_run 输出；
`normalized_score` 从判决行抄，hard 命中记 null。）

**放回**（每条审计成功的条目，按此顺序）：

1. 旧轨迹存档：压缩版 `cp pool/traj/<id>.md rounds/r<r>/replaced/<id>.md`，
   原版 `cp pool/traj_full/<id>.md rounds/r<r>/replaced/<id>.full.md`；
2. TN 条目把旧压缩版复制进 `stats/tn_traj/<id>.md`（同名覆盖）；
3. 新轨迹放回两份：原版
   `cp rounds/r<r>/new_traj/<id>.md pool/traj_full/<id>.md`，压缩版
   `python3 lib/compress.py rounds/r<r>/new_traj/<id>.md pool/traj/<id>.md`。
   判 fail 的新轨迹同样放回——它记录了当前技能做错什么，正是下一轮
   D 判、G 修的对象；
4. `pool/meta.json` 该条目 `g_version` 改为当前 `ledger.g_version`。

**记账**：

- `<条目ID>@<技能指纹>` 记进 `stats/audited.json`；
- kind 为 TN/FP 的行另存 `rounds/r<r>/audit_g.jsonl`（g-improve 唯一
  能看的审计结果）；
- TN 条目 ID 追加进 `stats/tn_seen.list`（去重）；
- 每个 FP 命中的每条规则在 `stats/rule_fp_counts.json` +1；
- 统计本轮 FP/FN 数（只用于派活）；
- 每条 kind 按执行顺序追加进 `stats/audit_tally.json` 的 `recent`，
  只留最后 20 条。

### 4. 改进 D

先处理漏放暂存：本轮 FN 追加进 `stats/fn_pending.jsonl`，每行：

```json
{"item":"<id>", "round": 3, "rules_hit":[], "oracle_evidence":"..."}
```

`oracle_evidence` 从 `audit.jsonl` 抄入（旧轮审计文件不再派发，暂存
条目只有自带真值可用）。同一条目已有暂存行时覆盖不追加（换指纹重审
再 FN 不能算两个例子）。追加后删掉 `round` 早于 `r−6` 的条目。
这一步是必要的：每轮 FN 常只有 0–1 条，而 d-improve 要求同类 2 例
才立判据，不跨轮攒 D 学不到新规则。

本轮 `FP == 0` 且暂存为空 → 跳过，记 `D=noop`。否则调 `d-improve`，
只给它：

- `rounds/r<r>/audit.jsonl`
- FP 条目和暂存条目的轨迹路径
- `stats/fn_pending.jsonl`
- `workspace/critics/`
- `stats/rule_fp_counts.json`（只读）
- 编辑预算 <edit_budget>
- 上轮回滚说明 `rounds/r<r-1>/rollback_D.txt`（存在才给）

输出存 `rounds/r<r>/d-improve-result.json`。三处后处理：

- `narrow_rule` 类编辑：把 `rule_fp_counts.json` 里对应规则计数清零
  （原值记进报告）——收窄后已是新规则，不再背旧账；
- `fn_resolved` 的条目从暂存删掉；
- `unjudgeable` 的条目在暂存行 `unjudgeable_count` +1；计数满 2 移出
  暂存、追加进 `stats/fn_out_of_scope.jsonl`。这个文件的长度是证据
  缺口指标：涨得快说明错误超出文本判别边界，该改的是证据保留策略或
  Oracle 路径，不是 D。收尾时报告。

### 5. 改进 G

从本轮 batch 选出：判 fail 且未被审计确认为 FP 的条目。每条复制两个
文件到 `rounds/r<r>/g_fail_items/`：D 判决时读的那份轨迹（被放回过的
用 `rounds/r<r>/replaced/<id>.md`，其余用 `pool/traj/<id>.md`）和
标记文件 `<id>.meta`，内容一行：`audited: true`（审计确认的失败）或
`audited: false`（仅 D 判 fail，可能混着未发现的误杀）。

**软信号（D→G 稠密通道）**：D 每轮判 16 条,即使 fail 很少,那些"判
pass 但 D 存疑"的条目也是可改进的稠密反馈。**只要 `g_fail_items/` 有
内容,或 `verdicts.jsonl` 里存在 verdict=pass 且 `concerns` 非空/
`confidence<0.7` 的条目,就调 g-improve**（把 verdicts.jsonl 原样给它,
它会自己从 concerns 聚类）。只有确凿失败和软信号**都**没有时,才记
`G=no_failure` 跳过。

调 `g-improve`，只给它：

- `rounds/r<r>/g_fail_items/`（含 `.meta`）
- `rounds/r<r>/verdicts.jsonl`（含每条的 `confidence` 和 `concerns`）
- `rounds/r<r>/audit_g.jsonl`
- `stats/tn_seen.list`
- `workspace/actor_skills/`
- 编辑预算 <edit_budget>
- 上轮回滚说明 `rounds/r<r-1>/rollback_G.txt`（存在才给）

输出存 `rounds/r<r>/g-improve-result.json`。

### 6. 门控：检查、接受或回滚

只查合法性，不评内容。对每个子 Agent 改动的每个文件：

门控只做**格式合法性 + 反作弊**检查,**不限制子 Agent 的改动幅度和
数量**（幅度/例数由子 Agent 自己分析判断,见其提示词）。检查项：

- frontmatter 可解析，含 `name`、`description`、`tags`；
- 单文件 ≤ 400 行；
- 新建文件：文件名与 `name` 一致且匹配
  `^[dg]-[a-z0-9]+(-[a-z0-9]+)+$`；名字末段不得是 general/misc/
  common/helper/utils/solve 这类泛词。**不再限制每轮新建数量、不再
  查 40% 改动幅度**——子 Agent 可以大改、重写、多建；
- 新增 R 判据只查信封：行首 `- R-<critic名>-<三位数> [hard|soft] `、
  行内含 ` 依据:`；
- R 的 ID 全库唯一；
- 新增文本不含具体答案值、题面原句、条目 ID（条目 ID 唯一例外：
  critics 里 R 判据的 `依据:` 字段）。题面/答案照抄用脚本比对新增行
  与本轮派发给该子 Agent 的任何轨迹文件的公共片段，按下面判定
  （检查的本意是拦答案和题面的**照抄**，不是禁用词汇）：
  - 重叠片段**含数字**，或含**连续 ≥8 个汉字** → 命中（数字串和成段
    中文才是答案值/题面泄露的真正形态）；
  - 纯英文且不含数字的重叠 → 连续 **≥16 字符**才命中（通用英文词组
    在语料和判据里都不可避免）；
  - 以下永远豁免：frontmatter 行（`name:`、`description:`、`tags:`）、
    R 判据信封（行首标记与 ` 依据:`）、与 `pool/gate_allowlist.txt`
    （若存在，每行一个字符串）中任一条目重叠的片段。

**违规整体回滚**：该子 Agent 任一文件违规，其本轮全部编辑退回
before 快照（编辑常互相依赖，不做单文件回滚）。原因写
`rounds/r<r>/rollback_D.txt`（或 `_G.txt`）并记报告，下轮派活时给
对应子 Agent。

**冒烟测试**：从 `stats/tn_seen.list` 随机抽 2 条，用改后的 critics
对 `stats/tn_traj/` 里的快照重跑 verify.sh（临时
`export VERISKILL_TRAJ=stats/tn_traj`，跑完恢复）。要求跑通、JSON
合法、且这 2 条仍判 pass——TN 是双确认过的好轨迹，改后被判 fail
说明新规则过宽。任一条不满足，critics 整库回滚到
`history/r<r>_D_before/`。（开局头几轮清单可能不足 2 条：跳过并记录。）

**接受**：通过的版本快照到 `history/r<r>_accepted_D/`、
`history/r<r>_accepted_G/`；`ledger.round = r`；G 侧有编辑存活时
`ledger.g_version += 1`。

### 7. 记账

第一次写 `report.md` 先写表头，之后每轮追加一行：

```markdown
| 轮 | 批大小 | fail_rate | 本轮FP | 本轮FN | 审计通过 | 放回 | D动作 | G动作 | g_version | 回滚 |
```

`审计通过` = `<oracle_pass=true 条数>/<本轮成功审计数>`（当前技能
重跑命中率，G 的实战成绩；审计数 0 填 `-`）。`放回` = 本轮替换进
池子的新轨迹条数。

聊天里输出一行：

```text
r=<r> 批=<n> fail_rate=<x> FP=<n> FN=<n> 审计=<x/y> 放回=<n> D=<动作> G=<动作> g_version=<v>
```

单轮 fail_rate 和 FP/FN 只记录不判断；收敛只看累计账。

**阈值自校准**：每条被审计条目自带一对标注（判决 `normalized_score`
+ 真值）。历史累计非 null 行 ≥ 15 时：扫描候选阈值取判对率最高者，
并列取最接近当前值的；与当前值差 ≥ 0.05 才更换；更换即
`export VERISKILL_RUBRIC_THRESHOLD=<新值>` 并记报告（旧值、新值、
样本数）。

子 Agent 返回 `needs_human=true` 只记录，不停循环、不回滚合法编辑。

**周期性 test 评估**（`r` 是 10 的倍数时，本步最后做）：用**当前**
技能测一次 test 集成功率。按收尾同款抽样（test 条目按 ID 排序、
`random.seed(0)`、取 `final_test_max` 条），逐条
`bash oracle_run.sh pool/traj/<id>.md`（**不带 --new-traj-out、不
放回**，test 池不动；环境故障条目剔除出分母）。结果追加一行进
`stats/test_curve.jsonl`：

```json
{"round": 10, "g_version": 4, "skill_hash": "<12位>",
 "pass": 11, "total": 18, "rate": 0.611}
```

并在报告记一行。**只做记录**：不作为任何改进依据、不给子 Agent 看、
不参与停止判断——test 隔离原则不变，这条曲线是给人看的成长记录。

---

## 停止

满足任一条即停：

- 跑满 `rounds` 轮；
- 用户叫停；
- **判准了**：累计账 `recent` 攒满 20 条且全是 TP/TN。不得用"连续
  3 轮 FP+FN==0"代替——每轮只审几条，三轮抓不到错很平常，会过早
  误判收敛；
- 轨迹池耗尽；
- Oracle 环境故障率超 30%（累计尝试满 10 次后才评估）；
- 核心脚本、数据或状态损坏。

## 收尾

1. 对全部 `split=test` 条目跑 `verify.sh`（判决便宜，全跑），算
   test fail_rate。
2. 重跑只做其中 `final_test_max` 条（默认 50）：多于此数时按 ID 排序
   `random.seed(0)` 抽样，抽样结果写进报告。逐条
   `bash oracle_run.sh pool/traj/<id>.md`（**不带 --new-traj-out，
   不放回**，test 池保持原样）。
3. 在这批条目上统计：**test 实战通过率**（oracle_pass 率，G 的最终
   成绩）、D 的 TP/FP/FN/TN 与准确率，存 `rounds/final_test/`。
4. 不得根据 test 结果再改 G 或 D。
5. 最终输出：逐轮指标表；test 指标（注明重跑了几条）；最终 accepted
   快照路径和 `g_version`；每轮 D/G 编辑摘要与回滚记录；全部判据清单
   （带依据和累计误杀数）；证据缺口（`fn_out_of_scope.jsonl` 条数及
   占全部 FN 的比例）；待人定夺清单（各轮 `needs_human` 与
   `unresolved` 汇总）；三段结论——G 学会了什么、D 学会了什么、还剩
   什么问题。

## 守则

- `pool/traj/` 只有第 3 步放回可写（旧轨迹必须先存档进
  `rounds/r<N>/replaced/`），其余场合只读；`pool/meta.json` 只在
  Setup 写入条目，循环中只改 `used_count` 和放回时的 `g_version`，
  `split` 永不变。
- 不建 Oracle 结果缓存，去重只靠 `stats/audited.json`。
- 永不编辑 `verify.sh`、`oracle_run.sh`、`lib/` 下的脚本。
- 编排者不直接改 G/D；子 Agent 不读派发清单外的路径。
- test 条目在收尾前不可见。
- 所有抽样、编辑、接受、回滚都要能从 `history/`、`ledger.json`、
  `report.md` 复现。
