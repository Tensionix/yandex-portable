from __future__ import annotations

from pathlib import Path
import json
import sys


def detect_python_mode(root: Path) -> str:
    if (root / "runtime" / "python.exe").exists():
        return "portable-runtime"
    if (root / "runtime" / "python" / "python.exe").exists():
        return "portable-runtime"
    return "system-python"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    payload = {
        "project_root": str(root),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "python_mode": detect_python_mode(root),
        "gui_entrypoint": str(root / "system_core" / "ui_nicegui" / "app.py"),
        "message": "GUI portable template is ready. Run launcher_gui.cmd.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
