| 轮 | 批大小 | fail_rate | 本轮FP | 本轮FN | 审计通过 | 放回 | D动作 | G动作 | g_version | 回滚 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16 | 0.00 | 0 | 1 | 3/4 | 4 | add_rule(1 critic,1 soft R) | new_skill(3) | 1 | 无 |
| 2 | 16 | 0.125 | 1 | 1 | 2/4 | 4 | new_critic(1,scope-misread,1 soft R) | new_skill(3) | 2 | 无 |
| 3 | 16 | 0.125 | 0 | 1 | 1/4 | 4 | new_critic(1,extrapolate-validity,1 soft R) | new_skill(3) | 3 | 无 |
| 4 | 16 | 0.062 | 1 | 3 | 1/4 | 4 | narrow_rule(1)+add_rule(1 soft R) | patch(2)+new_skill(2) | 4 | 无 |
| 5 | 16 | 0.00 | 0 | 3 | 1/4 | 4 | narrow_rule(1)+new_critic(2,2 soft R) | new_skill(3) | 5 | 无 |
| 6 | 16 | 0.125 | 0 | 0 | 2/4 | 4 | noop | new_skill(1)+patch(2) | 6 | 无 |

> r6 阈值自校准：0.75 → 0.81（样本 24，判对率 0.542→0.583，修正 ns=0.80 的 FN）

> r6 合并：noop（库已精简，15 actor + 5 critic 各覆盖独立错误模式，无近重/被支配/单题过拟合可上卷）

| 7 | 16 | 0.062 | 0 | 1 | 2/4 | 4 | promote_rule(1,sign-convention,soft→hard) | patch(2)+description(1) | 7 | 无 |

| 8 | 16 | 0.00 | 0 | 1 | 3/4 | 4 | new_critic(1,ratio-basis,1 soft R) | new_skill(1)+patch(2) | 8 | 无 |

> r8 阈值自校准：0.81 保持（样本 31，当前判对率 0.613 已达候选最优，候选 0.9 同精度 0.613 无增益，不更换）

| 9 | 16 | 0.00 | 0 | 2 | 2/4 | 4 | new_critic(1,comparison-basis,1 soft R)+add_rule(1 soft R) | new_skill(1)+patch(1) | 9 | 无 |

> r9 阈值自校准：0.81 保持（样本 35，当前判对率 0.600 已达候选最优，无增益更换）

| 10 | 16 | 0.188 | 1 | 1 | 2/4 | 4 | narrow_rule(1,model-selection,+S-N疲劳插值子情形) | new_skill(2)+description(2)+patch(1) | 10 | 无 |

> r10 阈值自校准：0.81 保持（样本 39，当前判对率 0.590 已达候选最优，候选 1.0 同精度 0.590 无增益，不更换）

| 11 | 16 | 0.125 | 0 | 2 | 0/4 | 4 | new_critic(1,d-sci-underdetermined-claim,1 soft R)+narrow_rule(1,model-selection,S-N多问统一拟合子情形) | new_skill(2,grade-not-source+shell-radius-attribution)+patch(2,sn-fatigue统一Basquin+missing-input欠定误判) | 11 | 无 |

> r11 阈值自校准：0.81 保持（样本 43，最优判对率 0.581 在 0.81 处达成，无 ≥0.05 增益更换）

| 12 | 16 | 0.000 | 0 | 3 | 1/4 | 4 | new_critic(1,d-sci-answer-format,1 soft R)+narrow_rule(1,underdetermined-claim,速率表达式即终答)+add_rule(1,model-selection,轴向误用偏心弯曲) | patch(3,missing-input-no-fabrication+m128+weld-group-control-point+m168+sigfig-rounding+m122) | 12 | 无 |

> r12 合并：noop（9 critic + 21 actor_skills 已精简，D/G 互为检测/预防对，无近重/被支配/单题过拟合可上卷）

