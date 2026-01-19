## Conventions

- File naming: do not include "phase", step numbers, "final", "v2", or "tmp" in filenames.
- Phases belong in git commits/tags and docs, not filenames.
- Eval code lives in `eval/`, scripts in `scripts/`, tests in `tests/`.
- Golden fixtures live in `tests/golden/`.
- If adding a new module, name by purpose (e.g., `eval/selector.py` not `eval/phase8_selector.py`).
- Update policy: prefer small PR-sized diffs.

### Extending the rules

- To add a new forbidden pattern, update `FORBIDDEN_PATTERNS` in `tests/filename_rules.py`.
- To exclude a directory, add it to `EXCLUDE_DIRS` or `EXCLUDE_PATH_PREFIXES` in `tests/filename_rules.py`.
- If a legacy file violates the rules and cannot be renamed yet, add a single, documented entry to `LEGACY_ALLOWLIST`.
