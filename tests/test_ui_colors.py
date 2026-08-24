"""Tests for the GUI color theme contract."""
from __future__ import annotations

from pathlib import Path

from system_core.core.config import load_yaml_or_json
from system_core.core.ui_theme_catalog import (
    CORE_THEME_LABELS_RU,
    CORE_THEME_ORDER,
    validate_theme_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


def _data() -> dict[str, object]:
    return load_yaml_or_json(ROOT / "config" / "ui_colors.yaml")


def _themes() -> dict[str, object]:
    data = _data()
    themes = data.get("themes")
    assert isinstance(themes, dict)
    return themes


def test_template_theme_catalog_contract() -> None:
    result = validate_theme_catalog(_data())
    assert result.ok, "\n".join(result.errors)


def test_template_theme_core_order_and_ru_labels() -> None:
    themes = _themes()
    assert tuple(themes)[: len(CORE_THEME_ORDER)] == CORE_THEME_ORDER
    assert [themes[theme_id]["label_ru"] for theme_id in CORE_THEME_ORDER] == [
        CORE_THEME_LABELS_RU[theme_id] for theme_id in CORE_THEME_ORDER
    ]


def test_template_theme_contract_allows_project_extensions_after_core() -> None:
    data = _data()
    themes = dict(_themes())
    project_theme = dict(themes["code_dark"])
    project_theme["label"] = "Project Dark"
    project_theme["label_ru"] = "Project Темная"
    themes["project_dark"] = project_theme

    result = validate_theme_catalog({**data, "themes": themes})

    assert result.ok, "\n".join(result.errors)
    assert result.extra_theme_ids == ("project_dark",)
