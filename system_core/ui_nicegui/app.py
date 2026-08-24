from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
import atexit
import argparse
import ctypes
import importlib
import ipaddress
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import app as nicegui_app, run, ui  # type: ignore

from system_core.ui_nicegui.workbench import (
    WorkbenchAdapter,
    WorkbenchConfig,
    WorkbenchHandlers,
    WorkbenchRenderer,
    WorkbenchRole,
    WORKBENCH_FEEDBACK_CSS,
    WORKBENCH_LAYOUT_CSS,
    WORKBENCH_OVERRIDE_CSS,
    canonical_role,
)

from system_core.core.ansi import ansi_to_html
from system_core.core.config import load_yaml_or_json
from system_core.core.jobs import execute_operation
from system_core.core.manifest import CommandNode, Operation, load_manifest
from system_core.core.paths import ensure_project_dirs, get_project_paths, open_folder
from system_core.core.ui_theme_catalog import DEFAULT_THEME_ID, normalize_theme_id
from system_core.core.ui_settings import load_ui_settings, save_ui_settings


paths = get_project_paths(ROOT)
ensure_project_dirs(paths)
manifest = load_manifest(paths.config / "tool_manifest.yaml")
settings_path = paths.config / "gui_settings.yaml"
settings = load_ui_settings(settings_path)
tool_info: dict[str, Any] = manifest.raw.get("tool", {})
ui_info: dict[str, Any] = manifest.raw.get("ui", {})

def _string_map(value: Any) -> dict[str, str]:
    return {str(key).strip(): str(item).strip() for key, item in dict(value).items() if str(key).strip()} if isinstance(value, dict) else {}


BUILTIN_THEMES: dict[str, dict[str, Any]] = {
    "code_dark": {
        "label": "Code Dark",
        "label_ru": "Code Темная",
        "mode": "dark",
        "tokens": {
            "color-background-primary": "#141413",
            "color-background-secondary": "#1f1e1a",
            "color-background-tertiary": "#0f0f0e",
            "color-text-primary": "#faf9f5",
            "color-text-secondary": "#e8e6dc",
            "color-text-tertiary": "#b0aea5",
            "color-border-tertiary": "rgba(250, 249, 245, 0.15)",
            "color-border-secondary": "rgba(250, 249, 245, 0.3)",
            "color-border-primary": "rgba(250, 249, 245, 0.4)",
            "color-accent-primary": "#d97757",
            "color-accent-secondary": "#6a9bcc",
            "color-accent-tertiary": "#788c5d",
        },
    },
    "code_graphite": {
        "label": "Code Graphite",
        "label_ru": "Code графит",
        "mode": "dark",
        "tokens": {
            "color-background-primary": "#2c2c2a",
            "color-background-secondary": "#34332f",
            "color-background-tertiary": "#141413",
            "color-text-primary": "#faf9f5",
            "color-text-secondary": "#e8e6dc",
            "color-text-tertiary": "#b0aea5",
            "color-border-tertiary": "rgba(250, 249, 245, 0.15)",
            "color-border-secondary": "rgba(250, 249, 245, 0.3)",
            "color-border-primary": "rgba(250, 249, 245, 0.4)",
            "color-accent-primary": "#d97757",
            "color-accent-secondary": "#6a9bcc",
            "color-accent-tertiary": "#788c5d",
        },
    },
    "code_light": {
        "label": "Code Light",
        "label_ru": "Code светлая",
        "mode": "light",
        "tokens": {
            "color-background-primary": "#faf9f5",
            "color-background-secondary": "#fffdf8",
            "color-background-tertiary": "#f1efe8",
            "color-text-primary": "#141413",
            "color-text-secondary": "#5f5e5a",
            "color-text-tertiary": "#888780",
            "color-border-tertiary": "rgba(20, 20, 19, 0.15)",
            "color-border-secondary": "rgba(20, 20, 19, 0.3)",
            "color-border-primary": "rgba(20, 20, 19, 0.4)",
            "color-accent-primary": "#d97757",
            "color-accent-secondary": "#6a9bcc",
            "color-accent-tertiary": "#788c5d",
        },
    },
    "code_warm": {
        "label": "Code Warm",
        "label_ru": "Code теплая",
        "mode": "light",
        "tokens": {
            "color-background-primary": "#fffdf8",
            "color-background-secondary": "#faf9f5",
            "color-background-tertiary": "#e8e6dc",
            "color-text-primary": "#141413",
            "color-text-secondary": "#444441",
            "color-text-tertiary": "#888780",
            "color-border-tertiary": "rgba(20, 20, 19, 0.15)",
            "color-border-secondary": "rgba(20, 20, 19, 0.3)",
            "color-border-primary": "rgba(20, 20, 19, 0.4)",
            "color-accent-primary": "#d97757",
            "color-accent-secondary": "#6a9bcc",
            "color-accent-tertiary": "#788c5d",
        },
    },
    "audion_light": {
        "label": "Audion Light",
        "label_ru": "Audion светлая",
        "mode": "light",
        "tokens": {
            "color-background-primary": "#f7fbff",
            "color-background-secondary": "#ffffff",
            "color-background-tertiary": "#e6f1fb",
            "color-text-primary": "#102033",
            "color-text-secondary": "#36546f",
            "color-text-tertiary": "#6f879c",
            "color-border-tertiary": "rgba(4, 44, 83, 0.15)",
            "color-border-secondary": "rgba(4, 44, 83, 0.3)",
            "color-border-primary": "rgba(4, 44, 83, 0.4)",
            "color-accent-primary": "#378ADD",
            "color-accent-secondary": "#1D9E75",
            "color-accent-tertiary": "#534AB7",
        },
    },
    "audion_dark": {
        "label": "Audion Dark",
        "label_ru": "Audion Темная",
        "mode": "dark",
        "tokens": {
            "color-background-primary": "#08131f",
            "color-background-secondary": "#102033",
            "color-background-tertiary": "#050b12",
            "color-text-primary": "#f7fbff",
            "color-text-secondary": "#d7e7f6",
            "color-text-tertiary": "#9bb7cf",
            "color-border-tertiary": "rgba(247, 251, 255, 0.15)",
            "color-border-secondary": "rgba(247, 251, 255, 0.3)",
            "color-border-primary": "rgba(247, 251, 255, 0.4)",
            "color-accent-primary": "#6a9bcc",
            "color-accent-secondary": "#5DCAA5",
            "color-accent-tertiary": "#7F77DD",
        },
    },
    "asar_dark": {
        "label": "Asar Dark",
        "label_ru": "Asar Темная",
        "mode": "dark",
        "tokens": {
            "color-background-primary": "#181a1f",
            "color-background-secondary": "#20242b",
            "color-background-tertiary": "#0f1115",
            "color-text-primary": "#f4f7fb",
            "color-text-secondary": "#d6dde7",
            "color-text-tertiary": "#9aa7b8",
            "color-border-tertiary": "rgba(244, 247, 251, 0.15)",
            "color-border-secondary": "rgba(244, 247, 251, 0.3)",
            "color-border-primary": "rgba(244, 247, 251, 0.4)",
            "color-accent-primary": "#85B7EB",
            "color-accent-secondary": "#9FE1CB",
            "color-accent-tertiary": "#CECBF6",
        },
    },
}


def _normalize_theme(theme_id: str, theme_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": str(theme_data.get("label") or theme_id).strip(),
        "label_ru": str(theme_data.get("label_ru") or theme_data.get("label") or theme_id).strip(),
        "mode": "dark" if str(theme_data.get("mode", "dark")).lower() == "dark" else "light",
        "tokens": _string_map(theme_data.get("tokens", {})),
    }


def builtin_themes() -> dict[str, dict[str, Any]]:
    return {
        theme_id: _normalize_theme(theme_id, theme_data)
        for theme_id, theme_data in BUILTIN_THEMES.items()
    }


def load_ui_colors(path: Path) -> dict[str, Any]:
    data = load_yaml_or_json(path) if path.exists() else {}
    if not isinstance(data, dict):
        data = {}
    themes: dict[str, dict[str, Any]] = builtin_themes()
    themes_raw = data.get("themes", {})
    if not isinstance(themes_raw, dict):
        themes_raw = {}
    for theme_id, theme_data in themes_raw.items():
        if not isinstance(theme_data, dict):
            continue
        normalized_id = normalize_theme_id(theme_id, default="")
        if not normalized_id:
            continue
        normalized = _normalize_theme(normalized_id, theme_data)
        if normalized_id in themes:
            base = themes[normalized_id]
            normalized["tokens"] = {**_string_map(base.get("tokens", {})), **normalized["tokens"]}
        themes[normalized_id] = normalized
    return {
        "ramps": data.get("ramps", {}) if isinstance(data.get("ramps", {}), dict) else {},
        "tokens": _string_map(data.get("tokens", {})),
        "themes": themes,
    }


ui_colors = load_ui_colors(paths.config / "ui_colors.yaml")


def tolerate_missing_process_pool() -> None:
    """Keep NiceGUI alive when multiprocessing is blocked by the environment.

    NiceGUI initializes a process pool even when the GUI only uses thread/io-bound
    jobs. Some portable, sandboxed, or enterprise Windows environments reject the
    underlying multiprocessing handles, but the shell can still work without CPU
    pool tasks.
    """
    try:
        import nicegui.run as nicegui_run  # type: ignore
    except Exception:
        return

    original_setup = getattr(nicegui_run, "setup", None)
    if not callable(original_setup):
        return

    def safe_setup() -> None:
        try:
            original_setup()
        except (OSError, PermissionError) as exc:
            logging.warning("NiceGUI process pool disabled: %s", exc)
            nicegui_run.process_pool = None

    nicegui_run.setup = safe_setup


tolerate_missing_process_pool()

LABELS = {
    "ru": {
        "workspace": "Рабочие папки",
        "operations": "Операции",
        "root_other_operations": "Другие операции",
        "maintenance": "Обслуживание",
        "status": "Статус",
        "log": "Журнал операции",
        "idle": "Ожидание",
        "running": "Выполняется",
        "done": "Готово",
        "error": "Ошибка",
        "cancel": "Отменить",
        "another_running": "Другая операция уже выполняется.",
        "confirm_title": "Подтвердите действие",
        "confirm_impact_title": "Что произойдет",
        "confirm_irreversible_note": "Проверьте параметры перед запуском. Если операция трогает диски, сеть, системные службы или учетные записи, откат может потребовать ручного восстановления.",
        "confirm_parameters_note": "Текущие параметры будут использованы ровно в этом виде.",
        "confirm_run_dangerous": "Понимаю, запустить",
        "run": "Запустить",
        "back": "Назад",
        "selected_operation": "Выбрана команда",
        "open_menu": "Открыть",
        "parameters": "Параметры",
        "advanced": "Дополнительно",
        "actions": "Действия",
        "section_advanced": "Дополнительно",
        "section_encoding": "Кодирование",
        "section_format": "Формат",
        "section_options": "Опции",
        "section_output": "Результат",
        "section_parameters": "Параметры",
        "section_preset": "Профиль",
        "section_run": "Запуск",
        "section_source": "Источник",
        "close": "Закрыть",
        "logs": "Logs",
        "report": "Report",
        "config": "CONFIG",
        "expand": "Развернуть",
        "clear_terminal_window": "Очистить окно терминала",
        "source_folder": "Источник",
        "target_folder": "Назначение",
        "clear_io_short": "Сбросить",
        "delete_io_short": "Удалить",
        "file_list_button": "Список",
        "file_list": "File List",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "file_list_ready": "File list generated: {count}.",
        "picker_cancelled": "Выбор отменен.",
        "path_required": "Нужен путь",
        "path_pinned": "Путь закреплен",
        "path_unpinned": "Закрепление снято",
        "path_deleted": "Путь удален из истории.",
        "source_selected": "Источник выбран",
        "target_selected": "Цель выбрана",
        "operation_done": "Операция завершена.",
        "operation_failed": "Операция завершилась с кодом {code}.",
        "select_required": "Выберите хотя бы один пункт: {field}",
        "refresh_options": "Обновить список",
        "select_group_all": "Отметить блок",
        "clear_group": "Снять блок",
        "checkbox_filter": "Фильтр",
        "checkbox_filter_placeholder": "Имя или ID",
        "checkbox_filter_count": "{visible}/{total}",
        "checkbox_filter_no_matches": "По фильтру ничего не найдено.",
        "theme": "Тема",
        "theme_saved": "Тема сохранена. Перезагружаю интерфейс.",
        "browse": "Выбрать...",
        "terminal_command": "Команда",
        "terminal_history": "История команд",
        "terminal_history_empty": "Нет сохранённых команд",
        "terminal_cwd": "CWD",
        "terminal_location": "Локация",
        "terminal_shell": "Shell",
        "terminal_run": "Выполнить",
        "terminal_file": "Файл",
        "terminal_folder": "Папка",
        "pick_folder": "Папка",
        "pick_file": "Файл",
        "pin_command": "Закрепить команду",
        "unpin_command": "Открепить команду",
        "clear_terminal_history": "Очистить",
        "command_required": "Введите команду.",
        "lang_switch": "EN",
    },
    "en": {
        "workspace": "Workspace folders",
        "operations": "Operations",
        "root_other_operations": "Other operations",
        "maintenance": "Maintenance",
        "status": "Status",
        "log": "Operation log",
        "idle": "Idle",
        "running": "Running",
        "done": "Done",
        "error": "Error",
        "cancel": "Cancel",
        "another_running": "Another operation is already running.",
        "confirm_title": "Confirm action",
        "confirm_impact_title": "What will happen",
        "confirm_irreversible_note": "Check the parameters before running. If the operation touches disks, network, system services, or accounts, rollback may require manual recovery.",
        "confirm_parameters_note": "The current parameters will be used exactly as shown.",
        "confirm_run_dangerous": "I understand, run",
        "run": "Run",
        "back": "Back",
        "selected_operation": "Selected command",
        "open_menu": "Open",
        "parameters": "Parameters",
        "advanced": "Advanced",
        "actions": "Actions",
        "section_advanced": "Advanced",
        "section_encoding": "Encoding",
        "section_format": "Format",
        "section_options": "Options",
        "section_output": "Output",
        "section_parameters": "Parameters",
        "section_preset": "Profile",
        "section_run": "Run",
        "section_source": "Source",
        "close": "Close",
        "logs": "Logs",
        "report": "Report",
        "config": "CONFIG",
        "expand": "Expand",
        "clear_terminal_window": "Clear terminal window",
        "source_folder": "Source",
        "target_folder": "Target",
        "clear_io_short": "Reset",
        "delete_io_short": "Delete",
        "file_list_button": "List",
        "file_list": "File List",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "file_list_ready": "File list generated: {count}.",
        "picker_cancelled": "Selection cancelled.",
        "path_required": "Path required",
        "path_pinned": "Path pinned",
        "path_unpinned": "Path unpinned",
        "path_deleted": "Path deleted from history.",
        "source_selected": "Source selected",
        "target_selected": "Target selected",
        "operation_done": "Operation finished.",
        "operation_failed": "Operation finished with exit code {code}.",
        "select_required": "Select at least one item: {field}",
        "refresh_options": "Refresh list",
        "select_group_all": "Select block",
        "clear_group": "Clear block",
        "checkbox_filter": "Filter",
        "checkbox_filter_placeholder": "Name or ID",
        "checkbox_filter_count": "{visible}/{total}",
        "checkbox_filter_no_matches": "No checkbox items match the filter.",
        "theme": "Theme",
        "theme_saved": "Theme saved. Reloading UI.",
        "browse": "Browse...",
        "terminal_command": "Command",
        "terminal_history": "Command history",
        "terminal_history_empty": "No saved commands",
        "terminal_cwd": "CWD",
        "terminal_location": "Location",
        "terminal_shell": "Shell",
        "terminal_run": "Run",
        "terminal_file": "File",
        "terminal_folder": "Folder",
        "pick_folder": "Folder",
        "pick_file": "File",
        "pin_command": "Pin",
        "unpin_command": "Unpin",
        "clear_terminal_history": "Clear",
        "command_required": "Enter a command.",
        "lang_switch": "RU",
    },
}

