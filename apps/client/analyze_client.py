from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_payload(path: str, mode: str) -> Dict[str, str]:
    return {"path": path, "mode": mode}


def post_analyze(url: str, payload: Dict[str, str]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{url.rstrip('/')}/v1/analyze",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def format_pretty(result: Dict[str, Any]) -> str:
    lines = []
    snapshot = result.get("snapshot") or ""
    if snapshot:
        lines.append(snapshot)
    risks = result.get("risks") or []
    lines.append(f"total risks: {len(risks)}")
    for risk in risks:
        lines.append(
            f"{risk.get('rule_id', 'unknown')} | {risk.get('severity', 'medium')} | {risk.get('message', '')}"
        )
        for source in (risk.get("evidence") or [])[:5]:
            resource_type = source.get("resource_type") or "unknown"
            resource_id = source.get("resource_id") or "unknown"
            lines.append(f"  - src: {resource_type}/{resource_id}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze patient via API.")
    parser.add_argument("--url", required=True, help="Base API URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--path", required=True, help="Path to patient JSON bundle.")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock")
    parser.add_argument("--pretty", action="store_true", help="Print human readable output.")
    parser.add_argument("--debug", action="store_true", help="Print resolved path and URL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    if not path.exists():
        print(f"Path not found: {path}", file=sys.stderr)
        return 1
    if args.debug:
        print(f"resolved_path={path}")
        print(f"request_url={args.url.rstrip('/')}/v1/analyze")
    payload = build_payload(str(path), args.mode)
    try:
        result = post_analyze(args.url, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        print(body or str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.pretty:
        print(format_pretty(result))
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
