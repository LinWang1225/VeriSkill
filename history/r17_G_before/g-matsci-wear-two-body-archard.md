---
name: g-matsci-wear-two-body-archard
description: 两体对磨（轴对套筒/滑动轴承、销对盘、块对环等）Archard 黏着磨损问题须按两体处理：总磨损由两个接触表面分担，等硬度同材配对相对单表面公式多一个因子 2；不得把单表面 1/H 直接套到两体情形。题面出现 shaft/sleeve/bearing/journal/同种材料配对/两种套筒材料比较磨损率/relative volume loss ratio 等即应触发。
tags:
  - materials-science
  - wear
  - archard
  - two-body
  - surface-sharing
  - adhesive-wear
  - shaft-sleeve
  - bearing
  - journal
  - hardness-ratio
  - volume-loss
  - relative-wear
  - same-material-pair
---

# 两体 Archard 磨损：表面分担因子，别把单表面公式直接套

## 触发情形

题面描述两个固体表面相互滑动磨损（轴对套筒、销对盘、块对环…），问体积磨损或磨损率。Archard 磨损定律单表面形式为 V = K·F·s / H（K 无量纲磨损系数、F 法向力、s 滑移距离、H 表面硬度）。典型翻车：把单表面 V = K·F·s/H 直接当成两体总磨损，丢掉两表面分担的因子。

## 硬约束

- **两体对磨时总磨损由两个表面分担**：每个表面各贡献 V_i = K·F·s / H_i，总磨损 V_total = V_1 + V_2 = K·F·s·(1/H_1 + 1/H_2)。
- **等硬度对（H_1 = H_2 = H）**：V_total = 2·K·F·s / H，相对单表面公式多一个**因子 2**。丢掉这个因子会把总磨损算小一半。
- **异硬度对**：V_total = K·F·s·(1/H_1 + 1/H_2)，不能只用一个表面的硬度。
- 若题面问的是"某一个表面的磨损量"而非总磨损 → 只取该表面的 V_i，不乘 2、不叠加。先看清题面问的是单面还是总磨损。

## 执行步骤

1. **判一两体**：题面是否描述两个表面相互滑动？是 → 两体处理；只有一个表面被磨损（另一表面视为刚性无磨损）→ 单表面。
2. **定各表面硬度**：两体时分别确认 H_1、H_2。同种材料（题面说"同种钢""both steel"等）→ H_1 = H_2，因子 2 出现；异种材料 → 各取各的硬度。
3. **算总磨损**：V_total = K·F·s·(1/H_1 + 1/H_2)；等硬度时化简为 2·K·F·s/H。
4. **确认题面所问**：题面问"total wear / 总磨损"→ 报 V_total；问"wear on surface X / 某表面磨损"→ 报该面 V_i。
5. **自查**：两体等硬度对的总磨损里是否含因子 2？若答案等于 K·F·s/H 而题面是等硬度两体总磨损 → 丢了因子 2，回第 3 步修正。若两体异硬度而答案只用了一个 H → 回第 2 步补齐两个硬度。

## 举例（通用占位，非任何具体题目）

两体对磨，法向力 F、滑移距离 s、磨损系数 K，表面 1 硬度 H_1、表面 2 硬度 H_2：
- 总磨损 V_total = K·F·s·(1/H_1 + 1/H_2)。
- 若 H_1 = H_2 = H（同种材料）→ V_total = 2·K·F·s / H。
- 若题面只问"surface 1 的磨损"→ V_1 = K·F·s / H_1，不乘 2。

判定动作：在题面找"two surfaces / 轴对套筒 / 销对盘 / 同种材料 / both of steel"等关键词；两体 + 等硬度 + 问总磨损 → 因子 2 必出现，漏掉即错。