PICKER_BOOTSTRAP = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AudionDpiAwareness {
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);
  [DllImport("shcore.dll")]
  public static extern int SetProcessDpiAwareness(int value);
}
"@
  try { [AudionDpiAwareness]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null }
  catch { [AudionDpiAwareness]::SetProcessDpiAwareness(2) | Out-Null }
} catch {}
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
"""

TERMINAL_HISTORY_PATH = paths.config / "terminal_commands.json"
TERMINAL_HISTORY_LIMIT = 200
PATH_HISTORY_PATH = paths.config / "path_history.json"
PATH_HISTORY_LIMIT = 100


def clean_terminal_commands(items: Any) -> list[str]:
    result: list[str] = []
    if not isinstance(items, list):
        return result
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result[:TERMINAL_HISTORY_LIMIT]


def load_terminal_cache() -> dict[str, Any]:
    default = {"history": [], "pinned": [], "last": "", "shell": "pwsh" if os.name == "nt" else "sh", "cwd": str(ROOT)}
    if not TERMINAL_HISTORY_PATH.exists():
        return default
    try:
        raw = json.loads(TERMINAL_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("Could not load terminal command history: %s", exc)
        return default
    if not isinstance(raw, dict):
        return default
    shell = str(raw.get("shell") or default["shell"]).strip().lower()
    if os.name == "nt":
        if shell not in {"pwsh", "cmd"}:
            shell = "pwsh"
    else:
        shell = "sh"
    cwd = str(raw.get("cwd") or default["cwd"]).strip() or str(ROOT)
    return {
        "history": clean_terminal_commands(raw.get("history", [])),
        "pinned": clean_terminal_commands(raw.get("pinned", [])),
        "last": str(raw.get("last") or "").strip(),
        "shell": shell,
        "cwd": cwd,
    }


initial_terminal_cache = load_terminal_cache()

state: dict[str, Any] = {
    "running": False,
    "cancel": False,
    "progress": 0.0,
    "status": "",
    "lines": [],
    "log_version": 0,
    "exit_code": None,
    "command_path": [],
    "pending_command": None,
    "field_values": {},
    "checkbox_filters": {},
    "terminal_cache": initial_terminal_cache,
    "terminal_command": "",
    "terminal_shell": str(initial_terminal_cache.get("shell") or ("pwsh" if os.name == "nt" else "sh")),
    "terminal_cwd": str(initial_terminal_cache.get("cwd") or ROOT),
    "source_path": str(getattr(settings, "source_path", "") or paths.input),
    "destination_path": str(getattr(settings, "destination_path", "") or paths.output),
    "workspace_feedback": {},
}

dynamic_option_cache: dict[str, tuple[float, list[Any]]] = {}


def tr(key: str, **kwargs: Any) -> str:
    lang = settings.language if settings.language in LABELS else "en"
    text = LABELS.get(lang, LABELS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def em(key: str) -> str:
    if not bool(getattr(settings, "emoji", False)):
        return ""
    return {
        "workspace": "📁 ",
        "operations": "⚙ ",
        "maintenance": "🧰 ",
        "status": "● ",
        "log": "🖥 ",
    }.get(key, "")


def app_title() -> str:
    return str(ui_info.get("title") or tool_info.get("name") or "Audion GUI Tool")


def active_theme() -> str:
    theme_id = normalize_theme_id(settings.theme)
    themes = ui_colors["themes"]
    if theme_id in themes:
        return theme_id
    return DEFAULT_THEME_ID if DEFAULT_THEME_ID in themes else next(iter(themes))


def active_theme_data() -> dict[str, Any]:
    return dict(ui_colors["themes"][active_theme()])


def active_theme_mode() -> str:
    return str(active_theme_data().get("mode", "dark"))


def theme_label(theme_id: str) -> str:
    theme_data = ui_colors["themes"].get(theme_id, {})
    label_key = "label_ru" if settings.language == "ru" else "label"
    return str(theme_data.get(label_key) or theme_data.get("label") or theme_id)


def theme_options() -> dict[str, str]:
    return {theme_id: theme_label(theme_id) for theme_id in ui_colors["themes"]}


def set_theme(theme_id: Any) -> None:
    selected = normalize_theme_id(theme_id)
    if selected not in ui_colors["themes"]:
        return
    settings.theme = selected
    save_ui_settings(settings_path, settings)
    safe_notify(tr("theme_saved"), "positive")
    ui.run_javascript("window.location.reload()")


def theme_change_handler(event: Any) -> None:
    set_theme(getattr(event, "value", None))


def theme_variables() -> dict[str, str]:
    variables: dict[str, str] = {}
    for ramp_name, stops in ui_colors["ramps"].items():
        if not isinstance(stops, dict):
            continue
        for stop, color in stops.items():
            variables[f"color-{ramp_name}-{stop}"] = str(color).strip()
    variables.update(ui_colors["tokens"])
    variables.update(_string_map(active_theme_data().get("tokens", {})))
    variables.setdefault("color-background-primary", "#141413")
    variables.setdefault("color-background-secondary", "#1f1e1a")
    variables.setdefault("color-background-tertiary", "#0f0f0e")
    variables.setdefault("color-text-primary", "#faf9f5")
    variables.setdefault("color-text-secondary", "#e8e6dc")
    variables.setdefault("color-text-tertiary", "#b0aea5")
    variables.setdefault("color-border-tertiary", "rgba(250, 249, 245, 0.15)")
    variables.setdefault("color-border-secondary", "rgba(250, 249, 245, 0.3)")
    variables.setdefault("color-border-primary", "rgba(250, 249, 245, 0.4)")
    variables.setdefault("color-accent-primary", "#d97757")
    variables.setdefault("font-sans", "Inter, Segoe UI, Arial, sans-serif")
    variables.setdefault("font-mono", "Cascadia Mono, Consolas, monospace")
    variables.setdefault("border-radius-md", "8px")
    variables.setdefault("border-radius-lg", "12px")
    return variables


def add_log(message: str) -> None:
    if not str(message).strip():
        return
    state["lines"].append(str(message).rstrip())
    state["lines"] = state["lines"][-700:]
    state["log_version"] = int(state["log_version"]) + 1


def clear_terminal_window() -> None:
    state["lines"] = []
    state["log_version"] = int(state["log_version"]) + 1


def terminal_html() -> str:
    return ansi_to_html("\n".join(state["lines"]))


def progress_text() -> str:
    return f"{round(max(0.0, min(1.0, float(state['progress']))) * 100):.0f}%"


def safe_notify(message: str, kind: str = "info") -> None:
    options = {"message": str(message), "type": kind}
    delivered = False
    for client in list(nicegui_app.clients()):
        if getattr(client, "_deleted", False) or not client.has_socket_connection:
            continue
        try:
            client.outbox.enqueue_message("notify", options, client.id)
            delivered = True
        except Exception as exc:
            logging.warning("NiceGUI notification delivery failed for client %s: %s", getattr(client, "id", "?"), exc)
    if delivered:
        return

    try:
        ui.notify(message, type=kind)
    except RuntimeError as exc:
        if "slot belongs to has been deleted" not in str(exc) and "current slot cannot be determined" not in str(exc):
            raise
        logging.warning("NiceGUI notification skipped because no live client slot was available: %s", message)


def dangerous_operation_notes(operation: Operation) -> list[str]:
    text = " ".join(
        [
            operation.id,
            operation.service,
            operation.display_title(settings.language),
            operation.display_description(settings.language),
        ]
    ).lower()
    notes: list[str] = []

    if any(word in text for word in ("disk", "partition", "format", "wipe", "winre", "diskpart", "vhd", "drive")):
        notes.append(
            "Возможны изменения дисков, разделов, VHD/образов или загрузочного окружения."
            if settings.language == "ru"
            else "Disk, partition, VHD/image, or recovery-boot data may be changed."
        )
    if any(word in text for word in ("network", "netsh", "wifi", "wi-fi", "winsock", "proxy", "adapter", "tcp", "ip", "dns")):
        notes.append(
            "Возможны сброс сети, переподключение адаптеров, изменение proxy/DNS или Wi-Fi профилей."
            if settings.language == "ru"
            else "Network reset, adapter reconnect, proxy/DNS, or Wi-Fi profile changes may occur."
        )
    if any(word in text for word in ("delete", "remove", "clean", "cleanup", "purge", "unregister", "reset")):
        notes.append(
            "Файлы, кэши, профили или зарегистрированные сущности могут быть удалены."
            if settings.language == "ru"
            else "Files, caches, profiles, or registered entities may be removed."
        )
    if any(word in text for word in ("wsl", "linux", "distro", "distribution", "import", "install", "export", "clone")):
        notes.append(
            "WSL-дистрибутивы могут быть созданы, импортированы, перемещены, экспортированы или перерегистрированы."
            if settings.language == "ru"
            else "WSL distributions may be created, imported, moved, exported, or registered again."
        )
    if any(word in text for word in ("admin", "uac", "elevat", "feature", "optionalfeature", "dism", "bcdedit", "set-service", "start-service", "stop-service", "sc.exe")):
        notes.append(
            "Windows может запросить UAC, а системные компоненты могут потребовать перезагрузку."
            if settings.language == "ru"
            else "Windows may request UAC, and system components may require a reboot."
        )

    if not notes:
        notes.append(operation.display_description(settings.language) or tr("confirm_parameters_note"))
    notes.append(tr("confirm_parameters_note"))
    return notes


RUN_STATE_LABELS = {
    "idle": ("idle", "audion-status-idle"),
    "running": ("running", "audion-status-running"),
    "done": ("done", "audion-status-done"),
    "error": ("error", "audion-status-error"),
}


def run_state() -> str:
    """Which of the four states the panel is showing.

    Colour carries this everywhere it appears, so it is decided once.
    """
    if bool(state["running"]):
        return "running"
    exit_code = state.get("exit_code")
    if exit_code is None:
        return "idle"
    return "done" if int(exit_code or 0) == 0 else "error"


def status_row_classes() -> str:
    return f"audion-status-row {RUN_STATE_LABELS[run_state()][1]}"


def status_state_text() -> str:
    return tr(RUN_STATE_LABELS[run_state()][0]).upper()


def elapsed_text(seconds: float | None) -> str:
    """A run's own clock, mm:ss, or an em dash before anything has run.

    The start is noticed by the refresh timer rather than written by the code that
    starts a run: there are several such places, and none of them has to know
    about the panel.
    """
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def status_dot_classes() -> str:
    base = "audion-status-dot text-lg leading-none"
    if bool(state["running"]):
        return f"{base} text-sky-400 animate-pulse"
    if state.get("exit_code") is None:
        return f"{base} text-gray-500"
    if int(state.get("exit_code") or 0) == 0:
        return f"{base} text-green-400"
    return f"{base} text-red-400"


def set_progress(value: float) -> None:
    state["progress"] = max(0.0, min(1.0, float(value)))


def cancel_requested() -> bool:
    return bool(state["cancel"])


def hidden_subprocess_flags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def resolve_dialog_powershell() -> list[str]:
    candidates = [
        [str(paths.system_core / "powershell" / "pwsh.exe"), "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command"],
    ]
    for candidate in candidates:
        exe = candidate[0]
        if Path(exe).exists() or shutil.which(exe):
            return candidate
    raise RuntimeError("PowerShell was not found for Windows picker.")


_PICKER_RUN_LOCK = threading.Lock()
_PICKER_JOB_LOCK = threading.Lock()
_PICKER_JOB_HANDLE: int | None = None


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def close_picker_job() -> None:
    global _PICKER_JOB_HANDLE
    with _PICKER_JOB_LOCK:
        handle = _PICKER_JOB_HANDLE
        _PICKER_JOB_HANDLE = None
    if os.name == "nt" and handle:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(wintypes.HANDLE(handle))


def _picker_job_handle() -> int | None:
    global _PICKER_JOB_HANDLE
    if os.name != "nt":
        return None
    with _PICKER_JOB_LOCK:
        if _PICKER_JOB_HANDLE:
            return _PICKER_JOB_HANDLE
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logging.warning("Could not create the Windows picker job: %s", ctypes.get_last_error())
            return None
        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        configured = kernel32.SetInformationJobObject(
            wintypes.HANDLE(job),
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not configured:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(job))
            logging.warning("Could not configure the Windows picker job: %s", error)
            return None
        _PICKER_JOB_HANDLE = int(job)
        return _PICKER_JOB_HANDLE


def _assign_picker_to_job(process: subprocess.Popen[str]) -> None:
    handle = _picker_job_handle()
    if os.name != "nt" or not handle:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assigned = kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(handle),
        wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
    )
    if not assigned:
        logging.warning("Could not attach picker PID %s to its Windows job: %s", process.pid, ctypes.get_last_error())


def run_picker_script(script: str, failure_message: str) -> str:
    if not _PICKER_RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("A Windows picker is already open.")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [*resolve_dialog_powershell(), script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=hidden_subprocess_flags(),
            startupinfo=hidden_subprocess_startupinfo(),
        )
        _assign_picker_to_job(process)
        try:
            stdout, stderr = process.communicate(timeout=3600)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise RuntimeError("Windows picker timed out.") from exc
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or failure_message)
        return stdout
    finally:
        if process is not None and process.poll() is None:
            process.kill()
        _PICKER_RUN_LOCK.release()


atexit.register(close_picker_job)
nicegui_app.on_shutdown(close_picker_job)


def parse_picker_paths(text: str) -> list[Path]:
    import json

    payload = text.strip()
    if not payload:
        return []
    data = json.loads(payload)
    if isinstance(data, str):
        data = [data]
    return [Path(str(item)).resolve() for item in data if str(item).strip()]


def pick_single_file(title: str = "Choose one source file") -> list[Path]:
    script = PICKER_BOOTSTRAP + r"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '__TITLE__'
$dialog.Multiselect = $false
$dialog.Filter = 'All supported files|*.*|All files|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  $dialog.FileName | ConvertTo-Json -Compress
}
""".replace("__TITLE__", title.replace("'", "''"))
    return parse_picker_paths(run_picker_script(script, "File picker failed."))


