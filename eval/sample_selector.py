from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def _selection_key(filename: str, seed: str) -> str:
    payload = f"{seed}:{filename}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_patients(data_dir: str | Path, n: int, seed: str = "phase8") -> list[str]:
    if n <= 0:
        return []
    base_dir = Path(data_dir)
    if not base_dir.exists():
        return []
    candidates = [
        path
        for path in base_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    ]
    ordered = sorted(candidates, key=lambda path: (_selection_key(path.name, seed), path.name))
    selected = ordered[:n]
    return [path.relative_to(base_dir).as_posix() for path in selected]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select deterministic patient bundles.")
    parser.add_argument("data_dir", help="Directory containing patient JSON bundles.")
    parser.add_argument("n", type=int, help="Number of patients to select.")
    parser.add_argument("--seed", default="phase8", help="Seed string for selection.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    selected = select_patients(args.data_dir, args.n, seed=args.seed)
    for rel_path in selected:
        print(rel_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
