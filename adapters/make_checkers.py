#!/usr/bin/env python3
"""为每条 FrontierScience-Olympiad 轨迹生成 Oracle checker。

  python3 make_checkers.py --golds pool/checkers/golds.json \
      --prompt adapters/olympiad_judge_prompt.txt --out pool/checkers

判分对齐官方：FrontierScience-Olympiad 用 LLM judge 比较等价性
（1 位小数容差、等价代数式、化学式↔名、单位等价）。checker 直接打
一次模型 API（Anthropic messages 接口 {BASE}/v1/messages），跑官方
judge prompt，解析 VERDICT: CORRECT/INCORRECT。不起 claude code
agent——judge 只是一次判对错的文本调用，直连 API 又快又省。

oracle_run.sh 约定：checker 以一个含「## 题目」「## 最终答案」节的文件
为参数（重跑产物、旧轨迹、test 轨迹都满足），退出码 0=pass 1=fail
其他=环境故障（API 失败/无 verdict）。API 端点、key、模型从 env.sh
export 的 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / VERISKILL_MODEL
读取（与 verify/oracle 同一后端与 key）。
"""
import argparse
import json
import os
import stat

CORE = r'''#!/usr/bin/env python3
import json, os, re, sys, urllib.request, urllib.error

def call_api(prompt, model, base, tok, timeout=600):
    body = json.dumps({"model": model, "max_tokens": 200,
                       "thinking": {"type": "disabled"},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": tok,
                 "anthropic-version": "2023-06-01"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    # glm 返回 [thinking, text]；拼接所有 text 类型 block
    return "\n".join(b.get("text", "") for b in r.get("content", [])
                     if b.get("type") == "text")

def extract_section(text, names):
    # 取最后一个匹配标记之后、到下一个 ## 之前的内容
    pat = r"^#+\s*(?:" + "|".join(names) + r")\s*$"
    last = None
    for m in re.finditer(pat, text, re.M):
        last = m
    if last is None:
        return None
    rest = text[last.end():]
    nxt = re.search(r"^#+\s+", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()

def main():
    tid, traj_path = sys.argv[1], sys.argv[2]
    here = os.path.dirname(os.path.abspath(__file__))
    golds = json.load(open(os.path.join(here, "golds.json")))
    if tid not in golds:
        print(f"no gold for {tid}"); return 4
    text = open(traj_path, encoding="utf-8").read()
    problem = extract_section(text, ["题目", "Problem", "问题"]) or ""
    answer = extract_section(text, ["最终答案", "Final Answer", "答案"])
    if not answer:
        print("轨迹缺「最终答案」节"); return 4
    ref = golds[tid]

    tmpl = open(os.path.join(here, "olympiad_judge_prompt.txt"), encoding="utf-8").read()
    prompt = (tmpl.replace("{problem}", problem[:3000])
                  .replace("{reference_answer}", ref)
                  .replace("{answer}", answer[:1000]))

    model = os.environ.get("VERISKILL_MODEL", "")
    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    tok = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not (model and base and tok):
        print("缺 VERISKILL_MODEL / ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN（source env.sh）"); return 5
    try:
        out = call_api(prompt, model, base, tok)
    except urllib.error.HTTPError as e:
        print(f"judge API HTTP {e.code}: {e.read()[:120]!r}"); return 5
    except Exception as e:
        print(f"judge API 失败: {e}"); return 5
    m = re.findall(r"VERDICT:\s*(CORRECT|INCORRECT)", out, re.I)
    if not m:
        print(f"judge 无 VERDICT: {out[:120]!r}"); return 5
    verdict = m[-1].upper()
    print(f"judge({model}): ref={ref[:40]!r} ans={answer[:40]!r} -> {verdict}")
    return 0 if verdict == "CORRECT" else 1

if __name__ == "__main__":
    sys.exit(main())
'''

SH = '''#!/bin/bash
exec /root/data/EvoSkill/.venv/bin/python "{core}" {tid} "$1"
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golds", required=True)
    ap.add_argument("--prompt", required=True, help="官方 judge prompt 模板")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    golds = json.load(open(a.golds))
    os.makedirs(a.out, exist_ok=True)

    core = os.path.abspath(os.path.join(a.out, "checker_core.py"))
    with open(core, "w", encoding="utf-8") as f:
        f.write(CORE)
    os.chmod(core, os.stat(core).st_mode | stat.S_IEXEC)

    # judge prompt 放到 checker 同目录，checker_core 从 here 读
    import shutil
    shutil.copy(a.prompt, os.path.join(a.out, "olympiad_judge_prompt.txt"))

    for tid in golds:
        p = os.path.join(a.out, f"{tid}.sh")
        with open(p, "w") as f:
            f.write(SH.format(core=core, tid=tid))
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    print(json.dumps({"checkers": len(golds), "judge": "official-olympiad-llm"}))


if __name__ == "__main__":
    main()
