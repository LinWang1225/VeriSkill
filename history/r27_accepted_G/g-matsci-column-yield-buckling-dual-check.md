---
name: g-matsci-column-yield-buckling-dual-check
description: 细长受压杆（round bar/strut/column "support"或"carry" a compressive load）设计直径或截面时，须同时校核屈服强度与 Euler 弹性屈曲，取两者所需尺寸的较大者；只做强度判据 σ=F/A≤σ_y 会忽略失稳，对低弹性模量材料（镁合金、聚合物等）尤其危险。
tags:
  - materials-science
  - mechanical-design
  - column-buckling
  - euler
  - yield-strength
  - compression-member
---

# 受压柱双判据：屈服 + Euler 屈曲取大径

## 触发情形

题面描述一根杆/柱/圆棒要"support""carry""sustain"一个载荷，且载荷沿轴向压缩（非拉伸），杆有一定长度（长细比不可忽略）。要求算最小直径（或截面尺寸）、重量、成本等。关键词：bar/rod/column/strut + support/load + 长度已给 + "without permanent deformation"/"without buckling"/"safely support"。

常见翻车：把受压柱当成简单拉杆，只用强度判据 σ=F/A≤σ_y 算直径，完全忽略长细比与弹性失稳，对镁合金（E≈45 GPa，远低于钢~207 GPa、铝~69 GPa）屈曲载荷可能远低于屈服载荷，所得直径偏小、不安全。

## 执行步骤

1. **判定受力性质**：在题面找"support/carry/sustain a load"并确认载荷沿杆轴向压缩（杆两端受压、或一端固定一端受载）。若为拉伸 → 用纯强度判据即可，本技能不适用。若为压缩且杆长 L 与直径 d 之比预期较大（L/d 粗大于~5 即需警惕）→ 进入双判据。

2. **强度判据（屈服）**：按 σ=F/A≤σ_y 算屈服所需直径下限 d_y。
   - 圆截面：A=πd²/4，d_y=√(4F/(π·σ_y))。
   - σ_y 取该合金牌号的屈服强度（查教材物性表，注明来源）。

3. **屈曲判据（Euler）**：按 P_cr=π²·E·I/L_e² ≥ F 算屈曲所需直径下限 d_cr。
   - 圆截面：I=πd⁴/64，代入得 d_cr=(64·F·L_e²/(π³·E))^(1/4)。
   - E 取该合金弹性模量；L_e 为有效长度（两端铰支 L_e=L；一端固定一端自由 L_e=2L；两端固定 L_e=L/2；一端固定一端铰支 L_e≈0.7L）。若题面未指定约束，默认两端铰支 L_e=L 并在解答中声明该假设。
   - 适用前提：长细比 L_e/r 超过比例极限对应的长细比（即弹性屈曲范围）。若算出 L_e/r 偏短（落在非弹性/Johnson 区），改用 Johnson 公式 P_cr=A·σ_y·(1−(σ_y·(L_e/r)²)/(4·π²·E))。先按 Euler 算，再检查 L_e/r 是否在弹性范围；不在则换 Johnson。

4. **取大值**：d_min = max(d_y, d_cr)。在解答中同时列出两个直径并说明哪个起控制作用（"屈服控制"或"屈曲控制"）。若 d_cr ≫ d_y → 屈曲控制（低 E 材料长柱典型）；若 d_y > d_cr → 强度控制（短粗杆或高 E 材料）。

5. **后续量基于 d_min**：重量 W=ρ·A_min·L、成本 cost=W×单价 等，一律用 d_min（而非 d_y）对应的截面积算。

6. **独立回代自查**：把 d_min 代回两个判据分别算 σ=F/A 与 P_cr=π²EI/L_e²，确认 σ≤σ_y 且 P_cr≥F（两条同时满足）。任一条不满足 → 回第 2/3 步重算。再用一条不依赖原推导路径的粗估（如把 d_min 量级与"同载荷下钢杆典型直径"比较，低 E 材料应更粗）核对量级合理。

## 判据/辨析要点

- "support a load without permanent deformation"≠"只查屈服"：永久变形由屈服保证不发生，但杆还可能因屈曲而失稳（失稳时应力可远低于 σ_y），两者都要不发生。
- 拉杆 vs 压杆：拉杆只看强度（无屈曲）；压杆须看强度+屈曲。先在题面确认载荷方向再选判据。
- Euler vs Johnson：长柱（L_e/r 大）用 Euler；中长柱过渡区用 Johnson；短柱用纯强度。先按 Euler 算再据 L_e/r 判定是否需切换。
- 有效长度 L_e 取决于端部约束：题面未说就声明"两端铰支"假设，不要默认固定端。

## 举例（通用占位，非任何具体题目）

载荷 F、杆长 L、合金屈服 σ_y、弹性模量 E、密度 ρ。两端铰支圆杆：
- d_y=√(4F/(π·σ_y))；d_cr=(64·F·L²/(π³·E))^(1/4)；d_min=max(d_y,d_cr)。
- 若 E 小（镁合金量级），d_cr 常大于 d_y → 屈曲控制，d_min=d_cr；若 E 大（钢），d_y 常大于 d_cr → 强度控制。
- 报出 d_min 后用 W=ρ·π·d_min²·L/4 算重量，再乘单价算成本。
- 自查动作：把 d_min 代回 P_cr=π²E(πd_min⁴/64)/L²，确认 P_cr≥F；代回 σ=F/(πd_min²/4)，确认 σ≤σ_y。
