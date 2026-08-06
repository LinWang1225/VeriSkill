---
name: d-matsci-scope-misread
description: 判别题目中时间/位置/过程步骤限定词（previous/next/initial/final pass、before/after、upstream/downstream 等）是否被正确解读并据此选择正确的计算起点。覆盖区熔精炼、多步热处理、多段扩散、多级分离等需按指定阶段而非当前阶段计算物量的题型。触发条件：题目以限定词指定一个非当前阶段（previous pass / next pass / before / after / initial / final 等），要求算该阶段的某物量。
tags: [scope-misread, zone-refining, multi-pass, process-step, materials-science]
---

## 方法库

### 子情形：区熔精炼逐 pass 递推——"previous pass"类
- 【正确方法】区熔精炼中分凝系数 k0 将界面处固体浓度 C_s 与液体浓度 C_l 联系：C_s = k0·C_l。当题目给出当前 pass 的固体浓度、问"previous pass"的液体（或固体）浓度时，须先由当前 pass 反推上一 pass 的固体浓度（简化单步模型：C_s,prev = C_s,curr / k0；完整多 pass 模型用区熔精炼递推公式按 pass 数回退），再对那一 pass 求 C_l,prev = C_s,prev / k0。关键：递推到题目指定的那一 pass，而非停在当前 pass。即"previous pass"的液体浓度需从当前固体浓度回退一整 pass（固体→上一 pass 固体→上一 pass 液体），共两次除以 k0（或等价的多 pass 回退），而非一次。
- 【错误签名】轨迹直接算 C_l = C_s,curr / k0 并当作"previous pass"的答案——这其实是当前 pass 的液体浓度，只回退了半步（从当前固体到当前液体），没有再回退一整 pass。特征：轨迹出现将"产生当前浓度的 pass"等同于"previous pass"的表述（如"the liquid on the pass that produced it"）；或轨迹只做了一次除以 k0 就给出答案，而题目问的是 previous pass（需两次除以 k0 或等价的多 pass 回退）。

### 子情形：多段/多步过程——"before/after/initial/final"类
- 【正确方法】当题目问某物量在"before""after""initial""final"等指定阶段的状态时，须先确定该阶段在过程序列中的位置，从该位置起算，而非从当前或最方便的阶段起算。若过程有 N 步、题目问第 M 步（M≠当前步），须显式回退或前进到第 M 步再计算。
- 【错误签名】轨迹把题目指定的非当前阶段当成当前阶段直接计算，或跳过了从当前阶段到指定阶段的过渡步骤；特征：轨迹未提及阶段切换、直接在当前阶段上算出答案。

## R 判据

- R-d-matsci-scope-misread-001 [soft] 若本题含时间/位置/过程步骤限定词（previous/next/initial/final pass、before/after 等）指定一个非当前阶段：在正文"方法库"里找与本题最匹配的子情形，按其【正确方法】核对轨迹是否递推/回退到题目指定的那一阶段、并查是否犯了其【错误签名】（停在当前阶段、把当前阶段当指定阶段、回退步数不足）；方法库无恰配子情形时用家族通用检查（核对轨迹计算所用的阶段是否与题目限定词一致，不一致即命中）。命中任一错误签名、或计算阶段与题目指定阶段不符，即命中。 依据:r2#qe055
