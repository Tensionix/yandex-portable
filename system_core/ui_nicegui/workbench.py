from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from nicegui import ui  # type: ignore


WorkbenchRole = Literal["source", "target"]


# Public Workbench vocabulary is owned by this reusable module. Projects may
# translate their own UI, but must not rename canonical Workbench controls.
CANONICAL_WORKBENCH_TEXT: dict[str, dict[str, str]] = {
    "ru": {
        "source_folder": "Источник",
        "target_folder": "Назначение",
        "source_selected": "Источник выбран.",
        "target_selected": "Назначение выбрано.",
        "clear_io_short": "Сбросить",
        "delete_io_short": "Удалить",
        "add_file_short": "Добавить файл...",
        "file_list_button": "Список",
        "path_required": "Выберите путь.",
        "path_pinned": "Путь закреплен.",
        "path_unpinned": "Закрепление снято.",
    },
    "en": {
        "source_folder": "Source",
        "target_folder": "Target",
        "source_selected": "Source selected.",
        "target_selected": "Target selected.",
        "clear_io_short": "Reset",
        "delete_io_short": "Delete",
        "add_file_short": "Add file...",
        "file_list_button": "List",
        "path_required": "Choose a path.",
        "path_pinned": "Path pinned.",
        "path_unpinned": "Path unpinned.",
    },
}


def canonical_workbench_text(language: str, key: str, **kwargs: Any) -> str | None:
    language_key = "ru" if str(language or "").strip().casefold().startswith("ru") else "en"
    template = CANONICAL_WORKBENCH_TEXT[language_key].get(str(key))
    if template is None:
        return None
    return template.format(**kwargs) if kwargs else template


