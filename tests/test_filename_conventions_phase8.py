from __future__ import annotations

from tests.filename_rules import find_filename_violations


# Rule summary: fail fast on phase/final/v/tmp filename markers.
def test_filename_conventions() -> None:
    violations = find_filename_violations()
    if violations:
        lines = ["Forbidden filenames detected:"]
        for item in violations:
            lines.append(f"- {item['path']} (pattern: {item['pattern']})")
        raise AssertionError("\n".join(lines))
