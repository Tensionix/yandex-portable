from __future__ import annotations

from pathlib import Path

from system_core.core.jobs import JobContext
from system_core.core.manifest import Operation
from system_core.core.paths import get_project_paths
from system_core.services.sample_service import input_file_options, validate_input


def _context(root: Path, source: Path) -> JobContext:
    paths = get_project_paths(root)
    paths.logs.mkdir(parents=True, exist_ok=True)
    paths.report.mkdir(parents=True, exist_ok=True)
    operation = Operation(
        id="validate_source",
        title="Validate source",
        description="",
        service="system_core.services.sample_service:validate_input",
        parameters={"gui_input_dir": str(source)},
    )
    return JobContext(
        paths=paths,
        operation=operation,
        log_file=paths.logs / "validate.log",
        report_dir=paths.report,
    )


def test_dynamic_options_accept_single_source_file(tmp_path: Path) -> None:
    source = tmp_path / "one document.txt"
    source.write_text("payload", encoding="utf-8")

    assert input_file_options(tmp_path, {"gui_input_dir": str(source)}) == [
        {"value": source.name, "label": source.name, "label_ru": source.name}
    ]


def test_validate_input_accepts_single_source_file(tmp_path: Path) -> None:
    source = tmp_path / "one document.txt"
    source.write_text("payload", encoding="utf-8")

    result = validate_input(_context(tmp_path, source))

    assert result["input"] == str(source.resolve())
    assert result["inventory"] == {"files": 1, "dirs": 0}