WORKBENCH_LAYOUT_CSS = r"""
.audion-workspace-panel {
            gap: 6px !important;
          }
          .audion-workspace-strip {
            box-sizing: border-box;
            display: grid;
            align-items: center;
            gap: 6px;
            width: 100%;
            min-width: 0;
            padding: 5px 7px 5px 12px;
            border: 1px solid var(--audion-divider);
            border-radius: 7px;
            background: var(--audion-block-background);
          }
          .audion-folder-strip {
            grid-template-columns: minmax(230px, 1fr) minmax(230px, 1fr);
          }
          .audion-route-strip {
            display: flex;
            justify-content: center;
          }
          .audion-route-groups {
            display: grid;
            grid-template-columns: 2fr 1fr 2fr 1fr;
            gap: 6px;
            width: min(100%, 1020px);
            min-width: 0;
          }
          .audion-route-group {
            display: grid;
            min-width: 0;
            height: 30px;
            overflow: hidden;
            border: 1px solid color-mix(in srgb, var(--audion-panel-border) 82%, transparent 18%);
            border-radius: 4px;
            background: color-mix(in srgb, var(--audion-terminal-background) 82%, var(--audion-panel-background) 18%);
          }
          .audion-route-group-source {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .audion-route-group-maintenance {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .audion-route-group-single {
            grid-template-columns: minmax(0, 1fr);
          }
          .audion-route-group .audion-route-action {
            height: 28px !important;
            min-height: 28px !important;
            border-radius: 0 !important;
          }
          .audion-route-group .audion-route-action + .audion-route-action {
            border-left: 1px solid var(--audion-panel-border) !important;
          }
          .audion-workspace-action {
            width: 100% !important;
            min-width: 0 !important;
          }
          .audion-route-action .q-btn__content {
            display: flex !important;
            flex-wrap: nowrap !important;
            justify-content: center !important;
            min-width: 0 !important;
            overflow: hidden !important;
            gap: 4px !important;
          }
          .audion-route-action {
            padding-left: 4px !important;
            padding-right: 4px !important;
          }
          .audion-route-action .q-btn__content .block {
            font-size: 10px !important;
          }
          .audion-route-action .q-icon {
            flex: 0 0 auto;
            font-size: 14px !important;
          }
          .audion-route-action .block {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .audion-folder-chip {
            display: grid;
            grid-template-columns: 28px 31px minmax(0, 1fr) 28px;
            align-items: center;
            gap: 3px;
            min-width: 0;
            width: 100%;
            height: 28px;
            border: 1px solid var(--audion-panel-border);
            border-radius: 6px;
            background: var(--audion-terminal-background);
            overflow: hidden;
          }
          .audion-folder-icon-button,
          .audion-folder-pin-button,
          .audion-folder-open-button {
            width: 28px !important;
            min-width: 28px !important;
            height: 26px !important;
            min-height: 26px !important;
            border-radius: 0 !important;
            padding: 0 !important;
          }
          .audion-folder-icon-button .q-icon,
          .audion-folder-pin-button .q-icon,
          .audion-folder-open-button .q-icon {
            font-size: 16px !important;
          }
          .audion-folder-pin-button {
            margin-left: 3px !important;
            border-left: 1px solid rgba(148, 163, 184, 0.18) !important;
          }
          .audion-folder-pin-inactive {
            opacity: 0.38;
          }
          .audion-folder-pin-active {
            opacity: 1;
            color: var(--color-accent-primary) !important;
            background: color-mix(in srgb, var(--color-accent-primary) 13%, transparent 87%) !important;
          }
          .audion-folder-path-select,
          .audion-folder-path-select .q-field__inner,
          .audion-folder-path-select .q-field__control {
            min-width: 0 !important;
            height: 26px !important;
            min-height: 26px !important;
          }
          .audion-folder-path-select .q-field__control {
            background: transparent !important;
            color: var(--audion-text) !important;
            padding: 0 4px 0 2px !important;
          }
          .audion-folder-path-select .q-field__native,
          .audion-folder-path-select .q-field__input,
          .audion-folder-path-select .q-field__append {
            min-height: 26px !important;
            height: 26px !important;
            color: var(--audion-text) !important;
          }
          .audion-folder-path-select .q-field__native > span {
            min-width: 0;
            overflow: hidden;
            text-overflow: clip;
            white-space: nowrap;
            color: var(--audion-text);
            font-family: var(--font-mono);
            font-size: 12px;
            line-height: 1;
            padding-right: 3px;
          }
          .audion-folder-path-select .q-field__native {
            position: relative;
            overflow: hidden;
          }
          .audion-folder-path-select .q-field__native::after {
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            width: 7px;
            height: 100%;
            pointer-events: none;
            background: linear-gradient(90deg, transparent, var(--audion-terminal-background));
          }
          .audion-folder-path-select .q-field__append {
            padding-left: 2px !important;
          }
          .audion-path-cache-popup {
            min-width: min(760px, calc(100vw - 48px)) !important;
            max-width: min(940px, calc(100vw - 48px)) !important;
            max-height: min(420px, calc(100vh - 96px)) !important;
            overflow-y: auto !important;
          }
          .audion-path-cache-popup .q-item {
            min-height: 30px !important;
            font-family: var(--font-mono);
            font-size: 12px;
          }
"""


