from __future__ import annotations

from pathlib import Path

from system_core.core.sh_lf import check_sh_files, normalize_sh_file


def test_normalize_sh_file_strips_bom_and_converts_to_lf(tmp_path: Path) -> None:
    script = tmp_path / "run.sh"
    script.write_bytes(b"\xef\xbb\xbf#!/usr/bin/env bash\r\necho ok\r\n")

    result = normalize_sh_file(script)

    assert result.ok
    assert result.has_bom is False
    assert result.crlf == 0
    assert result.lf == 2
    assert script.read_bytes() == b"#!/usr/bin/env bash\necho ok\n"


def test_check_sh_files_reports_nested_scripts(tmp_path: Path) -> None:
    nested = tmp_path / "tools" / "linux"
    nested.mkdir(parents=True)
    script = nested / "setup.sh"
    script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8", newline="\n")

    results = check_sh_files(tmp_path)

    assert [result.path for result in results] == [script]
    assert results[0].ok
