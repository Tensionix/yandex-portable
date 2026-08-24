from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import load_yaml_or_json


@dataclass(frozen=True)
class Operation:
    id: str
    title: str
    description: str
    service: str
    kind: str = "safe"
    title_ru: str = ""
    description_ru: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    fields: tuple[dict[str, Any], ...] = ()
    tooltip: str = ""
    tooltip_ru: str = ""

    def display_title(self, language: str) -> str:
        if language == "ru" and self.title_ru:
            return self.title_ru
        return self.title

    def display_description(self, language: str) -> str:
        if language == "ru" and self.description_ru:
            return self.description_ru
        return self.description

    def display_tooltip(self, language: str) -> str:
        if language == "ru" and self.tooltip_ru:
            return self.tooltip_ru
        return self.tooltip


@dataclass(frozen=True)
class CommandNode:
    id: str
    title: str
    description: str = ""
    service: str = ""
    kind: str = "safe"
    title_ru: str = ""
    description_ru: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    fields: tuple[dict[str, Any], ...] = ()
    children: tuple["CommandNode", ...] = ()
    tooltip: str = ""
    tooltip_ru: str = ""

    def display_title(self, language: str) -> str:
        if language == "ru" and self.title_ru:
            return self.title_ru
        return self.title

    def display_description(self, language: str) -> str:
        if language == "ru" and self.description_ru:
            return self.description_ru
        return self.description

    def display_tooltip(self, language: str) -> str:
        if language == "ru" and self.tooltip_ru:
            return self.tooltip_ru
        return self.tooltip

    def to_operation(self, parameters: dict[str, Any] | None = None) -> Operation:
        return Operation(
            id=self.id,
            title=self.title,
            description=self.description,
            service=self.service,
            kind=self.kind,
            title_ru=self.title_ru,
            description_ru=self.description_ru,
            tooltip=self.tooltip,
            tooltip_ru=self.tooltip_ru,
            parameters=dict(parameters if parameters is not None else self.parameters),
            fields=self.fields,
        )


@dataclass(frozen=True)
class ToolManifest:
    raw: dict[str, Any]
    operations: list[Operation]
    maintenance_operations: list[Operation]
    operation_groups: list[CommandNode]


def _extract_i18n(item: dict[str, Any], key: str) -> dict[str, Any]:
    value = item.get(f"{key}_i18n", {})
    return value if isinstance(value, dict) else {}


def _extract_parameters(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("parameters", item.get("params", {}))
    return dict(value) if isinstance(value, dict) else {}


def _extract_fields(item: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    value = item.get("fields", [])
    if not isinstance(value, list):
        return ()
    return tuple(dict(field) for field in value if isinstance(field, dict))


def _parse_operation(item: dict[str, Any]) -> Operation:
    title_i18n = _extract_i18n(item, "title")
    description_i18n = _extract_i18n(item, "description")
    tooltip_i18n = _extract_i18n(item, "tooltip")
    return Operation(
        id=str(item.get("id", "")).strip(),
        title=str(item.get("title", title_i18n.get("en", ""))).strip(),
        description=str(item.get("description", description_i18n.get("en", ""))).strip(),
        service=str(item.get("service", "")).strip(),
        kind=str(item.get("kind", "safe")).strip() or "safe",
        title_ru=str(item.get("title_ru", title_i18n.get("ru", ""))).strip(),
        description_ru=str(item.get("description_ru", description_i18n.get("ru", ""))).strip(),
        tooltip=str(item.get("tooltip", tooltip_i18n.get("en", ""))).strip(),
        tooltip_ru=str(item.get("tooltip_ru", tooltip_i18n.get("ru", ""))).strip(),
        parameters=_extract_parameters(item),
        fields=_extract_fields(item),
    )


def _parse_command_node(
    item: dict[str, Any],
    inherited_parameters: dict[str, Any] | None = None,
    inherited_fields: tuple[dict[str, Any], ...] = (),
) -> CommandNode:
    title_i18n = _extract_i18n(item, "title")
    description_i18n = _extract_i18n(item, "description")
    tooltip_i18n = _extract_i18n(item, "tooltip")
    parameters = dict(inherited_parameters or {})
    parameters.update(_extract_parameters(item))
    fields = (*inherited_fields, *_extract_fields(item))
    children_raw = item.get("children", [])
    children = tuple(
        _parse_command_node(child, parameters, fields)
        for child in children_raw
        if isinstance(child, dict)
    )
    return CommandNode(
        id=str(item.get("id", "")).strip(),
        title=str(item.get("title", title_i18n.get("en", ""))).strip(),
        description=str(item.get("description", description_i18n.get("en", ""))).strip(),
        tooltip=str(item.get("tooltip", tooltip_i18n.get("en", ""))).strip(),
        service=str(item.get("service", "")).strip(),
        kind=str(item.get("kind", "safe")).strip() or "safe",
        title_ru=str(item.get("title_ru", title_i18n.get("ru", ""))).strip(),
        description_ru=str(item.get("description_ru", description_i18n.get("ru", ""))).strip(),
        tooltip_ru=str(item.get("tooltip_ru", tooltip_i18n.get("ru", ""))).strip(),
        parameters=parameters,
        fields=fields,
        children=children,
    )


def load_manifest(path: Path) -> ToolManifest:
    raw = load_yaml_or_json(path)
    operations = [_parse_operation(item) for item in raw.get("operations", [])]
    maintenance = [_parse_operation(item) for item in raw.get("maintenance_operations", [])]
    operation_groups = [
        _parse_command_node(item)
        for item in raw.get("operation_groups", [])
        if isinstance(item, dict)
    ]

    for operation in [*operations, *maintenance]:
        if not operation.id:
            raise ValueError("Operation id is empty.")
        if ":" not in operation.service:
            raise ValueError(f"Operation service must use module:function syntax: {operation.id}")

    def validate_node(node: CommandNode) -> None:
        if not node.id:
            raise ValueError("Command node id is empty.")
        if node.children:
            for child in node.children:
                validate_node(child)
            return
        if ":" not in node.service:
            raise ValueError(f"Leaf command service must use module:function syntax: {node.id}")

    for group in operation_groups:
        validate_node(group)

    return ToolManifest(
        raw=raw,
        operations=operations,
        maintenance_operations=maintenance,
        operation_groups=operation_groups,
    )