WORKBENCH_OVERRIDE_CSS = r"""
/* Audion unified Workbench override */
          .audion-workspace-action {
            width: 100% !important;
            min-width: 0 !important;
          }
          .audion-route-action {
            padding-left: 4px !important;
            padding-right: 4px !important;
          }
          .audion-route-action .q-btn__content {
            display: flex !important;
            flex-wrap: nowrap !important;
            justify-content: center !important;
            min-width: 0 !important;
            overflow: hidden !important;
            gap: 4px !important;
          }
          .audion-route-action .q-btn__content .block {
            font-size: 10px !important;
          }
          .audion-route-action .q-icon {
            flex: 0 0 auto;
            font-size: 14px !important;
          }
          .audion-route-action .block {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .audion-folder-chip {
            display: grid;
            grid-template-columns: 28px 31px minmax(0, 1fr) 28px;
            align-items: center;
            gap: 3px;
            min-width: 0;
            width: 100%;
            height: 28px;
            border: 1px solid var(--audion-panel-border);
            border-radius: 6px;
            background: var(--audion-terminal-background);
            overflow: hidden;
          }
          .audion-folder-icon-button,
          .audion-folder-pin-button,
          .audion-folder-open-button {
            width: 28px !important;
            min-width: 28px !important;
            height: 26px !important;
            min-height: 26px !important;
            border-radius: 0 !important;
            padding: 0 !important;
          }
          .audion-folder-icon-button .q-icon,
          .audion-folder-pin-button .q-icon,
          .audion-folder-open-button .q-icon {
            font-size: 16px !important;
          }
          .audion-folder-pin-button {
            margin-left: 3px !important;
            border-left: 1px solid rgba(148, 163, 184, 0.18) !important;
          }
          .audion-folder-pin-inactive {
            opacity: 0.38;
          }
          .audion-folder-pin-active {
            opacity: 1;
            color: var(--color-accent-primary) !important;
            background: color-mix(in srgb, var(--color-accent-primary) 13%, transparent 87%) !important;
          }
          .audion-folder-path-select,
          .audion-folder-path-select .q-field__inner,
          .audion-folder-path-select .q-field__control {
            min-width: 0 !important;
            height: 26px !important;
            min-height: 26px !important;
          }
          .audion-folder-path-select {
            border-left: 1px solid rgba(148, 163, 184, 0.16);
            padding-left: 3px !important;
          }
          .audion-folder-path-select .q-field__control {
            background: transparent !important;
            color: var(--audion-text) !important;
            padding: 0 4px 0 2px !important;
          }
          .audion-folder-path-select .q-field__native,
          .audion-folder-path-select .q-field__input,
          .audion-folder-path-select .q-field__append {
            min-height: 26px !important;
            height: 26px !important;
            color: var(--audion-text) !important;
          }
          .audion-folder-path-select .q-field__native > span {
            min-width: 0;
            overflow: hidden;
            text-overflow: clip;
            white-space: nowrap;
            color: var(--audion-text);
            font-family: var(--font-mono);
            font-size: 12px;
            line-height: 1;
            padding-right: 3px;
          }
          .audion-folder-path-select .q-field__native {
            position: relative;
            overflow: hidden;
          }
          .audion-folder-path-select .q-field__native::after {
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            width: 7px;
            height: 100%;
            pointer-events: none;
            background: linear-gradient(90deg, transparent, var(--audion-terminal-background));
          }
          .audion-folder-path-select .q-field__append {
            margin-left: 3px !important;
            padding-left: 4px !important;
            border-left: 1px solid rgba(148, 163, 184, 0.14);
          }
          .audion-path-cache-popup {
            min-width: min(760px, calc(100vw - 48px)) !important;
            max-width: min(940px, calc(100vw - 48px)) !important;
            max-height: min(420px, calc(100vh - 96px)) !important;
            overflow-y: auto !important;
          }
          .audion-path-cache-popup .q-item {
            min-height: 30px !important;
            font-family: var(--font-mono);
            font-size: 12px;
          }
          .audion-path-option-item {
            min-height: 30px !important;
            padding: 3px 8px 3px 4px !important;
            font-family: var(--font-mono);
            font-size: 12px;
          }
          .audion-path-option-pin-cell {
            min-width: 15px !important;
            width: 15px !important;
            padding-right: 1px !important;
          }
          .audion-path-option-pin {
            color: #58a6ff !important;
            font-size: 12px !important;
            line-height: 1 !important;
          }
          .audion-path-option-pinned {
            border-left: 1px solid rgba(88, 166, 255, 0.72);
            background: rgba(88, 166, 255, 0.08) !important;
          }
          .audion-path-option-pinned .audion-path-option-label {
            color: #dbeafe !important;
            font-weight: 700;
          }
          .audion-path-option-label {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
"""


