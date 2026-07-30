#!/usr/bin/env python3
"""Archive an older VeriSkill run and initialize a clean v6 experiment state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class ResetError(RuntimeError):
    pass


def split_of(seed: int, item_id: str, train_ratio: float) -> str:
    bucket = int(hashlib.sha1(f"{seed}:{item_id}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < int(train_ratio * 100) else "test"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResetError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ResetError(f"invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def unique_archive(root: Path, archive_root: Path, label: str | None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = label or f"pre_v6_{stamp}"
    target = archive_root / base
    counter = 1
    while target.exists():
        target = archive_root / f"{base}_{counter}"
        counter += 1
    return target


def resolve_traj_snapshot(root: Path, value: str | None) -> Path | None:
    if value:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (root / path).resolve()
    default = root / "pool" / "traj_orig"
    return default.resolve() if default.is_dir() else None


def build_plan(
    root: Path, preserve_actor: bool, preserve_critics: bool, traj_snapshot: Path | None
) -> Dict[str, Any]:
    move_names = ["rounds", "stats", "history", "experience", "report.md", "ledger.json"]
    moves = [name for name in move_names if (root / name).exists()]
    skill_actions = []
    actor = root / "workspace" / "actor_skills"
    critics = root / "workspace" / "critics"
    if actor.exists() and not preserve_actor:
        skill_actions.append("workspace/actor_skills")
    if critics.exists() and not preserve_critics:
        skill_actions.append("workspace/critics")
    return {
        "move_to_archive": moves,
        "archive_and_clear_skills": skill_actions,
        "reset_meta": "pool/meta.json",
        "restore_trajectory_snapshot": str(traj_snapshot) if traj_snapshot else None,
        "create_flow_version": 6,
    }


def archive_path(src: Path, archive_dir: Path, rel: str) -> None:
    dst = archive_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)


def apply_reset(args: argparse.Namespace) -> Dict[str, Any]:
    root = Path(args.root).resolve()
    meta_path = root / "pool" / "meta.json"
    meta = load_json(meta_path)
    if not isinstance(meta, dict) or not isinstance(meta.get("items"), list):
        raise ResetError("pool/meta.json must contain an items list")
    ids = []
    for row in meta["items"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ResetError("every meta item must contain a string id")
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ResetError("pool/meta.json contains duplicate item ids")
    archive_root = (root / args.archive_root).resolve()
    archive_dir = unique_archive(root, archive_root, args.label)
    traj_snapshot = resolve_traj_snapshot(root, args.restore_traj_from)
    if traj_snapshot and not traj_snapshot.is_dir():
        raise ResetError(f"trajectory snapshot is not a directory: {traj_snapshot}")
    plan = build_plan(root, args.preserve_actor, args.preserve_critics, traj_snapshot)
    result = {
        "root": str(root),
        "archive": str(archive_dir),
        "plan": plan,
        "applied": False,
    }
    if not args.apply:
        return result

    archive_dir.mkdir(parents=True, exist_ok=False)
    # Save the exact pre-reset metadata even though meta.json remains in place.
    (archive_dir / "pool").mkdir(parents=True, exist_ok=True)
    shutil.copy2(meta_path, archive_dir / "pool" / "meta.json")

    for rel in plan["move_to_archive"]:
        archive_path(root / rel, archive_dir, rel)

    for rel in plan["archive_and_clear_skills"]:
        src = root / rel
        if src.exists():
            archive_path(src, archive_dir, rel)
        src.mkdir(parents=True, exist_ok=True)

    if traj_snapshot:
        traj_dir = root / "pool" / "traj"
        full_dir = root / "pool" / "traj.full"
        if traj_dir.exists():
            archive_path(traj_dir, archive_dir, "pool/traj_before_v6")
        if full_dir.exists():
            archive_path(full_dir, archive_dir, "pool/traj.full_before_v6")
        shutil.copytree(traj_snapshot, traj_dir)
        snapshot_full_candidates = [
            Path(str(traj_snapshot) + ".full"),
            traj_snapshot.parent / (traj_snapshot.name + ".full"),
        ]
        snapshot_full = next((x for x in snapshot_full_candidates if x.is_dir()), None)
        if snapshot_full:
            shutil.copytree(snapshot_full, full_dir)
        else:
            full_dir.mkdir(parents=True, exist_ok=True)
            for file_path in traj_dir.glob("*.md"):
                shutil.copy2(file_path, full_dir / file_path.name)

    # Preserved skill directories still need to exist.
    (root / "workspace" / "actor_skills").mkdir(parents=True, exist_ok=True)
    (root / "workspace" / "critics").mkdir(parents=True, exist_ok=True)

    train = test = 0
    for row in meta["items"]:
        row["used_count"] = 0
        row["g_version"] = 0
        if args.recompute_split:
            row["split"] = split_of(args.split_seed, row["id"], args.train_ratio)
        if row.get("split") == "train":
            train += 1
        elif row.get("split") == "test":
            test += 1
        else:
            raise ResetError(f"invalid split for {row['id']}: {row.get('split')}")
    write_json_atomic(meta_path, meta)

    for directory in ("rounds", "stats", "history", "experience/oracle_to_g", "experience/oracle_to_d"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "stats" / "candidate_eval.jsonl").write_text("", encoding="utf-8")
    (root / "stats" / "test_eval.jsonl").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "# VeriSkill v6 experiment\n\n"
        "| round | candidate | D verdict | revisions | scored | improvement | regression | net | accepted | g_version | d_version |\n"
        "|---:|---|---|---:|---:|---:|---:|---:|---|---:|---:|\n",
        encoding="utf-8",
    )
    ledger = {
        "flow_version": 6,
        "round": 0,
        "g_version": 0,
        "d_version": 0,
        "candidate_attempts": 0,
        "accepted_candidates": 0,
        "rejected_candidates": 0,
        "oracle_attempts": 0,
        "oracle_failures": 0,
    }
    write_json_atomic(root / "ledger.json", ledger)
    result.update({
        "applied": True,
        "train": train,
        "test": test,
        "preserved_actor": args.preserve_actor,
        "preserved_critics": args.preserve_critics,
        "restored_trajectory_snapshot": str(traj_snapshot) if traj_snapshot else None,
    })
    write_json_atomic(archive_dir / "reset_manifest.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--archive-root", default="archive")
    parser.add_argument("--label")
    parser.add_argument("--apply", action="store_true", help="perform the reset; without this flag only print the plan")
    parser.add_argument("--preserve-actor", action="store_true", help="warm-start from the current official G")
    parser.add_argument("--preserve-critics", action="store_true", help="keep old critics; not recommended across v5->v6")
    parser.add_argument(
        "--restore-traj-from",
        help="restore immutable training trajectories from this snapshot; defaults to pool/traj_orig when present",
    )
    parser.add_argument("--recompute-split", action="store_true")
    parser.add_argument("--split-seed", type=int, default=0)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 0 < args.train_ratio < 1:
        print("start_v6_experiment: --train-ratio must be between 0 and 1", file=sys.stderr)
        return 2
    try:
        result = apply_reset(args)
    except (ResetError, OSError) as exc:
        print(f"start_v6_experiment: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
