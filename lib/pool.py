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


def _rank_key(seed, item_id):
    # 稳定的每题哈希，作为排序键；id 做确定性 tiebreak 在调用处补。
    return int(hashlib.sha1(f"{seed}:{item_id}".encode()).hexdigest(), 16)


def assign_splits(all_ids, seed, train_ratio):
    """严格配额划分：对**全集** ID 按哈希排名，恰好取 round((1-r)*N) 条为 test。

    只依赖 (全集ID, seed, train_ratio) —— 与登记顺序、哪些题已产出轨迹无关，
    故既严格满足比例又完全可复现（增量登记每轮重算得同一结果）。
    高哈希端判 test（沿用旧语义方向：旧实现 hash%100>=r*100 → test）。
    返回 {id: "train"|"test"}。"""
    ids = sorted(set(all_ids))
    n = len(ids)
    if n == 0:
        return {}
    n_train = round(float(train_ratio) * n)
    n_test = n - n_train
    ranked = sorted(ids, key=lambda i: (_rank_key(seed, i), i))
    test_ids = set(ranked[n_train:]) if n_test > 0 else set()
    return {i: ("test" if i in test_ids else "train") for i in ids}


def _universe(a, meta, traj_ids):
    """全集 ID：优先按数据集/总量给出的 q%03d 全域，并入已登记与轨迹里的 ID。
    给了 --dataset/--total 才能保证严格 N 分母；否则退化为对已知集合严格划分。"""
    ids = set(it["id"] for it in meta["items"]) | set(traj_ids)
    total = None
    if getattr(a, "dataset", None):
        try:
            with open(a.dataset, encoding="utf-8") as f:
                total = sum(1 for line in f if line.strip())
        except OSError as e:
            print(f"警告：--dataset 读不到（{e}），退化为已知集合划分", file=sys.stderr)
    if total is None and getattr(a, "total", None):
        total = a.total
    if total:
        ids |= {f"q{i:03d}" for i in range(total)}
    return ids


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

    traj_ids = [fn[:-3] for fn in os.listdir(a.traj_dir) if fn.endswith(".md")]
    universe = _universe(a, meta, traj_ids)
    assignment = assign_splits(universe, a.seed, a.train_ratio)

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
            "split": assignment.get(item_id, "train"),
        })
        added += 1

    if added:
        save_meta(a.meta, meta)
    n_train = sum(1 for it in meta["items"] if it["split"] == "train")
    n_test = len(meta["items"]) - n_train
    # 设计配额（对全集严格） vs 实际登记；若有 test 题从未产出轨迹，
    # 实际 test 会少于设计 test —— 这是覆盖缺口，不是划分不严格。
    designed_test = sum(1 for v in assignment.values() if v == "test")
    registered = {it["id"] for it in meta["items"]}
    missing_test = sorted(i for i, v in assignment.items()
                          if v == "test" and i not in registered)
    if missing_test:
        print(f"警告：{len(missing_test)} 个 test 题尚无轨迹（不计入实际 test）："
              f"{missing_test}", file=sys.stderr)
    print(json.dumps({"added": added, "total": len(meta["items"]),
                      "train": n_train, "test": n_test,
                      "universe": len(assignment), "designed_test": designed_test},
                     ensure_ascii=False))


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
    fails = sorted((v for v in fresh if v["verdict"] == "fail"),
                   key=lambda v: (v.get("confidence", 0), v["item"]))

    # 误杀段：判 fail 里 confidence 最低的，找 FP
    b = a.budget
    mis = fails[:b // 2]
    pass_quota = b - len(mis)

    # 高效利用稀疏审计：判 pass 分两拨——低置信(D 不确定，最可能 FN)和
    # 高置信。优先审低置信 pass；名额有余再从高置信里随机抽一小部分
    # (保留无偏性、防 G 学会"让 D 高信心放行"逃审)。
    passes = [v for v in fresh if v["verdict"] == "pass"]
    LOWC = 0.8  # confidence < 0.8 视为"D 不确定"
    low = sorted((v for v in passes if v.get("confidence", 1.0) < LOWC),
                 key=lambda v: (v.get("confidence", 1.0), v["item"]))
    high = sorted((v for v in passes if v.get("confidence", 1.0) >= LOWC),
                  key=lambda v: v["item"])
    random.seed(a.round)
    # 低置信段占 pass 名额的至多 3/4，剩下留给高置信随机段保无偏
    low_quota = min(len(low), max(pass_quota - pass_quota // 4, pass_quota - 1)) \
        if pass_quota else 0
    low_pick = low[:low_quota]
    rand_quota = pass_quota - len(low_pick)
    rand = (random.sample(high, rand_quota) if len(high) > rand_quota
            else list(high))
    # 若高置信不够填满，补低置信里剩下的
    if len(low_pick) + len(rand) < pass_quota:
        extra = [v for v in low[low_quota:]][:pass_quota - len(low_pick) - len(rand)]
        low_pick += extra

    for v in low_pick:
        print(json.dumps({"item": v["item"], "segment": "低置信"}, ensure_ascii=False))
    for v in rand:
        print(json.dumps({"item": v["item"], "segment": "随机"}, ensure_ascii=False))
    for v in mis:
        print(json.dumps({"item": v["item"], "segment": "误杀"}, ensure_ascii=False))
    print(f"队列：低置信 {len(low_pick)} + 随机 {len(rand)} + 误杀 {len(mis)}"
          f"（预算 {b}，剔除已审 {len(verdicts) - len(fresh)} 条）", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("register")
    p.add_argument("--meta", required=True)
    p.add_argument("--traj-dir", required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--train-ratio", type=float, required=True)
    # 严格比例需要知道全集大小：给数据集路径（数行）或直接给总量。
    # 二者都不给则退化为对"已登记∪轨迹"集合严格划分（分母会随登记漂移）。
    p.add_argument("--dataset", help="全集题库路径（如 olympiad.jsonl），行数=全集大小")
    p.add_argument("--total", type=int, help="全集题数（替代 --dataset 直接给）")

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