def pick_folder(title: str = "Choose source folder", allow_new_folder: bool = False) -> list[Path]:
    script = PICKER_BOOTSTRAP + r"""
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '__TITLE__'
$dialog.ShowNewFolderButton = __ALLOW_NEW_FOLDER__
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  @($dialog.SelectedPath) | ConvertTo-Json -Compress
}
""".replace("__TITLE__", title.replace("'", "''")).replace("__ALLOW_NEW_FOLDER__", "$true" if allow_new_folder else "$false")
    return parse_picker_paths(run_picker_script(script, "Folder picker failed."))


def input_file_list_lines(source: Path) -> list[str]:
    if not source.exists():
        return [tr("file_list_missing", path=source)]
    names = (
        [source.name]
        if source.is_file()
        else sorted((path.name for path in source.rglob("*") if path.is_file()), key=lambda item: item.casefold())
    )
    if not names:
        return [tr("file_list_empty")]

    number_width = max(3, len(str(len(names))))
    lines = [
        f"{'No.':>{number_width}}  List",
        f"{'-' * number_width}  ----",
    ]
    lines.extend(f"{index:0{number_width}d}. {name}" for index, name in enumerate(names, start=1))
    return lines


async def show_input_file_list() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return

    title = tr("file_list")
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )
    try:
        lines = await run.io_bound(input_file_list_lines, current_source_path())
        for line in lines:
            add_log(line)
        count = max(0, len(lines) - 2)
        state["exit_code"] = 0
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{count}]"
        safe_notify(tr("file_list_ready", count=count), "positive")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


async def start_operation(operation: Operation) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    parameters = dict(operation.parameters)
    parameters["gui_input_dir"] = str(current_source_path())
    parameters["gui_output_dir"] = str(current_target_path())
    # The names the services actually read, same as in Audion Get. Without
    # these the Workbench is decoration: Source and Target are chosen in the
    # GUI while every operation still works on the project's own folders.
    parameters["input_path"] = str(current_source_path())
    parameters["output_path"] = str(current_target_path())
    operation = Operation(
        id=operation.id,
        title=operation.title,
        description=operation.description,
        service=operation.service,
        kind=operation.kind,
        title_ru=operation.title_ru,
        description_ru=operation.description_ru,
        parameters=parameters,
        fields=operation.fields,
        tooltip=operation.tooltip,
        tooltip_ru=operation.tooltip_ru,
    )

    if operation.kind == "dangerous":
        with ui.dialog() as dialog, ui.card().classes("audion-dialog audion-confirm-card rounded-lg"):
            ui.label(tr("confirm_title")).classes("text-base font-semibold")
            ui.label(operation.display_title(settings.language)).classes("text-sm font-semibold")
            description = operation.display_description(settings.language)
            if description:
                ui.label(description).classes("text-sm text-gray-400")
            ui.label(tr("confirm_impact_title")).classes("audion-confirm-subtitle")
            for note in dangerous_operation_notes(operation):
                ui.label(f"- {note}").classes("audion-confirm-note")
            ui.label(tr("confirm_irreversible_note")).classes("audion-confirm-warning")
            with ui.row().classes("w-full items-center justify-end gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat").classes("audion-action rounded-lg")
                ui.button(tr("confirm_run_dangerous"), on_click=lambda: dialog.submit(True)).props("dense flat no-wrap").classes("audion-action rounded-lg")
        confirmed = await dialog
        if not confirmed:
            return

    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {operation.display_title(settings.language)}",
            "lines": [],
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )
    started = time.perf_counter()
    try:
        result = await run.io_bound(
            execute_operation,
            active_project_paths(),
            operation,
            add_log,
            set_progress,
            cancel_requested,
        )
        elapsed = time.perf_counter() - started
        state["exit_code"] = 0 if result.ok else 1
        state["progress"] = 1.0
        state["status"] = f"{tr('done') if result.ok else tr('error')}: {operation.display_title(settings.language)} [{state['exit_code']}] {elapsed:.1f}s"
        safe_notify(result.message, "positive" if result.ok else "negative")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False


def toggle_language() -> None:
    settings.language = "en" if settings.language == "ru" else "ru"
    save_ui_settings(settings_path, settings)
    ui.run_javascript("window.location.reload()")


def save_advanced_open(event: Any) -> None:
    settings.advanced_open = bool(getattr(event, "value", False))
    save_ui_settings(settings_path, settings)


def current_source_path() -> Path:
    return Path(str(state.get("source_path") or getattr(settings, "source_path", "") or paths.input)).expanduser()


def current_target_path() -> Path:
    return Path(str(state.get("destination_path") or getattr(settings, "destination_path", "") or paths.output)).expanduser()


def active_project_paths():
    return replace(paths, input=current_source_path(), output=current_target_path())


def save_workspace_path(kind: str, value: Any) -> None:
    text = str(value or "").strip().strip('"')
    role = canonical_role(kind)
    if role == "target":
        settings.destination_path = text
        state["destination_path"] = text
        state.setdefault("field_values", {})["gui_output_dir"] = text or str(paths.output)
    else:
        settings.source_path = text
        state["source_path"] = text
        state.setdefault("field_values", {})["gui_input_dir"] = text or str(paths.input)
    dynamic_option_cache.clear()
    save_ui_settings(settings_path, settings)


def reload_ui(delay_ms: int = 0) -> None:
    script = f"window.setTimeout(() => window.location.reload(), {max(0, int(delay_ms))})"
    delivered = False
    for client in list(nicegui_app.clients()):
        if getattr(client, "_deleted", False) or not client.has_socket_connection:
            continue
        client.run_javascript(script)
        delivered = True
    if not delivered:
        ui.run_javascript(script)


def display_path(path_value: Any) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        relative = path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))
    except (OSError, ValueError):
        return str(path)
    return str(relative) or "."


def absolute_project_path(path_value: Any) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def remove_path_tree(path: Path) -> int:
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(path))
    if path.is_symlink() or is_junction:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return 1
    if path.is_file():
        path.unlink()
        return 1
    if path.is_dir():
        shutil.rmtree(path)
        return 1
    return 0


def clear_directory_contents(folder: Path) -> int:
    removed = 0
    if not folder.exists():
        return removed
    for child in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        # input and output must be genuinely empty after a clear, so every entry
        # is removed and nothing is spared. The folders come from
        # install/init_folders.cmd.
        removed += remove_path_tree(child)
    return removed


def normalized_absolute_path(path_value: Any) -> Path:
    return absolute_project_path(path_value).resolve(strict=False)


def paths_equal(left: Any, right: Any) -> bool:
    return os.path.normcase(str(normalized_absolute_path(left))) == os.path.normcase(str(normalized_absolute_path(right)))


def validate_workspace_delete_target(path_value: Any) -> Path:
    target = normalized_absolute_path(path_value)
    if target.parent == target:
        raise RuntimeError(f"Refusing to delete a filesystem root: {target}")
    if paths_equal(target, ROOT):
        raise RuntimeError(f"Refusing to delete the project root: {target}")
    return target


def delete_workspace_path_contents(path_value: Any) -> dict[str, Any]:
    target = validate_workspace_delete_target(path_value)
    if not target.exists() and not target.is_symlink():
        return {"path": str(target), "kind": "missing", "removed": 0}
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(target))
    if target.is_file() or target.is_symlink() or is_junction:
        removed = remove_path_tree(target)
        return {"path": str(target), "kind": "file", "removed": removed}
    if not target.is_dir():
        raise RuntimeError(f"Unsupported workspace path: {target}")
    removed = clear_directory_contents(target)
    return {"path": str(target), "kind": "folder", "removed": removed}


def delete_workspace_io_contents(source: Path, target: Path) -> dict[str, Any]:
    source_result = delete_workspace_path_contents(source)
    if paths_equal(source, target):
        target_result = {"path": str(normalized_absolute_path(target)), "kind": "same", "removed": 0}
    else:
        target_result = delete_workspace_path_contents(target)
    return {"source": source_result, "target": target_result}


def open_workspace_folder(role: str) -> None:
    role_key = canonical_role(role)
    folder = current_target_path() if role_key == "target" else current_source_path()
    if role_key != "target" and not folder.exists():
        raise FileNotFoundError(tr("source_folder_missing", path=folder))
    if folder.is_file():
        if os.name == "nt":
            subprocess.Popen(
                ["explorer.exe", f"/select,{folder}"],
                creationflags=hidden_subprocess_flags(),
                startupinfo=hidden_subprocess_startupinfo(),
            )
        else:
            open_folder(folder.parent)
        return
    open_folder(folder)


def mark_workspace_feedback(role: str, action: str) -> None:
    state["workspace_feedback"] = {
        "role": canonical_role(role),
        "action": str(action or "path"),
    }


def _save_workspace_adapter_path(role: WorkbenchRole, value: Any) -> None:
    save_workspace_path(role, value)


def _workspace_feedback() -> dict[str, str]:
    value = state.get("workspace_feedback")
    return dict(value) if isinstance(value, dict) else {}


def _clear_workspace_feedback() -> None:
    state["workspace_feedback"] = {}


WORKBENCH_CONFIG = WorkbenchConfig(
    root=ROOT,
    input_path=paths.input,
    output_path=paths.output,
    history_path=PATH_HISTORY_PATH,
    history_limit=PATH_HISTORY_LIMIT,
)
WORKBENCH_ADAPTER = WorkbenchAdapter(
    config=WORKBENCH_CONFIG,
    current_path_callback=lambda role: current_target_path() if role == "target" else current_source_path(),
    save_path_callback=_save_workspace_adapter_path,
    language_callback=lambda: settings.language,
    translate_callback=tr,
    log_callback=add_log,
    notify_callback=safe_notify,
    reload_callback=reload_ui,
    busy_callback=lambda: bool(state.get("running")),
    feedback_callback=_workspace_feedback,
    set_feedback_callback=mark_workspace_feedback,
    clear_feedback_callback=_clear_workspace_feedback,
)
WORKBENCH_ADAPTER.validate()
WORKBENCH_ADAPTER.ensure_initial_history()