| 13 | 16 | 0.125 | 1 | 1 | 2/4 | 4 | add_rule(1,model-selection,regular-solution Ω符号翻转 soft R) | new_skill(1,regular-solution-sign-convention)+patch(2,unitcell-Z-pair-check+model-validity-dilute-solution) | 13 | 无 |

> r13 d-improve：m245(FP)为评分路径误杀（rules_hit空、normalized_score=0、真值pass），无法定位具体细则项，记unresolved交阈值自校准；m276(FN)在model-selection加regular-solution稀溶液Ω符号翻转soft判据。g-improve：e229(TP)给unitcell每原子体积加(结构|V公式|Z)合法配对硬检查；m276新建regular-solution-sign-convention技能+model-validity-range补dilute-solution注意。

> r13 阈值自校准：0.81 保持（样本 51，最优判对率 0.549 在 0.81 处达成，与当前值差 <0.05，不更换）

| 14 | 16 | 0.062 | 0 | 3 | 0/4 | 4 | add_rule(1,scope-misread,spec-vs-measured)+narrow_rule(1,model-selection,S-logN图解)+add_rule(1,sign-convention,编号方程符号) | patch(5,regular-solution-sign+sn-fatigue-slogn+named-force-magnitude+grade-designation+model-validity) | 14 | 无 |

> r14 d-improve：3个FN(m029牌号下限当实测/m124 S-N log-log回归/e264编号方程丢负号)分别给scope-misread加spec-vs-measured子情形、model-selection收窄为S-logN半对数图解、sign-convention加编号方程符号约定子情形。g-improve：m276修正regular-solution稀溶公式符号exp(Ω/RT)→exp(−Ω/RT)且Ω<0报完全互溶；m124重写sn-fatigue为S-logN图解禁log-log回归；e264给named-force-magnitude补编号方程carve-out；m029给grade-designation补规格下限非实测硬约束；model-validity更新交叉引用。

> r14 阈值自校准：0.81 保持（样本 53，最优判对率 0.528 在 0.81 处达成，无 ≥0.05 增益更换）

| 15 | 16 | 0.062 | 1 | 2 | 1/4 | 4 | narrow_rule(1,model-selection,loglog措辞→核对方程形式)+promote(2,scope-misread+extrapolate-validity,升hard)+rubric(2,区熔多道次分布方程+居里点子情形) | new_skill(1,zone-refining-multi-pass)+patch(1,model-validity-range居里点硬边界) | 15 | 无 |

> r15 d-improve：m124(FP)收窄model-selection的loglog错误签名——要求拟合方程确为log S=a+b·log N才命中，排除虽提及loglog但实际用S=a+b·log N半对数的正确做法。e055/m250(FN)修正scope-misread区熔子情形正确方法描述(多道次分布方程)并升hard、extrapolate-validity新增居里点/磁相变子情形并将R-001/R-002升hard。g-improve：e055新建g-matsci-zone-refining-multi-pass(单步平衡偏析vs多道次分布方程)；m250给g-sci-model-validity-range补居里点/磁相变为线性电阻率硬边界。

> r15 阈值自校准：0.81 保持（样本 57，最优判对率在 0.81 处达成，无 ≥0.05 增益更换）

| 16 | 16 | 0.062 | 0 | 3 | 0/4 | 4 | add_rule(2,answer-format加法sigfig+scope-misread渗透总通量) | new_skill(1,permeation-steady-state)+patch(3,model-validity-range+sigfig-rounding+chart-lookup-read) | 16 | 无 |

> r16 d-improve：3个FN（m022读图/m057加法sigfig误按乘法/m102渗透丢弃总通量）。m057给answer-format加soft判据（加法结构按小数位舍入）；m102给scope-misread加soft判据（通量比+总通量须联立，原子/分子换算因子带入求和式）；m022读图精度纸面不可判，记unjudgeable（count=1）。g-improve：m057 patch g-matsci-sigfig-rounding（加减按小数位/乘除按有效数字位数）；m102新建g-matsci-permeation-steady-state；e252 patch g-sci-model-validity-range（教材惯例非T<Θ_D沿用线性律的有效辩护，电阻律边界是德拜温度非居里温度）；m022 patch g-matsci-chart-lookup-read（刻度线插值定坐标，不凭目测）。

