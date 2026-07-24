# VeriSkill v4

技能共演化框架。评估对象自始至终是**技能**，不是单条答案：

- **G（生成器）** = 解题技能库 `workspace/actor_skills/`，只产技能。
- **D（判别器/verify）** = 验证技能库 `workspace/critics/`。核心任务是
  **判断技能改得好不好**：池子里每条轨迹是某版技能做题的执行样本
  （frontmatter 的 `skill_hash` 标版本），D 读轨迹判 pass/fail 就是在
  评那版技能。fail 直接反馈给 g-improve 改技能。
- **Oracle** = `oracle_run.sh`。抽查 D 判得准不准：带**当前技能**把
  任务真实重跑一遍、给新结果判真值（checker → truth → 没报错三级），
  FP/FN 喂 d-improve 改 critics；重跑产出的新轨迹（带当前
  `skill_hash`）**替换**池子里的旧轨迹，池子随轮次逐步变成新技能的
  执行样本。

内环每轮转：D 判轨迹 → fail 喂 G 改技能。
外环抽查：Oracle 重跑取真值 → FP/FN 喂 D 改 critics → 新轨迹放回。

周期监测：每 `eval_every`（默认 10）轮用当前技能在 test 集上重跑一次记
成功率，收尾把各 checkpoint 串成成功率演进图（`stats/test_eval.svg`）。
纯监测，不回写池子、不喂 G/D、不影响收敛。

花钱主项是审计的重跑（每条一次做题调用）；配 checker 的条目判分零
模型调用。

## 目录布局

```
<项目根>/
├── .claude/
│   ├── commands/veriskill-loop.md   # /veriskill-loop 主流程（编排者）
│   └── agents/                      # d-improve / g-improve 子 Agent
├── verify.sh                        # D 文本判决（永不编辑）
├── oracle_run.sh                    # 审计：重跑+判分+产新轨迹（永不编辑）
├── eval_test.sh                     # 周期/收尾：当前技能跑 test 集记成功率（永不编辑）
├── plot_test_eval.py                # 报表：成功率演进图（SVG，无依赖）
├── lib/                             # 后端适配、JSON 解析、池子操作（永不编辑）
├── workspace/
│   ├── actor_skills/                # G 技能库（空库冷启动）
│   └── critics/                     # D 技能库（空库冷启动）
└── pool/
    ├── traj/<id>.md                 # 轨迹池（审计后滚动替换）
    ├── meta.json                    # Setup 登记，循环维护
    ├── checkers/<id>.sh             # 可选：专用判分脚本
    ├── truth/<id>.md                # 可选：参考答案
    └── gate_allowlist.txt           # 可选：门控白名单（领域通用词）
```

## 轨迹规范格式

```markdown
---
skill_hash: <12位指纹或省略>
---
## 题目
（题面）
## 激活技能         # 可选
## 过程             # 可选，保留原始证据（工具输出、表格原文）
## 最终答案
（答案）
```

必须能切出「题目」「最终答案」两节（节标记的同义写法见
`lib/extract.py` 文件头）。接入新数据集时在入库前写转换器统一成此
格式；gold 只进 checker/truth，绝不进轨迹文件。

## 在 101 服务器上跑起来（OfficeQA）

### 服务器与路径

| 对象 | 位置 |
|---|---|
| 服务器 | `11.11.1.101`（经跳板机 `113.44.113.202` 双跳：先 ssh 跳板机，再 `ssh 11.11.1.101`） |
| 项目根 | `/root/data/officeqa_run/veriskill/` |
| **轨迹池** | `/root/data/officeqa_run/veriskill/pool/traj/`（原始快照备份在 `pool/traj_orig/`，重置时 rsync 回来） |
| 原始轨迹 pkl | `/root/data/officeqa_run/results/hard_ds4flash.pkl` |
| 题目语料 | `/root/data/officeqa_run/workspace/data/treasury_bulletins/`（重跑时经 `VERISKILL_TASK_DATA` 以 symlink 挂进做题工作区） |
| gold/判分 | `pool/checkers/`（`make_checkers.py` 生成，官方 `score_answer` 判分）；gold 源在 `/root/.officeqa_keys/`（轨迹池外，做题看不到） |
| EvoSkill venv | `/root/data/EvoSkill/.venv/bin/python`（转换 pkl、checker 判分用） |

### 部署 + 点火

```bash
# 1. 把本包解压为项目根（或合并进已有目录）
cd /root/data/officeqa_run && unzip veriskill-v4.zip && mv v4 veriskill
cd veriskill

# 2. 一次性 Setup（幂等可重跑）：
#    转换 pkl→pool/traj、生成 checker、写 env.sh/.claude/settings.json
#    （token 从 /root/data/veriskill/.claude/settings.json 读入）、生成
#    门控白名单、轨迹格式体检、后端 selftest（花一次最小调用）
bash adapters/setup_officeqa_101.sh

# 3. 点火（nohup 常驻，watchdog 自动重启，断链不影响）
bash adapters/launch_loop_101.sh          # 默认 rounds=3 batch=30 audit_frac=0.2
bash adapters/launch_loop_101.sh 5 30 0.2 # 续跑到第 5 轮（ledger.round 接着走）
```

`env.sh` 里的关键项（setup 自动写好，改了下次点火生效）：

- `VERISKILL_TIMEOUT=1500`：单次调用超时。hard 题重跑常超 10 分钟，
  600 会大批误杀；
- `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`：headless 无限等后台子
  Agent，否则等满 600s 编排者就自行退出；
- `VERISKILL_TASK_DATA` / `VERISKILL_SOLVE_NOTE`：语料挂载与做题守则
  （只从源文档取数、带单位、禁上网、禁找答案文件）。

### 监控与产出

```bash
tail -f loop_*.log            # watchdog 记每次 attempt 与退出码
cat ledger.json               # round / g_version / oracle 计数
cat report.md                 # 逐轮指标表 + 备注 + 收尾报告
ls rounds/r<N>/               # 每轮判决、审计、放回、子 Agent 输出
ls workspace/actor_skills/    # 长出来的解题技能
ls workspace/critics/         # 长出来的验证技能
```

`rounds/r<N>/new_traj/` 是审计产出的新轨迹，`replaced/` 是被替换下来
的旧轨迹存档；`history/` 存每轮前后与 accepted 快照，回滚从这里拿。

### 已踩过的坑（本包已修复，列出防回退）

1. 重跑超时要 1500s（600s 时 hard 题 6 条审计里 4 条被杀）。
2. headless claude 等后台子 Agent 有 600s 上限，必须设
   `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`。
3. 门控 8 字重叠检查需排除 frontmatter 行/R 判据信封，并配
   `pool/gate_allowlist.txt`（领域通用词），否则 critic 永远立不住
   （`description:` 的 "descript" 八个字就能撞上轨迹英文文本）。
4. 机器上有外部监控进程会 SIGKILL 长时进程树（无痕死亡）——launch
   脚本的 watchdog 会记录退出码并自动续跑，最多 5 次。
5. 远程 ssh 里别用 `pkill -f <脚本名>`——命令串本身含该字符串会把
   自己的 shell 杀掉。

## 接入新数据集

在 `adapters/` 下放四样接入件（现有 OfficeQA 实现当样例）：
转换器（原始轨迹→规范格式）、checker 生成器（零模型调用判分）、
部署脚本（环境接线 + 幂等 setup）、点火脚本（nohup + watchdog）。
技能库不属于接入件——G/D 从空库冷启动，技能由共演化从数据里长出。
