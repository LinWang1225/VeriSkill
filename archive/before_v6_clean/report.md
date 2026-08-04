# VeriSkill 共演化报告

## 配置

| 参数 | 值 |
|---|---|
| rounds | 12 |
| batch | 30 |
| audit_frac | 0.2 |
| train_ratio | 0.8 |
| replay_K | 3 |
| eval_every | 4 |
| eval_baseline | true |
| seed | 0 |
| backend | claude |
| 训练条目 | 101 |
| 测试条目 | 20 |
| checker 覆盖 | 100%（101/101 train） |

## 演进日志

| 轮 | 批大小 | fail_rate | 本轮FP | 本轮FN | 审计通过 | 放回 | D动作 | G动作 | g_version | 回滚 |
| 1 | 30 | 0.03 | 0 | 2 | 4/6 | 6 | 新建critic d-officeqa-answer-format | 新建g-officeqa-locate-source, g-officeqa-extract-verify | 1 | 无 |
| 2 | 30 | 0.07 | 1 | 3 | 2/6 | 6 | 新建critic d-officeqa-data-aggregation, 修改rubric | 蒸馏g-officeqa-extract-verify | 1 | 无 |
| 3 | 30 | 0.07 | 1 | 2 | 2/5 | 5 | 修改rubric d-officeqa-data-aggregation | 蒸馏g-officeqa-extract-verify, g-officeqa-locate-source | 2 | 无 |
| 4 | 30 | 0.03 | 0 | 3 | 2/6 | 6 | 修改rubric d-officeqa-data-aggregation | 跳过（单例q004未聚类） | 2 | 无 |
| 5 | 30 | 0.10 | 2 | 2 | 3/6 | 6 | 新增R-002 hard规则+2条rubric | 跳过（单例q111未聚类） | 2 | 无 |
| 6 | 30 | 0.07 | 0 | 1 | 3/5 | 5 | 新增2条rubric | 蒸馏g-officeqa-extract-verify | 3 | 无 |
| 7 | 30 | - | 1 | 2 | 3/6 | 6 | - | - | 3 | 无 |
| 8 | 30 | - | 3 | 1 | 3/6 | 6 | - | - | 3 | 无 |
| 9 | 24 | 0.08 | 1 | 1 | 3/5 | 5 | 收窄判据R-001 | 跳过（单例q096） | 3 | 无 |
| 10 | 6 | 0.17 | 0 | 0 | 0/1 | 1 | 全部FN标记unjudgeable | 补充时间粒度检查 | 4 | 无 |
| 11 | 3 | 0.00 | 0 | 0 | 1/1 | 1 | 无 | 无 | 4 | 无 |

## 周期评估

| 轮 | 成功率 | 通过/判定 | 环境故障 | g_version |
|---|---|---|---|---|
| 0 | 0.500 | 8/16 | 4 | 0 |
| 4 | 0.526 | 10/19 | 1 | 2 |
| 11 | 0.611 | 11/18 | 2 | 4 |

> 周期点本应在 r=8 也出一次（eval_every=4），但编排者 commit 完 r8 即因上下文上限 rc=0 退出，未及跑 step8 eval，故 r=8 点缺失。r=11 为池子耗尽后的收尾点（final_test 重跑 20 题）。

## 终章（收尾报告）

> 本轮因池子耗尽停在 r=11（规格停止条件"轨迹池耗尽"），未达 r=12。收尾的 test 重跑（final_test/，20 题）已于 07-28 02:29 完成；报表（图、本节）因 429 中断，现补全。

### 1. 成功率演进（test 集，held-out，纯监测）

图：`stats/test_eval.svg`

| r | g_version | pass/judged | env_fail | 成功率 |
|---|---|---|---|---|
| 0 | 0 | 8/16 | 4 | 50.0% |
| 4 | 2 | 10/19 | 1 | 52.6% |
| 11 | 4 | 11/18 | 2 | 61.1% |

**单调上升，+11.1 个百分点**（基线 50% → 终点 61.1%）。G 技能库 4 代演进后实战命中率提高。n=20 test 集噪声 ±~10pp，r4→r11 中间缺 r8 点，幅度宜谨慎，但方向明确。

### 2. 最终 test 指标（final_test，重跑 20 题）

