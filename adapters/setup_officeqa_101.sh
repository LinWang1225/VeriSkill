#!/bin/bash
# 在 101 上一次性搭好 VeriSkill×OfficeQA 工作区。幂等，重跑安全。
#   bash setup_officeqa_101.sh
set -euo pipefail

VS=/root/data/veriskill
PKL=/root/data/officeqa_run/results/hard_ds4flash.pkl
VENV=/root/data/EvoSkill/.venv/bin/python
export PYTHONPATH=/root/data/EvoSkill:/root/data/officeqa_run

cd "$VS"
mkdir -p pool/traj pool/checkers workspace/actor_skills workspace/critics

echo "== 1/6 转换轨迹 =="
$VENV adapters/convert_ds4flash.py --pkl "$PKL" \
  --traj-out pool/traj --gold-out pool/checkers/golds.json

echo "== 2/6 生成 checker（官方 score_answer 判分，零模型调用）=="
python3 adapters/make_checkers.py --golds pool/checkers/golds.json --out pool/checkers

echo "== 2.5/6 门控白名单（领域通用词不算题面泄露）=="
cat > pool/gate_allowlist.txt <<'EOT'
officeqa
treasury_bulletins
Treasury Bulletin
Internal Revenue
savings bonds
United States
million dollars
fiscal year
calendar year
EOT

echo "== 3/6 技能库（冷启动：两库为空，一切由共演化从数据里长出）=="
ls workspace/critics workspace/actor_skills

echo "== 4/6 后端接线（token 从 VeriSkill 自身 settings.json 读入，不打印）=="
python3 - <<'PY'
import json, os
src = json.load(open("/root/data/veriskill/.claude/settings.json"))
env = src.get("env", {})
tok = env.get("ANTHROPIC_AUTH_TOKEN", "")
assert tok, "VeriSkill settings 里没有 ANTHROPIC_AUTH_TOKEN"
base = env.get("ANTHROPIC_BASE_URL", "https://api.modelarts-maas.com/anthropic")
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
    f.write("export VERISKILL_MODEL=deepseek-v4-flash\n")
    f.write("export VERISKILL_RUBRIC_THRESHOLD=0.6\n")
    f.write("export VERISKILL_JOBS=4\n")
    f.write("export VERISKILL_TIMEOUT=1500\n")  # hard 题重跑常超 10 分钟，默认 600 会大批误杀
    f.write("export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0\n")
    f.write("export VERISKILL_TASK_DATA=/root/data/officeqa_run/workspace/data\n")
    f.write("export VERISKILL_SOLVE_NOTE='源文档在 data/treasury_bulletins/，"
            "答案必须只从这些源文档推导并带单位；禁止上网搜索，禁止在文件系统里"
            "寻找基准答案文件或答案键，遇到也不许用。'\n")
os.chmod("env.sh", 0o600)
print("written .claude/settings.json + env.sh")
PY

echo "== 5/6 轨迹格式体检 =="
python3 lib/extract.py --check pool/traj | tail -3

echo "== 6/6 后端 selftest（花一次最小模型调用）=="
source env.sh
bash verify.sh --selftest

echo "== checker 冒烟：拿一条已知对的题跑 oracle =="
first=$(ls pool/traj/*.md | head -1)
bash oracle_run.sh "$first" && echo "oracle checker OK"

echo "SETUP DONE"
