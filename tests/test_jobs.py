from __future__ import annotations

from pathlib import Path
import sys

import pytest

from system_core.core.jobs import JobContext, decoded_process_lines, decode_process_line, redact_parameters, run_process
from system_core.core.ansi import ansi_to_html
from system_core.core.manifest import Operation
from system_core.core.paths import ensure_project_dirs, get_project_paths


def _context(tmp_path: Path) -> JobContext:
    paths = get_project_paths(tmp_path)
    ensure_project_dirs(paths)
    return JobContext(
        paths=paths,
        operation=Operation(
            id="test",
            title="Test",
            description="",
            service="pkg.module:test",
        ),
        log_file=paths.logs / "test.log",
        report_dir=paths.report,
    )


def test_run_process_streams_output(tmp_path: Path) -> None:
    context = _context(tmp_path)

    result = run_process(
        context,
        [sys.executable, "-c", "print('hello from child')"],
    )

    assert result.exit_code == 0
    assert result.lines == ("hello from child",)
    assert "hello from child" in context.log_file.read_text(encoding="utf-8")


def test_run_process_raises_on_nonzero_exit(tmp_path: Path) -> None:
    context = _context(tmp_path)

    with pytest.raises(RuntimeError, match="exit code 7"):
        run_process(context, [sys.executable, "-c", "raise SystemExit(7)"])


def test_decode_process_line_handles_utf16le_without_bom() -> None:
    raw = "Этот подсистема Windows для Linux не установлен.\n".encode("utf-16-le")

    assert decode_process_line(raw).startswith("Этот подсистема")


def test_decode_process_line_preserves_utf8_terminal_graphics() -> None:
    raw = "████████ 1.90 MB / 1.90 MB\n".encode("utf-8")

    assert decode_process_line(raw).startswith("████████")


def test_decode_process_line_preserves_ansi_color_sequences() -> None:
    raw = b"\x1b[31mred\x1b[0m\n"

    decoded = decode_process_line(raw)

    assert "\x1b[31m" in decoded
    assert "red" in decoded
    assert "color:" in ansi_to_html(decoded)


def test_decode_process_line_preserves_utf8_cyrillic_with_progress_graphics() -> None:
    raw = "Найден Deno [DenoLand.Deno] Version 2.3\n████ 12.0 MB / 40.0 MB\n".encode("utf-8")

    decoded = decode_process_line(raw)

    assert "Найден Deno" in decoded
    assert "████" in decoded
    assert "╨" not in decoded


def test_decode_process_line_still_handles_oem_cyrillic() -> None:
    raw = "Проверка завершена\n".encode("cp866")

    assert decode_process_line(raw).startswith("Проверка")


def test_decoded_process_lines_drops_spinner_only_carriage_return_frames() -> None:
    raw = b"   -\r   \\\r   |\rDownloading file\r"

    assert decoded_process_lines(raw) == ["Downloading file"]


def test_decoded_process_lines_keeps_carriage_return_progress_frames() -> None:
    raw = "████▒▒ 12.0 MB / 40.0 MB\r██████ 40.0 MB / 40.0 MB\r".encode("utf-8")

    assert decoded_process_lines(raw) == [
        "████▒▒ 12.0 MB / 40.0 MB",
        "██████ 40.0 MB / 40.0 MB",
    ]


def test_run_process_accepts_stdin_text(tmp_path: Path) -> None:
    context = _context(tmp_path)

    result = run_process(
        context,
        [
            sys.executable,
            "-c",
            "import sys; print(sys.stdin.read().strip().upper())",
        ],
        input_text="hello\n",
    )

    assert result.lines == ("HELLO",)


def test_redact_parameters_masks_sensitive_values() -> None:
    safe = redact_parameters(
        {
            "linux_username": "audion",
            "linux_password": "secret-pass",
            "nested": {"api_key": "abc123", "plain": "visible"},
        }
    )

    assert safe["linux_username"] == "audion"
    assert safe["linux_password"] == "***REDACTED***"
    assert safe["nested"]["api_key"] == "***REDACTED***"
    assert safe["nested"]["plain"] == "visible"
