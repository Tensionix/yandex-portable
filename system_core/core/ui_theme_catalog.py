from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re


DEFAULT_THEME_ID = "code_dark"
THEME_ALIASES = {"dark": "code_dark", "light": "code_light"}

CORE_THEME_ORDER = (
    "code_dark",
    "code_graphite",
    "code_light",
    "code_warm",
    "audion_light",
    "audion_dark",
    "asar_dark",
)

CORE_THEME_LABELS_RU = {
    "code_dark": "Code Темная",
    "code_graphite": "Code графит",
    "code_light": "Code светлая",
    "code_warm": "Code теплая",
    "audion_light": "Audion светлая",
    "audion_dark": "Audion Темная",
    "asar_dark": "Asar Темная",
}

REQUIRED_THEME_TOKENS = frozenset(
    {
        "color-background-primary",
        "color-background-secondary",
        "color-background-tertiary",
        "color-text-primary",
        "color-text-secondary",
        "color-text-tertiary",
        "color-border-tertiary",
        "color-border-secondary",
        "color-border-primary",
        "color-accent-primary",
        "color-accent-secondary",
        "color-accent-tertiary",
    }
)

THEME_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class ThemeCatalogCheck:
    ok: bool
    errors: tuple[str, ...]
    theme_ids: tuple[str, ...]
    extra_theme_ids: tuple[str, ...]


def normalize_theme_id(value: Any, default: str = DEFAULT_THEME_ID) -> str:
    text = str(value or default).strip().lower()
    text = THEME_ALIASES.get(text, text)
    cleaned = "".join(char for char in text if char.isascii() and (char.isalnum() or char == "_"))
    return cleaned or default


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}


def validate_theme_catalog(data: Mapping[str, Any]) -> ThemeCatalogCheck:
    errors: list[str] = []

    base_tokens_raw = data.get("tokens", {})
    if not isinstance(base_tokens_raw, Mapping):
        errors.append("top-level tokens must be a mapping")
    base_tokens = _string_map(base_tokens_raw)

    themes_raw = data.get("themes")
    if not isinstance(themes_raw, Mapping):
        return ThemeCatalogCheck(
            ok=False,
            errors=tuple([*errors, "themes must be a mapping"]),
            theme_ids=(),
            extra_theme_ids=(),
        )

    theme_ids = tuple(str(theme_id).strip() for theme_id in themes_raw)
    expected_prefix = tuple(CORE_THEME_ORDER)
    actual_prefix = theme_ids[: len(expected_prefix)]
    if actual_prefix != expected_prefix:
        errors.append(
            "core theme order must start with "
            f"{', '.join(expected_prefix)}; got {', '.join(actual_prefix) or '(none)'}"
        )

    for theme_id, expected_label_ru in CORE_THEME_LABELS_RU.items():
        theme_data = themes_raw.get(theme_id)
        if not isinstance(theme_data, Mapping):
            errors.append(f"{theme_id}: core theme is missing or is not a mapping")
            continue
        label_ru = str(theme_data.get("label_ru", "")).strip()
        if label_ru != expected_label_ru:
            errors.append(f"{theme_id}: label_ru must be {expected_label_ru!r}, got {label_ru!r}")

    for raw_theme_id, theme_data in themes_raw.items():
        theme_id = str(raw_theme_id).strip()
        if not THEME_ID_PATTERN.fullmatch(theme_id):
            errors.append(f"{theme_id or '(empty)'}: theme id must match {THEME_ID_PATTERN.pattern}")

        if not isinstance(theme_data, Mapping):
            errors.append(f"{theme_id}: theme must be a mapping")
            continue

        label = str(theme_data.get("label", "")).strip()
        label_ru = str(theme_data.get("label_ru", "")).strip()
        mode = str(theme_data.get("mode", "")).strip().lower()
        tokens_raw = theme_data.get("tokens", {})

        if not label:
            errors.append(f"{theme_id}: label is required")
        if not label_ru:
            errors.append(f"{theme_id}: label_ru is required")
        if "ё" in label_ru or "Ё" in label_ru:
            errors.append(f"{theme_id}: label_ru must not use ё/Ё in theme names")
        if mode not in {"dark", "light"}:
            errors.append(f"{theme_id}: mode must be dark or light")
        if not isinstance(tokens_raw, Mapping):
            errors.append(f"{theme_id}: tokens must be a mapping")
            tokens_raw = {}

        effective_tokens = {**base_tokens, **_string_map(tokens_raw)}
        missing_tokens = sorted(REQUIRED_THEME_TOKENS - set(effective_tokens))
        if missing_tokens:
            errors.append(f"{theme_id}: missing tokens: {', '.join(missing_tokens)}")

    extra_theme_ids = theme_ids[len(CORE_THEME_ORDER) :]
    return ThemeCatalogCheck(
        ok=not errors,
        errors=tuple(errors),
        theme_ids=theme_ids,
        extra_theme_ids=extra_theme_ids,
    )
