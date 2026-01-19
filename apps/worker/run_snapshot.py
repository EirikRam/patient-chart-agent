from __future__ import annotations

import sys

from packages.pipeline.steps.snapshot import build_snapshot


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python apps/worker/run_snapshot.py <patient.json>", file=sys.stderr)
        return 1

    print(build_snapshot(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
