---
name: g-matsci-unitcell-formula-unit-scaling
description: 题面问"per unit cell / of a unit cell"的量（磁矩、偶极矩、原子数、密度等）而晶体结构含 Z>1 个化学式单元时，须先确认 Z 再把 per-formula-unit 值乘以 Z 缩放，不能把每式单元值直接当单胞值。
tags:
  - materials-science
  - crystallography
  - unit-cell
  - formula-unit
  - scaling
---

# 单胞量 vs 每式单元量：确认 Z 再缩放

## 触发情形

题面问某个量"per unit cell""of a unit cell""in one unit cell"，而该量你按化学式（per formula unit / per molecule）算出了一个值。晶体结构的单胞通常含 Z 个化学式单元（Z>1 时最危险），单胞量 = 每式单元量 × Z。典型翻车：把亚晶格相消后得到的 per-formula-unit 净矩（或净电荷、原子数、偶极矩等）直接当作单胞量提交，漏乘 Z。

## 常见结构的 Z（化学式单元数/单胞）

- 尖晶石 spinel (AB₂O₄): Z=8
- 萤石 fluorite (CaF₂ 型): Z=4
- 钙钛矿 perovskite (ABO₃): Z=1
- 金刚石/闪锌矿 diamond/zinc-blende: Z=8（双原子基元 × 面心）
- fcc: Z=4；bcc: Z=2；hcp: Z=2；简单立方: Z=1
- 六方 Wurtzite (ZnS): Z=2；金红石 rutile (TiO₂): Z=2

若结构不在上列，据 Wyckoff 位置数出单胞内化学式单元数，不要凭记忆猜。

## 执行步骤

1. **确认题面所问的基准**：题面说"per unit cell / of a unit cell / in the unit cell" → 需缩放到单胞；说"per formula unit / per molecule / per atom" → 不要乘 Z，保持每式单元值。
2. **定 Z**：据结构类型查上表或从 Wyckoff 位置数出单胞含几个化学式单元。在解答中注明"该结构 Z=…（来源：晶体学表/教材）"。
3. **算每式单元量** → 再乘 Z → 得单胞量。若题面问的是每式单元量，则不乘 Z。
4. **自查**：题面说"unit cell"而你的答案等于每式单元量（未乘 Z）→ 若 Z>1 则漏了缩放，回第 3 步乘 Z。反之题面说"per formula unit"而你的答案被乘了 Z → 回第 3 步除掉。

## 举例（通用占位，非任何具体题目）

结构 Z=Z₀（Z₀>1），每式单元净矩算得 m₀ μB，题面问"magnetic moment of a unit cell"：单胞矩 = Z₀ × m₀ μB，在答案旁注明"Z=Z₀（该结构化学式单元数/单胞）"。若题面改问"per formula unit"：报 m₀ μB，不乘 Z₀。判定动作：在题面找"unit cell / per formula unit / per molecule"关键词，据此决定是否乘 Z。