WORKBENCH_FEEDBACK_CSS = r"""
<style id="audion-workspace-feedback-style">
  html body .audion-workspace-path-flash,
  html body .audion-workspace-pin-flash,
  html body .audion-workspace-delete-flash {
    position: relative !important;
    overflow: hidden !important;
  }
  html body .audion-workspace-path-flash::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: inherit;
    background: linear-gradient(90deg, transparent 0%, rgba(88, 166, 255, 0.08) 28%, rgba(88, 166, 255, 0.28) 50%, rgba(88, 166, 255, 0.08) 72%, transparent 100%);
    box-shadow: inset 0 0 0 1px rgba(88, 166, 255, 0.42);
    animation: audion-workspace-path-sheen 975ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  html body .audion-workspace-pin-flash::after {
    content: "";
    position: absolute;
    inset: 1px;
    pointer-events: none;
    border-radius: inherit;
    background: rgba(88, 166, 255, 0.34);
    animation: audion-workspace-pin-pop 520ms ease-out both;
  }
  html body .audion-workspace-delete-flash::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: inherit;
    background: linear-gradient(90deg, transparent 0%, rgba(239, 68, 68, 0.08) 28%, rgba(239, 68, 68, 0.26) 50%, rgba(239, 68, 68, 0.08) 72%, transparent 100%);
    box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.38);
    animation: audion-workspace-delete-sheen 720ms cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  @keyframes audion-workspace-path-sheen {
    0% { opacity: 0; transform: translateX(-110%); }
    18% { opacity: 1; }
    100% { opacity: 0; transform: translateX(110%); }
  }
  @keyframes audion-workspace-pin-pop {
    0% { opacity: 0; transform: scale(0.72); }
    30% { opacity: 1; transform: scale(1); }
    100% { opacity: 0; transform: scale(1); }
  }
  @keyframes audion-workspace-delete-sheen {
    0% { opacity: 0; transform: translateX(-105%); }
    22% { opacity: 1; }
    100% { opacity: 0; transform: translateX(105%); }
  }
  @media (prefers-reduced-motion: reduce) {
    html body .audion-workspace-path-flash::after,
    html body .audion-workspace-pin-flash::after,
    html body .audion-workspace-delete-flash::after { animation: none !important; display: none !important; }
  }
</style>
"""


def canonical_role(role: str) -> WorkbenchRole:
    normalized = str(role or "").strip().casefold()
    return "target" if normalized in {"target", "targets", "dst", "destination"} else "source"


@dataclass(frozen=True, slots=True)
class WorkbenchConfig:
    root: Path
    input_path: Path
    output_path: Path
    history_path: Path
    history_limit: int = 24

    def default_path(self, role: str) -> Path:
        return self.output_path if canonical_role(role) == "target" else self.input_path


