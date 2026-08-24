"""Tests for cleanup_workspace safety guarantees.

Symlink tests are skipped on Windows because creating symlinks there
requires Developer Mode or admin rights. The intent is verified on
Linux/macOS, which is enough — the safety logic is platform-agnostic.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from system_core.core.jobs import JobContext
from system_core.core.manifest import Operation
from system_core.core.paths import ProjectPaths
from system_core.services.sample_service import _inventory, cleanup_input_output, cleanup_workspace


def _make_paths(root: Path) -> ProjectPaths:
    paths = ProjectPaths(
        root=root,
        input=root / "input",
        output=root / "output",
        logs=root / "logs",
        report=root / "report",
        workspace=root / "workspace",
        config=root / "config",
        release=root / "release",
        system_core=root / "system_core",
    )
    for directory in (paths.input, paths.output, paths.logs, paths.report, paths.workspace, paths.config, paths.release, paths.system_core):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def _make_context(paths: ProjectPaths) -> JobContext:
    operation = Operation(
        id="test_cleanup",
        title="Test cleanup",
        description="Test cleanup operation",
        service="system_core.services.sample_service:cleanup_workspace",
        kind="dangerous",
    )
    return JobContext(
        paths=paths,
        operation=operation,
        log_file=paths.logs / "test.log",
        report_dir=paths.report,
        log_callback=lambda _msg: None,
        progress_callback=lambda _v: None,
        cancel_callback=lambda: False,
    )


def test_inventory_handles_missing_folder(tmp_path: Path) -> None:
    assert _inventory(tmp_path / "nope") == {"files": 0, "dirs": 0}


def test_inventory_counts_correctly(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f1.txt").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "f2.txt").write_text("y", encoding="utf-8")
    (tmp_path / "b").mkdir()
    inv = _inventory(tmp_path)
    assert inv["files"] == 2
    assert inv["dirs"] == 2


def test_inventory_accepts_single_source_file(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")

    assert _inventory(source) == {"files": 1, "dirs": 0}


def test_lean_cleanup_preserves_git_history() -> None:
    script = (Path(__file__).resolve().parents[1] / "cleanup_project.cmd").read_text(encoding="utf-8")

    assert 'call :RemoveDir "%BASE_DIR%\\.git"' not in script
    assert "Git history is preserved" in script


def test_cleanup_removes_files_inside_workspace(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    (paths.workspace / "junk.txt").write_text("garbage", encoding="utf-8")
    (paths.workspace / "subdir").mkdir()
    (paths.workspace / "subdir" / "nested.txt").write_text("more", encoding="utf-8")

    result = cleanup_workspace(_make_context(paths))
    assert result["removed_items"] == 2
    assert result["skipped_items"] == []
    assert not (paths.workspace / "junk.txt").exists()
    assert not (paths.workspace / "subdir").exists()


def test_cleanup_input_output_empties_both_folders(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    # Dotfiles are not spared either: input and output must end up genuinely empty.
    (paths.input / ".leftover").write_text("", encoding="utf-8")
    (paths.output / ".leftover").write_text("", encoding="utf-8")
    (paths.input / "source.txt").write_text("in", encoding="utf-8")
    (paths.output / "result.txt").write_text("out", encoding="utf-8")

    result = cleanup_input_output(_make_context(paths))

    assert result["removed_items"] == 4
    assert not any(paths.input.iterdir())
    assert not any(paths.output.iterdir())


@pytest.mark.skipif(sys.platform.startswith("win"), reason="symlink creation requires admin on Windows")
def test_cleanup_does_not_follow_symlinks_to_outside(tmp_path: Path) -> None:
    """Symlink inside workspace pointing outside the project must be unlinked,
    NOT followed; the target's contents must remain untouched."""
    paths = _make_paths(tmp_path)

    # External directory we want to protect.
    external = tmp_path.parent / "external_data_test"
    external.mkdir(exist_ok=True)
    protected = external / "protected.txt"
    protected.write_text("DO NOT DELETE", encoding="utf-8")

    # Symlink inside workspace pointing to it.
    link = paths.workspace / "evil_link"
    os.symlink(external, link, target_is_directory=True)

    try:
        result = cleanup_workspace(_make_context(paths))
        # The link should be removed from workspace.
        assert not link.exists() and not link.is_symlink()
        # The target directory and its contents must survive.
        assert external.exists()
        assert protected.exists()
        assert protected.read_text(encoding="utf-8") == "DO NOT DELETE"
        assert result["removed_items"] >= 1
    finally:
        if protected.exists():
            protected.unlink()
        if external.exists():
            external.rmdir()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="symlink creation requires admin on Windows")
def test_cleanup_blocks_when_workspace_itself_is_symlink(tmp_path: Path) -> None:
    """If workspace is itself a symlink, cleanup must refuse outright."""
    real_root = tmp_path / "project"
    real_root.mkdir()
    (real_root / "system_core").mkdir()
    (real_root / "config").mkdir()

    real_workspace_target = tmp_path / "elsewhere"
    real_workspace_target.mkdir()
    (real_workspace_target / "important.txt").write_text("KEEP", encoding="utf-8")

    workspace_link = real_root / "workspace"
    os.symlink(real_workspace_target, workspace_link, target_is_directory=True)

    paths = ProjectPaths(
        root=real_root,
        input=real_root / "input",
        output=real_root / "output",
        logs=real_root / "logs",
        report=real_root / "report",
        workspace=workspace_link,
        config=real_root / "config",
        release=real_root / "release",
        system_core=real_root / "system_core",
    )
    for directory in (paths.input, paths.output, paths.logs, paths.report, paths.config, paths.release):
        directory.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="symbolic link"):
        cleanup_workspace(_make_context(paths))

    assert (real_workspace_target / "important.txt").exists()
