from __future__ import annotations

from typing import Any


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title_default": "Audion GUI Tool",
        "workspace": "Workspace",
        "input": "Input",
        "output": "Output",
        "logs": "Logs",
        "release": "Release",
        "open_input": "Open input",
        "open_output": "Open output",
        "open_logs": "Open logs",
        "open_release": "Open release",
        "operations": "Operations",
        "maintenance": "Maintenance",
        "job_status": "Job status",
        "operations_log": "Operations log",
        "operation_log_placeholder": "Operation log will appear here.",
        "cancel_current_job": "Cancel current job",
        "run": "Run",
        "run_maintenance_action": "Run maintenance action",
        "confirm_maintenance_action": "Confirm maintenance action",
        "confirm_maintenance_note": "This action may change the managed workspace. Original input files must not be deleted.",
        "cancel": "Cancel",
        "another_operation_running": "Another operation is already running.",
        "settings": "Settings",
        "theme": "Theme",
        "language": "Language",
        "dark": "Dark",
        "light": "Light",
        "english": "English",
        "russian": "Russian",
        "theme_saved": "Theme saved.",
        "language_saved": "Language saved. Reloading UI.",
        "language_saved_restart_required": "Language saved. Restart the app to apply.",
        "idle": "Idle",
        "running_prefix": "Running",
        "project_root": "Project root",
    },
    "ru": {
        "app_title_default": "Audion GUI Tool",
        "workspace": "Рабочая область",
        "input": "Входные данные",
        "output": "Результаты",
        "logs": "Логи",
        "release": "Релиз",
        "open_input": "Открыть input",
        "open_output": "Открыть output",
        "open_logs": "Открыть logs",
        "open_release": "Открыть release",
        "operations": "Операции",
        "maintenance": "Обслуживание",
        "job_status": "Статус задачи",
        "operations_log": "Журнал операций",
        "operation_log_placeholder": "Здесь появится журнал операции.",
        "cancel_current_job": "Отменить текущую задачу",
        "run": "Запустить",
        "run_maintenance_action": "Запустить обслуживание",
        "confirm_maintenance_action": "Подтвердить действие обслуживания",
        "confirm_maintenance_note": "Действие может изменить управляемую рабочую папку. Исходные input-файлы удалять нельзя.",
        "cancel": "Отмена",
        "another_operation_running": "Другая операция уже выполняется.",
        "settings": "Настройки",
        "theme": "Тема",
        "language": "Язык",
        "dark": "Тёмная",
        "light": "Светлая",
        "english": "Английский",
        "russian": "Русский",
        "theme_saved": "Тема сохранена.",
        "language_saved": "Язык сохранён. Перезагружаю интерфейс.",
        "language_saved_restart_required": "Язык сохранён. Перезапустите приложение, чтобы применить.",
        "idle": "Ожидание",
        "running_prefix": "Выполняется",
        "project_root": "Корень проекта",
    },
}


def t(language: str, key: str, **kwargs: Any) -> str:
    lang = language if language in TRANSLATIONS else "en"
    text = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["en"].get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text