@dataclass(frozen=True, slots=True)
class WorkbenchHistory:
    """Persistent source/target path history without any NiceGUI dependency."""

    config: WorkbenchConfig

    @staticmethod
    def key(role: str) -> str:
        return "targets" if canonical_role(role) == "target" else "sources"

    @staticmethod
    def empty() -> dict[str, list[dict[str, Any]]]:
        return {"sources": [], "targets": []}

    @staticmethod
    def boolish(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "yes", "true", "on", "pinned"}

    @staticmethod
    def normalize_path(path_value: str) -> str:
        return str(Path(str(path_value or "").strip()).expanduser())

    def load(self) -> dict[str, Any]:
        path = self.config.history_path
        if not path.exists():
            return self.empty()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.empty()
        if not isinstance(data, dict):
            return self.empty()
        data.setdefault("sources", [])
        data.setdefault("targets", [])
        return data

    def save(self, data: dict[str, Any]) -> None:
        path = self.config.history_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def coerce_entry(self, item: Any) -> dict[str, Any] | None:
        if isinstance(item, str):
            path_text = item.strip()
            if not path_text:
                return None
            return {"path": path_text, "count": 1, "last_used": "", "pinned": False}
        if not isinstance(item, dict):
            return None
        path_text = str(item.get("path") or "").strip()
        if not path_text:
            return None
        try:
            count = max(1, int(item.get("count", 1) or 1))
        except (TypeError, ValueError):
            count = 1
        return {
            "path": path_text,
            "count": count,
            "last_used": str(item.get("last_used") or "").strip(),
            "pinned": self.boolish(item.get("pinned")),
        }

    def normalize_entries(self, entries: Any) -> list[dict[str, Any]]:
        if not isinstance(entries, list):
            return []

        merged: dict[str, dict[str, Any]] = {}
        for item in entries:
            entry = self.coerce_entry(item)
            if entry is None:
                continue
            key = str(entry["path"]).casefold()
            existing = merged.get(key)
            if existing is None:
                merged[key] = entry
                continue
            existing["count"] = int(existing.get("count", 0) or 0) + int(entry.get("count", 0) or 0)
            existing["pinned"] = bool(existing.get("pinned")) or bool(entry.get("pinned"))
            existing["last_used"] = max(str(existing.get("last_used", "")), str(entry.get("last_used", "")))
            if str(entry.get("last_used", "")) >= str(existing.get("last_used", "")):
                existing["path"] = entry["path"]

        result = list(merged.values())
        result.sort(
            key=lambda item: (
                bool(item.get("pinned")),
                int(item.get("count", 0) or 0),
                str(item.get("last_used", "")),
            ),
            reverse=True,
        )
        return result[: self.config.history_limit]

    def normalize(self, data: Any) -> dict[str, list[dict[str, Any]]]:
        if isinstance(data, list):
            return {"sources": self.normalize_entries(data), "targets": []}
        if not isinstance(data, dict):
            raise ValueError("Path history JSON must be an object.")
        return {
            "sources": self.normalize_entries(data.get("sources", data.get("source", []))),
            "targets": self.normalize_entries(data.get("targets", data.get("target", []))),
        }

    def entries(self, role: str) -> list[dict[str, Any]]:
        data = self.normalize(self.load())
        return list(data.get(self.key(role), []))

    def set_pinned(self, role: str, path_value: str, pinned: bool, *, required_message: str) -> None:
        path_text = str(path_value or "").strip()
        if not path_text:
            raise ValueError(required_message)
        key = self.key(role)
        normalized = self.normalize_path(path_text)
        data = self.normalize(self.load())
        entries = list(data.get(key, []))
        now = datetime.now().isoformat(timespec="seconds")
        found = False
        for item in entries:
            if str(item.get("path", "")).casefold() != normalized.casefold():
                continue
            item["path"] = normalized
            item["pinned"] = bool(pinned)
            item["count"] = max(1, int(item.get("count", 0) or 0))
            item["last_used"] = now
            found = True
            break
        if not found:
            entries.append({"path": normalized, "count": 1, "last_used": now, "pinned": bool(pinned)})
        data[key] = self.normalize_entries(entries)
        self.save(data)

    def delete(self, role: str, path_value: str, *, required_message: str) -> dict[str, Any]:
        path_text = str(path_value or "").strip()
        if not path_text:
            raise ValueError(required_message)
        key = self.key(role)
        normalized = self.normalize_path(path_text)
        data = self.normalize(self.load())
        entries = data.get(key, [])
        kept = [item for item in entries if str(item.get("path", "")).casefold() != normalized.casefold()]
        removed = len(entries) - len(kept)
        data[key] = self.normalize_entries(kept)
        default_path = str(self.config.default_path(role))
        next_path = default_path
        if removed and data[key]:
            next_path = str(data[key][0].get("path") or default_path)
        self.save(data)
        return {"removed": removed, "next_path": next_path}

    def remember(self, role: str, path_value: str) -> None:
        path_text = str(path_value or "").strip()
        if not path_text:
            return
        key = self.key(role)
        normalized = self.normalize_path(path_text)
        data = self.normalize(self.load())
        entries = list(data.get(key, []))
        now = datetime.now().isoformat(timespec="seconds")
        found = False
        for item in entries:
            if str(item.get("path", "")).casefold() != normalized.casefold():
                continue
            item["path"] = normalized
            item["count"] = int(item.get("count", 0) or 0) + 1
            item["last_used"] = now
            item["pinned"] = bool(item.get("pinned"))
            found = True
            break
        if not found:
            entries.append({"path": normalized, "count": 1, "last_used": now, "pinned": False})
        data[key] = self.normalize_entries(entries)
        self.save(data)

    def clear_cache_keep_pins(self) -> dict[str, int]:
        data = self.normalize(self.load())
        removed_sources = 0
        removed_targets = 0
        kept_pins = 0
        for key in ("sources", "targets"):
            entries = data.get(key, [])
            pinned_entries = [item for item in entries if bool(item.get("pinned"))]
            if key == "sources":
                removed_sources = len(entries) - len(pinned_entries)
            else:
                removed_targets = len(entries) - len(pinned_entries)
            kept_pins += len(pinned_entries)
            data[key] = self.normalize_entries(pinned_entries)
        self.save(data)
        return {
            "removed_sources": removed_sources,
            "removed_targets": removed_targets,
            "kept_pins": kept_pins,
        }

    def ensure_initial(self) -> None:
        if self.config.history_path.exists():
            return
        data = self.empty()
        data["sources"] = [{"path": str(self.config.input_path), "count": 1, "last_used": "", "pinned": False}]
        data["targets"] = [{"path": str(self.config.output_path), "count": 1, "last_used": "", "pinned": False}]
        self.save(data)


