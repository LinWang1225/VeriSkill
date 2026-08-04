#!/bin/bash
# 在 101 上一次性搭好 VeriSkill×FrontierScience(Olympiad) 工作区。幂等。
#   bash setup_frontiersci_101.sh
set -euo pipefail

VS=/root/data/frontiersci_run/veriskill
PKL=/root/data/frontiersci_run/results/all_ds4flash.pkl
KEYS=/root/.frontiersci_keys/olympiad_all.csv
VENV=/root/data/EvoSkill/.venv/bin/python
export PYTHONPATH=/root/data/EvoSkill:/root/data/frontiersci_run

mkdir -p "$VS"
cd "$VS"
mkdir -p pool/traj pool/traj_full pool/checkers workspace/actor_skills workspace/critics

echo "== 1/6 转换轨迹（原版进 traj_full，压缩版进 traj；剔除超时 error）=="
$VENV adapters/convert_frontiersci.py --pkl "$PKL" --keys "$KEYS" \
  --traj-out pool/traj_full --gold-out pool/checkers/golds.json
python3 lib/compress.py --dir pool/traj_full pool/traj

echo "== 2/6 生成 checker（官方 Olympiad judge，每次判分一次模型调用）=="
python3 adapters/make_checkers.py --golds pool/checkers/golds.json \
  --prompt adapters/olympiad_judge_prompt.txt --out pool/checkers

echo "== 2.5/6 门控白名单（学科通用词不算题面泄露）=="
cat > pool/gate_allowlist.txt <<'EOT'
olympiad
physics
chemistry
biology
final answer
closed-form
supercoiled
plasmid
electrophoresis
polymerase
signaling pathway
free energy
magnetic field
EOT

echo "== 3/6 技能库（冷启动：两库为空，一切由共演化从数据里长出）=="
ls workspace/critics workspace/actor_skills

echo "== 4/6 后端接线（token 优先读 officeqa veriskill 的新 key，退回 EvoSkill）=="
python3 - <<'PY'
import json, os
src = None
for p in ("/root/data/officeqa_run/veriskill/.claude/settings.json",
          "/root/data/EvoSkill/.claude/settings.json"):
    if os.path.exists(p):
        src = json.load(open(p)); break
env = src.get("env", {})
tok = env.get("ANTHROPIC_AUTH_TOKEN", "")
assert tok, "找不到 ANTHROPIC_AUTH_TOKEN"
base = env.get("ANTHROPIC_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding")
os.makedirs(".claude", exist_ok=True)
cfg = {"env": {"ANTHROPIC_AUTH_TOKEN": tok, "ANTHROPIC_API_KEY": tok,
               "ANTHROPIC_BASE_URL": base, "IS_SANDBOX": "1"}}
json.dump(cfg, open(".claude/settings.json", "w"), indent=1)
with open("env.sh", "w") as f:
    f.write(f"export ANTHROPIC_AUTH_TOKEN='{tok}'\n")
    f.write(f"export ANTHROPIC_API_KEY='{tok}'\n")
    f.write(f"export ANTHROPIC_BASE_URL='{base}'\n")
    f.write("export IS_SANDBOX=1\n")
    f.write("export VERISKILL_BACKEND=claude\n")
    f.write("export VERISKILL_MODEL=deepseek-v4-flash-260601\n")
    f.write("export VERISKILL_RUBRIC_THRESHOLD=0.6\n")
    f.write("export VERISKILL_JOBS=4\n")
    f.write("export VERISKILL_TIMEOUT=1500\n")
    f.write("export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0\n")
    # 闭卷：不挂任务数据。做题守则已并入 oracle 的基础提示词（对齐生成期
    # TASK_PROMPT），SOLVE_NOTE 置空避免重复/中英文混杂。
    f.write("export VERISKILL_SOLVE_NOTE=''\n")
os.chmod("env.sh", 0o600)
print("written .claude/settings.json + env.sh")
PY

echo "== 5/6 轨迹格式体检 =="
python3 lib/extract.py --check pool/traj | tail -3

echo "== 6/6 后端 selftest + checker 冒烟 =="
source env.sh
bash verify.sh --selftest
first=$(ls pool/traj/*.md | head -1)
bash oracle_run.sh "$first" >/dev/null 2>&1 && echo "oracle 冒烟 OK" || echo "oracle 冒烟返回非0（可能该题当前技能重跑判错，正常）"

echo "SETUP DONE"
