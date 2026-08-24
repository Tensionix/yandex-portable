from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_yaml_or_json
from .ui_theme_catalog import DEFAULT_THEME_ID, normalize_theme_id


SUPPORTED_LANGUAGES = {"en", "ru"}


@dataclass
class UiSettings:
    language: str = "ru"
    theme: str = DEFAULT_THEME_ID
    emoji: bool = False
    allow_runtime_switching: bool = True
    advanced_open: bool = False
    source_path: str = ""
    destination_path: str = ""


def _safe_language(value: Any) -> str:
    text = str(value or "ru").strip().lower()
    return text if text in SUPPORTED_LANGUAGES else "ru"


def _safe_theme(value: Any) -> str:
    return normalize_theme_id(value)


def load_ui_settings(path: Path) -> UiSettings:
    data = load_yaml_or_json(path) if path.exists() else {}
    ui_data: Any = {}
    if isinstance(data, dict):
        gui_data = data.get("gui")
        legacy_ui_data = data.get("ui")
        if isinstance(gui_data, dict):
            ui_data = gui_data
        elif isinstance(legacy_ui_data, dict):
            ui_data = legacy_ui_data
        else:
            ui_data = data
    if not isinstance(ui_data, dict):
        ui_data = {}
    return UiSettings(
        language=_safe_language(ui_data.get("language", "ru")),
        theme=_safe_theme(ui_data.get("theme", DEFAULT_THEME_ID)),
        emoji=bool(ui_data.get("emoji", False)),
        allow_runtime_switching=bool(ui_data.get("allow_runtime_switching", True)),
        advanced_open=bool(ui_data.get("advanced_open", False)),
        source_path=str(ui_data.get("source_path") or "").strip(),
        destination_path=str(ui_data.get("destination_path") or "").strip(),
    )


def save_ui_settings(path: Path, settings: UiSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "gui:\n"
        "  # Change to \"en\" for public GitHub builds.\n"
        f"  language: \"{_safe_language(settings.language)}\"\n"
        f"  theme: \"{_safe_theme(settings.theme)}\"\n"
        f"  emoji: {str(bool(settings.emoji)).lower()}\n"
        f"  allow_runtime_switching: {str(bool(settings.allow_runtime_switching)).lower()}\n"
        f"  advanced_open: {str(bool(settings.advanced_open)).lower()}\n"
        f"  source_path: \"{str(settings.source_path).replace(chr(92), chr(92) + chr(92)).replace(chr(34), chr(92) + chr(34))}\"\n"
        f"  destination_path: \"{str(settings.destination_path).replace(chr(92), chr(92) + chr(92)).replace(chr(34), chr(92) + chr(34))}\"\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")
