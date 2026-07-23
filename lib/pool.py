#!/usr/bin/env python3
"""池子操作的确定性实现：登记、取批、排审计队列。

编排者每轮调这里的子命令，**不要自己现写等价逻辑**——同一份规则手写
两遍就是两种实现，抽样顺序稍有出入，"全程可从 history 复现"就破产了。

子命令：

  register    扫描 pool/traj/ 里新出现的轨迹，登记进 meta.json（含 split）
  sample      取一批训练轨迹，写 batch.list，回写 used_count
  audit-queue 按两段制排出本轮审计队列（剔除已审组合）

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

    ids = {it["id"] for it in picked}
    for it in meta["items"]:
        if it["id"] in ids:
            it["used_count"] += 1
    save_meta(a.meta, meta)

    batch_sorted = sorted(it["id"] for it in picked)
    with open(a.out_batch, "w") as f:
        f.write("".join(i + "\n" for i in batch_sorted))
    print(json.dumps({"batch": len(batch_sorted)}))


# ---------------------------------------------------------------- audit-queue

def cmd_audit_queue(a):
    with open(a.audited, encoding="utf-8") as f:
        audited = set(json.load(f))

    verdicts = []
    with open(a.verdicts, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                verdicts.append(json.loads(line))

    # 两种去重键都要查：checker/truth 条目审过一次记 <id>@static（结论与
    # 技能无关，永久免审）；真实重做条目记 <id>@<指纹>（技能变了算新观测）
    fresh = [v for v in verdicts
             if f'{v["item"]}@static' not in audited
             and f'{v["item"]}@{a.fingerprint}' not in audited]
    passes = sorted((v for v in fresh if v["verdict"] == "pass"),
                    key=lambda v: v["item"])
    fails = sorted((v for v in fresh if v["verdict"] == "fail"),
                   key=lambda v: (v.get("confidence", 0), v["item"]))

    b = a.budget
    mis = fails[:b // 2]
    rand_quota = b - len(mis)
    random.seed(a.round)
    rand = (random.sample(passes, rand_quota) if len(passes) > rand_quota
            else list(passes))

    for v in rand:
        print(json.dumps({"item": v["item"], "segment": "随机"}, ensure_ascii=False))
    for v in mis:
        print(json.dumps({"item": v["item"], "segment": "误杀"}, ensure_ascii=False))
    print(f"队列：随机 {len(rand)} + 误杀 {len(mis)}（预算 {b}，"
          f"剔除已审 {len(verdicts) - len(fresh)} 条）", file=sys.stderr)


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

    a = ap.parse_args()
    {"register": cmd_register, "sample": cmd_sample,
     "audit-queue": cmd_audit_queue}[a.cmd](a)


if __name__ == "__main__":
    main()
