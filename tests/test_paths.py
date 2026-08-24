"""Tests for system_core.core.paths."""
from __future__ import annotations

from pathlib import Path

import pytest

from system_core.core.paths import (
    ensure_project_dirs,
    find_project_root,
    get_project_paths,
)


def _make_fake_project(root: Path) -> None:
    (root / "system_core").mkdir(parents=True)
    (root / "config").mkdir(parents=True)


def test_find_project_root_from_nested_file(tmp_path: Path) -> None:
    _make_fake_project(tmp_path)
    deep = tmp_path / "system_core" / "services" / "subpkg"
    deep.mkdir(parents=True)
    deep_file = deep / "module.py"
    deep_file.write_text("# noop", encoding="utf-8")

    found = find_project_root(deep_file)
    assert found == tmp_path.resolve()


def test_find_project_root_from_directory(tmp_path: Path) -> None:
    _make_fake_project(tmp_path)
    found = find_project_root(tmp_path / "system_core")
    assert found == tmp_path.resolve()


def test_get_project_paths_layout(tmp_path: Path) -> None:
    _make_fake_project(tmp_path)
    paths = get_project_paths(tmp_path)
    assert paths.root == tmp_path.resolve()
    assert paths.input == tmp_path.resolve() / "input"
    assert paths.output == tmp_path.resolve() / "output"
    assert paths.logs == tmp_path.resolve() / "logs"
    assert paths.report == tmp_path.resolve() / "report"
    assert paths.workspace == tmp_path.resolve() / "workspace"
    assert paths.config == tmp_path.resolve() / "config"
    assert paths.release == tmp_path.resolve() / "release"


def test_ensure_project_dirs_is_idempotent(tmp_path: Path) -> None:
    _make_fake_project(tmp_path)
    paths = get_project_paths(tmp_path)
    ensure_project_dirs(paths)
    # Second call must not raise.
    ensure_project_dirs(paths)
    for sub in (paths.input, paths.output, paths.logs, paths.report, paths.workspace, paths.release):
        assert sub.exists()
        assert sub.is_dir()
    # .gitkeep is banned here: ensure_project_dirs only creates the directories,
    # it never seeds a .gitkeep marker in any of them.
    for sub in (paths.input, paths.output, paths.logs, paths.report, paths.workspace, paths.release):
        assert not (sub / ".gitkeep").exists()
