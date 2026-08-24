from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import contextlib
import json
import os
import shutil
import time

from system_core.core.jobs import JobContext, run_process
from tqdm import tqdm


def _project_path(project_root: Path, value: object, default: str) -> Path:
    text = str(value if value not in {None, ""} else default).strip().strip('"')
    path = Path(os.path.expandvars(text)).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _input_dir(context: JobContext) -> Path:
    return _project_path(context.paths.root, context.operation.parameters.get("gui_input_dir"), "input")


def _output_dir(context: JobContext) -> Path:
    return _project_path(context.paths.root, context.operation.parameters.get("gui_output_dir"), "output")


def input_file_options(root: Path | str | None = None, values: dict[str, object] | None = None, _field: dict[str, object] | None = None) -> list[dict[str, str]]:
    """Dynamic manifest option provider for files staged in input."""
    project_root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
    input_dir = _project_path(project_root, (values or {}).get("gui_input_dir"), "input")
    if not input_dir.exists():
        return [{"value": "", "label": "input is missing", "label_ru": "input не найден"}]

    if input_dir.is_file():
        return [{"value": input_dir.name, "label": input_dir.name, "label_ru": input_dir.name}]

    files = sorted(path for path in input_dir.rglob("*") if path.is_file())
    if not files:
        return [{"value": "", "label": "input is empty", "label_ru": "input пуст"}]

    options: list[dict[str, str]] = []
    for path in files[:200]:
        relative = path.relative_to(input_dir).as_posix()
        options.append({"value": relative, "label": relative, "label_ru": relative})
    return options


class _LogStream:
    def __init__(self, context: JobContext) -> None:
        self.context = context
        self.buffer = ""
        self.last_progress_emit = 0.0

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not text:
            return 0

        for char in text:
            if char == "\n":
                self._emit(self.buffer)
                self.buffer = ""
            elif char == "\r":
                self._emit_progress_snapshot()
                self.buffer = ""
            else:
                self.buffer += char
        return len(text)

    def flush(self) -> None:
        self._emit(self.buffer)
        self.buffer = ""

    def _emit(self, text: str) -> None:
        line = text.rstrip()
        if line:
            self.context.log(line)

    def _emit_progress_snapshot(self) -> None:
        now = time.monotonic()
        if now - self.last_progress_emit < 0.5:
            return
        self.last_progress_emit = now
        self._emit(self.buffer)


@contextlib.contextmanager
def relay_output(context: JobContext):
    stream = _LogStream(context)
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        yield
    stream.flush()


def _inventory(folder: Path) -> dict[str, int]:
    if not folder.exists():
        return {"files": 0, "dirs": 0}
    if folder.is_file():
        return {"files": 1, "dirs": 0}

    files = 0
    dirs = 0
    for item in folder.rglob("*"):
        if item.is_file():
            files += 1
        elif item.is_dir():
            dirs += 1
    return {"files": files, "dirs": dirs}


def validate_input(context: JobContext) -> dict[str, object]:
    input_dir = _input_dir(context)
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
    inventory = _inventory(input_dir)
    context.log(f"Input path: {input_dir}")
    context.log(f"Input inventory: {inventory['files']} files, {inventory['dirs']} directories")
    context.progress(1.0)
    return {"input": str(input_dir), "inventory": inventory}


def run_sample_job(context: JobContext) -> dict[str, object]:
    input_dir = _input_dir(context)
    output_dir = _output_dir(context)
    output_dir.mkdir(parents=True, exist_ok=True)

    with relay_output(context):
        steps = range(1, 6)
        for step in tqdm(steps, desc="Sample job", unit="step"):
            if context.cancelled():
                context.log("Operation cancelled by user.")
                return {"cancelled": True}
            print(f"Processing sample step {step} of 5")
            context.progress(step / 5)
            time.sleep(0.2)

    report = {
        "project_root": str(context.paths.root),
        "input": _inventory(input_dir),
        "parameters": context.operation.parameters,
        "message": "Replace sample_service.py with real project services.",
    }
    report_path = output_dir / "sample_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    context.log(f"Created: {report_path}")
    return {"report": str(report_path)}


def package_output(context: JobContext) -> dict[str, object]:
    output_dir = _output_dir(context)
    output_dir.mkdir(parents=True, exist_ok=True)
    context.paths.release.mkdir(parents=True, exist_ok=True)

    files = [p for p in output_dir.rglob("*") if p.is_file()]
    zip_path = context.paths.release / "output_package.zip"

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        total = max(1, len(files))
        for index, file_path in enumerate(files, start=1):
            if context.cancelled():
                context.log("Packaging cancelled by user.")
                return {"cancelled": True}
            archive.write(file_path, file_path.relative_to(output_dir).as_posix())
            context.progress(index / total)

    context.log(f"Created: {zip_path}")
    return {"zip": str(zip_path), "files": len(files)}


def _resolve_powershell() -> str:
    project_root = Path(__file__).resolve().parents[2]
    bundled_pwsh = project_root / "system_core" / "powershell" / "pwsh.exe"
    if bundled_pwsh.exists():
        return str(bundled_pwsh)
    return shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"


