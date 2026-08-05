# d-coverage-partial-gaps

审查候选 skill 的 coverage 质量与 PASS 门限关系。

## 规则

- R-coverage-partial-gaps-001 [soft] 统计 current_batch 每条 coverage 状态。若存在 `partial` 条目且其 feedback 指出了具体缺失能力（缺动作、缺路由规则、缺检查/回退、适用边界不覆盖），而非仅 "unjudgeable"，则这些 partial 应计入 PASS 的不利证据。当带具体缺失的 partial 占 batch 的 >=25% 时，不应直接 PASS；应在 feedback_to_g 中给出可操作修复并考虑 REVISE，或若缺失效果不可从文本判定则 ABSTAIN。 依据:r1 false_accept（D PASS，Oracle 0 improvement，retained_pass 1，门控未通过）

- R-coverage-partial-gaps-002 [soft] coverage 标 `covered` 必须在候选技能文件中有明确触发条件 + 可执行步骤 + 完成条件的三元证据；若证据仅复述 manifest 而未指向具体步骤文本，应降为 `partial` 或 `unjudgeable`。 依据:r1 false_accept（manifest expected_coverage 与候选步骤的一致性未做文本核验）

- R-coverage-partial-gaps-003 [abstain] 当全部可靠配对均为 retained_pass（improvement=0, regression=0）且 scored_pairs 不足门控下限时，候选是否优于 baseline 仅凭技能文本无法判定，应倾向 ABSTAIN 让 Oracle 决定，而非 PASS。 依据:r1 false_accept（scored_pairs=1, improvements=0, net_gain=0）
