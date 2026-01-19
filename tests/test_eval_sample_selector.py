from __future__ import annotations

from pathlib import Path

from eval.sample_selector import select_patients


def _write_files(base_dir: Path, filenames: list[str]) -> None:
    for name in filenames:
        (base_dir / name).write_text("{}", encoding="utf-8")


def test_select_patients_deterministic(tmp_path: Path) -> None:
    names = [
        "alpha.json",
        "bravo.json",
        "charlie.json",
        "delta.json",
        "echo.json",
    ]
    _write_files(tmp_path, names)
    first = select_patients(tmp_path, 3, seed="seed-a")
    second = select_patients(tmp_path, 3, seed="seed-a")
    assert first == second


def test_select_patients_seed_changes_output(tmp_path: Path) -> None:
    names = [
        "alpha.json",
        "bravo.json",
        "charlie.json",
        "delta.json",
        "echo.json",
    ]
    _write_files(tmp_path, names)
    first = select_patients(tmp_path, 4, seed="seed-a")
    second = select_patients(tmp_path, 4, seed="seed-b")
    assert first != second


def test_select_patients_normalizes_windows_paths(tmp_path: Path) -> None:
    names = ["alpha.json", "bravo.json", "charlie.json"]
    _write_files(tmp_path, names)
    windows_style = str(tmp_path).replace("/", "\\")
    direct = select_patients(tmp_path, 2, seed="seed-a")
    windows = select_patients(windows_style, 2, seed="seed-a")
    assert direct == windows
    assert all("\\" not in path for path in windows)
