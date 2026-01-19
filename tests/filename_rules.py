from __future__ import annotations

from pathlib import Path
import re

# Rule summary: keep filenames purpose-based by banning phase/final/v/tmp markers.
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (r"(?i)\bphase[\W_]*\d", re.compile(r"(?i)\bphase[\W_]*\d")),
    (r"(?i)\bphase[\W_]*\d+\.\d+", re.compile(r"(?i)\bphase[\W_]*\d+\.\d+")),
    (r"(?i)\bfinal\b", re.compile(r"(?i)\bfinal\b")),
    (r"(?i)\bv\d+\b", re.compile(r"(?i)\bv\d+\b")),
    (r"(?i)\btmp\b", re.compile(r"(?i)\btmp\b")),
]

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
EXCLUDE_PATH_PREFIXES = {
    Path("data") / "raw",
    Path("tests") / "golden" / "_out",
}

# Legacy phase-named files kept for continuity; avoid adding new ones.
LEGACY_ALLOWLIST = {
    Path("tests/test_eval_runner_phase7.py"),
    Path("tests/test_result_contract_phase7.py"),
    Path("tests/test_cli_contract_matrix_phase6.py"),
    Path("tests/test_api_contract_matrix_phase6.py"),
    Path("tests/test_golden_phase6.py"),
    Path("tests/test_verifier_agent_phase5.py"),
    Path("tests/test_cli_analyze_phase5.py"),
    Path("tests/test_evidence_enrichment_phase5.py"),
    Path("tests/test_agent_pipeline_phase5.py"),
    Path("tests/test_contradiction_agent_phase5.py"),
    Path("tests/test_missing_info_agent_phase5.py"),
    Path("tests/test_timeline_agent_phase5.py"),
    Path("tests/test_schema_result_phase5.py"),
    Path("tests/golden/Kris249_Moore224_api_phase5_mock_agents.json"),
    Path("tests/golden/Berna338_Moore224_api_phase5_mock_agents.json"),
    Path("tests/golden/Kris249_Moore224_phase5_mock_agents.json"),
    Path("tests/golden/Berna338_Moore224_phase5_mock_agents.json"),
    Path("tests/test_filename_conventions_phase8.py"),
    Path("tests/test_quality_gate_phase9.py"),
}


def _is_excluded(rel_path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in rel_path.parts):
        return True
    for prefix in EXCLUDE_PATH_PREFIXES:
        if rel_path.parts[: len(prefix.parts)] == prefix.parts:
            return True
    if rel_path in LEGACY_ALLOWLIST:
        return True
    return False


def find_filename_violations(repo_root: Path | None = None) -> list[dict[str, str]]:
    root = repo_root or Path(__file__).resolve().parents[1]
    violations: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        if _is_excluded(rel_path):
            continue
        name = path.name
        for raw_pattern, compiled in FORBIDDEN_PATTERNS:
            if compiled.search(name):
                violations.append(
                    {
                        "path": rel_path.as_posix(),
                        "pattern": raw_pattern,
                    }
                )
                break
    violations.sort(key=lambda item: item["path"])
    return violations


__all__ = ["find_filename_violations", "FORBIDDEN_PATTERNS"]
