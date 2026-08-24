"""Tests for system_core.core.ui_settings."""
from __future__ import annotations

from pathlib import Path

from system_core.core.ui_settings import (
    UiSettings,
    load_ui_settings,
    save_ui_settings,
)


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    settings = load_ui_settings(tmp_path / "does_not_exist.yaml")
    assert settings.language == "ru"
    assert settings.theme == "code_dark"
    assert settings.allow_runtime_switching is True


def test_load_normalizes_invalid_language(tmp_path: Path) -> None:
    path = tmp_path / "ui.yaml"
    path.write_text(
        'ui:\n  language: "klingon"\n  theme: "dark"\n  allow_runtime_switching: true\n',
        encoding="utf-8",
    )
    settings = load_ui_settings(path)
    assert settings.language == "ru"  # falls back to default
    assert settings.theme == "code_dark"  # legacy ui:/dark alias


def test_load_normalizes_invalid_theme(tmp_path: Path) -> None:
    path = tmp_path / "ui.yaml"
    path.write_text(
        'ui:\n  language: "en"\n  theme: "neon theme!"\n  allow_runtime_switching: false\n',
        encoding="utf-8",
    )
    settings = load_ui_settings(path)
    assert settings.theme == "neontheme"


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "ui.yaml"
    save_ui_settings(path, UiSettings(language="en", theme="code_light", allow_runtime_switching=False))
    loaded = load_ui_settings(path)
    assert loaded.language == "en"
    assert loaded.theme == "code_light"
    assert loaded.allow_runtime_switching is False


def test_save_writes_lf_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "ui.yaml"
    save_ui_settings(path, UiSettings())
    raw = path.read_bytes()
    # The template writes LF for YAML config; CRLF would indicate a regression.
    assert b"\r\n" not in raw