def workspace_pin_click_handler(role: str, pinned: bool):
    async def handler() -> None:
        path_value = str(current_target_path() if role == "target" else current_source_path())
        if not path_value:
            safe_notify(WORKBENCH_ADAPTER.translate("path_required"), "warning")
            return
        try:
            await run.io_bound(WORKBENCH_ADAPTER.set_path_pinned, role, path_value, pinned)
            mark_workspace_feedback(role, "pin" if pinned else "unpin")
            add_log(f"{'Pinned' if pinned else 'Unpinned'} {role} path: {path_value}")
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def workspace_delete_path_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        role_key = canonical_role(role)
        path = current_target_path() if role_key == "target" else current_source_path()
        path_value = str(path)
        if not path_value:
            safe_notify(WORKBENCH_ADAPTER.translate("path_required"), "warning")
            return
        external_source = role_key == "source" and not paths_equal(path, paths.input)
        if external_source:
            is_file = path.is_file()
            with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
                title = "Удалить исходный файл?" if is_file else "Очистить внешний ИСТОЧНИК?"
                if settings.language != "ru":
                    title = "Delete the source file?" if is_file else "Clear the external SOURCE?"
                ui.label(title).classes("text-base font-semibold")
                warning = (
                    "Будет удалён исходный файл. Другой копии может не существовать."
                    if is_file
                    else "Будут безвозвратно удалены все файлы и вложенные папки."
                )
                if settings.language != "ru":
                    warning = (
                        "The source file will be deleted. Another copy may not exist."
                        if is_file
                        else "All files and nested folders will be permanently deleted."
                    )
                ui.label(warning).classes("text-sm text-gray-300")
                ui.label(str(normalized_absolute_path(path))).classes("max-w-3xl break-all font-mono text-xs text-gray-400")
                with ui.row().classes("gap-2"):
                    ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                    ui.button(WORKBENCH_ADAPTER.translate("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
            if not await dialog:
                return
        try:
            result = await run.io_bound(delete_workspace_path_contents, path)
            if result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, role_key, path_value)
                save_workspace_path(role_key, "")
            mark_workspace_feedback(role_key, "delete")
            add_log(
                f"Cleared {'TARGET' if role_key == 'target' else 'SOURCE'}: {result.get('path')} "
                f"[kind={result.get('kind')}, removed={result.get('removed', 0)}]"
            )
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def workspace_single_file_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        try:
            selected = await run.io_bound(pick_single_file)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, "source", path_value)
        mark_workspace_feedback("source", "path")
        add_log(f"SOURCE FILE -> {path_value}")
        reload_ui(150)

    return handler


def workspace_open_click_handler(role: str):
    async def handler() -> None:
        try:
            await run.io_bound(open_workspace_folder, role)
            role_key = canonical_role(role)
            path = current_target_path() if role_key == "target" else current_source_path()
            add_log(f"Opened {role_key} path: {path}")
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def reset_workspace_paths_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        result = await run.io_bound(WORKBENCH_ADAPTER.clear_path_history_cache_keep_pins)
        save_workspace_path("source", "")
        save_workspace_path("target", "")
        add_log(f"Workspace route reset: SOURCE -> {paths.input}")
        add_log(f"Workspace route reset: TARGET -> {paths.output}")
        add_log(
            "Workspace path cache cleared: "
            f"sources={result.get('removed_sources', 0)}, targets={result.get('removed_targets', 0)}, "
            f"pins kept={result.get('kept_pins', 0)}"
        )
        safe_notify(tr("operation_done"), "positive")
        reload_ui()

    return handler


