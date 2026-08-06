# MatSciBench 切片

数据：MatSciBench（Jun-Kai-Zhang/MatSciBench）`Materials: Metals` × medium+hard × 纯文本 NUM 题。
238 条，train/test = 190/48。

## 池子构造

`build_pool.py` 从 `run_gen.py` 产的探针轨迹里建 **1:1 平衡池**：全部错题 + 等量正确题，
按难度分层配对。这样「D 全判 pass」只值 50%，判别力才有意义。train/test 按 hash 排序
取精确配额（不是 Bernoulli，否则 test 条数会漂）。

> ⚠️ `meta.json` 的条目顺序是「先全部错题、后全部对题」，`eval_test.sh` 按这个顺序生成
> `items.list`。所以**评估跑到一半时看通过率会严重偏低**——前半区全是基线做错的难题。
> 要么跑完再看，要么先把 `items.list` 打散。

## 判分

`checker_core_matsci.py` 直接调官方 `evaluation.rule_judge.judge_num_answer`
（sympy 符号等价 + 5% 相对容差），零 LLM、零自研判分。

已知的官方判分器行为，有无技能两侧同等受影响，不影响对照：

- LaTeX 分数被逐数字抓取：`\frac{2}{3}` 解析成 `[2, 3]` 而非 `0.667`
- 同一量给出第二种单位的换算副本，会因解析值个数不符而判错

## harness 对齐

`oracle_run.sh` 的 `write_solve_prompt` 已对齐 MatSciBench 官方 harness
（`methods/prompts.py:SYSTEM_PROMPT`）：材料学教授 persona、reason step by step、
答案不带单位。与无技能基线（`run_gen.py`）逐字一致，因此「有技能 vs 无技能」的差异
纯来自技能库。

两处有意偏离官方，写在 `oracle_run.sh` 注释里：JSON 信封（管道需要 result / process /
evidence / skills_used 四字段）、闭卷 + 禁查答案键那句（oracle 侧模型有
Read/Grep/Glob/Bash，`golds.json` 可达）。

> **注意**：`oracle_run.sh` 跨 benchmark 共享。本切片把 persona 和答案约定直接改在
> 里面了，frontiersci / GPQA / HLE / stat 复用时需改回通用奥赛口径，或把这两段提成
> 环境变量（同 `VERISKILL_SOLVE_NOTE` 的做法）。

## 结果

同一批 47 道 test 题、同一官方判分器、同一 harness，唯一变量是技能库：

| | 通过率 |
|---|---|
| 无技能基线 | 24/47 = 51.1% |
| r21 技能库（28 个） | 31/47 = 66.0% |

7 进步 / 0 退步，McNemar 精确检验双尾 p = 0.0156。

D 侧（88 条 oracle 审计，召回按 D 的 fail 判定比例重加权——审计段是按 D 判决分层
抽样的，直接汇总会得到采样伪影）：

| | r1–r17 | r18–r22 |
|---|---|---|
| 判 fail 比例 | 0.074 | 0.325 |
| 判 fail 时正确率 | 0.74 | 0.70 |
| 判 pass 时正确率 | 0.55 | 0.50 |
| 推算真实召回 | 0.11 | 0.40 |

召回提升来自「网撒得更大」而非判别力提升：pass 侧正确率没有改善。

## 脚本

| 文件 | 用途 |
|---|---|
| `run_gen.py` | 官方 harness 探针，产无技能基线轨迹 |
| `run_gen_skills.py` | 官方 harness + 技能库，消融对照 |
| `build_pool.py` | 1:1 平衡池 + 分层 train/test 划分 |
| `checker_core_matsci.py` | 官方 rule_judge 封装 |
| `score.py` / `score_skills.py` | 判分与配对检验 |
| `classify.py` | 题目分类 |

轮次驱动见 `../../adapters/run_rounds_matsci.sh`。
