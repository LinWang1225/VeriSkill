# CADRE 论文草稿

`CADRE_draft.md` —— 论文草稿。已有结果已填入，未跑的实验以 `[TBD]` 标记，文末附
「实验计划与待补数据」一节，列出每项待跑实验的目的、预估耗时与优先级。

## 命名

框架原名 VeriSkill，与 Jia et al. 2026《VeriSkill: A Self-Evolution Framework for
Program Verification Skills》(arXiv:2607.27733) 重名，论文中改称 **CADRE**
(Calibrated Audit-Driven Refinement of Expertise)。仓库与代码未改名。

## 数字怎么来的

`analysis/` 下四个脚本复现论文中所有已填数字。除 OfficeQA 那个之外，都在本分支的
数据上直接跑。

| 脚本 | 产出 | 对应章节 |
|---|---|---|
| `baseline_no_skill.py` | 无技能基线逐题对错（读 `matsci_probe/traj/`） | §6.1 |
| `paired_test_matscibench.py` | 基线 / r21 / r27 三方配对 + McNemar | §6.1、§6.6 |
| `critic_reweighted_metrics.py` | 判别器分层重加权指标（f、精度、pass 侧、召回） | §4.6、§6.5 |
| `paired_test_officeqa_pilot.py` | OfficeQA pilot 配对（读 `origin/main` 的 archive） | §6.1、§6.11 |

`baseline_no_skill.py` 与 `paired_test_matscibench.py` 依赖 `~/Documents/openclaw-rl/matsci_probe/`
下的探针轨迹（无技能基线与官方 harness 消融的原始产物），已随
`benchmarks/matscibench/results/` 入库，脚本里的路径需按实际位置调整。

`paired_test_officeqa_pilot.py` 读的是 `origin/main` 分支
`archive/before_v6_clean/rounds/` 下的旧运行产物——那是 `flow_version: 6` 的候选审查
流程，**不是**本文 §4 的审计校准循环，论文中作为 §6.11 的对照单列。

## 待办

见草稿文末「实验计划与待补数据」。最小可投稿集合按当前估算约 6–7 天，其中
「加第二个数据集」优先级高于「审计预算扫描」。
