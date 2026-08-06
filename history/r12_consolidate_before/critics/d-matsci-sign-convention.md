---
name: d-matsci-sign-convention
description: 判别物理量报告的符号约定是否与题目所问一致。覆盖两类情形：(1) 题目以命名物理量（force of attraction/repulsion、binding energy、potential energy 等）提问、期望模量（正值）或特定惯用符号约定、但解答按另一约定（如矢量分量带符号、势能取负号）填入；(2) 题目要求以 tuple（数值, 定性方向标签）形式作答、标签已承载方向信息（contraction/expansion、increase/decrease 等），但解答又在数值字段重复编码符号（负号+contraction），使方向信息出现两次。触发条件：题目以命名物理量提问且轨迹给出带符号数值而题目期望模量；或题目要求 tuple(value, direction_label) 且轨迹数值字段带符号与标签语义重复。
tags: [sign-convention, magnitude-vs-signed, reporting-format, tuple-sign-redundancy, physics, materials-science]
---

## 方法库

### 子情形：命名力/能量——模量 vs 有符号矢量分量
- 【正确方法】当题目问"force of attraction""force of repulsion""binding energy"等命名物理量时，这些量本身是模量（正值）或以惯用符号约定报告（如引力势能取负、结合能取正）。须按题目所问的物理量定义报告：attraction/repulsion 的"力"是模量（正），两力大小相等、方向相反，但分别以正值报告；若题目要求矢量分量则需指定坐标系。关键：区分"问一个命名物理量的值"（模量/惯用约定）与"问一个矢量在某坐标系的分量"（有符号）——题目未指定坐标系/未要求分量时，命名物理量以模量报告。
- 【错误签名】轨迹把库仑/离子相互作用的有符号表达式（如 F = −Z₁Z₂e²/(4πε₀r²)，负号表示吸引方向）原样填入"force of attraction"的答案位，使吸引力报告为负值；或把势能的负号带入"binding energy"（应为正）。核对特征：题目问命名物理量（attraction/repulsion 等），轨迹最终答案含负号且负号来自矢量/势能符号约定而非题目要求的报告约定；或轨迹两分量大小相等符号相反，但题目期望两个正模量；或轨迹自述"attractive, negative"等将方向符号混入模量报告。

### 子情形：tuple（数值, 方向标签）——符号冗余
- 【正确方法】当题目要求以 tuple（数值量, 定性标签）形式作答、且定性标签已承载方向/类型信息（如 contraction/expansion、increase/decrease、heating/cooling、compression/tension）时，数值字段应报告模量（正值），方向由标签表达。符号信息只出现一次——在标签里，不在数值字段里。典型场景：题目问"percent volume change"并要求 tuple(percent, transformation_type)，percent 取正值、第二字段填 contraction 或 expansion；题目问"Is this a contraction or expansion?"并要求 tuple 作答时同理。若题目明确要求有符号数值（如"以负值表示收缩"）则不在此列。
- 【错误签名】轨迹在数值字段带符号（如负号表示 contraction/decrease）同时又给出与该符号一致的方向标签，方向信息被编码两次。核对特征：题目要求 (percent_change, transformation_type) 或 (value, direction) 类 tuple，轨迹数值字段含负号且同时给出方向标签、且标签语义与负号一致（负号+contraction/decrease/compression，或正号+expansion/increase/tension）；即轨迹的数值符号与标签表达同一方向，构成冗余。正确做法是数值取绝对值、方向仅由标签承载。命中即符号冗余错误。

## R 判据

- R-d-matsci-sign-convention-001 [hard] 若本题以命名物理量（force of attraction/repulsion、binding energy、potential energy 等）提问、或要求以 tuple（数值, 方向标签）形式作答：在正文"方法库"里找与本题最匹配的子情形，按其【正确方法】核对轨迹报告的符号约定是否与题目所问物理量的定义/答案格式一致、并查是否犯了其【错误签名】（把有符号矢量分量/势能值填入命名物理量答案位使模量带负号；或在 tuple 数值字段带符号且与方向标签语义重复、方向信息编码两次）；方法库无恰配子情形时用家族通用检查（核对轨迹最终答案的符号是否与题目所问命名物理量的惯用报告约定/答案格式一致，不一致即命中）。命中任一错误签名、或符号约定与题目所问/所要求格式不符，即命中。 依据:r5#e264,r7#e229
