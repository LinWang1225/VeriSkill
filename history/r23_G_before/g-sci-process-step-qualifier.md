---
name: g-sci-process-step-qualifier
description: 题面用 previous/next/last/initial/final/nth pass 等限定词指定非当前阶段（区熔精炼 zone refining 多次通过、Pfann 分布、偏析/分凝 segregation、硅棒提纯、多级萃取、逐级结晶、连乘反应器、逐次稀释等）时，须按该过程的逐遍递推关系推到所问阶段再作答，不得把当前阶段的量直接当成限定词所指阶段的量；区熔题尤须区分"同一界面瞬时固—液平衡 Cs=k·Cl"与"跨一整遍 pass 的递推"。题面即使未出现"zone refining"字样，只要含"previous/next pass + 杂质浓度/纯度 + 偏析/分凝/segregation/distribution coefficient/silicon bar/ppb/ppm"等组合即应触发。
tags:
  - science
  - process-steps
  - recursion
  - qualifier
  - zone-refining
  - pfann
  - segregation-coefficient
  - distribution-coefficient
  - multi-pass
  - segregation
  - previous-pass
  - silicon-purification
  - impurity-concentration
  - pass-recursion
---

# 过程步骤限定词：递推到指定阶段，不要停在当前

## 触发情形

题目描述一个分阶段/分 pass 的递推过程（区熔精炼逐 pass、多级萃取、逐级结晶、连乘反应器、逐次稀释等），问"上一阶段/下一阶段/初始/最终/第 n 道"的某个量，而题面同时给了"当前阶段"的某个量。典型错：把当前阶段的量直接当成限定词所指阶段的量，少走（或多走）一步递推。

## 硬约束

- 限定词 previous/last/next/initial/final/nth 指向的阶段 ≠ 当前给数阶段时，必须显式列出从给数阶段到所问阶段的递推步数，逐步套用该过程的递推关系，到所问阶段为止。
- 在答案旁标注"从第 k 道到第 k+m 道走了 m 步递推"，让步数可审计。

## 执行步骤

1. 在题面圈出限定词（previous/next/initial/final/nth/第几道…）与给数阶段，确认两者是否同一阶段。不同 → 进入递推。
2. 写出该过程一步的递推关系（如区熔精炼一步：C_s = k₀·C_l，C_l 为该 pass 液体浓度、C_s 为该 pass 刚凝固固体浓度；上一道固体 = 当前道液体等衔接关系）。
3. 数清从给数阶段到所问阶段要跨几步、每步方向（向更早阶段是反推、向更晚阶段是正推）。
4. 逐步套递推关系走到所问阶段，每步标注阶段编号与方向。
5. 自查：所问阶段的量是否确实由给数阶段经正确步数得到；若只走了一步但限定词要求两步，回第 4 步补步。

## 区熔精炼专项：同界面平衡 ≠ 跨遍递推

区熔（zone refining）多次通过时，C_s = k·C_l（k 为偏析/分配系数）只描述**同一凝固界面、同一瞬时**的固—液平衡：该 pass 凝固出的固体 C_s 与该 pass 界面处液相 C_l 之间成立。它**不**直接联系"当前遍固体"与"上一遍液体"——两者之间隔着整整一遍 pass，须按逐遍递推（Pfann 区熔分布）回退，而非一次除以 k。

**一次通过分布方程** C_s(x) = C₀[1 − (1−k)·e^{−kx/l}]（l 为液区长度、C₀ 为初始均匀浓度、x 为距起始端距离）描述液区从左到右扫一遍后固相沉积的浓度分布；多道时由上一道分布经一次通过方程递推（或 Pfann 多道递推关系联系相邻两遍）。**极端纯化极限**（液区远长于特征距离、已多道精炼后）的退化形式 C_l ≈ C_s/k 仅在题面明确说"已达稳态纯化极限"时可用——题面说"上一遍 pass"≠ 稳态极限，须走分布方程或递推。

判别动作：
1. 题面出现 "previous pass / next pass / last pass / 多次通过 / multi-pass / zone refining / Pfann" → 进入逐遍递推模式，不要只做一次 C_s = k·C_l。
2. 标出题面给数的是哪一遍的哪个相（固体/液体）、所问的是哪一遍的哪个相，数清两者间隔几遍。
3. 每跨一遍按该遍的递推关系走一步（反推时除以 k、正推时乘以 k，并注意相邻遍衔接关系），步数 = 跨过的遍数，不是 1。
4. 自查：若只做了一次除以 k 就得到答案，而限定词指向的是另一遍 → 少退了一遍，回第 3 步补步。

## 举例（通用占位，非任何具体题目）

过程一步关系 y_n = r·x_n（x_n 为第 n 道液体、y_n 为第 n 道固体），且相邻道衔接 y_{n−1} = x_n（上一道固体进入下一道成为液体）。题面给"当前第 n 道固体 y_n"，问"上一道（第 n−1 道）液体 x_{n−1}"：先由 y_n = r·x_n 反推 x_n（当前道液体），再由 y_{n−1} = x_n 与 y_{n−1} = r·x_{n−1} 反推 x_{n−1}——共两步。少走一步会把 x_n 误当 x_{n−1}，差一个因子 r。区熔中即：一次除以 k 只给"产生当前固体的那遍液体"，要"上一遍液体"须再退一遍。
