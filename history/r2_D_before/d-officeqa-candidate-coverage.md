# D critic: candidate coverage and breadth review for officeqa

Used by D in review_candidate mode to judge whether G's candidate skills
truly cover the current_batch patterns or merely claim broad coverage.

## Rules

- R-officeqa-coverage-001 [hard] For each cluster in candidate_manifest, check that the claimed common_pattern is supported by at least 2 trajectories with distinct root reasoning (not just same table family). If a cluster merges items whose required computations differ (e.g., CAGR vs geometric mean vs OLS vs centered moving average), verify the candidate skill has a distinct, concrete step for each computation type. A single generic "compute the statistic" step covering >4 distinct formulas without per-formula verification is a coverage gap. 依据:r1 false_accept: C02 merged 27 items with 10+ computation types into one skill step "步骤6 compute", and q048 regressed because the generic step could not guarantee correct centered-moving-average precision.

- R-officeqa-coverage-002 [abstain] When a candidate skill lists multiple numeric formulas (CAGR, geometric mean, OLS, centered moving average, population std dev, arc elasticity, percent-share change, inflation correction) in a single compute step, D cannot statically verify that the actor will select the correct formula and produce a numerically precise result for each item. Mark such items unjudgeable rather than covered, unless the skill gives a per-formula selection rule keyed to question wording. 依据:r1 false_accept: q048 baseline 0.388 vs candidate 0.377 — a precision/selection error invisible in skill text.

- R-officeqa-coverage-003 [soft] If a candidate skill covers >20 items from current_batch in one cluster, examine whether the breadth is real (distinct reusable sub-steps) or nominal (one vague compute step). Breadth without per-sub-step checks inflates apparent coverage and masks regression risk on retained-pass items. 依据:r1 false_accept: 4 retained_pass items were marked covered by the same generic step that caused q048 regression.

- R-officeqa-coverage-004 [hard] When current_batch contains items that were already passing under baseline (retained-pass risk), D must identify them and require the candidate to show a non-destructive change or explicit preservation of the baseline computation path for those items. If the candidate replaces a working computation with a broad generic step and cannot show preservation, mark those items partial, not covered. 依据:r1 false_accept: q048 was a retained-pass item destroyed by the candidate's generic compute step; D marked it covered.
