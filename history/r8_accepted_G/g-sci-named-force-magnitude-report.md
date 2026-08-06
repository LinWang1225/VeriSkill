---
name: g-sci-named-force-magnitude-report
description: 题面问"force of attraction/repulsion/tension/compression"等有名力的量时，应按大小（模量，非负）报告；不得把带符号的矢量分量或库仑/弹簧表达式原样填入，避免多挂负号。
tags:
  - science
  - force
  - sign-convention
  - magnitude
  - named-quantity
  - reporting
---

# 有名力按模量报告：attraction/repulsion/tension/compression 取绝对值

## 触发情形

题面问某个**有名力**的大小："force of attraction""force of repulsion""tension""compressive force""magnitude of the force"等。这些命名本身已指明力的**性质方向**（吸引/排斥/拉/压），所问的数值是其**大小**（模量，非负）。典型翻车：把带符号的库仑力表达式 F = −k·q₁·q₂/r²（或弹簧力 F = −kx）原样当作"吸引力"填入，因表达式中自带的负号而给结果多挂一个负号；或把矢量某分量的代数值（可正可负）直接当"力的大小"提交，符号与题面所问性质不符。

## 硬约束

- **有名力的大小 ≥ 0**：attraction、repulsion、tension、compression 等命名力的"大小/量"是非负标量。题面问的是大小 → 报 |F|，不报带符号的 F。
- **符号由命名承载，不由数值承载**：题面说"force of attraction"即已指明方向是吸引，数值只报大小；不要再在数值里重复一个负号来"表示吸引"——那是把方向信息重复编码，导致符号错误。
- **矢量分量 ≠ 有名力大小**：若你算的是力矢量的某分量 F_x（可正可负），题面问的是有名力大小 → 取 |F_x|（或 |**F**|）报告，不要把分量代数值直接当答案。

## 执行步骤

1. **辨题面所问**：题面用的是"force of attraction / repulsion / tension / compression / magnitude of force"等**有名/模量**措辞，还是"the force""F_x""component"等**带符号矢量**措辞？
   - 有名/模量 → 走第 2–3 步，报非负大小。
   - 带符号矢量/分量 → 报代数值（含符号），不走本技能。
2. **算力的大小**：由物理关系算出该力的模量。若你手上的表达式带符号（库仑 F=±kq₁q₂/r²、弹簧 F=−kx），取**绝对值**作为大小；若由平衡条件得两力等大反号，两者大小相等、均报正。
3. **核对符号**：报出前检查——答案是否为非负？若为负 → 多挂了负号，取绝对值修正。再检查：是否把表达式的内禀符号（库仑的负、弹簧的负）当成了"答案的符号"重复编码？若是 → 去掉，只报大小。
4. **多力情形**：题面问多个有名力（如同时问 attraction 与 repulsion）→ 各自报各自的大小（均非负），不要让一个带符号、另一个不带；两力若由平衡得等大反号，报两个相等的正值。
5. **自查**：题面问的是有名力大小而我的答案带负号 → 取绝对值再提交。题面问的是矢量分量而我报了绝对值 → 回第 1 步改报代数值。

## 举例（通用占位，非任何具体题目）

两电荷相互作用，库仑力表达式 F = −k·q₁·q₂/r²（负号表吸引）。题面问"force of attraction"：报 |F| = k·|q₁·q₂|/r²（正值），不报 −k·q₁·q₂/r²（带符号原式）。若题面同时问"force of repulsion"且由平衡知排斥力与吸引力等大反号：报与 attraction 相同的正值，不报带符号的负值。判定动作：题面出现 attraction/repulsion/tension/compression/magnitude → 答案取绝对值；出现 component/F_x/the force（带方向语境）→ 保留符号。
