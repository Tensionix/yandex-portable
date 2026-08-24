from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .ansi import strip_ansi


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    plain_message = strip_ansi(message)
    with log_file.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{timestamp()}] {plain_message}\n")
