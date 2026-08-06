---
name: g-matsci-tuple-magnitude-direction-split
description: 题面要求把答案写成 (数值量, 方向/类型标签) 形式的 tuple 时——如 (percent_volume_change, transformation_type)、(strain, elongation_or_shortening)、(deformation, tension_or_compression)——数值字段报正幅值，方向由标签字段单独承载；不得在数值里带符号同时又给方向标签（方向重复编码）。
tags:
  - materials-science
  - sign-convention
  - tuple
  - magnitude-direction
  - reporting
  - double-encoding
---

# (数值, 方向标签) tuple：数值报正幅值，方向由标签承载，禁止重复编码

## 触发情形

题面要求答案是一个 tuple，其中一个字段是数值量（百分变化、应变、变形量…），另一个字段是方向/类型标签（contraction/expansion、elongation/shortening、tension/compression、heating/cooling…）。典型翻车：把数值字段写成带符号（如把收缩记成负百分数），同时又用标签字段标了 contraction——方向信息被编码两次，数值字段本应取正幅值。审计约定：当存在独立的方向/类型标签字段时，数值字段取正幅值（magnitude），符号不进数值。

**关键辨析——何时本技能适用、何时不适用**：
- 适用：tuple 里有**独立的**方向/类型字段（字符串/枚举标签），如 `(percent_change, type)`。此时数值字段取正幅值。
- 不适用：题面只要单一数值字段、且该量名语义上是有符号量（如只问 "percent volume change" 一个数，无配套标签字段），或题面显式定义该字段为带符号量 ΔX/X×100。此时符号留在数值里承载方向，不走本技能。
- 判据：看题面要求的答案结构里**有没有独立的标签字段**——有 → 数值取正幅值；没有 → 符号留在数值里。

## 硬约束

1. **先辨答案结构**：题面要的是 `(数值, 标签)` 还是单一数值？只有存在独立标签字段时本技能适用。
2. **数值字段取正幅值**：算出带符号的变化量 ΔX（可正可负），数值字段报 |ΔX|（或 |ΔX/X|×100 的正幅值），方向由标签字段从 ΔX 的符号导出（ΔX<0 → contraction/shortening/compression 类标签；ΔX>0 → expansion/elongation/tension 类标签）。
3. **禁止重复编码**：不得在数值字段写负号同时又用标签标方向。即 `(-|Δ|, contraction)` 和 `(|Δ|, expansion)` 都是错的——前者方向编码两次，后者方向与标签矛盾。正确：`(|Δ|, contraction)` 或 `(|Δ|, expansion)`，数值恒正、标签承载方向。
4. **标签须与 ΔX 符号一致**：ΔX<0 必须配收缩类标签，ΔX>0 必须配膨胀类标签；数值取正后，标签是方向的唯一载体，标错即方向错。

## 执行步骤

1. **辨答案结构**：题面要 tuple 里有独立标签字段吗？没有 → 不走本技能，符号留在数值里。有 → 继续。
2. **算带符号变化量**：按物理定义算 ΔX（如 ΔV = V_final − V_initial，带符号），记录其符号。
3. **数值字段取正幅值**：数值字段 = |ΔX|（或 |ΔX/X_ref|×100），不带入符号。
4. **由符号定标签**：ΔX<0 → 收缩类标签（contraction/shortening/compression/shrinkage）；ΔX>0 → 膨胀类标签（expansion/elongation/tension/growth）。标签须与 ΔX 符号一致。
5. **自查（硬门控）**：
   - 数值字段是否为正？若为负 → 取绝对值修正，方向已由标签承载。
   - 数值符号与标签是否重复编码了同一方向？`(-|Δ|, contraction)` → 把数值改正，保留标签。
   - 标签与 ΔX 实际符号是否一致？ΔX<0 却标 expansion → 标签错了，回第 4 步修正。

## 举例（通用占位，非任何具体题目）

相变前后每原子体积 v_initial、v_final，题面要 `(percent_volume_change, transformation_type)`。ΔV = v_final − v_initial（带符号），percent = |ΔV|/v_initial×100（正幅值）。ΔV<0 → 标 contraction；ΔV>0 → 标 expansion。正确：`(|ΔV|/v_initial×100, contraction)`。错误：`(-|ΔV|/v_initial×100, contraction)`——数值带负号又标 contraction，方向编码两次。又一例：应变 ε 带符号，题面要 `(strain, elongation_or_shortening)`：数值报 |ε|，ε>0 标 elongation、ε<0 标 shortening。

## 与单数值情形的区分

若题面只问 "percent volume change" 一个数、无标签字段 → 该量按其定义 ΔV/V×100 带符号报，符号承载方向，本技能不适用。判据动作：先数题面要求字段数与有无标签字段——有标签字段 → 数值取正幅值；无标签字段 → 符号留在数值里。
