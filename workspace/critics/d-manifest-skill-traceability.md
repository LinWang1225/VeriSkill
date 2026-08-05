# d-manifest-skill-traceability

审查 manifest 的 cluster/coverage 声称是否可追溯到候选技能文件真实步骤。

## 规则

- R-manifest-skill-traceability-001 [soft] 对 manifest 中每条 expected_coverage 引用的 "skill#Step N"，在候选技能文件中确认该步骤存在且其文本能执行所述动作。若引用的步骤不存在或文本与所述动作不符，记 hard_defect（coverage 引用不存在）。 依据:r1 false_accept（D 未逐条核验 expected_coverage 步骤文本，直接采信 manifest）

- R-manifest-skill-traceability-002 [soft] cluster 的 common_pattern 不得用具体题面特征（具体年份、具体 bulletin 期号、具体表代码）冒充一般模式；若 common_pattern 含 batch 内可识别的具体值，视为过拟合风险，应要求 G 改写为一般化描述。 依据:r1 false_accept（common_pattern 含 "September issue"/"January issue" 等可读为具体而非一般化）
