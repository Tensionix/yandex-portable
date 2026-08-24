from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib
import os
import platform
import shutil
import sys

REQUIRED_MODULES = [
    ("tqdm", "tqdm"),
    ("rich", "rich"),
    ("pydantic", "pydantic"),
    ("nicegui", "nicegui"),
    ("webview", "pywebview"),
    ("yaml", "pyyaml"),
    ("markdown_it", "markdown-it-py"),
]

OPTIONAL_MODULES = [
    ("requests", "requests"),
    ("docx", "python-docx"),
    ("openai", "openai"),
    ("google.genai", "google-genai"),
    ("pandas", "pandas"),
    ("openpyxl", "openpyxl"),
    ("fitz", "pymupdf"),
    ("pptx", "python-pptx"),
]


def ansi_enabled() -> bool:
    return (
        "NO_COLOR" not in os.environ
        and (
            os.environ.get("AUDION_GUI_TERMINAL") == "1"
            or os.environ.get("FORCE_COLOR") == "1"
            or os.environ.get("CLICOLOR_FORCE") == "1"
            or sys.stdout.isatty()
        )
    )


def color(text: object, code: str) -> str:
    value = str(text)
    if not ansi_enabled():
        return value
    return f"\033[{code}m{value}\033[0m"


def section_title(text: str) -> None:
    print(color(f"[{text}]", "35;1"))


def info_row(label: str, value: object) -> None:
    print(f"{color('[INFO]', '36;1')} {label:<12}: {value}")


def status_label(status: str, width: int = 4) -> str:
    normalized = status.upper()
    if normalized == "OK":
        code = "32;1"
    elif normalized in {"MISS", "MISSING_FUNC", "NOT_CALLABLE"}:
        code = "33;1"
    elif normalized in {"FAIL", "MANIFEST_FAIL", "BAD_SYNTAX", "IMPORT_FAIL"}:
        code = "31;1"
    else:
        code = "36;1"
    return color(f"{status:<{width}}", code)


def check_module(import_name: str) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "unknown")
        return True, str(version)
    except Exception as exc:
        return False, exc.__class__.__name__


def detect_python_mode(root: Path) -> str:
    if (root / "runtime" / "python.exe").exists():
        return "portable-runtime"
    if (root / "runtime" / "python" / "python.exe").exists():
        return "portable-runtime"
    if (root / "._runtime" / "python.exe").exists():
        return "template-portable-runtime"
    if (root / "._runtime" / "python" / "python.exe").exists():
        return "template-portable-runtime"
    return "system-python"


