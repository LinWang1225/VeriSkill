#!/usr/bin/env python3
"""池子操作的确定性实现：登记、取批、排审计队列。

编排者每轮调这里的子命令，**不要自己现写等价逻辑**——同一份规则手写
两遍就是两种实现，抽样顺序稍有出入，"全程可从 history 复现"就破产了。

子命令：

  register    扫描 pool/traj/ 里新出现的轨迹，登记进 meta.json（含 split）
  sample      取一批训练轨迹，写 batch.list，回写 used_count
  audit-queue 分层排出本轮审计队列（剔除已审组合与无真值条目）

统一约定：所有随机操作先按条目 ID 排序，再 random.seed(轮号)，再抽。
meta.json 写回一律先写临时文件再原子替换。

退出码：0 正常；2 参数或文件问题；3 轨迹池耗尽（sample 专用）。
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------- 公共

def load_meta(path):
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    if "items" not in meta or not isinstance(meta["items"], list):
        sys.exit("meta.json 缺 items 数组")
    return meta


def save_meta(path, meta):
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def split_of(seed, item_id, train_ratio):
    b = int(hashlib.sha1(f"{seed}:{item_id}".encode()).hexdigest()[:8], 16) % 100
    return "train" if b < int(float(train_ratio) * 100) else "test"


G_VERSION_RE = re.compile(r"^[^A-Za-z0-9]*g_version:\s*(\d+)")


def traj_g_version(path):
    with open(path, encoding="utf-8") as f:
        for _, line in zip(range(30), f):
            m = G_VERSION_RE.match(line)
            if m:
                return int(m.group(1))
    return 0  # 轨迹没写版本头时按 0 记，register 会对此打警告


# ---------------------------------------------------------------- register

def cmd_register(a):
    meta = load_meta(a.meta)
    known = {it["id"] for it in meta["items"]}
    if len(known) != len(meta["items"]):
        sys.exit("meta.json 里有重复 ID，先修数据")

    added = 0
    for fn in sorted(os.listdir(a.traj_dir)):
        if not fn.endswith(".md"):
            continue
        item_id = fn[:-3]
        if item_id in known:
            continue
        path = os.path.join(a.traj_dir, fn)
        meta["items"].append({
            "id": item_id,
            "g_version": traj_g_version(path),  # 没写版本头就按 0，只作记录
            "used_count": 0,
            "split": split_of(a.seed, item_id, a.train_ratio),
        })
        added += 1

    if added:
        save_meta(a.meta, meta)
    n_train = sum(1 for it in meta["items"] if it["split"] == "train")
    print(json.dumps({"added": added, "total": len(meta["items"]),
                      "train": n_train, "test": len(meta["items"]) - n_train}))


# ---------------------------------------------------------------- sample

def cmd_sample(a):
    out_path = Path(a.out_batch)
    # 幂等：本轮已写过 batch（文件存在且非空）就原样回吐，不再 +1 used_count。
    # 同轮重抽本就得到同一批（seed=轮号），重跑的唯一副作用是把 used_count
    # 重复 +1，提前烧掉 replay_K 预算、误触"池子耗尽"。编排者崩溃续跑据此
    # 安全重入，不依赖编排者自觉检查文件是否存在；想强制重抽就先删掉该文件。
    if out_path.exists():
        existing_ids = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if existing_ids:
            print(json.dumps({"batch": len(existing_ids), "resumed": True}))
            return

    meta = load_meta(a.meta)
    eligible = [it for it in meta["items"]
                if it["split"] == "train" and it["used_count"] < a.replay_k]
    if not eligible:
        print("轨迹池耗尽：没有可用的训练轨迹", file=sys.stderr)
        sys.exit(3)

    eligible.sort(key=lambda it: it["id"])
    random.seed(a.round)
    picked = (random.sample(eligible, a.batch)
              if len(eligible) > a.batch else list(eligible))

    batch_sorted = sorted(it["id"] for it in picked)
    # 先落 out_batch（本轮取批的 checkpoint）再回写 used_count：out_batch 存在
    # 即视为本轮已取样。崩溃若落在两者之间，只可能少计一次（安全方向），
    # 不会重复计数烧预算。
    with open(a.out_batch, "w") as f:
        f.write("".join(i + "\n" for i in batch_sorted))

    ids = set(batch_sorted)
    for it in meta["items"]:
        if it["id"] in ids:
            it["used_count"] += 1
    save_meta(a.meta, meta)

    print(json.dumps({"batch": len(batch_sorted)}))


# ---------------------------------------------------------------- audit-queue

def cmd_audit_queue(a):
    audited = set()
    audited_path = Path(a.audited)
    if audited_path.exists():
        raw = audited_path.read_text(encoding="utf-8").strip()
        if raw:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, list):
                for value in obj:
                    if isinstance(value, str):
                        audited.add(value)
                    elif isinstance(value, dict) and value.get("dedup_key"):
                        audited.add(str(value["dedup_key"]))
            elif isinstance(obj, dict):
                for value in obj.get("audited", []):
                    audited.add(str(value))
            else:
                for line in raw.splitlines():
                    row = json.loads(line)
                    if isinstance(row, str):
                        audited.add(row)
                    elif isinstance(row, dict) and row.get("dedup_key"):
                        audited.add(str(row["dedup_key"]))
    verdicts = []
    with open(a.verdicts, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                verdicts.append(json.loads(line))

    fresh_all = [v for v in verdicts
                 if f'{v["item"]}@static' not in audited
                 and f'{v["item"]}@{a.fingerprint}' not in audited]

    def has_truth(v):
        if a.allow_redo_as_truth or not (a.checker_dir or a.truth_dir):
            return True
        item = v["item"]
        checker = os.path.join(a.checker_dir, item + ".sh") if a.checker_dir else ""
        truth = os.path.join(a.truth_dir, item + ".md") if a.truth_dir else ""
        return (checker and os.path.isfile(checker) and os.access(checker, os.X_OK)) \
            or (truth and os.path.isfile(truth))

    fresh = [v for v in fresh_all if has_truth(v)]
    skipped_no_truth = len(fresh_all) - len(fresh)
    passes = sorted((v for v in fresh if v["verdict"] == "pass"),
                    key=lambda v: (v.get("confidence", 0), v["item"]))
    fails = sorted((v for v in fresh if v["verdict"] == "fail"),
                   key=lambda v: (v.get("confidence", 0), v["item"]))

    b = max(0, a.budget)
    segment_order = ("fail-low", "pass-low", "fail-high", "pass-random")
    base, extra = divmod(b, len(segment_order))
    targets = {name: base + (i < extra)
               for i, name in enumerate(segment_order)}
    selected = []
    selected_ids = set()

    def take(seq, n, segment):
        taken = 0
        for v in seq:
            if taken >= n:
                break
            if v["item"] in selected_ids:
                continue
            selected.append((v, segment))
            selected_ids.add(v["item"])
            taken += 1

    take(fails, targets["fail-low"], "fail-low")
    take(reversed(fails), targets["fail-high"], "fail-high")
    take(passes, targets["pass-low"], "pass-low")
    remaining_passes = [v for v in passes if v["item"] not in selected_ids]
    random.seed(a.round)
    random.shuffle(remaining_passes)
    take(remaining_passes, targets["pass-random"], "pass-random")

    remaining = [v for v in sorted(fresh, key=lambda x: x["item"])
                 if v["item"] not in selected_ids]
    random.seed(a.round + 1000003)
    random.shuffle(remaining)
    for v in remaining:
        if len(selected) >= b:
            break
        segment = "fail-low" if v["verdict"] == "fail" else "pass-random"
        selected.append((v, segment))
        selected_ids.add(v["item"])

    counts = {k: 0 for k in ("fail-low", "fail-high", "pass-low", "pass-random")}
    for v, segment in selected[:b]:
        counts[segment] += 1
        print(json.dumps({"item": v["item"], "segment": segment}, ensure_ascii=False))
    print("队列：" + " + ".join(f"{k} {counts[k]}" for k in counts)
          + f"（预算 {b}，剔除已审 {len(verdicts) - len(fresh_all)} 条，"
            f"无 checker/truth {skipped_no_truth} 条）", file=sys.stderr)

# VERISKILL_CALIBRATION_V5_163DCD8
# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("register")
    p.add_argument("--meta", required=True)
    p.add_argument("--traj-dir", required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--train-ratio", type=float, required=True)

    p = sub.add_parser("sample")
    p.add_argument("--meta", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--replay-k", type=int, required=True)
    p.add_argument("--out-batch", required=True)

    p = sub.add_parser("audit-queue")
    p.add_argument("--verdicts", required=True)
    p.add_argument("--audited", required=True)
    p.add_argument("--fingerprint", required=True)
    p.add_argument("--budget", type=int, required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--checker-dir")
    p.add_argument("--truth-dir")
    p.add_argument("--allow-redo-as-truth", action="store_true")

    a = ap.parse_args()
    {"register": cmd_register, "sample": cmd_sample,
     "audit-queue": cmd_audit_queue}[a.cmd](a)


if __name__ == "__main__":
    main()