> r16 门控冒烟：m107 pass、m194 fail（rules_hit空，verify.sh独立核查判答案单位格式不符，非本轮新规则所致——回滚critics不会改变该结果，保留编辑）。阈值自校准：本轮无新增非null normalized_score行，跳过。

---

### r17/r18 交界：三处机制改动（人工介入，非本轮 D/G 编辑）

r1–r16 的账在这里断一次，读表时注意口径变了。

**1. 存疑扣分（`lib/jsonx.py`）** —— `normalized_score` 实测是二值的
（pass→1.0 / fail→0.0），28 条 FN 里 26 条 ns=1.0，与 19 条 TN 完全
重合。改为在 pass 侧按 `adjusted = ns − 0.25×soft命中 − 0.10×concerns
− 1.0×(1−自报信心)` 扣分，低于阈值翻成 fail，留痕
`flipped_by=concern-penalty` / `raw_verdict`。依据：28 条 FN 里 27 条
D 已在 concerns 写明了正确疑点却仍判 pass。在 47 条已审计 pass 样本上
回放：翻转 19/28 FN、误伤 2/19 TN，累计召回 30%→78%、精度 71%→82%。

**2. 晋升门放宽（`lib/rule_stats.py` + 门控）** —— 原门槛要求 hard 判据
`依据:` 含 ≥2 个互异 #q，16 轮下来 10 条判据只有 4 条升上去，其余长期
挂 soft 而 soft 不改判决。新增第二条路径：历史命中 ≥2 次且 fp==0 即可
晋升。d-improve 每轮开工前先跑 rule_stats 主动清 soft，不占编辑预算。

**3. 回归门（`regression_gate.sh` + `stats/tp_traj/`）** —— 原冒烟只抽
2 条 TN 防误杀，不防遗忘：e055 r6/r7 抓到、r15 又漏，m128 r3 抓到、
r11/r12 连漏，m029 r11 抓到、r14 漏；12 道重复审计的题里 9 道最后一次
仍 oracle-fail。现把 11 条确认 TP 的原始轨迹钉成回归集，每轮接受编辑
前重跑（默认最近 4 条），翻成 pass 即整库回滚。

**附带修掉的既有 bug**：`verify.sh` 的 D 提示词用的是不带引号的
heredoc，第 105 行 `` `concerns` `` 未转义，从 r1 起每次生成提示词都在
执行 `concerns` 这个不存在的命令，并把该字段名替换成空串（stderr 一直
在刷 `concerns: command not found`）。已转义。

**阈值**：`env.sh` 里一直是 0.75，而每轮报告写的 0.81 只在轮内 export、
从未落盘——在旧的二值 ns 下两者无差别，所以没人发现。现保持 0.75，
并把第 7 步自校准的输入从 `normalized_score` 改成 `adjusted_score`、
要求更换时改写 env.sh。

预期副作用：fail_rate 会从 ~0.06 跳到 0.4 上下（这才接近 oracle 实测的
真实失败率），g-improve 每轮拿到的失败簇会变多。

