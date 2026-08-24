"""Tests for system_core.core.manifest."""
from __future__ import annotations

from pathlib import Path

import pytest

from system_core.core.manifest import load_manifest


def _write_manifest(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_load_manifest_minimal(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
tool:
  id: test
  name: Test
operations:
  - id: validate
    title: Validate
    description: ''
    service: pkg.module:func
    kind: safe
""".strip(),
    )

    manifest = load_manifest(manifest_path)
    assert len(manifest.operations) == 1
    op = manifest.operations[0]
    assert op.id == "validate"
    assert op.service == "pkg.module:func"
    assert op.kind == "safe"


def test_load_manifest_rejects_missing_id(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operations:
  - id: ''
    title: ''
    description: ''
    service: pkg.module:func
""".strip(),
    )
    with pytest.raises(ValueError, match="id is empty"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_bad_service_syntax(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operations:
  - id: bad
    title: bad
    description: ''
    service: pkg.module.func
""".strip(),
    )
    with pytest.raises(ValueError, match="module:function"):
        load_manifest(manifest_path)


def test_load_manifest_i18n_fields(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operations:
  - id: validate
    title: Validate input
    title_ru: Проверить input
    description: Check the input.
    description_ru: Проверить вход.
    service: pkg.module:func
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    op = manifest.operations[0]
    assert op.display_title("en") == "Validate input"
    assert op.display_title("ru") == "Проверить input"
    assert op.display_title("xx") == "Validate input"  # fallback to EN


def test_load_manifest_tooltips(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operations:
  - id: validate
    title: Validate input
    description: Check the input.
    tooltip: Runs local validation only.
    tooltip_ru: Запускает только локальную проверку.
    service: pkg.module:func
operation_groups:
  - id: group
    title: Group
    description: Group description.
    tooltip_i18n:
      en: Group tooltip.
      ru: Подсказка раздела.
    children:
      - id: run
        title: Run
        service: pkg.module:run
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    op = manifest.operations[0]
    group = manifest.operation_groups[0]
    assert op.display_tooltip("en") == "Runs local validation only."
    assert op.display_tooltip("ru") == "Запускает только локальную проверку."
    assert group.display_tooltip("en") == "Group tooltip."
    assert group.display_tooltip("ru") == "Подсказка раздела."


def test_load_manifest_separates_maintenance(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operations:
  - id: a
    title: A
    description: ''
    service: pkg.module:a
maintenance_operations:
  - id: cleanup
    title: Cleanup
    description: ''
    service: pkg.module:cleanup
    kind: dangerous
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    assert [op.id for op in manifest.operations] == ["a"]
    assert [op.id for op in manifest.maintenance_operations] == ["cleanup"]
    assert manifest.maintenance_operations[0].kind == "dangerous"


def test_load_manifest_operation_groups_inherit_parameters_and_fields(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operation_groups:
  - id: convert
    title: Convert
    parameters:
      family: document
    children:
      - id: pdf
        title: PDF
        parameters:
          format: pdf
        fields:
          - id: dpi
            type: number
            default: 300
        children:
          - id: run_pdf
            title: Run PDF
            service: pkg.module:run_pdf
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    leaf = manifest.operation_groups[0].children[0].children[0]
    assert leaf.id == "run_pdf"
    assert leaf.parameters == {"family": "document", "format": "pdf"}
    assert [field["id"] for field in leaf.fields] == ["dpi"]
    assert leaf.to_operation().parameters == {"family": "document", "format": "pdf"}


def test_load_manifest_keeps_checkbox_group_field(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operation_groups:
  - id: convert
    title: Convert
    fields:
      - id: input_formats
        type: checkboxes
        default: [docx, xlsx]
        min_selected: 1
        options:
          - value: docx
            label: DOCX
          - value: xlsx
            label: XLSX
          - value: pptx
            label: PPTX
    children:
      - id: run_convert
        title: Run convert
        service: pkg.module:run_convert
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    leaf = manifest.operation_groups[0].children[0]
    field = leaf.fields[0]
    assert field["id"] == "input_formats"
    assert field["type"] == "checkboxes"
    assert field["default"] == ["docx", "xlsx"]
    assert field["min_selected"] == 1
    assert [option["value"] for option in field["options"]] == ["docx", "xlsx", "pptx"]


def test_load_manifest_keeps_dynamic_options_and_presets(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operation_groups:
  - id: convert
    title: Convert
    fields:
      - id: sample_profiles
        type: profile_buttons
        presets:
          - id: office
            label: Office
            values:
              input_formats: [docx, xlsx]
      - id: selected_files
        type: checkboxes
        default: []
        options_source: pkg.module:file_options
        cache_seconds: 20
    children:
      - id: run_convert
        title: Run convert
        service: pkg.module:run_convert
""".strip(),
    )
    manifest = load_manifest(manifest_path)
    leaf = manifest.operation_groups[0].children[0]
    profile_field = leaf.fields[0]
    dynamic_field = leaf.fields[1]
    assert profile_field["type"] == "profile_buttons"
    assert profile_field["presets"][0]["values"]["input_formats"] == ["docx", "xlsx"]
    assert dynamic_field["options_source"] == "pkg.module:file_options"
    assert dynamic_field["cache_seconds"] == 20


def test_load_manifest_rejects_group_leaf_without_service(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path / "config" / "tool_manifest.yaml",
        """
operation_groups:
  - id: broken
    title: Broken
""".strip(),
    )
    with pytest.raises(ValueError, match="Leaf command service"):
        load_manifest(manifest_path)