def terminal_command(context: JobContext) -> dict[str, object]:
    """Generic command runner used by the GUI terminal command bar."""
    parameters = context.operation.parameters
    command_text = str(parameters.get("command") or "").strip()
    if not command_text:
        raise RuntimeError("Command is empty.")

    shell = str(parameters.get("shell") or ("pwsh" if os.name == "nt" else "sh")).strip().lower()
    cwd_text = str(parameters.get("cwd") or context.paths.root).strip()
    cwd = Path(cwd_text).expanduser()
    if not cwd.is_absolute():
        cwd = context.paths.root / cwd
    if cwd.is_file():
        cwd = cwd.parent
    if not cwd.exists():
        raise RuntimeError(f"Working directory does not exist: {cwd}")

    if os.name == "nt":
        if shell == "cmd":
            command = ["cmd.exe", "/d", "/c", command_text]
        else:
            powershell = _resolve_powershell()
            exe_name = Path(powershell).name.lower()
            if exe_name == "powershell.exe":
                command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command_text]
            else:
                command = [powershell, "-NoLogo", "-NoProfile", "-Command", command_text]
    else:
        command = ["sh", "-lc", command_text]

    context.log(f"Terminal shell: {shell}")
    result = run_process(context, command, cwd=cwd, check=False, progress_seconds=300.0)
    if result.exit_code != 0:
        raise RuntimeError(f"Terminal command failed with exit code {result.exit_code}.")
    return {"exit_code": result.exit_code, "command": command_text, "cwd": str(cwd)}


def _is_inside(child: Path, parent: Path) -> bool:
    """True iff `child` (after resolve) is inside `parent` (after resolve).

    Uses os.path.commonpath which is stricter than `parent in child.parents`
    when `child == parent` and works correctly across symlinks because both
    sides are already resolved.
    """
    try:
        child_resolved = str(child.resolve())
        parent_resolved = str(parent.resolve())
    except OSError:
        return False
    try:
        common = os.path.commonpath([child_resolved, parent_resolved])
    except ValueError:
        # Different drives on Windows, etc.
        return False
    return common == parent_resolved


def _clean_managed_folder(context: JobContext, folder: Path, label: str) -> dict[str, object]:
    root = context.paths.root.resolve()
    if folder.is_symlink():
        raise RuntimeError(f"{label} is a symbolic link. Cleanup blocked for safety.")

    folder.mkdir(parents=True, exist_ok=True)
    folder_resolved = folder.resolve()
    if not _is_inside(folder_resolved, root):
        raise RuntimeError(f"{label} path is outside project root. Cleanup blocked.")

    removed = 0
    skipped: list[str] = []
    for item in folder.iterdir():
        try:
            if item.is_symlink():
                item.unlink()
            elif item.is_dir():
                if not _is_inside(item, folder_resolved):
                    skipped.append(f"{item.name} (escapes {label})")
                    continue
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
            context.log(f"Removed from {label}: {item.name}")
        except OSError as exc:
            skipped.append(f"{item.name} ({exc})")

    return {"folder": label, "removed_items": removed, "skipped_items": skipped}


def cleanup_input_output(context: JobContext) -> dict[str, object]:
    context.log("Cleaning managed input/output folders.")
    input_result = _clean_managed_folder(context, _input_dir(context), "input")
    context.progress(0.5)
    if context.cancelled():
        context.log("Input/output cleanup cancelled by user after input cleanup.")
        return {"cancelled": True, "input": input_result}

    output_result = _clean_managed_folder(context, _output_dir(context), "output")
    context.progress(1.0)
    total_removed = int(input_result["removed_items"]) + int(output_result["removed_items"])
    total_skipped = len(input_result["skipped_items"]) + len(output_result["skipped_items"])
    context.log(f"Input/output cleanup complete. Removed: {total_removed}, skipped: {total_skipped}")
    return {"input": input_result, "output": output_result, "removed_items": total_removed, "skipped_items": total_skipped}


def cleanup_workspace(context: JobContext) -> dict[str, object]:
    """Delete only files inside the managed workspace folder.

    Safety rules:
    - workspace must resolve to a path inside the project root.
    - Symlinks inside workspace are unlinked, never traversed. shutil.rmtree
      with follow_symlinks=False is not enough on Windows because Path.rmtree
      via shutil treats junctions inconsistently — we handle symlinks first
      and explicitly.
    - Non-symlink subdirectories are checked again before removal: their
      resolved path must still be inside workspace. This catches the case
      where workspace itself contains a directory whose resolve() escapes
      (e.g. a junction or reparse point set up between the outer check and
      iteration).
    """
    workspace = context.paths.workspace
    root = context.paths.root.resolve()

    # Reject workspaces that are themselves symlinks pointing outside root.
    if workspace.is_symlink():
        raise RuntimeError("Workspace is a symbolic link. Cleanup blocked for safety.")

    workspace_resolved = workspace.resolve()
    if not _is_inside(workspace_resolved, root):
        raise RuntimeError("Workspace path is outside project root. Cleanup blocked.")

    workspace.mkdir(parents=True, exist_ok=True)

    removed = 0
    skipped: list[str] = []

    for item in workspace.iterdir():
        # Symlinks: unlink the link itself, do NOT follow.
        if item.is_symlink():
            try:
                item.unlink()
                removed += 1
                context.log(f"Removed symlink: {item.name}")
            except OSError as exc:
                skipped.append(f"{item.name} (symlink, {exc})")
            continue

        # Re-verify directory containment before recursive delete.
        if item.is_dir():
            if not _is_inside(item, workspace_resolved):
                skipped.append(f"{item.name} (escapes workspace after resolve)")
                context.log(f"Skipped (escapes workspace): {item.name}")
                continue
            shutil.rmtree(item)
            removed += 1
            continue

        # Regular file.
        item.unlink()
        removed += 1

    context.log(f"Workspace cleanup complete. Removed: {removed}, skipped: {len(skipped)}")
    if skipped:
        context.log("Skipped items: " + ", ".join(skipped))
    context.progress(1.0)
    return {"removed_items": removed, "skipped_items": skipped}