def workspace_path_select_handler(role: str):
    async def handler(event: Any) -> None:
        path_value = str(getattr(event, "value", "") or "").strip()
        if not path_value:
            return
        role_key = canonical_role(role)
        current = current_target_path() if role_key == "target" else current_source_path()
        if paths_equal(current, path_value):
            return
        save_workspace_path(role_key, path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role_key, path_value)
        mark_workspace_feedback(role_key, "path")
        add_log(f"{'TARGET' if role_key == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui(150)

    return handler


def workspace_delete_both_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        source = current_source_path()
        target = current_target_path()
        source_external = not paths_equal(source, paths.input)
        with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
            ui.label("Удалить содержимое I/O?" if settings.language == "ru" else "Delete I/O contents?").classes("text-base font-semibold")
            warning = (
                "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ. Внешний ИСТОЧНИК может быть единственным экземпляром."
                if source_external
                else "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ."
            )
            if settings.language != "ru":
                warning = (
                    "SOURCE and TARGET files will be deleted. The external SOURCE may be the only copy."
                    if source_external
                    else "SOURCE and TARGET files will be deleted."
                )
            ui.label(warning).classes("text-sm text-gray-300")
            ui.label(f"SOURCE: {normalized_absolute_path(source)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            ui.label(f"TARGET: {normalized_absolute_path(target)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(WORKBENCH_ADAPTER.translate("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        if not await dialog:
            return
        state["running"] = True
        try:
            result = await run.io_bound(delete_workspace_io_contents, source, target)
            source_result = result.get("source", {})
            target_result = result.get("target", {})
            if source_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "source", str(source))
                save_workspace_path("source", "")
            if target_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "target", str(target))
                save_workspace_path("target", "")
            add_log(
                f"Cleared SOURCE: {source_result.get('path')} "
                f"[kind={source_result.get('kind')}, removed={source_result.get('removed', 0)}]"
            )
            add_log(
                f"Cleared TARGET: {target_result.get('path')} "
                f"[kind={target_result.get('kind')}, removed={target_result.get('removed', 0)}]"
            )
            mark_workspace_feedback("source", "delete")
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
        finally:
            state["running"] = False

    return handler


def workspace_pick_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        role_key = canonical_role(role)
        try:
            selected = await run.io_bound(
                pick_folder,
                WORKBENCH_ADAPTER.translate("target_folder") if role_key == "target" else WORKBENCH_ADAPTER.translate("source_folder"),
                True,
            )
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path(role_key, path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role_key, path_value)
        mark_workspace_feedback(role_key, "path")
        add_log(f"{'TARGET' if role_key == 'target' else 'SOURCE'} -> {path_value}")
        safe_notify(
            WORKBENCH_ADAPTER.translate("target_selected" if role_key == "target" else "source_selected"),
            "positive",
        )
        reload_ui(150)

    return handler


WORKBENCH_RENDERER = WorkbenchRenderer(
    adapter=WORKBENCH_ADAPTER,
    handlers=WorkbenchHandlers(
        delete_path=workspace_delete_path_click_handler,
        pin_path=workspace_pin_click_handler,
        select_path=workspace_path_select_handler,
        pick_path=workspace_pick_click_handler,
        open_path=workspace_open_click_handler,
        add_file=workspace_single_file_click_handler,
        reset_paths=reset_workspace_paths_click_handler,
        delete_io=workspace_delete_both_click_handler,
        list_files=show_input_file_list,
    ),
    display_path_callback=display_path,
)



AUDION_CANONICAL_TOOLTIP_DELAY_MS = 1500
AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS = 100
AUDION_CANONICAL_TOOLTIP_TRANSITION_MS = 100


def install_audion_canonical_tooltip_defaults() -> None:
    """Give every tooltip in this app the canonical timing and look.

    NiceGUI shows a tooltip almost immediately, which turns a dense panel into a
    flicker of popups as the pointer crosses it. The canon waits 1500 ms, so a
    tooltip only appears when someone actually stopped to ask.
    """
    try:
        from nicegui.elements.tooltip import Tooltip as NiceGuiTooltip  # type: ignore
    except Exception:
        return
    if getattr(NiceGuiTooltip, "_audion_canonical_tooltip_defaults", False):
        return
    original_init = NiceGuiTooltip.__init__

    def audion_tooltip_init(self: Any, text: str = "") -> None:
        original_init(self, text)
        self.props["delay"] = AUDION_CANONICAL_TOOLTIP_DELAY_MS
        self.props["hide-delay"] = AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS
        self.props["transition-duration"] = AUDION_CANONICAL_TOOLTIP_TRANSITION_MS
        self.classes("audion-tooltip")

    NiceGuiTooltip.__init__ = audion_tooltip_init  # type: ignore[method-assign]
    NiceGuiTooltip._audion_canonical_tooltip_defaults = True  # type: ignore[attr-defined]


install_audion_canonical_tooltip_defaults()


def attach_tooltip(element: Any, text: str) -> Any:
    clean_text = str(text or "").strip()
    if clean_text:
        element.tooltip(clean_text)
    return element


def operation_button(operation: Operation) -> None:
    description = operation.display_description(settings.language)
    tooltip = operation.display_tooltip(settings.language) or description
    with ui.element("div").classes("audion-operation-row"):
        button = ui.button(
            operation.display_title(settings.language),
            on_click=operation_click_handler(operation),
        ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        attach_tooltip(button, tooltip)
        ui.label(description).classes("audion-operation-description")


def operation_click_handler(operation: Operation):
    async def handler() -> None:
        await start_operation(operation)

    return handler


def terminal_cache() -> dict[str, Any]:
    cache = state.get("terminal_cache")
    if not isinstance(cache, dict):
        cache = load_terminal_cache()
        state["terminal_cache"] = cache
    cache["history"] = clean_terminal_commands(cache.get("history", []))
    cache["pinned"] = clean_terminal_commands(cache.get("pinned", []))
    return cache


def save_terminal_cache() -> None:
    cache = terminal_cache()
    cache["last"] = str(state.get("terminal_command") or "").strip()
    shell = str(state.get("terminal_shell") or ("pwsh" if os.name == "nt" else "sh")).strip().lower()
    if os.name == "nt":
        cache["shell"] = shell if shell in {"pwsh", "cmd"} else "pwsh"
    else:
        cache["shell"] = "sh"
    cache["cwd"] = str(state.get("terminal_cwd") or ROOT).strip() or str(ROOT)
    TERMINAL_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    TERMINAL_HISTORY_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def remember_terminal_command(command: str) -> None:
    command = command.strip()
    if not command:
        return
    cache = terminal_cache()
    history = [command, *[item for item in cache["history"] if item != command]]
    cache["history"] = history[:TERMINAL_HISTORY_LIMIT]
    state["terminal_command"] = command
    save_terminal_cache()


def terminal_command_options() -> dict[str, str]:
    cache = terminal_cache()
    pinned = clean_terminal_commands(cache.get("pinned", []))
    history = [item for item in clean_terminal_commands(cache.get("history", [])) if item not in pinned]
    last = str(cache.get("last") or "").strip()
    current = str(state.get("terminal_command") or "").strip()
    ordered = [*pinned]
    for command in (current, last, *history):
        if command and command not in ordered:
            ordered.append(command)
    options: dict[str, str] = {}
    for command in ordered[:TERMINAL_HISTORY_LIMIT]:
        options[command] = terminal_command_option_label(command, command in pinned)
    if not options:
        options[""] = tr("terminal_history_empty")
    return options


def terminal_command_option_label(command: str, pinned: bool = False) -> str:
    text = " ".join(str(command or "").split())
    if len(text) > 120:
        text = f"{text[:117]}..."
    return f"PIN {text}" if pinned else text


def terminal_history_value() -> str | None:
    options = terminal_command_options()
    current = str(state.get("terminal_command") or "").strip()
    if current and current in options:
        return current
    return None


def terminal_command_is_pinned() -> bool:
    command = str(state.get("terminal_command") or "").strip()
    return bool(command and command in terminal_cache().get("pinned", []))


def event_value(event: Any) -> Any:
    if hasattr(event, "value"):
        return event.value
    args = getattr(event, "args", None)
    if isinstance(args, list) and args:
        return args[0]
    if isinstance(args, dict):
        return args.get("value") or args.get("inputValue") or args.get("input")
    return args


def resolve_terminal_history_value(value: Any) -> str:
    value = event_value(value)
    if isinstance(value, dict):
        value = value.get("value") or value.get("label") or value.get("name") or ""
    if isinstance(value, list) and value:
        value = value[0]
    text = str(value or "").strip()
    options = terminal_command_options()
    if text in options:
        return text
    for command, label in options.items():
        if text == str(label).strip():
            return command
    return text


def set_terminal_command(value: Any) -> None:
    state["terminal_command"] = str(value or "").strip()
    save_terminal_cache()


def select_terminal_history(value: Any) -> None:
    set_terminal_command(resolve_terminal_history_value(value))
    terminal_command_bar.refresh()


def set_terminal_shell(value: Any) -> None:
    shell = str(value or ("pwsh" if os.name == "nt" else "sh")).strip().lower()
    if os.name == "nt":
        state["terminal_shell"] = shell if shell in {"pwsh", "cmd"} else "pwsh"
    else:
        state["terminal_shell"] = "sh"
    save_terminal_cache()


def set_terminal_cwd(value: Any) -> None:
    state["terminal_cwd"] = str(value or "").strip() or str(ROOT)
    save_terminal_cache()


def append_terminal_argument(value: Path | str) -> None:
    text = str(value)
    quoted = f'"{text}"' if any(char.isspace() for char in text) else text
    current = str(state.get("terminal_command") or "").rstrip()
    state["terminal_command"] = f"{current} {quoted}".strip() if current else quoted
    save_terminal_cache()
    terminal_command_bar.refresh()


def pin_terminal_command() -> None:
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("command_required"), "warning")
        return
    cache = terminal_cache()
    pinned = [item for item in cache["pinned"] if item != command]
    pinned.insert(0, command)
    cache["pinned"] = pinned[:TERMINAL_HISTORY_LIMIT]
    remember_terminal_command(command)
    terminal_command_bar.refresh()


def unpin_terminal_command() -> None:
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("command_required"), "warning")
        return
    cache = terminal_cache()
    cache["pinned"] = [item for item in cache["pinned"] if item != command]
    remember_terminal_command(command)
    terminal_command_bar.refresh()


def clear_terminal_history() -> None:
    cache = terminal_cache()
    cache["history"] = [item for item in cache["history"] if item in cache["pinned"]]
    cache["last"] = ""
    state["terminal_command"] = ""
    save_terminal_cache()
    terminal_command_bar.refresh()


async def pick_terminal_location(kind: str) -> None:
    try:
        if kind == "file":
            picked = await run.io_bound(pick_single_file, tr("pick_file"))
        else:
            picked = await run.io_bound(pick_folder, tr("pick_folder"), True)
    except Exception as exc:
        safe_notify(str(exc), "negative")
        return
    if not picked:
        safe_notify(tr("picker_cancelled"), "warning")
        return
    selected = picked[0]
    if selected.is_file():
        set_terminal_cwd(str(selected.parent))
        append_terminal_argument(selected)
    else:
        set_terminal_cwd(str(selected))
    terminal_command_bar.refresh()


def terminal_location_click_handler(kind: str):
    async def handler() -> None:
        await pick_terminal_location(kind)

    return handler


async def start_terminal_command() -> None:
    command = str(state.get("terminal_command") or "").strip()
    if not command:
        safe_notify(tr("command_required"), "warning")
        return
    remember_terminal_command(command)
    terminal_command_bar.refresh()
    shell = str(state.get("terminal_shell") or ("pwsh" if os.name == "nt" else "sh")).strip().lower()
    cwd = str(state.get("terminal_cwd") or ROOT).strip()
    operation = Operation(
        id="terminal_command",
        title="Terminal command",
        title_ru="Команда терминала",
        description=command,
        description_ru=command,
        service="system_core.services.sample_service:terminal_command",
        kind="safe",
        parameters={"command": command, "shell": shell, "cwd": cwd},
    )
    await start_operation(operation)


async def terminal_enter_handler(_event: Any = None) -> None:
    await start_terminal_command()


def operation_to_command_node(operation: Operation) -> CommandNode:
    return CommandNode(
        id=operation.id,
        title=operation.title,
        description=operation.description,
        service=operation.service,
        kind=operation.kind,
        title_ru=operation.title_ru,
        description_ru=operation.description_ru,
        tooltip=operation.tooltip,
        tooltip_ru=operation.tooltip_ru,
        parameters=dict(operation.parameters),
        fields=operation.fields,
    )


def root_command_nodes() -> list[CommandNode]:
    if manifest.operation_groups:
        return manifest.operation_groups
    return [operation_to_command_node(operation) for operation in manifest.operations]


def current_command_level() -> tuple[list[CommandNode], list[CommandNode]]:
    trail: list[CommandNode] = []
    nodes = root_command_nodes()
    for node_id in list(state.get("command_path", [])):
        node = next((candidate for candidate in nodes if candidate.id == node_id), None)
        if node is None:
            state["command_path"] = []
            state["pending_command"] = None
            return [], root_command_nodes()
        trail.append(node)
        nodes = list(node.children)
    return trail, nodes


def enter_command_node(node: CommandNode, path_prefix: list[str] | None = None) -> None:
    state["pending_command"] = None
    base_path = list(state.get("command_path", [])) if path_prefix is None else list(path_prefix)
    state["command_path"] = [*base_path, node.id]
    command_tree.refresh()


def select_command_node(node: CommandNode) -> None:
    previous = state.get("pending_command")
    if not isinstance(previous, CommandNode) or previous.id != node.id:
        state["checkbox_filters"] = {}
    state["pending_command"] = node
    command_tree.refresh()


async def activate_command_node(node: CommandNode, path_prefix: list[str] | None = None) -> None:
    if node.children:
        enter_command_node(node, path_prefix)
        return
    if node.fields:
        select_command_node(node)
        return
    state["pending_command"] = None
    await start_operation(node.to_operation(dict(node.parameters)))


def command_click_handler(node: CommandNode, path_prefix: list[str] | None = None):
    async def handler() -> None:
        await activate_command_node(node, path_prefix)

    return handler


def go_back_command() -> None:
    if state.get("pending_command") is not None:
        state["pending_command"] = None
    else:
        path = list(state.get("command_path", []))
        if path:
            path.pop()
        state["command_path"] = path
    command_tree.refresh()


def field_id(field: dict[str, Any]) -> str:
    return str(field.get("id") or field.get("name") or "").strip()


def field_label(field: dict[str, Any]) -> str:
    language = settings.language
    if language == "ru" and field.get("label_ru"):
        return str(field["label_ru"])
    return str(field.get("label") or field.get("title") or field_id(field))


def field_hint(field: dict[str, Any]) -> str:
    language = settings.language
    if language == "ru" and field.get("hint_ru"):
        return str(field["hint_ru"])
    return str(field.get("hint") or "")

def field_tooltip(field: dict[str, Any]) -> str:
    language = settings.language
    if language == "ru" and field.get("tooltip_ru"):
        return str(field["tooltip_ru"])
    return str(field.get("tooltip") or "")


def field_control_tooltip(field: dict[str, Any]) -> str:
    """What a field says when the pointer rests on it.

    The tooltip carries the explanation and may be as long as it needs to be;
    the caption beside the control stays short. The hint, then the label, are
    the fallbacks so a narrow control still tells the user what it is.
    """
    return field_tooltip(field) or field_hint(field) or field_label(field)


def attach_field_tooltip(control: Any, field: dict[str, Any]) -> Any:
    text = str(field_control_tooltip(field) or "").strip()
    if text:
        control.tooltip(text)
    return control




def field_default(field: dict[str, Any]) -> Any:
    if "default" in field:
        return field["default"]
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    options = field.get("options", [])
    if kind in {"checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}:
        if not isinstance(options, list):
            return []
        selected: list[Any] = []
        for option in options:
            if isinstance(option, dict) and option.get("default", False):
                selected.append(option.get("value", option.get("id", option.get("label"))))
        return selected
    if isinstance(options, list) and options:
        first = options[0]
        if isinstance(first, dict):
            return first.get("value", first.get("id", ""))
        return first
    return ""


def current_field_value(field: dict[str, Any]) -> Any:
    key = field_id(field)
    values = state.setdefault("field_values", {})
    if key not in values:
        values[key] = field_default(field)
    return values[key]


def current_option_values() -> dict[str, Any]:
    pending = state.get("pending_command")
    values: dict[str, Any] = {}
    if pending is not None:
        values.update(getattr(pending, "parameters", {}) or {})
    values.update(dict(state.setdefault("field_values", {})))
    values["gui_input_dir"] = str(current_source_path())
    values["gui_output_dir"] = str(current_target_path())
    return values


def set_field_value(key: str, value: Any) -> None:
    state.setdefault("field_values", {})[key] = value


def adjusted_number_value(field: dict[str, Any], current: Any, direction: int) -> int | float:
    step_raw = field.get("step", 1)
    try:
        step = float(step_raw)
    except (TypeError, ValueError):
        step = 1.0

    seed = current
    if seed is None or seed == "":
        seed = field_default(field) or 0
    try:
        value = float(seed)
    except (TypeError, ValueError):
        value = 0.0

    value += step * (1 if direction > 0 else -1)
    for bound_key, clamp in (("min", max), ("max", min)):
        bound = field.get(bound_key)
        if bound is None or bound == "":
            continue
        try:
            value = clamp(value, float(bound))
        except (TypeError, ValueError):
            continue

    kind = str(field.get("type", field.get("kind", "number"))).lower()
    integer_like = kind in {"number", "int", "integer"} and float(step).is_integer()
    return int(round(value)) if integer_like else round(value, 6)


def spin_number_field(key: str, field: dict[str, Any], control: Any, direction: int) -> None:
    value = adjusted_number_value(field, state.setdefault("field_values", {}).get(key), direction)
    set_field_value(key, value)
    control.set_value(value)


def dynamic_option_source(field: dict[str, Any]) -> str:
    return str(field.get("options_source") or field.get("source") or "").strip()


def refresh_dynamic_options(field: dict[str, Any]) -> None:
    source = dynamic_option_source(field)
    if source:
        dynamic_option_cache.pop(source, None)
    key = field_id(field)
    if key:
        state.setdefault("field_values", {}).pop(key, None)
    command_tree.refresh()


def refresh_options_click_handler(field: dict[str, Any]):
    def handler() -> None:
        refresh_dynamic_options(field)

    return handler


def apply_preset(preset: dict[str, Any]) -> None:
    values = preset.get("values", {})
    if not isinstance(values, dict):
        return
    field_values = state.setdefault("field_values", {})
    for key, value in values.items():
        field_values[str(key)] = value
    command_tree.refresh()


def preset_label(preset: dict[str, Any]) -> str:
    if settings.language == "ru" and preset.get("label_ru"):
        return str(preset["label_ru"])
    return str(preset.get("label") or preset.get("title") or preset.get("id") or "Preset")


def preset_click_handler(preset: dict[str, Any]):
    def handler() -> None:
        apply_preset(preset)

    return handler


def load_dynamic_options(field: dict[str, Any]) -> list[Any]:
    source = dynamic_option_source(field)
    if not source:
        return []

    cache_seconds = float(field.get("cache_seconds", 45) or 0)
    now = time.monotonic()
    cached = dynamic_option_cache.get(source)
    if cached and cache_seconds > 0 and now - cached[0] < cache_seconds:
        return cached[1]

    try:
        if ":" not in source:
            raise RuntimeError(f"Dynamic option source must use module:function syntax: {source}")
        module_name, function_name = source.split(":", 1)
        module = importlib.import_module(module_name)
        provider = getattr(module, function_name)
        try:
            options = provider(ROOT, current_option_values(), field)
        except TypeError:
            try:
                options = provider(ROOT, current_option_values())
            except TypeError:
                try:
                    options = provider(ROOT)
                except TypeError:
                    options = provider()
        if not isinstance(options, list):
            raise RuntimeError(f"Dynamic option source returned {type(options).__name__}, expected list.")
    except Exception as exc:
        message = f"Option source failed: {exc.__class__.__name__}: {exc}"
        options = [{"value": "", "label": message, "label_ru": message}]

    dynamic_option_cache[source] = (now, options)
    return options


def field_options(field: dict[str, Any]) -> list[Any]:
    dynamic_options = load_dynamic_options(field)
    if dynamic_options:
        return dynamic_options
    options = field.get("options", [])
    return options if isinstance(options, list) else []


def select_options(field: dict[str, Any]) -> dict[Any, str] | list[Any]:
    options = field_options(field)
    if all(isinstance(option, dict) for option in options):
        result: dict[Any, str] = {}
        for option in options:
            value = option.get("value", option.get("id", ""))
            if settings.language == "ru" and option.get("label_ru"):
                label = str(option["label_ru"])
            else:
                label = str(option.get("label") or option.get("title") or value)
            result[value] = label
        return result
    return options


def option_value(option: Any) -> Any:
    if isinstance(option, dict):
        return option.get("value", option.get("id", option.get("label", "")))
    return option


def option_label(option: Any) -> str:
    if not isinstance(option, dict):
        return str(option)
    language = settings.language
    if language == "ru" and option.get("label_ru"):
        return str(option["label_ru"])
    return str(option.get("label") or option.get("title") or option_value(option))


def checkbox_options(field: dict[str, Any]) -> list[tuple[Any, str]]:
    options = field_options(field)
    return [(option_value(option), option_label(option)) for option in options]


# An unselected browser wears its own colour on the outline; the selected one is
# filled with the standard Quasar blue whatever the browser is. The keys are the
# ids from `browser_registry`, so a new browser without a tone still gets a
# button - just a neutral one.
BROWSER_BUTTON_TONES = {
    "chrome": "chrome",
    "yandex": "yandex",
    "brave": "brave",
    "chromium_gost": "gost",
    "ungoogled_chromium": "ungoogled",
}


# `Авто`, `x64`, `ZIP` share one width; anything longer gets the wide row.
CHOICE_BUTTON_WIDE_CHARS = 6


def choice_button_classes(option_key: Any, selected: bool) -> str:
    """Classes of one switch button: its tone, and whether it is chosen."""
    classes = "audion-choice-button"
    tone = BROWSER_BUTTON_TONES.get(str(option_key).strip().lower(), "")
    if tone:
        classes += f" audion-browser-tone-{tone}"
    if selected:
        classes += " audion-choice-selected"
    return classes


def mark_choice_button(button: Any, selected: bool) -> None:
    if selected:
        button.classes(add="audion-choice-selected")
    else:
        button.classes(remove="audion-choice-selected")


def is_checkbox_group(field: dict[str, Any]) -> bool:
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    return kind in {"checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}


def checkbox_fields(node: CommandNode) -> list[dict[str, Any]]:
    return [field for field in node.fields if is_checkbox_group(field)]


WINDOW_CHECKBOX_FILTER_KEY = "__window__"


def checkbox_filter_value(key: str = WINDOW_CHECKBOX_FILTER_KEY) -> str:
    filters = state.setdefault("checkbox_filters", {})
    if not isinstance(filters, dict):
        filters = {}
        state["checkbox_filters"] = filters
    return str(filters.get(key, "") or "").strip()


def set_checkbox_filter_value(value: Any, key: str = WINDOW_CHECKBOX_FILTER_KEY) -> None:
    filters = state.setdefault("checkbox_filters", {})
    if not isinstance(filters, dict):
        filters = {}
        state["checkbox_filters"] = filters
    text = str(value or "").strip()
    if text:
        filters[key] = text
    else:
        filters.pop(key, None)
    command_tree.refresh()


def field_uses_local_checkbox_filter(field: dict[str, Any]) -> bool:
    key = field_id(field)
    source = str(field.get("options_source") or field.get("source") or "")
    return bool(
        field.get("local_filter")
        or field.get("extra_filter")
        or key in {"uninstall_other", "packages_installed_other"}
        or source.endswith(":installed_uninstall_other_options")
    )


def filter_checkbox_options(options: list[tuple[Any, str]], query: str) -> list[tuple[Any, str]]:
    needle = query.casefold()
    if not needle:
        return options
    return [
        (option_key, option_text)
        for option_key, option_text in options
        if not str(option_key).strip() or needle in f"{option_text} {option_key}".casefold()
    ]


def checkbox_filter_count(fields: list[dict[str, Any]], query: str) -> tuple[int, int]:
    total = 0
    visible = 0
    for field in fields:
        selectable = [(option_key, option_text) for option_key, option_text in checkbox_options(field) if str(option_key).strip()]
        total += len(selectable)
        visible += len(filter_checkbox_options(selectable, query)) if query else len(selectable)
    return visible, total


# A filter earns its place only when there is something to search through.
# Five browsers fit on screen whole, and a search box over them reads as a
# question about what is hidden - when nothing is.
CHECKBOX_FILTER_MIN_OPTIONS = 12


def render_checkbox_window_filter(fields: list[dict[str, Any]]) -> None:
    if not fields:
        return
    query = checkbox_filter_value()
    visible_count, total_count = checkbox_filter_count(fields, query)
    if total_count < CHECKBOX_FILTER_MIN_OPTIONS and not query:
        return
    with ui.row().classes("audion-checkbox-window-filter-row w-full items-center gap-2"):
        ui.input(
            label=tr("checkbox_filter"),
            value=query,
            placeholder=tr("checkbox_filter_placeholder"),
            on_change=lambda event: set_checkbox_filter_value(event.value),
        ).props("dense outlined clearable debounce=250").classes("audion-checkbox-filter audion-checkbox-window-filter")
        ui.label(
            tr("checkbox_filter_count", visible=visible_count, total=total_count)
        ).classes("audion-checkbox-filter-count")


def field_container_classes(field: dict[str, Any]) -> str:
    span = str(field.get("span") or field.get("width") or "").lower()
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    if kind in {"radio", "radiobuttons", "radio-buttons"}:
        return "audion-field audion-field-wide audion-field-radio"
    # A checkbox is one card in the section grid. Given the whole row it turns
    # into a banner, which is what a stretched chip looked like.
    if kind in {"checkbox", "bool", "boolean", "toggle"}:
        return "audion-field audion-field-checkbox"
    if kind in {"checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}:
        return "audion-field audion-field-wide audion-field-checkboxes"
    if span in {"full", "wide", "100%", "1/-1"}:
        return "audion-field audion-field-wide"
    if kind in {"select", "choice", "format"}:
        return "audion-field audion-field-select"
    if kind in {"textarea", "multiline", "path", "file", "folder"}:
        return "audion-field audion-field-wide"
    if kind in {"preset_buttons", "presets", "profile_buttons", "profiles"}:
        return "audion-field audion-field-wide"
    return "audion-field"


def normalize_selected_list(value: Any) -> list[Any]:
    """A multi-select value as a list, whatever shape it arrived in.

    A checkbox group is stored as a list, but a single saved choice can come back
    as a bare string and an empty one as None. Callers want a list either way.
    """
    if isinstance(value, list):
        return [item for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [item for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def render_field(field: dict[str, Any]) -> None:
    key = field_id(field)
    if not key:
        return
    if key in {"gui_input_dir", "gui_output_dir"}:
        set_field_value("gui_input_dir", str(current_source_path()))
        set_field_value("gui_output_dir", str(current_target_path()))
        return
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    label = field_label(field)
    value = current_field_value(field)
    hint = field_hint(field)

    field_container = ui.element("div").classes(field_container_classes(field))

    attach_field_tooltip(field_container, field)

    with field_container:
        if kind in {"preset_buttons", "presets", "profile_buttons", "profiles"}:
            presets = field.get("presets", field.get("options", []))
            if not isinstance(presets, list):
                presets = []
            with ui.row().classes("audion-profile-row w-full items-center gap-2"):
                ui.label(label).classes("audion-field-label audion-profile-label mb-0")
                for preset in presets:
                    if not isinstance(preset, dict):
                        continue
                    ui.button(
                        preset_label(preset),
                        on_click=preset_click_handler(preset),
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
            return

        if kind in {"select", "choice", "format"}:
            select = ui.select(
                options=select_options(field),
                label=label,
                value=value,
                on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
            )
            props = "dense outlined popup-content-class=audion-select-popup"
            if bool(field.get("searchable", field.get("with_input", False))):
                props += " use-input input-debounce=0"
            select.props(props).classes("audion-select w-full")
            if dynamic_option_source(field):
                ui.button(
                    tr("refresh_options"),
                    on_click=refresh_options_click_handler(field),
                ).props("dense flat no-wrap").classes("audion-action mt-1 rounded-lg")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"radio", "radiobuttons", "radio-buttons"}:
            ui.label(label).classes("audion-field-label")
            options = select_options(field)
            option_pairs = (
                list(options.items())
                if isinstance(options, dict)
                else [(item, str(item)) for item in options]
            )
            choice_buttons: dict[Any, Any] = {}

            def choose_option(chosen: Any, item_key: str = key) -> None:
                set_field_value(item_key, chosen)
                for option_key, button in choice_buttons.items():
                    mark_choice_button(button, option_key == chosen)

            # Short values line up at one width; names like `Прокси библиотека`
            # do not fit that width, so their row is laid out like the browsers:
            # each button by its own caption, the row filling the block.
            longest = max((len(str(text)) for _key, text in option_pairs), default=0)
            row_classes = "audion-choice-buttons"
            if longest > CHOICE_BUTTON_WIDE_CHARS:
                row_classes += " audion-choice-buttons-wide"
            with ui.row().classes(row_classes):
                for option_key, option_text in option_pairs:
                    choice_buttons[option_key] = ui.button(
                        option_text,
                        color=None,
                        on_click=lambda _event=None, chosen=option_key: choose_option(chosen),
                    ).props("dense unelevated no-wrap").classes(
                        choice_button_classes(option_key, option_key == value)
                    )
            if dynamic_option_source(field):
                ui.button(
                    tr("refresh_options"),
                    on_click=refresh_options_click_handler(field),
                ).props("dense flat no-wrap").classes("audion-action mt-1 rounded-lg")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"number", "int", "integer", "float"}:
            number_input = ui.number(
                label=label,
                value=value if value != "" else None,
                min=field.get("min"),
                max=field.get("max"),
                step=field.get("step", 1),
                on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
            ).props("dense outlined").classes("audion-number w-full")
            with number_input.add_slot("append"):
                with ui.element("div").classes("audion-number-spinner"):
                    ui.button(
                        icon="keyboard_arrow_up",
                        on_click=lambda item_key=key, item_field=field, control=number_input: spin_number_field(item_key, item_field, control, 1),
                    ).props("dense flat round tabindex=-1").classes("audion-number-spin-button")
                    ui.button(
                        icon="keyboard_arrow_down",
                        on_click=lambda item_key=key, item_field=field, control=number_input: spin_number_field(item_key, item_field, control, -1),
                    ).props("dense flat round tabindex=-1").classes("audion-number-spin-button")
            if hint:
                ui.label(hint).classes("audion-field-hint")
            return

        if kind in {"checkbox", "bool", "boolean", "toggle"}:
            # One card, one switch: the hint stays in the tooltip of the field,
            # so every card in a row of the grid keeps the same height.
            with ui.element("div").classes("audion-checkbox-card"):
                ui.checkbox(
                    label,
                    value=bool(value),
                    on_change=lambda event, item_key=key: set_field_value(item_key, bool(event.value)),
                ).props("dense").classes("audion-single-checkbox")
            return

        if is_checkbox_group(field):
            selected = set(normalize_selected_list(value))
            controls: dict[Any, Any] = {}
            window_filter_query = checkbox_filter_value()
            local_filter_query = checkbox_filter_value(key) if field_uses_local_checkbox_filter(field) else ""
            options = checkbox_options(field)
            visible_options = filter_checkbox_options(
                filter_checkbox_options(options, window_filter_query),
                local_filter_query,
            )
            visible_option_keys = {
                option_key for option_key, _option_text in visible_options if str(option_key).strip()
            }
            has_active_filter = bool(window_filter_query or local_filter_query)

            def sync_checkboxes(item_key: str = key) -> None:
                current = current_field_value(field)
                preserved = [
                    item
                    for item in normalize_selected_list(current)
                    if has_active_filter and item not in visible_option_keys
                ]
                seen_preserved = set(preserved)
                set_field_value(
                    item_key,
                    [
                        *preserved,
                        *[
                            option_key
                            for option_key, _option_text in visible_options
                            if option_key in selected and option_key not in seen_preserved
                        ],
                    ],
                )

            def toggle_option(option_key: Any, item_key: str = key) -> None:
                if option_key in selected:
                    selected.discard(option_key)
                else:
                    selected.add(option_key)
                mark_choice_button(controls[option_key], option_key in selected)
                sync_checkboxes(item_key)

            def set_group_selection(checked: bool, item_key: str = key) -> None:
                for option_key, button in controls.items():
                    if checked:
                        selected.add(option_key)
                    else:
                        selected.discard(option_key)
                    mark_choice_button(button, checked)
                sync_checkboxes(item_key)

            with ui.element("div").classes("audion-choice-header"):
                ui.label(label).classes("audion-field-label")
                if visible_option_keys:
                    ui.button(
                        tr("select_group_all"),
                        on_click=lambda: set_group_selection(True),
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
                    ui.button(
                        tr("clear_group"),
                        on_click=lambda: set_group_selection(False),
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
                if dynamic_option_source(field):
                    ui.button(
                        tr("refresh_options"),
                        on_click=refresh_options_click_handler(field),
                    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
            if field_uses_local_checkbox_filter(field):
                ui.input(
                    label=tr("checkbox_filter"),
                    value=local_filter_query,
                    placeholder=tr("checkbox_filter_placeholder"),
                    on_change=lambda event, item_key=key: set_checkbox_filter_value(event.value, item_key),
                ).props("dense outlined clearable debounce=250").classes("audion-checkbox-filter mb-1")
            # Product names are long, so this group gets the wider column.
            with ui.row().classes("audion-choice-buttons audion-choice-buttons-wide"):
                if has_active_filter and not visible_option_keys:
                    ui.label(tr("checkbox_filter_no_matches")).classes("audion-empty-options")
                for option_key, option_text in visible_options:
                    if not str(option_key).strip():
                        ui.label(option_text).classes("audion-empty-options")
                        continue
                    button = ui.button(
                        option_text,
                        color=None,
                        on_click=lambda _event=None, chosen=option_key: toggle_option(chosen),
                    ).props("dense unelevated no-wrap").classes(
                        choice_button_classes(option_key, option_key in selected)
                    )
                    button.tooltip(str(option_text))
                    controls[option_key] = button
            if hint:
                ui.label(hint).classes("audion-field-hint")
            sync_checkboxes()
            return

        ui.input(
            label=label,
            value=str(value) if value is not None else "",
            placeholder=str(field.get("placeholder", "")),
            on_change=lambda event, item_key=key: set_field_value(item_key, event.value),
        ).props("dense outlined").classes("w-full")
        if hint:
            ui.label(hint).classes("audion-field-hint")


def operation_from_pending_command(node: CommandNode) -> Operation:
    parameters = dict(node.parameters)
    values = state.setdefault("field_values", {})
    for field in node.fields:
        key = field_id(field)
        if key:
            parameters[key] = values.get(key, field_default(field))
    parameters["gui_input_dir"] = str(current_source_path())
    parameters["gui_output_dir"] = str(current_target_path())
    return node.to_operation(parameters)


def validate_pending_fields(node: CommandNode) -> bool:
    values = state.setdefault("field_values", {})
    for field in node.fields:
        if not is_checkbox_group(field):
            continue
        min_selected = int(field.get("min_selected", 0) or 0)
        if min_selected <= 0:
            continue
        key = field_id(field)
        selected = values.get(key, field_default(field))
        if not isinstance(selected, list) or len(selected) < min_selected:
            safe_notify(tr("select_required", field=field_label(field)), "warning")
            return False
    return True


async def run_pending_command(node: CommandNode) -> None:
    if validate_pending_fields(node):
        await start_operation(operation_from_pending_command(node))


def run_pending_click_handler(node: CommandNode):
    async def handler() -> None:
        await run_pending_command(node)

    return handler


def field_signature(fields: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(field_id(field) for field in fields if field_id(field))


def can_inline_child_actions(parent: CommandNode | None, children: list[CommandNode]) -> bool:
    if parent is None or not parent.fields or not children:
        return False
    parent_signature = field_signature(parent.fields)
    if not parent_signature:
        return False
    return all(not child.children and field_signature(child.fields) == parent_signature for child in children)


def render_inline_child_action(node: CommandNode) -> None:
    description = node.display_tooltip(settings.language) or node.display_description(settings.language)
    button = ui.button(
        node.display_title(settings.language),
        on_click=run_pending_click_handler(node),
    ).props("dense flat no-wrap").classes("audion-action rounded-lg")
    attach_tooltip(button, description)


ADVANCED_FIELD_SUFFIXES = (
    "_model_override",
    "_chunk_tokens",
    "_overlap_tokens",
    "_min_chunks",
    "_max_retries",
    "_max_output_tokens",
    "_timeout_sec",
    "_resume",
)


def is_advanced_field(field: dict[str, Any]) -> bool:
    if bool(field.get("advanced", False)):
        return True
    priority = str(field.get("priority") or field.get("section") or "").strip().lower()
    if priority in {"advanced", "expert", "rare"}:
        return True
    key = field_id(field)
    return any(key.endswith(suffix) for suffix in ADVANCED_FIELD_SUFFIXES)


def split_primary_advanced_fields(fields: tuple[dict[str, Any], ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary: list[dict[str, Any]] = []
    advanced: list[dict[str, Any]] = []
    for field in fields:
        if is_advanced_field(field):
            advanced.append(field)
        else:
            primary.append(field)
    return primary, advanced


def field_section_id(field: dict[str, Any]) -> str:
    key = field_id(field)
    kind = str(field.get("type", field.get("kind", "text"))).lower()
    section = str(field.get("section") or "").strip().lower()
    explicit = str(field.get("group") or field.get("ui_group") or field.get("section_group") or "").strip().lower()
    if not explicit and section and section not in {"advanced", "expert", "rare"}:
        explicit = section
    if explicit:
        return explicit
    if kind in {"profile_select", "profile-select", "preset_select", "preset-select", "preset_buttons", "presets", "profile_buttons", "profiles"}:
        return "preset"
    if key in {"overwrite", "dry_run", "limit_first_file", "test_first_file"} or key.endswith(("_dry_run", "_overwrite")):
        return "run"
    if any(part in key for part in ("source", "input", "url", "file", "folder", "path")):
        return "source"
    if any(part in key for part in ("format", "container", "profile", "preset", "quality", "dpi", "bitrate", "resolution")):
        return "format"
    if any(part in key for part in ("output", "report", "export", "package", "release")):
        return "output"
    if any(part in key for part in ("codec", "encode", "model", "engine")):
        return "encoding"
    if kind in {"checkbox", "bool", "boolean", "toggle", "checkboxes", "multi_checkbox", "multicheckbox", "multi-select", "multiselect"}:
        return "options"
    return "parameters"


def field_section_label(section_id: str) -> str:
    key = f"section_{section_id}"
    label = tr(key)
    if label != key:
        return label
    return section_id.replace("_", " ").title()


def group_fields_by_section(fields: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    group_index: dict[str, int] = {}
    for field in fields:
        section_id = field_section_id(field)
        if section_id not in group_index:
            group_index[section_id] = len(groups)
            groups.append((section_id, [field]))
        else:
            groups[group_index[section_id]][1].append(field)
    return groups


def render_field_grid(fields: list[dict[str, Any]]) -> None:
    if not fields:
        return
    with ui.element("div").classes("audion-fields-grid"):
        for section_id, section_fields in group_fields_by_section(fields):
            with ui.element("section").classes(f"audion-field-section audion-field-section-{section_id}"):
                ui.label(field_section_label(section_id)).classes("audion-section-title")
                with ui.element("div").classes("audion-section-fields"):
                    for field in section_fields:
                        render_field(field)


def render_advanced_fields(fields: list[dict[str, Any]]) -> None:
    if not fields:
        return
    with ui.expansion(
        tr("advanced"),
        value=bool(getattr(settings, "advanced_open", False)),
        on_value_change=save_advanced_open,
    ).classes("audion-advanced-expansion w-full") as expansion:
        expansion.props("dense switch-toggle-side")
        render_field_grid(fields)


def command_node_button(node: CommandNode, path_prefix: list[str] | None = None) -> None:
    has_children = bool(node.children)
    label = node.display_title(settings.language)
    description = node.display_description(settings.language)
    tooltip = node.display_tooltip(settings.language) or description
    if has_children and not description:
        description = tr("open_menu")
        tooltip = tooltip or description

    with ui.element("div").classes("audion-operation-row"):
        button = ui.button(
            label,
            on_click=command_click_handler(node, path_prefix),
        ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        attach_tooltip(button, tooltip)
        ui.label(description).classes("audion-operation-description")


def render_root_command_section(
    title: str,
    description: str,
    nodes: list[CommandNode],
    path_prefix: list[str] | None = None,
    tooltip: str = "",
) -> None:
    with ui.column().classes("audion-root-section audion-panel w-full gap-1 p-3"):
        title_label = ui.label(title).classes("audion-root-section-title")
        attach_tooltip(title_label, tooltip or description)
        if description:
            description_label = ui.label(description).classes("audion-root-section-description")
            attach_tooltip(description_label, tooltip)
        for node in nodes:
            command_node_button(node, path_prefix)


def select_root_tab(tab_id: str) -> None:
    state["root_tab"] = tab_id
    command_tree.refresh()


def render_root_tab_command(node: CommandNode, path_prefix: list[str]) -> None:
    """One command on a tab: a row when it is plain, a panel when it has fields.

    A command with fields is laid out where it stands - its own parameters and
    its own run button, named after the action. Walking into a child window to
    press an identical `Run` is what this switcher exists to remove.
    """
    if node.children or not node.fields:
        command_node_button(node, path_prefix)
        return

    description = node.display_description(settings.language)
    tooltip = node.display_tooltip(settings.language) or description
    with ui.column().classes("audion-inline-command audion-panel w-full gap-1 p-3"):
        # The run button stands at the right edge of its panel and says what it
        # does by its own name; the explanation is in the tooltip, so the line
        # carries no second caption to read past.
        with ui.row().classes("audion-inline-command-head w-full items-center gap-2"):
            ui.space()
            run_button = ui.button(
                node.display_title(settings.language),
                on_click=run_pending_click_handler(node),
            ).props("dense flat no-wrap").classes(
                "audion-action audion-run-action audion-inline-command-run rounded-lg"
            )
            attach_tooltip(run_button, tooltip)

        primary_fields, advanced_fields = split_primary_advanced_fields(node.fields)
        render_checkbox_window_filter(checkbox_fields(node))
        render_field_grid(primary_fields)
        render_advanced_fields(advanced_fields)


def render_root_switcher(nodes: list[CommandNode]) -> None:
    """Root is one window: tabs across the top, that tab's commands below.

    Every top-level group is a tab, so what the switcher offers is decided by
    the manifest rather than by code. Loose commands - ones with no group of
    their own - join the last tab instead of forming a nameless section.
    """
    tabs = [node for node in nodes if node.children]
    loose = [node for node in nodes if not node.children]
    if not tabs:
        for node in nodes:
            command_node_button(node)
        return

    active = next((node for node in tabs if node.id == state.get("root_tab")), tabs[0])
    with ui.element("div").classes("audion-ai-tabs w-full"):
        for node in tabs:
            classes = "audion-action audion-ai-tab"
            if node.id == active.id:
                classes += " audion-ai-tab-active"
            tab_button = ui.button(
                node.display_title(settings.language),
                on_click=lambda _event=None, tab_id=node.id: select_root_tab(tab_id),
            ).props("dense flat no-wrap").classes(classes)
            attach_tooltip(
                tab_button,
                node.display_tooltip(settings.language) or node.display_description(settings.language),
            )

    with ui.element("div").classes("audion-ai-pane"):
        commands = list(active.children)
        if loose and active.id == tabs[-1].id:
            commands.extend(loose)
        for child in commands:
            render_root_tab_command(child, [active.id])


def render_root_command_sections(nodes: list[CommandNode]) -> None:
    loose_nodes: list[CommandNode] = []
    with ui.column().classes("w-full gap-3"):
        for node in nodes:
            if not node.children or node.fields:
                loose_nodes.append(node)
                continue
            render_root_command_section(
                node.display_title(settings.language),
                node.display_description(settings.language),
                list(node.children),
                [node.id],
                node.display_tooltip(settings.language),
            )
        if loose_nodes:
            render_root_command_section(tr("root_other_operations"), "", loose_nodes)


def command_nav_row(
    trail: list[CommandNode],
    pending: CommandNode | None,
    inline_actions: list[CommandNode] | None = None,
) -> None:
    can_go_back = pending is not None or bool(trail)
    if pending is not None:
        title = pending.display_title(settings.language)
    elif trail:
        title = " / ".join(node.display_title(settings.language) for node in trail)
    else:
        title = ""

    with ui.row().classes("audion-command-nav w-full items-center gap-2"):
        if can_go_back:
            ui.button(
                tr("back"),
                on_click=go_back_command,
            ).props("dense flat no-wrap").classes("audion-action w-28 rounded-lg")
        ui.label(title).classes("audion-command-title min-w-0 flex-1 truncate text-sm text-gray-400")
        if pending is not None:
            run_button = ui.button(
                tr("run"),
                on_click=run_pending_click_handler(pending),
            ).props("dense flat no-wrap").classes("audion-action audion-nav-run-button rounded-lg")
            attach_tooltip(run_button, pending.display_tooltip(settings.language) or pending.display_description(settings.language))
        elif inline_actions:
            with ui.row().classes("audion-command-nav-actions items-center gap-2"):
                for node in inline_actions:
                    inline_button = ui.button(
                        node.display_title(settings.language),
                        on_click=run_pending_click_handler(node),
                    ).props("dense flat no-wrap").classes("audion-action audion-nav-run-button rounded-lg")
                    attach_tooltip(inline_button, node.display_tooltip(settings.language) or node.display_description(settings.language))


@ui.refreshable
def command_tree() -> None:
    trail, nodes = current_command_level()
    pending = state.get("pending_command")
    parent = trail[-1] if trail else None
    inline_actions = nodes if pending is None and can_inline_child_actions(parent, nodes) else []

    if pending is None and not trail and not inline_actions:
        if any(node.children for node in nodes):
            render_root_switcher(nodes)
            return
        for node in nodes:
            command_node_button(node)
        return

    command_nav_row(trail, pending, inline_actions)

    if pending is not None:
        if pending.fields:
            primary_fields, advanced_fields = split_primary_advanced_fields(pending.fields)
            ui.label(tr("parameters")).classes("text-sm font-semibold text-gray-300")
            render_checkbox_window_filter(checkbox_fields(pending))
            render_field_grid(primary_fields)
        if pending.fields:
            render_advanced_fields(advanced_fields)
        return

    if inline_actions:
        primary_fields, advanced_fields = split_primary_advanced_fields(parent.fields)
        ui.label(tr("parameters")).classes("text-sm font-semibold text-gray-300")
        render_checkbox_window_filter(checkbox_fields(parent))
        render_field_grid(primary_fields)
        render_advanced_fields(advanced_fields)
        return

    for node in nodes:
        command_node_button(node)


@ui.refreshable
def terminal_command_bar() -> None:
    shell_options = {"pwsh": "PowerShell", "cmd": "CMD"} if os.name == "nt" else {"sh": "Shell"}
    with ui.column().classes("audion-terminal-command w-full gap-1"):
        with ui.row().classes("w-full items-center gap-2"):
            shell_select = ui.select(
                options=shell_options,
                label=tr("terminal_shell"),
                value=str(state.get("terminal_shell") or next(iter(shell_options))),
                on_change=lambda event: set_terminal_shell(event.value),
            )
            shell_select.props("dense outlined popup-content-class=audion-select-popup").classes("audion-terminal-shell")

            history_select = ui.select(
                options=terminal_command_options(),
                label=tr("terminal_history"),
                value=terminal_history_value(),
                on_change=lambda event: select_terminal_history(event),
            )
            history_select.props("dense outlined popup-content-class=audion-select-popup").classes("audion-terminal-history min-w-0 flex-1")

            pin_button = ui.button(
                icon="push_pin",
                on_click=pin_terminal_command,
            ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-pin")
            pin_button.tooltip(tr("pin_command"))
            unpin_button = ui.button(
                icon="block",
                on_click=unpin_terminal_command,
            ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-unpin")
            unpin_button.tooltip(tr("unpin_command"))
            clear_button = ui.button(
                icon="delete",
                on_click=clear_terminal_history,
            ).props("dense flat round").classes("audion-action audion-terminal-icon-button audion-terminal-clear")
            clear_button.tooltip(tr("clear_terminal_history"))
            ui.button(
                tr("terminal_run"),
                on_click=start_terminal_command,
            ).props("dense flat no-wrap").classes("audion-action audion-terminal-run rounded-lg")

        command_area = ui.textarea(
            label=tr("terminal_command"),
            value=str(state.get("terminal_command") or ""),
            on_change=lambda event: set_terminal_command(event.value),
        )
        command_area.props("dense outlined autogrow rows=3").classes("audion-terminal-command-text w-full")
        command_area.on("keydown.ctrl.enter", terminal_enter_handler)

        with ui.row().classes("w-full items-center gap-2"):
            ui.input(
                label=tr("terminal_cwd"),
                value=str(state.get("terminal_cwd") or ROOT),
                on_change=lambda event: set_terminal_cwd(event.value),
            ).props("dense outlined").classes("audion-terminal-cwd min-w-0 flex-1")
            ui.button(
                tr("terminal_folder"),
                on_click=terminal_location_click_handler("folder"),
            ).props("dense flat no-wrap").classes("audion-action audion-terminal-picker rounded-lg")
            ui.button(
                tr("terminal_file"),
                on_click=terminal_location_click_handler("file"),
            ).props("dense flat no-wrap").classes("audion-action audion-terminal-picker rounded-lg")


def operation_by_id(operation_id: str) -> Operation | None:
    for operation in [*manifest.operations, *manifest.maintenance_operations]:
        if operation.id == operation_id:
            return operation
    return None


_application_css_cache: dict[str, str] = {}


def application_css(name: str) -> str:
    """A stylesheet that lives next to this module rather than inside it."""
    if name not in _application_css_cache:
        path = Path(__file__).resolve().with_name(name)
        _application_css_cache[name] = path.read_text(encoding="utf-8")
    return _application_css_cache[name]


def add_styles() -> None:
    variables_css = "\n".join(
        f"            --{key}: {value};"
        for key, value in sorted(theme_variables().items())
    )
    ui.add_head_html(
        "<style>\n"
        ":root {\n"
        f"{variables_css}\n"
        "}\n"
        + application_css("tokens.css")
        + application_css("theme.css")
        + "\n</style>\n"
    )
    ui.add_head_html(f"<style>{WORKBENCH_LAYOUT_CSS}{WORKBENCH_OVERRIDE_CSS}</style>")
    ui.add_head_html(WORKBENCH_FEEDBACK_CSS)


def build_ui() -> None:
    ensure_project_dirs(paths)
    state.setdefault("field_values", {})["gui_input_dir"] = str(current_source_path())
    state.setdefault("field_values", {})["gui_output_dir"] = str(current_target_path())
    if not state["status"]:
        state["status"] = tr("idle")
    if active_theme_mode() == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()
    add_styles()

    with ui.header().classes("audion-header h-[42px] items-center justify-between px-4"):
        ui.label(app_title()).classes("audion-header-title text-lg font-bold")
        with ui.row().classes("audion-header-controls items-center gap-2"):
            ui.icon("palette").classes("text-lg")
            ui.select(
                options=theme_options(),
                value=active_theme(),
                on_change=theme_change_handler,
            ).props("dense outlined options-dense").classes("audion-theme-select")
            ui.button(tr("lang_switch"), on_click=toggle_language).props("dense flat").classes("audion-action rounded-lg")
            cancel_button = ui.button(tr("cancel"), on_click=lambda: state.update({"cancel": True})).props("dense flat color=negative")
            cancel_button.visible = False

    with ui.element("div").classes("audion-shell"):
        with ui.column().classes("audion-pane audion-scroll gap-3"):
            with ui.column().classes("audion-panel audion-workspace-panel w-full gap-2 p-2"):
                WORKBENCH_RENDERER.render_address_rows()
                WORKBENCH_RENDERER.render_action_bar()

            # Service actions sit above the switcher, not under the tabs: they
            # belong to the program rather than to any one tab, and at the
            # bottom of a long pane they fell below the fold entirely.
            if manifest.maintenance_operations:
                with ui.row().classes("audion-service-strip w-full items-center gap-2"):
                    ui.label(tr("maintenance")).classes("audion-subsection-label")
                    for operation in manifest.maintenance_operations:
                        if operation.id == "cleanup_input_output":
                            continue
                        service_button = ui.button(
                            operation.display_title(settings.language),
                            on_click=operation_click_handler(operation),
                        ).props("dense flat no-wrap").classes("audion-action audion-service-action rounded-lg")
                        attach_tooltip(
                            service_button,
                            operation.display_tooltip(settings.language) or operation.display_description(settings.language),
                        )

            command_tree()

        ui.element("div").classes("audion-splitter").props('title="Resize panels"')

        with ui.element("div").classes("audion-pane audion-right gap-2 pt-3"):
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                        with ui.element("div").classes(status_row_classes()) as status_row:
                            status_dot_main = ui.element("span").classes("audion-status-dot-mark")
                            status_state_label = ui.label(status_state_text()).classes("audion-status-state")
                            status_label = ui.label(str(state["status"])).classes("audion-status-message")
                            status_clock = ui.label(elapsed_text(None)).classes("audion-status-clock")
                            with ui.element("div").classes("audion-status-bar"):
                                status_bar_fill = ui.element("i").style("width: 0%")
                            status_percent = ui.label(progress_text()).classes("audion-status-percent")

            with ui.column().classes("audion-terminal-panel w-full gap-2 p-3"):
                with ui.row().classes("audion-log-toolbar w-full items-center gap-2"):
                    ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                    ui.space()
                    ui.button(tr("logs"), on_click=lambda: open_folder(paths.logs)).props("dense flat").classes("audion-action rounded-lg")
                    ui.button(tr("report"), on_click=lambda: open_folder(paths.report)).props("dense flat").classes("audion-action rounded-lg")
                    ui.button(tr("config"), on_click=lambda: open_folder(paths.config)).props("dense flat").classes("audion-action rounded-lg")
                    clear_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_window).props("dense flat round").classes("audion-action audion-log-icon-button")
                    clear_log_button.tooltip(tr("clear_terminal_window"))
                    expand_log_button = ui.button(icon="open_in_full", on_click=lambda: log_dialog.open()).props("dense flat round").classes("audion-action audion-log-icon-button")
                    expand_log_button.tooltip(tr("expand"))
                log_view = ui.html("", sanitize=False).classes("audion-terminal w-full min-h-[66vh]")
                terminal_command_bar()
                with ui.row().classes("audion-terminal-footer w-full items-center gap-2 px-1 pt-1"):
                    status_dot = ui.label("●").classes(status_dot_classes())
                    terminal_status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 truncate text-xs")

    with ui.dialog() as log_dialog:
        with ui.card().classes("audion-dialog h-[92vh] w-[92vw] rounded-lg p-3"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                ui.space()
                ui.button(tr("config"), on_click=lambda: open_folder(paths.config)).props("dense flat").classes("audion-action rounded-lg")
                clear_dialog_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_window).props("dense flat round").classes("audion-action audion-log-icon-button")
                clear_dialog_log_button.tooltip(tr("clear_terminal_window"))
                ui.button(tr("close"), on_click=log_dialog.close).props("dense flat").classes("audion-action rounded-lg")
            expanded_log_view = ui.html("", sanitize=False).classes("audion-terminal audion-terminal-expanded w-full")

    ui.run_javascript(
        """
        (() => {
          const storageKey = 'audion_gui_terminal_width_px';
          const defaultWidth = 666;
          const minLeft = 460;
          const minRight = 460;

          const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

          const applyWidth = (width) => {
            const shell = document.querySelector('.audion-shell');
            if (!shell) return;
            const rect = shell.getBoundingClientRect();
            const maxRight = Math.max(minRight, rect.width - minLeft - 40);
            const next = clamp(Number(width) || defaultWidth, minRight, maxRight);
            shell.style.setProperty('--audion-terminal-width', `${Math.round(next)}px`);
            localStorage.setItem(storageKey, String(Math.round(next)));
          };

          const setup = () => {
            const shell = document.querySelector('.audion-shell');
            const splitter = document.querySelector('.audion-splitter');
            if (!shell || !splitter) {
              setTimeout(setup, 80);
              return;
            }
            if (splitter.dataset.audionReady === '1') return;
            splitter.dataset.audionReady = '1';

            applyWidth(localStorage.getItem(storageKey) || defaultWidth);

            let dragging = false;
            const updateFromEvent = (event) => {
              if (!dragging) return;
              const rect = shell.getBoundingClientRect();
              const rightWidth = rect.right - event.clientX - 10;
              applyWidth(rightWidth);
            };

            splitter.addEventListener('pointerdown', (event) => {
              dragging = true;
              splitter.setPointerCapture?.(event.pointerId);
              document.body.classList.add('audion-resizing');
              event.preventDefault();
            });
            splitter.addEventListener('pointermove', updateFromEvent);
            splitter.addEventListener('pointerup', (event) => {
              dragging = false;
              splitter.releasePointerCapture?.(event.pointerId);
              document.body.classList.remove('audion-resizing');
            });
            splitter.addEventListener('pointercancel', () => {
              dragging = false;
              document.body.classList.remove('audion-resizing');
            });
            window.addEventListener('resize', () => applyWidth(localStorage.getItem(storageKey) || defaultWidth));
          };

          setup();
        })();
        """
    )

    last_log_version = {"value": -1}
    refresh_timer: Any | None = None

    # Every one of these used to be written twice a second whether or not it had
    # changed, so an idle window still sent ten element updates a second. Holding
    # the last value makes an idle panel cost nothing and pays for the clock.
    shown = {"status": None, "state": None, "row": None, "clock": None, "percent": None, "fill": None}
    run_clock: dict[str, float | None] = {"started": None, "frozen": None}

    def refresh() -> None:
        nonlocal refresh_timer
        try:
            running = bool(state["running"])
            if running and run_clock["started"] is None:
                run_clock["started"] = time.monotonic()
                run_clock["frozen"] = None
            elif not running and run_clock["started"] is not None:
                run_clock["frozen"] = time.monotonic() - run_clock["started"]
                run_clock["started"] = None
            seconds = (
                time.monotonic() - run_clock["started"]
                if run_clock["started"] is not None
                else run_clock["frozen"]
            )

            def show(key: str, value: Any, assign: Any) -> None:
                if shown[key] != value:
                    shown[key] = value
                    assign(value)

            message = str(state["status"])
            show("status", message, lambda value: (
                setattr(status_label, "text", value),
                setattr(terminal_status_label, "text", value),
            ))
            show("state", status_state_text(), lambda value: setattr(status_state_label, "text", value))
            show("row", status_row_classes(), lambda value: (
                status_row.classes(replace=value),
                status_dot.classes(replace=status_dot_classes()),
            ))
            show("clock", elapsed_text(seconds), lambda value: setattr(status_clock, "text", value))
            show("percent", progress_text(), lambda value: setattr(status_percent, "text", value))
            show("fill", f"{float(state['progress']) * 100:.1f}%",
                lambda value: status_bar_fill.style(f"width: {value}"))
            log_version = int(state["log_version"])
            if log_version != last_log_version["value"]:
                last_log_version["value"] = log_version
                log_content = terminal_html()
                log_view.content = log_content
                expanded_log_view.content = log_content
                ui.run_javascript(
                    """
                    requestAnimationFrame(() => {
                      document.querySelectorAll('.audion-terminal').forEach((el) => {
                        el.scrollTop = el.scrollHeight;
                      });
                    });
                    """
                )
            cancel_button.visible = bool(state["running"])
        except RuntimeError as exc:
            if "slot belongs to has been deleted" not in str(exc):
                raise
            logging.warning("NiceGUI refresh timer stopped because the client slot was deleted.")
            if refresh_timer is not None:
                refresh_timer.deactivate()

    refresh_timer = ui.timer(0.5, refresh)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion NiceGUI shell.")
    parser.add_argument("--host", default=str(ui_info.get("host", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(ui_info.get("port", 8080)))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def port_is_open(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def assert_gui_host_allowed(host: str) -> None:
    normalized = str(host or "").strip().lower().strip("[]")
    try:
        is_loopback = normalized == "localhost" or ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        is_loopback = normalized == "localhost"
    if is_loopback or env_flag_enabled("AUDION_ALLOW_REMOTE_GUI"):
        return
    raise SystemExit(
        "Refusing non-loopback host for a GUI with process execution. "
        "Use 127.0.0.1/localhost/::1, or set AUDION_ALLOW_REMOTE_GUI=1 explicitly."
    )


def build_ui_once() -> dict[str, int]:
    """Build the whole page once, headlessly, and report what came of it.

    `--smoke` used to print a line and return, so an app could ship a `build_ui`
    that raised on its first statement and still pass — twice in this fleet it did.
    Here the page is actually built: no browser and no HTTP request, so whatever
    the app defers until a client attaches is skipped, but every widget is
    constructed and the stylesheet has to arrive.
    """
    import asyncio
    import logging
    import re

    from nicegui import core
    from nicegui.client import Client
    from nicegui.page import page as page_definition

    async def build() -> tuple[int, str]:
        core.loop = asyncio.get_running_loop()
        # Work deferred to a connected browser fails here and says nothing about
        # the build. An exception raised by build_ui itself still propagates.
        core.loop.set_exception_handler(lambda _loop, _context: None)
        logging.getLogger("nicegui").setLevel(logging.CRITICAL)
        client = Client(page_definition("/__smoke__"))
        with client:
            build_ui()
        report = len(client.elements), client.shared_head_html + client.head_html
        # The page starts work that waits for a browser to attach. Nothing will
        # attach, so stop it deliberately instead of letting the loop close on it.
        pending = asyncio.all_tasks(core.loop) - {asyncio.current_task()}
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return report

    element_count, head = asyncio.run(build())
    if element_count < 2:
        raise RuntimeError("build_ui produced no widgets")
    # Token prefixes differ between apps, so look for any custom property rather
    # than for one project's naming.
    if not re.search(r"--[\w-]+\s*:", head):
        raise RuntimeError("the stylesheet never reached the page")
    return {"elements": element_count, "stylesheet_bytes": len(head)}


def main() -> int:
    args = parse_args()
    assert_gui_host_allowed(args.host)
    ensure_project_dirs(paths)
    if args.smoke:
        try:
            report = build_ui_once()
        except Exception as error:  # noqa: BLE001
            print(f"FAIL nicegui shell: {ROOT}: {error}")
            return 1
        print(
            f"OK nicegui shell: {ROOT}"
            f" | widgets={report['elements']}"
            f" | stylesheet={report['stylesheet_bytes']} bytes"
        )
        return 0

    if port_is_open(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        print(f"GUI already appears to be running: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    ui.run(
        root=build_ui,
        title=app_title(),
        host=args.host,
        port=args.port,
        reload=False,
        native=False,
        show=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