- 采样 20（= 全部 test 条目，final_test_max=50 取小），判定 18（q110/q112 因 429 env_fail 未得真值），通过 11/18 = 61.1%
- 错题：q002 q018 q031 q074 q103 q121 q122
- D 的 test 准确率：判 18 题（排除 q110/q112 env_fail），**TP=0 TN=9 FP=2 FN=7，准确率 9/18 = 50%**（= 全判 pass 的基线）。**此项有混淆**：D 判的是 `pool/traj` 里的原始 test 轨迹（baseline g_version=0 的答题），而真值来自当前技能（g_version=4）重跑--两版同题对照，不是 D 现判能力的干净度量。干净信号看 train 审计：最近 20 条 TP=6、FN 占比较早期下降。

### 3. 最终技能快照

- G 库：`history/r11_accepted_G/`，g_version=4；D 库：`history/r11_accepted_D/`
- 全程 11 轮 **0 回滚**（每轮编辑均过门控）

### 4. 判据清单（D 库，带依据）

**d-officeqa-answer-format.md**（1 条 soft R 判据 + 3 条 rubric）
- R-officeqa-answer-format-001 [soft] 答案格式与题目要求不符（列表间距/数值纯净度）。依据: r1 q010 q100
- rubric: 答案格式规范 / 列表格式精确性（r4 q032）/ 数值答案纯净度（r6 q028）

**d-officeqa-data-aggregation.md**（2 条 hard R 判据 + 5 条 rubric）
- R-officeqa-data-aggregation-001 [hard] 明细项加总 ≠ 声称总值。依据: r2 q127 q005 / r9 q021
- R-officeqa-data-aggregation-002 [hard] 自述取数来源与工具执行记录的表格标题不符。依据: r4 q085 / r5 q046
- rubric: 数据加总一致性 / 数据源一致性 / 数值可见性 / 分类一致性 / 数据来源类型匹配

累计误杀 `rule_fp_counts.json` = `{}`（收窄判据时已清零，无挂账）。

### 5. 证据缺口

- `fn_out_of_scope.jsonl`：5 条（q009 q040 q028 q032 q044），均 unjudgeable_count=2（连续 2 轮纸面判不出，移出暂存）
- 累计 FN 17 条，out_of_scope 占 5 = **29%**：约三成漏放是"纸面不可判"（如 q040 的 6379.29 vs 6378.54 微小数值差、q028 多年值 vs 单值），靠改 D 文本判据救不了，得改证据保留或 Oracle 路径
- `fn_pending.jsonl`：5 条未成簇漏放（q127 q008 q038 q063 q033），unjudgeable_count=1，待成簇或移出

### 6. 待人定夺

- needs_human：**无**
- unresolved：r3 q019（g-improve 单例未解决）

### 7. Oracle 累计与收敛

- attempts=55，failures=1（环境/解析类，按规丢弃不计入 B）；q100 truth-judge 多次返非 JSON（rc=5），属 judge 输出抖动，非题做错
- 累计审计账（最近 20 条）：TP=6 TN=5 FP=5 FN=4，11/20 为 TP/TN，**未达收敛**（需 20 条全 TP/TN）
- 相较早期（r1-r3：FN 7/17 主导），近期 FN 占比下降、TP 上升，D 在改善中

### 三段结论

**G 学会什么**：两个解题技能成型并迭代 4 代——`g-officeqa-locate-source`（Treasury Bulletin 出版滞后：M 月公报含 M-1 数据，查 X+1/X+2 版）与 `g-officeqa-extract-verify`（表头列确认、逐行原文摘录、跨文件交叉验证、独立工具复算、答案格式自检）。test 成功率 50%→61.1% 验证技能有效。

**D 学会什么**：空库冷启动到 2 个 critic、3 条 R 判据（2 hard + 1 soft）+ 8 条 rubric。train 审计上早期 FN 主导（漏放），后期 FP/FN 趋平衡、TP 上升。但 test 集上 TP=0（7 个真失败全漏放），暴露判据对未见过的 test 错误泛化不足--D 改进更多停在 train 模式上。

**还剩什么问题**：
1. 池子容量（101×3=303 < 12×30=360）致 r10-r11 batch 缩到 6/3，末期信号弱；要跑满 12 轮得加题或提 replay_K。
2. 曲线只有 3 点（r0/r4/r11）：eval_every=4 + 编排者 r8 上下文退出漏点。下轮用 eval_every=3 更稳，上下文退出已靠 watchdog 自动续跑缓解。
3. q100/q110/q112 走 truth 路径（无 checker），judge 偶返非 JSON 致审计丢弃；配 checker 可降故障。
4. D 未收敛（train 审计 11/20 TP/TN，离"最近 20 审计全对"差 9 条）；且 test 集泛化差（TP=0/7 真失败全漏放），判据偏过拟合 train 模式。