@dataclass(frozen=True, slots=True)
class WorkbenchAdapter:
    """Project boundary for the reusable Workbench backend and renderer.

    The adapter deliberately contains callbacks instead of importing ``app.py``.
    During the first extraction gate the existing implementation remains in
    ``app.py``; subsequent gates move behavior behind this boundary one piece at
    a time without changing the project's outer layout.
    """

    config: WorkbenchConfig
    current_path_callback: Callable[[WorkbenchRole], Path]
    save_path_callback: Callable[[WorkbenchRole, Any], None]
    language_callback: Callable[[], str]
    translate_callback: Callable[..., str]
    log_callback: Callable[[str], None]
    notify_callback: Callable[[str, str], None]
    reload_callback: Callable[[int], None]
    busy_callback: Callable[[], bool]
    feedback_callback: Callable[[], dict[str, str]]
    set_feedback_callback: Callable[[WorkbenchRole, str], None]
    clear_feedback_callback: Callable[[], None]

    def current_path(self, role: str) -> Path:
        return Path(self.current_path_callback(canonical_role(role)))

    @property
    def history(self) -> WorkbenchHistory:
        return WorkbenchHistory(self.config)

    def save_path(self, role: str, value: Any) -> None:
        self.save_path_callback(canonical_role(role), value)

    def language(self) -> str:
        return str(self.language_callback() or "ru")

    def translate(self, key: str, **kwargs: Any) -> str:
        canonical = canonical_workbench_text(self.language(), key, **kwargs)
        if canonical is not None:
            return canonical
        return str(self.translate_callback(key, **kwargs))

    def log(self, message: str) -> None:
        self.log_callback(str(message))

    def notify(self, message: str, level: str) -> None:
        self.notify_callback(str(message), str(level))

    def reload(self, delay_ms: int = 150) -> None:
        self.reload_callback(max(0, int(delay_ms)))

    def is_busy(self) -> bool:
        return bool(self.busy_callback())

    def feedback(self) -> dict[str, str]:
        value = self.feedback_callback()
        return dict(value) if isinstance(value, dict) else {}

    def set_feedback(self, role: str, action: str) -> None:
        self.set_feedback_callback(canonical_role(role), str(action or "path"))

    def clear_feedback(self) -> None:
        self.clear_feedback_callback()

    def normalize_history_path(self, path_value: str) -> str:
        return self.history.normalize_path(path_value)

    def history_entries(self, role: str) -> list[dict[str, Any]]:
        return self.history.entries(role)

    def set_path_pinned(self, role: str, path_value: str, pinned: bool) -> None:
        self.history.set_pinned(role, path_value, pinned, required_message=self.translate("path_required"))

    def delete_path_history(self, role: str, path_value: str) -> dict[str, Any]:
        return self.history.delete(role, path_value, required_message=self.translate("path_required"))

    def remember_path(self, role: str, path_value: str) -> None:
        self.history.remember(role, path_value)

    def clear_path_history_cache_keep_pins(self) -> dict[str, int]:
        return self.history.clear_cache_keep_pins()

    def ensure_initial_history(self) -> None:
        self.history.ensure_initial()

    def validate(self) -> None:
        if self.config.history_limit < 1:
            raise ValueError("Workbench history_limit must be positive.")
        for path in (
            self.config.root,
            self.config.input_path,
            self.config.output_path,
            self.config.history_path,
        ):
            if not isinstance(path, Path):
                raise TypeError("Workbench paths must be pathlib.Path instances.")
        for role in ("source", "target"):
            self.current_path(role)


