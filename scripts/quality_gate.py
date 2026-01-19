from __future__ import annotations

import argparse
import subprocess
import sys
from typing import NamedTuple, Sequence


class GateStep(NamedTuple):
    name: str
    cmd: Sequence[str]


STEPS: list[GateStep] = [
    GateStep("Pytest (full)", [sys.executable, "-m", "pytest", "-q"]),
    GateStep(
        "Pytest (golden phase 6)",
        [sys.executable, "-m", "pytest", "-q", "tests/test_golden_phase6.py"],
    ),
    GateStep(
        "Pytest (result contract phase 7)",
        [sys.executable, "-m", "pytest", "-q", "tests/test_result_contract_phase7.py"],
    ),
    GateStep(
        "Pytest (filename conventions phase 8)",
        [sys.executable, "-m", "pytest", "-q", "tests/test_filename_conventions_phase8.py"],
    ),
    GateStep("Eval (mock)", [sys.executable, "-m", "eval.run_eval", "--modes", "mock", "--quiet"]),
]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic quality gate checks in order.",
    )
    parser.add_argument(
        "--continue",
        dest="continue_on_failure",
        action="store_true",
        help="Continue running all steps after a failure.",
    )
    return parser.parse_args(argv)


def _format_command(command: Sequence[str]) -> str:
    return " ".join(command)


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    out = stdout or ""
    err = stderr or ""
    if out and err:
        return f"{out}\n{err}"
    return out or err


def _tail_lines(output: str, max_lines: int = 80) -> str:
    lines = output.splitlines()
    if len(lines) <= max_lines:
        return output
    return "\n".join(lines[-max_lines:])


def run_gate(continue_on_failure: bool = False) -> int:
    results: list[tuple[GateStep, bool]] = []
    for step in STEPS:
        command_str = _format_command(step.cmd)
        print(f"Running: {command_str}")
        completed = subprocess.run(step.cmd, text=True, capture_output=True)
        ok = completed.returncode == 0
        results.append((step, ok))
        if ok:
            print(f"PASS: {step.name}")
        else:
            print(f"FAIL: {step.name}")
            output = _combine_output(completed.stdout, completed.stderr)
            print("Output (last 80 lines):")
            if output.strip():
                print(_tail_lines(output, 80))
            else:
                print("(no output)")
            if not continue_on_failure:
                break

    print("Summary:")
    for step, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"- {status}: {step.name}")
    any_failed = any(not ok for _, ok in results)
    return 1 if any_failed else 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return run_gate(continue_on_failure=args.continue_on_failure)


if __name__ == "__main__":
    sys.exit(main())
