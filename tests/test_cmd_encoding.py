from __future__ import annotations

from pathlib import Path

from system_core.core.cmd_encoding import (
    check_cmd_files,
    inspect_cmd_file,
    normalize_cmd_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_repository_cmd_files_are_utf8_no_bom_crlf() -> None:
    bad = [result for result in check_cmd_files(PROJECT_ROOT) if not result.ok]

    assert not bad, "\n".join(
        f"{result.path}: {result.summary()} {result.error}" for result in bad
    )


def test_inspect_cmd_file_detects_bom_and_lf_only(tmp_path: Path) -> None:
    path = tmp_path / "bad.cmd"
    path.write_bytes(b"\xef\xbb\xbf@echo off\n")

    result = inspect_cmd_file(path)

    assert result.has_bom is True
    assert result.lone_lf == 1
    assert result.ok is False


def test_normalize_cmd_file_strips_bom_and_converts_to_crlf(tmp_path: Path) -> None:
    path = tmp_path / "fix.cmd"
    path.write_bytes(b"\xef\xbb\xbf@echo off\nset X=1\n")

    result = normalize_cmd_file(path)

    assert result.ok is True
    assert path.read_bytes() == b"@echo off\r\nset X=1\r\n"


def test_check_cmd_files_skips_generated_and_user_data_dirs(tmp_path: Path) -> None:
    for dirname in ("runtime", "._runtime", "input", "output", "logs", "report", "data", "wheelhouse", "workspace"):
        (tmp_path / dirname).mkdir()
        (tmp_path / dirname / "vendor.cmd").write_bytes(b"\xef\xbb\xbf@echo off\n")
    (tmp_path / "launcher.cmd").write_bytes(b"@echo off\r\n")

    results = check_cmd_files(tmp_path)

    assert [result.path.name for result in results] == ["launcher.cmd"]
    assert results[0].ok is True