@dataclass(frozen=True, slots=True)
class WorkbenchHandlers:
    delete_path: Callable[[WorkbenchRole], Any]
    pin_path: Callable[[WorkbenchRole, bool], Any]
    select_path: Callable[[WorkbenchRole], Any]
    pick_path: Callable[[WorkbenchRole], Any]
    open_path: Callable[[WorkbenchRole], Any]
    add_file: Callable[[], Any]
    reset_paths: Callable[[], Any]
    delete_io: Callable[[], Any]
    list_files: Callable[[], Any]


@dataclass(frozen=True, slots=True)
class WorkbenchRenderer:
    """NiceGUI renderer for the two address rows and the action bar."""

    adapter: WorkbenchAdapter
    handlers: WorkbenchHandlers
    display_path_callback: Callable[[Any], str]

    def display_path(self, value: Any) -> str:
        return str(self.display_path_callback(value))

    def path_option_items(self, role: str, current: Path) -> list[dict[str, Any]]:
        current_text = self.adapter.normalize_history_path(str(current))
        entries = self.adapter.history_entries(role)
        if not any(str(item.get("path", "")).casefold() == current_text.casefold() for item in entries):
            entries.append({"path": current_text, "count": 1, "last_used": "", "pinned": False})
        return self.adapter.history.normalize_entries(entries)

    def path_select_options(self, role: str, current: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in self.path_option_items(role, current):
            path_text = str(item.get("path", "")).strip()
            if path_text:
                result[path_text] = self.display_path(path_text)
        return result

    def decorate_path_select_options(self, select: Any, role: str, current: Path) -> None:
        pinned_by_path = {
            str(item.get("path", "")).casefold()
            for item in self.path_option_items(role, current)
            if bool(item.get("pinned")) and str(item.get("path", "")).strip()
        }
        values = list(getattr(select, "_values", []))
        # NiceGUI 3.14 serializes these select values as numeric indexes.
        # Raw Windows paths must never be embedded in the Vue expression.
        pinned_indexes = [index for index, value in enumerate(values) if str(value).casefold() in pinned_by_path]
        pinned_indexes_json = json.dumps(pinned_indexes)
        select.add_slot(
            "option",
            f"""
            <q-item
              v-bind="props.itemProps"
              dense
              :class="['audion-path-option-item', {pinned_indexes_json}.includes(Number(props.opt.value)) ? 'audion-path-option-pinned' : '']"
            >
              <q-item-section avatar class="audion-path-option-pin-cell">
                <q-icon v-if="{pinned_indexes_json}.includes(Number(props.opt.value))" name="push_pin" class="audion-path-option-pin" />
              </q-item-section>
              <q-item-section>
                <q-item-label class="audion-path-option-label">{{{{ props.opt.label || props.opt.value }}}}</q-item-label>
              </q-item-section>
            </q-item>
            """,
        )

    def path_is_pinned(self, role: str, current: Path) -> bool:
        current_text = self.adapter.normalize_history_path(str(current)).casefold()
        return any(
            bool(item.get("pinned")) and str(item.get("path", "")).strip().casefold() == current_text
            for item in self.path_option_items(role, current)
        )

    def folder_chip(self, role: WorkbenchRole) -> None:
        folder = self.adapter.current_path(role)
        role_title = self.adapter.translate("target_folder") if role == "target" else self.adapter.translate("source_folder")
        folder_label = self.display_path(folder)
        feedback = self.adapter.feedback()
        flash_this = str(feedback.get("role") or "") == role
        flash_action = str(feedback.get("action") or "")
        chip_classes = "audion-folder-chip"
        if flash_this and flash_action == "path":
            chip_classes += " audion-workspace-path-flash"
        elif flash_this and flash_action == "delete":
            chip_classes += " audion-workspace-delete-flash"
        pinned = self.path_is_pinned(role, folder)
        with ui.element("div").classes(chip_classes):
            delete_button = ui.button(icon="delete", on_click=self.handlers.delete_path(role)).props("dense flat round").classes("audion-action audion-folder-icon-button")
            if role == "source" and folder.is_file():
                delete_tip = f"Удалить файл-источник: {folder_label}" if self.adapter.language() == "ru" else f"Delete source file: {folder_label}"
            else:
                delete_tip = f"Очистить содержимое {role_title}: {folder_label}" if self.adapter.language() == "ru" else f"Clear {role_title} contents: {folder_label}"
            delete_button.tooltip(delete_tip)
            pin_classes = "audion-action audion-folder-pin-button " + ("audion-folder-pin-active" if pinned else "audion-folder-pin-inactive")
            if flash_this and flash_action in {"pin", "unpin"}:
                pin_classes += " audion-workspace-pin-flash"
            pin_button = ui.button(icon="push_pin", on_click=self.handlers.pin_path(role, not pinned)).props(
                f"dense flat round aria-pressed={'true' if pinned else 'false'}"
            ).classes(pin_classes)
            if self.adapter.language() == "ru":
                pin_button.tooltip(f"{'Открепить' if pinned else 'Закрепить'} {role_title}: {folder_label}")
            else:
                pin_button.tooltip(f"{'Unpin' if pinned else 'Pin'} {role_title}: {folder_label}")
            path_value = self.adapter.normalize_history_path(str(folder))
            path_options = self.path_select_options(role, folder)
            path_options.setdefault(path_value, self.display_path(path_value))
            path_select = ui.select(
                options=path_options,
                value=path_value,
                on_change=self.handlers.select_path(role),
            ).props("dense borderless options-dense popup-content-class=audion-path-cache-popup").classes("audion-folder-path-select")
            self.decorate_path_select_options(path_select, role, folder)
            path_select.tooltip(f"{role_title}: {folder_label}")
            pick_button = ui.button(icon="drive_file_move", on_click=self.handlers.pick_path(role)).props("dense flat round").classes("audion-action audion-folder-open-button")
            pick_button.tooltip(f"Выбрать {role_title}: {folder_label}" if self.adapter.language() == "ru" else f"Choose {role_title}: {folder_label}")
        if flash_this:
            self.adapter.clear_feedback()

    def route_tooltip(self, role: str) -> str:
        russian = self.adapter.language() == "ru"
        if role == "target":
            return "Открыть текущую целевую папку." if russian else "Open the current target folder."
        if role == "list":
            return "Создать список файлов выбранного источника в журнале." if russian else "Write the selected source file list to the log."
        if role == "cleanup":
            return "Сбросить выбранные пути на проектные INPUT и OUTPUT." if russian else "Reset selected paths to project INPUT and OUTPUT."
        if role == "delete_io":
            return "Удалить содержимое текущих ИСТОЧНИКА и НАЗНАЧЕНИЯ." if russian else "Delete current SOURCE and TARGET contents."
        if role == "add_file":
            return "Выбрать один файл как текущий ИСТОЧНИК." if russian else "Choose one file as the current SOURCE."
        return "Открыть текущую папку-источник." if russian else "Open the current source folder."

    def route_button(self, label_key: str, icon: str, role: str, on_click: Any) -> None:
        button = ui.button(
            self.adapter.translate(label_key),
            icon=icon,
            on_click=on_click,
        ).props("dense flat no-wrap").classes("audion-action audion-workspace-action audion-route-action rounded-md")
        button.tooltip(self.route_tooltip(role))

    def render_address_rows(self) -> None:
        with ui.element("div").classes("audion-workspace-strip audion-folder-strip"):
            self.folder_chip("source")
            self.folder_chip("target")

    def render_action_bar(self) -> None:
        with ui.element("div").classes("audion-workspace-strip audion-route-strip"):
            with ui.element("div").classes("audion-route-groups"):
                with ui.element("div").classes("audion-route-group audion-route-group-source"):
                    self.route_button("source_folder", "folder_open", "source", self.handlers.open_path("source"))
                    self.route_button("add_file_short", "note_add", "add_file", self.handlers.add_file())
                with ui.element("div").classes("audion-route-group audion-route-group-single"):
                    self.route_button("target_folder", "outbox", "target", self.handlers.open_path("target"))
                with ui.element("div").classes("audion-route-group audion-route-group-maintenance"):
                    self.route_button("clear_io_short", "backspace", "cleanup", self.handlers.reset_paths())
                    self.route_button("delete_io_short", "delete_sweep", "delete_io", self.handlers.delete_io())
                with ui.element("div").classes("audion-route-group audion-route-group-single"):
                    self.route_button("file_list_button", "format_list_bulleted", "list", self.handlers.list_files)