| 17 | 16 | 0.125 | 0 | 2 | 0/4 | 4 | patch(2,model-selection升hard+轴瓦单面子情形/param-lookup晶胞体积Z配套子情形) | patch(3,grade-designation硬约束+ttt-phase激活+independent-verify反循环) | 17 | 无 |
| 18 | 16 | 0.375 | 0 | 2 | 0/4 | 4 | patch(2,model-selection K-edge子情形+answer-format单位换算副本子情形) | new+patch(6,lefm-crack-length-convention新建+hall-effect-desc+ttt比值校验+model-validity跨界门槛+mixing上下界反推+independent-verify循环论证) | 18 | 无 |
| 19 | 16 | 0.25 | 0 | 1 | 0/4 | 4 | patch(1,sign-convention磁滞回线coercive-field带符号截距子情形) | new+patch(4,given-unit-faithful-conversion新建+comparison-controlled-variable牌号纯度核验+wear-two-body单面vs总磨损+weld答非所问门控) | 19 | 无 |
| 20 | 16 | 0.25 | 1 | 0 | 3/4 | 4 | patch(2,param-lookup查表豁免narrow+answer-format sigfig输入精度豁免) | new+patch(1,column-yield-buckling-dual-check新建受压柱双判据+unitcell-formula HCP系数(3√3/2)修正+c/a自洽) | 20 | 无 |
| 21 | 16 | 0.375 | 2 | 1 | 3/4 | 4 | rollback(冒烟TN m143被concern-penalty误杀,3 edits退回) | new+patch(4,model-validity-range线性外推硬门控+missing-input表达式即终答+weld-group肢宽/所问量双门控+param-lookup-consistent-source新建) | 21 | D回滚 |
| 22 | 16 | 0.375 | 0 | 1 | 1/4 | 4 | patch(1,answer-format R-001拓宽触发措辞+符号表达式多值子情形+e079依据) | new(3,table-cell-row-column-attribution查表行列归因+thermal-expansion-sign-direction膨胀方向+answer-final-numeric-form boxed单数值) | 22 | 无 |
| 23 | 16 | 0.3125 | 1 | 1 | 1/4 | 4 | patch(1,scope-misread加晶胞vs式量单元豁免子情形)+new(1,d-sci-unit-dimension量纲一致性soft) | new+patch(5,unit-system-consistency新建+arrhenius D0量级拦截+table-cell量级自洽扩展+sigfig多报/末尾0歧义+weld腿宽激活警告) | 23 | 无 |
| 24 | 16 | 0.625 | 2 | 0 | 4/4 | 4 | patch(2,scope-misread题目显式约定豁免扩展+param-lookup教材公认取值区间豁免) | patch(2,unitcell-formula HCP密度反求双配对交叉核验+independent-verify交叉核对子情形强化) | 24 | 无(冒烟m231为既有TN回归,非本轮D编辑所致,before-critics亦fail adj0.62) |

### r24 合并（consolidate）
noop：两个 placeholder（zone-refining-multi-pass、comparison-basis）已在前序轮次裁剪且无悬挂引用；其余条目经核验均非近重/被支配，按"拿不准就不合并"保留。actor 32→32，critic R 判据 12→12，未改任何文件。
| 25 | 16 | 0.438 | 0 | 1 | 1/4 | 4 | add_rule(construct-verify soft)+promote underdetermined→hard | new(tuple-magnitude-direction-split)+patch(named-force,missing-input) | 25 | 无 |
| 26 | 16 | 0.3125 | 0 | 1 | 1/4 | 4 | narrow(sign-convention:电化学电池电势方向) | new(yield-strength-def,nernst-complete,unit-dimension-check)+patch(independent-verify) | 26 | 无 |
| 27 | 16 | 0.1875 | 0 | 1 | 1/4 | 4 | add_rule(model-selection:Hosford R位置)→回滚(回归门m255翻pass) | new(anisotropic-yield-r-placement)+patch(answer-final-numeric-form,named-force,param-lookup) | 27 | D回滚 |
| 28 | 16 | 0.4375 | 1 | 1 | 2/4 | 4 | add_rule(model-selection:CM模型混用)+narrow(sign-convention:tuple)→回滚(回归门m255翻pass) | patch(sigfig:大数相减,model-validity:模型混用)+rename(sn-fatigue-slogn-graphical) | 28 | D回滚 |
