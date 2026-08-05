#!/usr/bin/env python3
"""Canonical, location-independent fingerprints for VeriSkill directories."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Iterable

IGNORED_NAMES = {".DS_Store"}
IGNORED_SUFFIXES = (".tmp", ".swp")


def _iter_files(root: Path) -> Iterable[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name not in IGNORED_NAMES
        and not path.name.endswith(IGNORED_SUFFIXES)
    )


def hash_dir(path: Path | str, *, length: int = 12) -> str:
    """Hash relative names, executable mode bits and bytes, never absolute paths."""
    root = Path(path)
    if not root.exists():
        return "none"
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    if length < 1 or length > 64:
        raise ValueError("length must be in [1, 64]")

    digest = hashlib.sha256()
    for file_path in _iter_files(root):
        relative = file_path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update((file_path.stat().st_mode & 0o777).to_bytes(4, "big"))
        data = file_path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()[:length]


def hash_file(path: Path | str, *, length: int = 12) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise ValueError(f"not a file: {file_path}")
    if length < 1 or length > 64:
        raise ValueError("length must be in [1, 64]")
    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:length]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--length", type=int, default=12)
    args = parser.parse_args()
    try:
        print(hash_dir(args.directory, length=args.length))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