def check_picker_powershell(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    candidates = [
        ("portable pwsh", root / "system_core" / "powershell" / "pwsh.exe"),
        ("PATH pwsh", "pwsh.exe"),
        ("Windows PowerShell", "powershell.exe"),
    ]
    rows: list[tuple[str, bool, str]] = []
    any_ok = False
    for label, candidate in candidates:
        if isinstance(candidate, Path):
            ok = candidate.exists()
            detail = str(candidate)
        else:
            resolved = shutil.which(candidate)
            ok = bool(resolved)
            detail = resolved or "not found"
        rows.append((label, ok, detail))
        any_ok = any_ok or ok
    return any_ok, rows


def check_manifest_operations(root: Path) -> tuple[bool, list[tuple[str, str, str]]]:
    """Validate every operation declared in config/tool_manifest.yaml.

    For each operation tries to import the module and resolve the function.
    Returns (all_ok, [(operation_id, status, detail), ...]).

    Status codes:
      OK              — module imports and function is callable
      MANIFEST_FAIL   — manifest file missing or unparseable (emitted once)
      BAD_SYNTAX      — service string does not match module:function
      IMPORT_FAIL     — importlib.import_module raised
      MISSING_FUNC    — module imports, attribute does not exist
      NOT_CALLABLE    — attribute exists but is not callable
    """
    # Make sure system_core is importable when running doctor as
    # `python -m system_core.doctor` from the project root.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from system_core.core.manifest import load_manifest  # noqa: WPS433
    except Exception as exc:
        return False, [("(loader)", "MANIFEST_FAIL", f"{exc.__class__.__name__}: {exc}")]

    manifest_path = root / "config" / "tool_manifest.yaml"
    if not manifest_path.exists():
        return False, [("(loader)", "MANIFEST_FAIL", f"Not found: {manifest_path}")]

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        return False, [("(loader)", "MANIFEST_FAIL", f"{exc.__class__.__name__}: {exc}")]

    rows: list[tuple[str, str, str]] = []
    all_ok = True

    def collect_group_operations(nodes: list[Any]) -> list[Any]:
        operations: list[Any] = []
        for node in nodes:
            children = list(getattr(node, "children", ()) or ())
            if children:
                operations.extend(collect_group_operations(children))
            else:
                operations.append(node.to_operation(dict(getattr(node, "parameters", {}) or {})))
        return operations

    every_operation = [
        *manifest.operations,
        *collect_group_operations(manifest.operation_groups),
        *manifest.maintenance_operations,
    ]
    for op in every_operation:
        if ":" not in op.service:
            rows.append((op.id, "BAD_SYNTAX", op.service))
            all_ok = False
            continue

        module_name, function_name = op.service.split(":", 1)
        try:
            mod = importlib.import_module(module_name)
        except Exception as exc:
            rows.append((op.id, "IMPORT_FAIL", f"{module_name} ({exc.__class__.__name__})"))
            all_ok = False
            continue

        if not hasattr(mod, function_name):
            rows.append((op.id, "MISSING_FUNC", f"{module_name}:{function_name}"))
            all_ok = False
            continue

        if not callable(getattr(mod, function_name)):
            rows.append((op.id, "NOT_CALLABLE", f"{module_name}:{function_name}"))
            all_ok = False
            continue

        rows.append((op.id, "OK", op.service))

    return all_ok, rows


def check_cmd_encoding(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from system_core.core.cmd_encoding import check_cmd_files  # noqa: WPS433
    except Exception as exc:
        return False, [("(loader)", False, f"{exc.__class__.__name__}: {exc}")]

    rows: list[tuple[str, bool, str]] = []
    all_ok = True
    for result in check_cmd_files(root):
        try:
            relative = str(result.path.resolve().relative_to(root.resolve()))
        except ValueError:
            relative = str(result.path)

        detail = result.summary()
        if result.error:
            detail = f"{detail} {result.error}"
        rows.append((relative, result.ok, detail))
        if not result.ok:
            all_ok = False

    return all_ok, rows


def check_sh_lf(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from system_core.core.sh_lf import check_sh_files  # noqa: WPS433
    except Exception as exc:
        return False, [("(loader)", False, f"{exc.__class__.__name__}: {exc}")]

    rows: list[tuple[str, bool, str]] = []
    all_ok = True
    for result in check_sh_files(root):
        try:
            relative = str(result.path.resolve().relative_to(root.resolve()))
        except ValueError:
            relative = str(result.path)

        detail = result.summary()
        if result.error:
            detail = f"{detail} {result.error}"
        rows.append((relative, result.ok, detail))
        if not result.ok:
            all_ok = False

    return all_ok, rows


def check_gui_theme_catalog(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from system_core.core.config import load_yaml_or_json  # noqa: WPS433
        from system_core.core.ui_theme_catalog import validate_theme_catalog  # noqa: WPS433
    except Exception as exc:
        return False, [("(loader)", False, f"{exc.__class__.__name__}: {exc}")]

    try:
        data = load_yaml_or_json(root / "config" / "ui_colors.yaml")
    except Exception as exc:
        return False, [("catalog", False, f"{exc.__class__.__name__}: {exc}")]

    result = validate_theme_catalog(data)
    if not result.ok:
        return False, [("catalog", False, error) for error in result.errors]

    rows = [
        ("theme order", True, f"core prefix OK; {len(result.theme_ids)} theme(s)"),
        ("extension themes", True, ", ".join(result.extra_theme_ids) or "none"),
    ]
    return True, rows


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    print(color("======================================================================", "36;1"))
    print(color("AUDION PYTHON GUI PORTABLE TEMPLATE - DOCTOR", "36;1"))
    print(color("======================================================================", "36;1"))
    info_row("Project root", root)
    info_row("Executable", sys.executable)
    info_row("Python", sys.version.split()[0])
    info_row("Python mode", detect_python_mode(root))
    info_row("Platform", platform.platform())
    print()

    failed = False

    section_title("Required modules")
    for import_name, package_name in REQUIRED_MODULES:
        ok, detail = check_module(import_name)
        status = "OK" if ok else "FAIL"
        print(f"  - {package_name:<18} : {status_label(status)} {detail}")
        if not ok:
            failed = True

    print()
    section_title("GUI portability")
    picker_ok, picker_rows = check_picker_powershell(root)
    for label, ok, detail in picker_rows:
        status = "OK" if ok else "MISS"
        print(f"  - {label:<18} : {status_label(status)} {detail}")
    if not picker_ok:
        print(f"  - picker dialogs     : {status_label('FAIL')} PowerShell was not found")
        failed = True
    else:
        print(f"  - picker dialogs     : {status_label('OK')} PowerShell-backed Windows dialogs available")

    print()
    section_title("GUI themes")
    themes_ok, theme_rows = check_gui_theme_catalog(root)
    for label, ok, detail in theme_rows:
        status = "OK" if ok else "FAIL"
        print(f"  - {label:<18} : {status_label(status)} {detail}")
    if not themes_ok:
        failed = True

    print()
    section_title("Optional modules")
    for import_name, package_name in OPTIONAL_MODULES:
        ok, detail = check_module(import_name)
        status = "OK" if ok else "MISS"
        print(f"  - {package_name:<18} : {status_label(status)} {detail}")

    print()
    section_title("Manifest operations")
    manifest_ok, rows = check_manifest_operations(root)
    if not rows:
        print("  (no operations found)")
    else:
        for op_id, status, detail in rows:
            print(f"  - {op_id:<22} : {status_label(status, 13)} {detail}")
    if not manifest_ok:
        failed = True

    print()
    section_title("CMD encoding")
    cmd_ok, cmd_rows = check_cmd_encoding(root)
    if not cmd_rows:
        print("  (no CMD files found)")
    else:
        for relative, result_ok, detail in cmd_rows:
            status = "OK" if result_ok else "FAIL"
            print(f"  - {relative:<58} : {status_label(status)} {detail}")
    if not cmd_ok:
        failed = True

    print()
    section_title("SH LF")
    sh_ok, sh_rows = check_sh_lf(root)
    if not sh_rows:
        print("  (no SH files found)")
    else:
        for relative, result_ok, detail in sh_rows:
            status = "OK" if result_ok else "FAIL"
            print(f"  - {relative:<58} : {status_label(status)} {detail}")
    if not sh_ok:
        failed = True

    print()
    if failed:
        print(f"{color('[RESULT]', '31;1')} One or more checks failed.")
        return 1

    print(f"{color('[RESULT]', '32;1')} Required environment looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
