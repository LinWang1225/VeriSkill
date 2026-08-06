# VeriSkill × MatSciBench

生成器技能库 **G** 与判别器规则库 **D** 协同进化，Oracle（benchmark 官方判分器）
提供真值。本分支只保留 MatSciBench 切片的代码与运行结果。

## 循环

每轮 16 条：

```
取批 → D 判决 → Oracle 审计（4 条，按 D 判决分层抽样）
     → d-improve（修 FP/FN）→ g-improve（修失败簇）
     → 门控（冒烟 + 回归门 + 晋升门）→ 记账
```

- **Oracle** = MatSciBench 官方 `evaluation.rule_judge.judge_num_answer`
  （sympy 符号等价 + 5% 相对容差），零 LLM、零自研判分
- **审计分层**：误杀段抽 D 判 fail 的（查精度），随机/低置信段抽 D 判 pass 的（查漏检）
- **放回**：审计过的 4 条用当前技能库重解，新轨迹放回池中

## 结果

跑了 28 轮，约 36 小时。技能库 0 → 37 个，critics 0 → 11 个。

### G：技能有效，但已走平

同一批 48 道 test 题、同一 harness、同一官方判分器，唯一变量是技能库：

| | 技能数 | 通过率 |
|---|---|---|
| 无技能基线 | 0 | 24/48 = 50.0% |
| r27 技能库 | 37 | **32/48 = 66.7%** |

配对：9 进步 / 1 退步，McNemar 精确检验双尾 p = 0.0215。

增益几乎全部来自前 28 个技能；最近六轮新增 9 个技能只换来净 +1 题（4 进步
3 退步，p = 1.0）。退步的三条都是先前被技能攻克、又被后续技能改动破坏的——
新技能开始干扰老技能。15/48（31%）的题 28 轮零进展。

### D：网撒得更大，判别力没变

审计段是**按 D 的判决分层抽样**的，直接把四段汇总算召回会得到采样伪影
（D 判 fail 越多，误杀段能填满的槽越多，汇总召回自动变高）。下表按 D 的
fail 判定比例 f 重加权：

| | r1–r17 | r18–r28 |
|---|---|---|
| D 判 fail 比例 f | 0.074 | 0.358 |
| 判 fail 时正确率（精度） | 0.74 | 0.68 |
| **判 pass 时正确率** | 0.55 | **0.55** |
| 推算真实召回 | 0.11 | **0.46** |

召回提升 4.2×，但**全部来自 f 变大**。判 pass 时正确率一动没动，等同抛硬币——
D 的信号只存在于 fail 方向。而 g-improve 正是靠 D 判 fail 才拿到失败簇，pass 侧
零判别力意味着大量真失败根本进不了 G 的改进队列。这解释了 G 为什么走平。

### r17/r18 交界的三处机制改动

1. **存疑扣分**（`lib/jsonx.py`）：`normalized_score` 实测是二值的（28 条 FN 里
   26 条 ns=1.0，与 TN 完全重合）。改为在 pass 侧按 concerns / soft 命中 / 自报
   信心扣分，低于阈值翻成 fail，留痕 `flipped_by=concern-penalty`。
2. **晋升门放宽**（`lib/rule_stats.py`）：原门槛要求 hard 判据依据含 ≥2 个互异
   `#q`，16 轮只升上去 4 条。新增路径：历史命中 ≥2 次且 `fp==0` 即可晋升。
3. **回归门**（`regression_gate.sh`）：原冒烟只抽 TN 防误杀，不防遗忘。把确认 TP
   的原始轨迹钉成回归集，每轮接受编辑前重跑，翻成 pass 即整库回滚。

已知问题：回滚粒度过粗——「冒烟 TN 翻 fail 即整库退」不区分新规则直接命中导致的
误杀和间接影响的边界抖动，曾把专门修 FP 的编辑连坐退回。

## 目录

| 路径 | 内容 |
|---|---|
| `oracle_run.sh` | 用当前技能库重解 + 官方判分器裁定 |
| `verify.sh` | D 对一批轨迹出判决 |
| `regression_gate.sh` | 回归门：重跑历史 TP 轨迹 |
| `eval_test.sh` | test 集评估，结果追加进 `stats/test_curve.jsonl` |
| `lib/` | 判决解析、池管理、规则统计、回归集构建 |
| `benchmarks/matscibench/` | 建池、判分核心、探针与消融脚本，**含基线/消融原始轨迹** |
| `adapters/run_rounds_matsci.sh` | 确定性轮次驱动（一轮一个全新上下文） |
| `rounds/` `history/` `stats/` `workspace/` | 28 轮的运行产物 |

细节见 [`benchmarks/matscibench/README.md`](benchmarks/matscibench/README.md)。

## 复现

数据集是公开的（[JunkaiZ/MatSciBench](https://huggingface.co/datasets/JunkaiZ/MatSciBench)），
`pool/traj` 与 `pool/checkers` 不入库，用 `benchmarks/matscibench/build_pool.py` 重建。

```bash
cp env.sh.example env.sh   # 填 token 与 base_url
python3 benchmarks/matscibench/run_gen.py        # 无技能基线轨迹
python3 benchmarks/matscibench/build_pool.py     # 1:1 平衡池 + train/test 划分
bash adapters/run_rounds_matsci.sh 50            # 跑 50 轮
bash eval_test.sh 4                              # test 评估
```

> `adapters/run_rounds_matsci.sh` 顶部的 `VS=` 是硬编码的本机路径，换机器要改。
