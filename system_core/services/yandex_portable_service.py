"""Yandex Browser Portable: build it, update it, and keep Chrome++ current.

The full Yandex installer is a PE whose resource section holds one file,
`browser.7z`, and that archive holds `Browser-bin` — the browser itself. So a
portable build is two unpackings and a copy, with no installation anywhere:

    Yandex.exe (full_installer)
      -> browser.7z
        -> Browser-bin\\           -> <build>\\App\\
             browser.exe
             <version>\\

Portability itself comes from Chrome++ (`version.dll` beside `browser.exe`):
`browser.exe` imports `VERSION.dll`, the name is not in `KnownDLLs`, so the
hijack takes and the profile moves to `Data` beside `App` instead of
`%LOCALAPPDATA%`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import contextlib
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile

from system_core.core.jobs import JobContext, hidden_subprocess_kwargs, utf8_subprocess_env


# Yandex answers this address with a 302 to the CDN, and the CDN path carries the
# version: `.../browser/yandex/26_6_5_621_113843/ru/Yandex.exe`. That is why the
# update check costs one HEAD request instead of 200 MB.
YANDEX_FULL_INSTALLER_URL = "https://browser.yandex.ru/download?full=1"
# With a non-Windows agent the same address redirects to the App Store, so the
# agent is not decoration here.
WINDOWS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)
GITHUB_USER_AGENT = "Audion-Yandex-Portable"

CHROME_PLUS_REPO = "Bush2021/chrome_plus"

# What makes a build portable, and the operator picks one:
#   chrome_plus    - Chrome++, the wrapper this program started with;
#   proxy_library  - the other proxy `version.dll`, published on GitFlic.
PORTABLE_ENGINES = ("chrome_plus", "proxy_library")
DEFAULT_PORTABLE_ENGINE = "chrome_plus"

PROXY_LIBRARY_HOST = "https://gitflic.ru"
PROXY_LIBRARY_PROJECT = "neyrostalker/proksi-biblioteka"
PROXY_LIBRARY_DLL = {"x86": "version x32.dll", "x64": "version x64.dll"}
CHROME_PLUS_ASSET = re.compile(r"Chrome\+\+_v.+_x86_x64_arm64\.7z", re.IGNORECASE)

PORTABLE_NAME = "Yandex Browser Portable"
BROWSER_EXECUTABLE = "browser.exe"
PAYLOAD_ARCHIVE = "browser.7z"
PAYLOAD_DIRECTORY = "Browser-bin"
UPDATER_EXECUTABLE = "service_update.exe"
BUILD_STAMP_FILE = "Portable-Build.json"

# Yandex keeps counters here rather than in the profile, so a portable build
# still leaves this behind. Chrome++ wipes it on exit when the build asks for it.
YANDEX_REGISTRY_BRANCH = r"HKCU\Software\Yandex\YandexBrowser"


@dataclass(frozen=True)
class DownloadedAsset:
    name: str
    url: str
    path: Path
    sha256: str
    size: int


@dataclass(frozen=True)
class BuildVersions:
    """What a build on disk actually carries, read from the build itself."""

    yandex: str
    chrome_plus: str


def _param_text(context: JobContext, key: str, default: str = "") -> str:
    return str(context.operation.parameters.get(key, default) or "").strip()


def _param_bool(context: JobContext, key: str, default: bool = False) -> bool:
    value = context.operation.parameters.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    if value is None:
        return default
    return bool(value)


def _resolve_project_path(context: JobContext, raw_path: str, default_name: str) -> Path:
    path_text = str(raw_path or "").strip().strip('"') or default_name
    path = Path(os.path.expandvars(path_text)).expanduser()
    if not path.is_absolute():
        path = context.paths.root / path
    return path.resolve()


def _output_root(context: JobContext) -> Path:
    output = _resolve_project_path(context, _param_text(context, "output_path"), "output")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _input_root(context: JobContext) -> Path:
    return _resolve_project_path(context, _param_text(context, "input_path"), "input")


def _portable_root(context: JobContext) -> Path:
    portable_root = _output_root(context) / "Portable"
    portable_root.mkdir(parents=True, exist_ok=True)
    return portable_root


def _archives_dir(context: JobContext) -> Path:
    path = _portable_root(context) / "_archives"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tmp_dir(context: JobContext) -> Path:
    path = _portable_root(context) / "_tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_tree(path: Path, *, ignore_missing: bool = True) -> None:
    if not path.exists():
        if ignore_missing:
            return
        raise FileNotFoundError(str(path))

    def handle_remove_error(function: Any, item_path: str, _exc_info: Any) -> None:
        os.chmod(item_path, 0o700)
        function(item_path)

    shutil.rmtree(path, onerror=handle_remove_error)


def _reset_dir(path: Path) -> None:
    if path.exists():
        _remove_tree(path)
    path.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    return cleaned or "download"


def _progress_between(context: JobContext, start: float | None, end: float | None, fraction: float) -> None:
    if start is None or end is None:
        return
    context.progress(start + (end - start) * max(0.0, min(1.0, fraction)))


def _download(
    context: JobContext,
    url: str,
    target: Path,
    label: str,
    *,
    user_agent: str = GITHUB_USER_AGENT,
    progress_start: float | None = None,
    progress_end: float | None = None,
) -> DownloadedAsset:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        size = target.stat().st_size
        digest = _sha256(target)
        context.log(f"[CACHE] {label}: {target} ({size:,} bytes)")
        context.log(f"[SHA256] {digest}")
        _progress_between(context, progress_start, progress_end, 1.0)
        return DownloadedAsset(label, url, target, digest, size)

    context.log(f"[DOWNLOAD] {label}")
    context.log(f"[URL] {url}")
    request = Request(url, headers={"User-Agent": user_agent})
    part = target.with_name(target.name + ".part")
    if part.exists():
        part.unlink()
    try:
        with urlopen(request, timeout=120) as response, part.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            last_logged_percent = -10
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    fraction = downloaded / total
                    _progress_between(context, progress_start, progress_end, fraction)
                    percent = int(fraction * 100)
                    if percent >= last_logged_percent + 10:
                        context.log(f"[DOWNLOAD] {label}: {percent}% ({downloaded:,}/{total:,} bytes)")
                        last_logged_percent = percent
            if total <= 0:
                _progress_between(context, progress_start, progress_end, 1.0)
        part.replace(target)
    except (HTTPError, URLError, TimeoutError) as exc:
        if part.exists():
            part.unlink()
        raise RuntimeError(f"Download failed: {url} ({exc})") from exc
    size = target.stat().st_size
    digest = _sha256(target)
    context.log(f"[OK] {target} ({size:,} bytes)")
    context.log(f"[SHA256] {digest}")
    return DownloadedAsset(label, url, target, digest, size)


def github_latest_assets(repo: str) -> tuple[str, list[tuple[str, str]]]:
    """Tag and `(name, url)` of every asset in the latest release.

    The API answers in one request but allows only 60 anonymous calls an hour,
    and that runs out quietly. The same list is on the release pages, where
    there is no quota at all, so the HTML is the fallback. The download link
    comes from whichever answer worked, so nothing is asked of GitHub between
    finding the file and fetching it.
    """
    headers = {"User-Agent": GITHUB_USER_AGENT, "Accept": "application/vnd.github+json"}
    try:
        request = Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
        with urlopen(request, timeout=60) as response:
            release = json.loads(response.read().decode("utf-8"))
        assets = [
            (str(item.get("name") or ""), str(item.get("browser_download_url") or ""))
            for item in release.get("assets", [])
        ]
        if assets:
            return str(release.get("tag_name") or "latest"), assets
    except Exception:  # noqa: BLE001 - any network or quota trouble falls back
        pass

    plain = {"User-Agent": GITHUB_USER_AGENT}
    request = Request(f"https://github.com/{repo}/releases/latest", headers=plain)
    with urlopen(request, timeout=60) as response:
        tag = response.geturl().rstrip("/").rsplit("/", 1)[-1]
    request = Request(f"https://github.com/{repo}/releases/expanded_assets/{tag}", headers=plain)
    with urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", "replace")
    assets: list[tuple[str, str]] = []
    for path in re.findall(r'href="(/[^"]+/releases/download/[^"]+)"', page):
        name = path.rsplit("/", 1)[-1]
        url = "https://github.com" + path
        if (name, url) not in assets:
            assets.append((name, url))
    if not assets:
        raise RuntimeError(f"No release assets found for {repo}, neither through the API nor on the release page.")
    return tag, assets


def chrome_plus_release() -> tuple[str, str, str]:
    """Version, asset name and URL of the current Chrome++ release."""
    tag, assets = github_latest_assets(CHROME_PLUS_REPO)
    for name, url in assets:
        if CHROME_PLUS_ASSET.fullmatch(name):
            return tag.lstrip("v"), name, url
    listed = ", ".join(name for name, _url in assets)
    raise RuntimeError(f"Chrome++ archive was not found in release {tag}. Assets: {listed}")


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", str(text or ""))][:4]
    return tuple(parts + [0] * (4 - len(parts)))


def same_version(left: str, right: str) -> bool:
    """`1.18.2` and `1.18.2.0` are the same release.

    A release is tagged `1.18.2` and the file it ships reports `1.18.2.0`, so a
    plain string comparison would report an update on every single check.
    """
    if not left or not right:
        return False
    return _version_tuple(left) == _version_tuple(right)


def _version_from_cdn_url(url: str) -> str:
    """`26.6.5.621` out of `.../browser/yandex/26_6_5_621_113843/ru/Yandex.exe`."""
    match = re.search(r"/browser/yandex/(\d+)_(\d+)_(\d+)_(\d+)(?:_\d+)?/", url)
    if not match:
        return ""
    return ".".join(match.groups())


def yandex_available_version(url: str = YANDEX_FULL_INSTALLER_URL) -> tuple[str, str]:
    """Version and the resolved file URL, without downloading the 200 MB file."""
    request = Request(url, headers={"User-Agent": WINDOWS_USER_AGENT}, method="HEAD")
    try:
        with urlopen(request, timeout=60) as response:
            resolved = response.geturl()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not resolve the Yandex installer URL: {exc}") from exc
    if "Yandex.exe" not in resolved:
        raise RuntimeError(
            f"The download address did not resolve to a Windows installer: {resolved}. "
            "Yandex picks the platform by the user agent."
        )
    return _version_from_cdn_url(resolved), resolved


def _file_version(path: Path) -> str:
    """FileVersion of a Windows binary, read through the version API."""
    if os.name != "nt" or not path.is_file():
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        version_api = ctypes.WinDLL("version.dll")
        size = version_api.GetFileVersionInfoSizeW(ctypes.c_wchar_p(str(path)), None)
        if not size:
            return ""
        buffer = ctypes.create_string_buffer(size)
        if not version_api.GetFileVersionInfoW(ctypes.c_wchar_p(str(path)), 0, size, buffer):
            return ""
        block = ctypes.c_void_p()
        length = wintypes.UINT()
        if not version_api.VerQueryValueW(
            buffer, ctypes.c_wchar_p("\\"), ctypes.byref(block), ctypes.byref(length)
        ):
            return ""
        fixed = ctypes.cast(block, ctypes.POINTER(ctypes.c_uint32 * 4)).contents
        most, least = fixed[2], fixed[3]
        return f"{most >> 16}.{most & 0xFFFF}.{least >> 16}.{least & 0xFFFF}"
    except Exception:  # noqa: BLE001 - a version is a nicety, never a blocker
        return ""


def _seven_zip_path(context: JobContext) -> Path:
    return context.paths.root / "tools" / "7zip" / "bin" / "7za.exe"


def _seven_zip_version(context: JobContext) -> str:
    exe = _seven_zip_path(context)
    if not exe.exists():
        return ""
    result = subprocess.run(
        [str(exe), "i"],
        cwd=str(context.paths.root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_subprocess_kwargs(),
    )
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if "7-Zip" in line:
            return line.strip()
    return "7-Zip available"


def _require_7zip(context: JobContext) -> Path:
    exe = _seven_zip_path(context)
    version = _seven_zip_version(context)
    if not exe.exists() or not version:
        raise RuntimeError("Portable 7-Zip is not available. Run 'Check / install portable 7-Zip' first.")
    context.log(f"[7ZIP] {version}")
    return exe


# --- Defender exclusion guard -------------------------------------------------
#
# Chrome++'s unsigned `version.dll` is a routine Defender false positive. When
# real-time protection grabs it mid-build, the packaging step dies with a bare
# `OSError [Errno 22]`. To keep a build from failing on machines where Defender
# is active, the output folder is excluded from scanning for the duration of the
# build and put back afterwards. The exclusion is a real hole in the machine's
# protection, so it is opened only when Defender is actually running, only for as
# long as the build runs, and it is always paired with a way to take it back.

_DEFENDER_GUARD_DIRNAME = ".defender_guard"
_DEFENDER_GUARD_MAX_SECONDS = 3600


def _defender_guard_script(context: JobContext) -> Path:
    return context.paths.system_core / "powershell" / "defender_guard.ps1"


def _defender_guard_dir(context: JobContext) -> Path:
    path = context.paths.workspace / _DEFENDER_GUARD_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _defender_active(context: JobContext) -> bool:
    """True only when Windows Defender real-time protection is actually running.

    Read-only and unelevated, so it never triggers UAC by itself: a machine
    without Defender (or with it disabled) answers 'inactive' and the whole guard
    turns into a no-op, exactly the case on the owner's box.
    """
    if os.name != "nt":
        return False
    probe = (
        "$s = Get-Service WinDefend -ErrorAction SilentlyContinue; "
        "if (-not $s -or $s.Status -ne 'Running') { 'inactive'; exit 0 }; "
        "try { if ((Get-MpComputerStatus).RealTimeProtectionEnabled) { 'active' } else { 'inactive' } } "
        "catch { 'active' }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", probe],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            **hidden_subprocess_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return bool(lines) and lines[-1].lower() == "active"


def _run_elevated_powershell(script: Path, arguments: list[str]) -> int:
    """Launch an elevated, hidden PowerShell through UAC; return ShellExecute code.

    >32 means the process started (the user accepted UAC); 5 (SE_ERR_ACCESSDENIED)
    means UAC was declined; anything else <=32 is another launch failure. It does
    not wait - the guard coordinates through files instead.
    """
    if os.name != "nt":
        return 0
    parts = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", f'"{script}"', *arguments]
    params = " ".join(parts)
    SW_HIDE = 0
    return int(ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, SW_HIDE))


def _read_guard_result(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not raw:
        return ""
    status, _, detail = raw.partition("\t")
    return f"{status}: {detail}".strip() if detail else status


def _cleanup_guard_files(*paths: Path) -> None:
    for path in paths:
        with contextlib.suppress(OSError):
            path.unlink()


def _guard_path_argument(paths: list[Path]) -> str:
    # Folders are joined with '|', which Windows paths can never contain, so a
    # single quoted argument survives ShellExecute and the script splits it back.
    return "|".join(str(path) for path in paths)


@contextlib.contextmanager
def _defender_guard(context: JobContext, paths: Path | Iterable[Path]) -> Iterator[None]:
    """Exclude one or more folders from Defender for the block, then restore them."""
    targets = [paths] if isinstance(paths, (str, Path)) else list(paths)
    # Keep unique, existing-or-not folders in a stable order.
    seen: dict[str, Path] = {}
    for item in targets:
        resolved = Path(item)
        seen.setdefault(str(resolved), resolved)
    folders = list(seen.values())
    label = ", ".join(str(folder) for folder in folders)

    if not folders or not _defender_active(context):
        context.log("[DEFENDER] Real-time protection is not active; no exclusion needed.")
        yield
        return

    guard_dir = _defender_guard_dir(context)
    uid = uuid.uuid4().hex
    lock = guard_dir / f"{uid}.lock"
    ready = guard_dir / f"{uid}.ready"
    result = guard_dir / f"{uid}.result"
    lock.write_text("lock", encoding="utf-8")
    excluded = False
    try:
        context.log(f"[DEFENDER] Requesting a temporary exclusion for {label} (Windows will ask for UAC).")
        code = _run_elevated_powershell(
            _defender_guard_script(context),
            [
                "-Action", "Begin",
                "-Path", f'"{_guard_path_argument(folders)}"',
                "-ParentPid", str(os.getpid()),
                "-Lock", f'"{lock}"',
                "-Ready", f'"{ready}"',
                "-Result", f'"{result}"',
                "-MaxSeconds", str(_DEFENDER_GUARD_MAX_SECONDS),
            ],
        )
        if code <= 32:
            reason = "UAC was declined" if code == 5 else f"elevation failed (code {code})"
            context.log(f"[DEFENDER] {reason}; building without an exclusion (it may fail on version.dll).")
        else:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if ready.exists():
                    excluded = True
                    break
                if result.exists():
                    break
                time.sleep(0.3)
            if excluded:
                context.log(f"[DEFENDER] Temporary exclusion active for {label}.")
            else:
                status = _read_guard_result(result)
                context.log(
                    f"[DEFENDER] {status or 'Exclusion was not confirmed'}; "
                    "building without an exclusion (it may fail on version.dll)."
                )
        yield
    finally:
        # Releasing the lock is the signal for the elevated guard to remove the
        # exclusion; it also removes it on its own if this process has died.
        _cleanup_guard_files(lock)
        if excluded:
            deadline = time.monotonic() + 15
            removed = False
            while time.monotonic() < deadline:
                if _read_guard_result(result).startswith("REMOVED"):
                    removed = True
                    break
                time.sleep(0.3)
            context.log(
                "[DEFENDER] Exclusion removed."
                if removed
                else "[DEFENDER] Removal not confirmed in time; if it lingers, run 'Defender: remove exclusion'."
            )
        _cleanup_guard_files(ready, result)


def defender_exclusion_remove(context: JobContext) -> dict[str, object]:
    """Manually take back the exclusions the build and update guards add.

    A safety net for the rare case where an operation was killed hard and the
    elevated guard never got to remove its exclusion. It clears the output folder
    and, if a build is present in input (what an update excludes), that folder
    too. Idempotent: removing a path that is not excluded is not an error.
    """
    if os.name != "nt":
        raise RuntimeError("Defender exclusions are a Windows-only concern.")
    folders = [_output_root(context)]
    with contextlib.suppress(RuntimeError):
        folders.append(_find_input_build(context))
    label = ", ".join(str(folder) for folder in folders)
    if not _defender_active(context):
        context.log("[DEFENDER] Real-time protection is not active; nothing to remove.")
        context.progress(1.0)
        return {"removed": False, "reason": "defender inactive", "paths": [str(f) for f in folders]}

    guard_dir = _defender_guard_dir(context)
    result = guard_dir / f"remove_{uuid.uuid4().hex}.result"
    context.log(f"[DEFENDER] Removing the exclusion for {label} (Windows will ask for UAC).")
    code = _run_elevated_powershell(
        _defender_guard_script(context),
        ["-Action", "Remove", "-Path", f'"{_guard_path_argument(folders)}"', "-Result", f'"{result}"'],
    )
    if code <= 32:
        _cleanup_guard_files(result)
        if code == 5:
            raise RuntimeError("UAC was declined; the exclusion was not removed.")
        raise RuntimeError(f"Could not elevate to remove the exclusion (code {code}).")

    deadline = time.monotonic() + 20
    status = ""
    while time.monotonic() < deadline:
        status = _read_guard_result(result)
        if status:
            break
        time.sleep(0.3)
    _cleanup_guard_files(result)
    context.log(f"[DEFENDER] {status or 'No confirmation received.'}")
    context.progress(1.0)
    return {"removed": status.startswith("REMOVED"), "paths": [str(f) for f in folders]}


def _run_7z(context: JobContext, args: list[str], *, cwd: Path | None = None) -> None:
    exe = _require_7zip(context)
    command = [str(exe), *args]
    context.log("[7Z] " + " ".join(command))
    result = subprocess.run(
        command,
        cwd=str(cwd or context.paths.root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        **hidden_subprocess_kwargs(),
    )
    for line in result.stdout.splitlines():
        if line.strip():
            context.log(line)
    for line in result.stderr.splitlines():
        if line.strip():
            context.log("[STDERR] " + line)
    if result.returncode != 0:
        raise RuntimeError(f"7-Zip failed with exit code {result.returncode}.")


def _extract_archive(context: JobContext, archive: Path, target: Path) -> None:
    _reset_dir(target)
    _run_7z(context, ["x", str(archive), f"-o{target}", "-y"])


def _copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            if destination.exists():
                _remove_tree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def _find_dir(root: Path, name: str) -> Path | None:
    lowered = name.lower()
    for item in root.rglob("*"):
        if item.is_dir() and item.name.lower() == lowered:
            return item
    return None


def _find_file(root: Path, name: str) -> Path | None:
    lowered = name.lower()
    for item in root.rglob("*"):
        if item.is_file() and item.name.lower() == lowered:
            return item
    return None


def _zip_dir(context: JobContext, source_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    context.log(f"[ZIP] {source_dir} -> {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in source_dir.rglob("*"):
            if item.is_dir():
                rel = item.relative_to(source_dir.parent).as_posix().rstrip("/") + "/"
                archive.writestr(rel, b"")
            elif item.is_file():
                archive.write(item, item.relative_to(source_dir.parent))
    context.log(f"[OK] ZIP: {zip_path} ({zip_path.stat().st_size:,} bytes)")
    return zip_path


def _archive_format(context: JobContext) -> str:
    value = _param_text(context, "archive_format", "zip").lower()
    return value if value in {"zip", "7z"} else "zip"


def _archive_portable_dir(context: JobContext, source_dir: Path, base_name: str) -> Path:
    archive_format = _archive_format(context)
    if archive_format == "7z":
        archive_path = _portable_root(context) / f"{base_name}.7z"
        if archive_path.exists():
            archive_path.unlink()
        context.log(f"[7Z] {source_dir} -> {archive_path}")
        _run_7z(context, ["a", "-t7z", "-mx=9", str(archive_path), source_dir.name], cwd=source_dir.parent)
        context.log(f"[OK] 7Z: {archive_path} ({archive_path.stat().st_size:,} bytes)")
        return archive_path
    return _zip_dir(context, source_dir, _portable_root(context) / f"{base_name}.zip")


def _safe_output_child(context: JobContext, name: str) -> Path:
    portable = _portable_root(context).resolve()
    target = (portable / name).resolve()
    if target == portable or not target.is_relative_to(portable):
        raise RuntimeError(f"Refusing unsafe portable output path: {target}")
    return target


def _publish_portable_dir(context: JobContext, source_dir: Path, name: str) -> Path:
    target = _safe_output_child(context, name)
    if target.exists():
        _remove_tree(target)
    context.log(f"[PUBLISH] {source_dir} -> {target}")
    shutil.copytree(source_dir, target)
    context.log(f"[OK] FOLDER: {target}")
    return target


def _chrome_plus_arch(context: JobContext) -> str:
    value = _param_text(context, "chrome_plus_arch", "x64").lower()
    return value if value in {"x86", "x64", "arm64"} else "x64"


def _download_chrome_plus(
    context: JobContext,
    *,
    progress_start: float | None = None,
    progress_end: float | None = None,
) -> tuple[DownloadedAsset, str]:
    version, name, url = chrome_plus_release()
    context.log(f"[GITHUB] {CHROME_PLUS_REPO} latest={version} asset={name}")
    asset = _download(
        context,
        url,
        _archives_dir(context) / _safe_name(name),
        f"Chrome++ {version}",
        progress_start=progress_start,
        progress_end=progress_end,
    )
    return asset, version


def _download_yandex_installer(
    context: JobContext,
    *,
    progress_start: float | None = None,
    progress_end: float | None = None,
) -> tuple[DownloadedAsset, str]:
    source = _param_text(context, "yandex_download_url", YANDEX_FULL_INSTALLER_URL) or YANDEX_FULL_INSTALLER_URL
    version, resolved = yandex_available_version(source)
    context.log(f"[YANDEX] full installer {version or 'version unknown'}")
    filename = f"Yandex-{version}.exe" if version else "Yandex.exe"
    asset = _download(
        context,
        resolved,
        _archives_dir(context) / _safe_name(filename),
        f"Yandex Browser full installer {version}".strip(),
        user_agent=WINDOWS_USER_AGENT,
        progress_start=progress_start,
        progress_end=progress_end,
    )
    return asset, version


def _extract_browser_payload(context: JobContext, installer: Path) -> Path:
    """`Browser-bin` out of the installer: PE resource, then the 7z inside it."""
    resource_dir = _tmp_dir(context) / "installer"
    _extract_archive(context, installer, resource_dir)
    payload_archive = _find_file(resource_dir, PAYLOAD_ARCHIVE)
    if not payload_archive:
        raise RuntimeError(f"{PAYLOAD_ARCHIVE} was not found inside the Yandex installer.")
    context.log(f"[FOUND] {PAYLOAD_ARCHIVE}: {payload_archive}")
    payload_dir = _tmp_dir(context) / "payload"
    _extract_archive(context, payload_archive, payload_dir)
    browser_bin = _find_dir(payload_dir, PAYLOAD_DIRECTORY)
    if not browser_bin:
        raise RuntimeError(f"{PAYLOAD_DIRECTORY} was not found after extracting {PAYLOAD_ARCHIVE}.")
    return browser_bin


def _chrome_plus_arch_dir(context: JobContext, archive: Path) -> Path:
    extract_root = _tmp_dir(context) / "chrome_plus"
    _extract_archive(context, archive, extract_root)
    arch = _chrome_plus_arch(context)
    arch_dir = extract_root / arch
    if not arch_dir.is_dir():
        arch_dir = _find_dir(extract_root, arch) or arch_dir
    if not arch_dir.is_dir():
        raise RuntimeError(f"{arch} folder was not found inside the Chrome++ archive.")
    return arch_dir


def _clear_app_dir(portable_dir: Path) -> Path:
    """Wipe `App` only, and only inside a folder that is ours."""
    app_dir = portable_dir / "App"
    if portable_dir.name != PORTABLE_NAME:
        raise RuntimeError(f"Refusing to update an unexpected portable root: {portable_dir}")
    if app_dir.resolve().parent != portable_dir.resolve():
        raise RuntimeError(f"Refusing to clear an unsafe App path: {app_dir}")
    if app_dir.exists():
        _remove_tree(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def _place_browser(context: JobContext, portable_dir: Path, browser_bin: Path) -> None:
    app_dir = portable_dir / "App"
    app_dir.mkdir(parents=True, exist_ok=True)
    context.log(f"[COPY] {PAYLOAD_DIRECTORY} contents -> {app_dir}")
    _copy_tree_contents(browser_bin, app_dir)
    if not (app_dir / BROWSER_EXECUTABLE).exists():
        raise RuntimeError(f"{BROWSER_EXECUTABLE} was not found in {PORTABLE_NAME}\\App after the copy.")


def _place_chrome_plus(context: JobContext, portable_dir: Path, arch_dir: Path) -> None:
    """The two Chrome++ files go beside browser.exe; Data and Cache stay put."""
    app_template = arch_dir / "App"
    app_dir = portable_dir / "App"
    app_dir.mkdir(parents=True, exist_ok=True)
    for name in ("version.dll", "chrome++.ini"):
        source = app_template / name
        if not source.is_file():
            raise RuntimeError(f"Chrome++ archive has no {name} for this architecture.")
        shutil.copy2(source, app_dir / name)
        context.log(f"[COPY] Chrome++ {name} -> {app_dir / name}")
    for folder_name in ("Data", "Cache"):
        (portable_dir / folder_name).mkdir(parents=True, exist_ok=True)


def _disable_bundled_updater(context: JobContext, portable_dir: Path) -> list[str]:
    """A portable build must not be updated by the vendor's own service."""
    removed: list[str] = []
    app_dir = portable_dir / "App"
    for updater in app_dir.rglob(UPDATER_EXECUTABLE):
        if not updater.is_file():
            continue
        if not updater.resolve().is_relative_to(app_dir.resolve()):
            continue
        updater.unlink()
        removed.append(str(updater.relative_to(portable_dir)))
        context.log(f"[CLEAN] bundled updater removed: {updater.relative_to(portable_dir)}")
    if not removed:
        context.log(f"[INFO] No {UPDATER_EXECUTABLE} in this build.")
    return removed


def _read_ini(path: Path) -> tuple[str, str, bytes]:
    """Text, newline and byte-order mark, so a rewrite keeps the file's shape.

    Chrome++ ships `chrome++.ini` as UTF-16 LE with LF endings. Rewriting it as
    UTF-8 leaves Chrome++ unable to read it — and it fails silently, falling
    back to defaults that look exactly like a working configuration, because
    the default `data_dir` is the same `%app%\\..\\Data` the build wants anyway.
    """
    raw = path.read_bytes()
    for bom, encoding in ((b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"), (b"\xef\xbb\xbf", "utf-8")):
        if raw.startswith(bom):
            text = raw[len(bom):].decode(encoding)
            return text, ("\r\n" if "\r\n" in text else "\n"), bom
    text = raw.decode("utf-8", "replace")
    return text, ("\r\n" if "\r\n" in text else "\n"), b""


def _write_ini(path: Path, text: str, bom: bytes) -> None:
    encoding = {b"\xff\xfe": "utf-16-le", b"\xfe\xff": "utf-16-be"}.get(bom, "utf-8")
    path.write_bytes(bom + text.encode(encoding))


def _registry_vendor(branch: str) -> str:
    """`Google` out of `HKCU\\Software\\Google\\Chrome` - who owns the branch."""
    parts = [part for part in branch.replace("/", "\\").split("\\") if part]
    return parts[2] if len(parts) > 2 else ""


def installed_browser_path() -> str:
    """Where the same browser is installed on this machine, or `''`.

    `App Paths` is what every Windows installer fills in, and it is readable
    without elevation. A portable build never writes there, so a hit means a
    real installation. The executable name alone is not enough: Chromium-Gost
    and Ungoogled ship `chrome.exe` too, and the entry an installed Google
    Chrome leaves would otherwise be read as theirs - so the path has to name
    the vendor whose registry branch is at stake.
    """
    import winreg

    vendor = "Yandex"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(
                    root,
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{BROWSER_EXECUTABLE}",
                    0,
                    winreg.KEY_READ | view,
                ) as key:
                    value = str(winreg.QueryValueEx(key, "")[0] or "").strip('"')
            except OSError:
                continue
            if value and (not vendor or vendor.lower() in value.lower()):
                return value
    return ""


def _registry_wipe_allowed(context: JobContext, wipe_registry: bool) -> bool:
    """Whether this build may take the browser's registry branch with it.

    The branch belongs to the browser, not to the build: an installed copy of
    the same browser keeps its own settings there. Wiping it on exit would take
    those along, so where such a copy exists the cleanup is dropped and said out
    loud rather than done quietly.
    """
    if not wipe_registry:
        return False
    installed = installed_browser_path()
    if installed:
        context.log(
            f"[GUARD] Yandex Browser is installed on this machine ({installed}). "
            f"{YANDEX_REGISTRY_BRANCH} is shared with it, so the build leaves the branch alone."
        )
        return False
    return True


def _configure_chrome_plus_ini(context: JobContext, portable_dir: Path, *, wipe_registry: bool) -> None:
    """Write the two settings this build owns, leave the rest of the file alone."""
    ini_path = portable_dir / "App" / "chrome++.ini"
    if not ini_path.is_file():
        raise RuntimeError(f"chrome++.ini was not found: {ini_path}")
    text, newline, bom = _read_ini(ini_path)
    exit_command = f'reg delete "{YANDEX_REGISTRY_BRANCH}" /f;' if _registry_wipe_allowed(context, wipe_registry) else ""
    # A callable replacement, because the command is a registry path: `\S` in
    # `HKCU\Software` would otherwise be read as an escape in the template.
    replaced = re.sub(
        r"(?m)^launch_on_exit=.*$",
        lambda _match: f"launch_on_exit={exit_command}",
        text,
        count=1,
    )
    if replaced == text and "launch_on_exit=" not in text:
        replaced = text.rstrip("\r\n") + f"{newline}launch_on_exit={exit_command}{newline}"
    _write_ini(ini_path, replaced, bom)
    if wipe_registry:
        context.log(f"[INI] launch_on_exit wipes {YANDEX_REGISTRY_BRANCH} when the browser closes")
    else:
        context.log("[INI] launch_on_exit left empty: the registry branch is kept")


# The library's own defaults also mute Google traffic, block broadcasts and
# rewrite the user agent. This file keeps to portability alone, so the browser
# behaves the way its own settings say; the rest is a hand edit away, and every
# key is documented in the library's README.
PROXY_LIBRARY_INI = """\
; Written by this program for the build it sits in.
[Parameters]
APPDIR=1
REGOFF={regoff}
AIDOFF=1
DIROFF=0
RMDISK=0
REFINE=0
SPFOLD=1
BCTOFF=0
STARTM=0
ECHOFF=0
DNSOFF=0

[General]
COMPNAME=
DATADIR=..\\Data
CACHEDIR=..\\Cache
SPECFOLDER=..\\Data
RUNPARAM=
"""


def _gitflic_page(path: str) -> str:
    request = Request(f"{PROXY_LIBRARY_HOST}{path}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def proxy_library_release() -> tuple[str, str]:
    """Version and download URL of the newest proxy library release.

    GitFlic's REST API needs a personal token, so the public pages are read
    instead. The version is the first four-part number on the list, which is
    sorted newest first: the heading beside it is hand-written, the number is
    what the release is named after.
    """
    listing = _gitflic_page(f"/project/{PROXY_LIBRARY_PROJECT}/release?sort=TIME&direction=DESC")
    releases = re.findall(rf"/project/{PROXY_LIBRARY_PROJECT}/release/([0-9a-f-]{{36}})", listing)
    versions = re.findall(r"\b(\d+\.\d+\.\d+\.\d+)\b", listing)
    if not releases:
        raise RuntimeError("No releases were found on the proxy library page.")
    version = versions[0] if versions else ""
    page = _gitflic_page(f"/project/{PROXY_LIBRARY_PROJECT}/release/{releases[0]}")
    match = re.search(rf'href="(/project/{PROXY_LIBRARY_PROJECT}/release/{releases[0]}/[0-9a-f-]{{36}}/download)"', page)
    if match:
        return version, f"{PROXY_LIBRARY_HOST}{match.group(1)}"
    # No attachment on that release: the repository archive of the same tag
    # carries the very same `Bin` folder.
    if not version:
        raise RuntimeError("The proxy library release has neither an attachment nor a version to fall back on.")
    return version, f"{PROXY_LIBRARY_HOST}/project/{PROXY_LIBRARY_PROJECT}/file/downloadAll?branch={version}&format=zip"


def _download_proxy_library(
    context: JobContext,
    *,
    progress_start: float | None = None,
    progress_end: float | None = None,
) -> tuple[DownloadedAsset, str]:
    version, url = proxy_library_release()
    context.log(f"[GITFLIC] {PROXY_LIBRARY_PROJECT} latest={version or 'unknown'}")
    asset = _download(
        context,
        url,
        _archives_dir(context) / f"proxy-library-{version or 'latest'}.zip",
        f"Proxy library {version}".strip(),
        progress_start=progress_start,
        progress_end=progress_end,
    )
    return asset, version


def _write_proxy_library_ini(context: JobContext, portable_dir: Path, *, block_registry: bool) -> None:
    text = PROXY_LIBRARY_INI.format(regoff="1" if block_registry else "0")
    (portable_dir / "App" / "version.ini").write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    if block_registry:
        context.log("[INI] registry writes are blocked while the browser runs")
    else:
        context.log("[INI] registry writes left alone: the browser keeps its own branch")


def _place_proxy_library(
    context: JobContext,
    portable_dir: Path,
    archive: Path,
    *,
    block_registry: bool,
) -> None:
    """The proxy library's `version.dll` goes beside browser.exe, plus its ini.

    Unlike Chrome++ it does not wipe the registry branch on exit - it blocks the
    writes outright, so nothing accumulates to be wiped. The cost is that
    `Set as default browser` stops working, which a portable build has no
    business doing anyway.
    """
    arch = _chrome_plus_arch(context)
    if arch not in PROXY_LIBRARY_DLL:
        raise RuntimeError(
            f"The proxy library ships x86 and x64 only, and {arch} was asked for. "
            "Chrome++ is the wrapper that covers ARM64."
        )
    extract_root = _tmp_dir(context) / "proxy_library"
    if not extract_root.exists() or not any(extract_root.iterdir()):
        _extract_archive(context, archive, extract_root)
    source = _find_file(extract_root, PROXY_LIBRARY_DLL[arch])
    if source is None:
        raise RuntimeError(f"{PROXY_LIBRARY_DLL[arch]} was not found inside the proxy library archive.")
    app_dir = portable_dir / "App"
    app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, app_dir / "version.dll")
    context.log(f"[COPY] proxy library {PROXY_LIBRARY_DLL[arch]} -> {app_dir / 'version.dll'}")
    _write_proxy_library_ini(context, portable_dir, block_registry=block_registry)
    for folder_name in ("Data", "Cache"):
        (portable_dir / folder_name).mkdir(parents=True, exist_ok=True)


def _portable_engine(context: JobContext) -> str:
    value = _param_text(context, "portable_engine", DEFAULT_PORTABLE_ENGINE).strip().lower()
    return value if value in PORTABLE_ENGINES else DEFAULT_PORTABLE_ENGINE


def _download_wrapper(
    context: JobContext,
    engine: str,
    *,
    progress_start: float | None = None,
    progress_end: float | None = None,
) -> tuple[DownloadedAsset | None, str]:
    """The archive the chosen engine needs, or `(None, "")` when it needs none."""
    if engine == "chrome_plus":
        return _download_chrome_plus(context, progress_start=progress_start, progress_end=progress_end)
    return _download_proxy_library(context, progress_start=progress_start, progress_end=progress_end)


def _place_wrapper(
    context: JobContext,
    portable_dir: Path,
    *,
    engine: str,
    asset: DownloadedAsset | None,
    wipe_registry: bool,
) -> None:
    if engine == "chrome_plus":
        _place_chrome_plus(context, portable_dir, _chrome_plus_arch_dir(context, asset.path))
        _configure_chrome_plus_ini(context, portable_dir, wipe_registry=wipe_registry)
        return
    _place_proxy_library(context, portable_dir, asset.path, block_registry=wipe_registry)


def _write_launcher(context: JobContext, portable_dir: Path) -> Path:
    """One click from the build root, so nobody has to walk into `App`.

    The wrapper reads the profile paths itself, so the browser needs no
    switches here.
    """
    launcher = portable_dir / f"{PORTABLE_NAME}.cmd"
    launcher.write_text(
        "@echo off\r\n"
        f'start "" "%~dp0App\\{BROWSER_EXECUTABLE}" %*\r\n',
        encoding="utf-8",
    )
    context.log(f"[OK] LAUNCHER: {launcher}")
    return launcher


def build_versions(portable_dir: Path) -> BuildVersions:
    """Read the versions out of the build itself, not out of a state file.

    A build handed over by someone else has no state file, and the folder is
    still the truth: the browser names its own version folder, and Chrome++
    carries its version in `version.dll`.
    """
    app_dir = portable_dir / "App"
    yandex = _file_version(app_dir / BROWSER_EXECUTABLE)
    if not yandex:
        versions = sorted(
            (item.name for item in app_dir.iterdir() if item.is_dir() and re.fullmatch(r"[\d.]+", item.name)),
            key=lambda name: [int(part) for part in name.split(".") if part.isdigit()],
        ) if app_dir.is_dir() else []
        yandex = versions[-1] if versions else ""
    return BuildVersions(yandex, _file_version(app_dir / "version.dll"))


def _write_build_stamp(
    context: JobContext,
    portable_dir: Path,
    versions: BuildVersions,
    extra: dict[str, Any],
) -> Path:
    """A human-readable note beside the build. Nothing reads it back."""
    stamp = portable_dir / BUILD_STAMP_FILE
    payload = {
        "product": PORTABLE_NAME,
        "yandex_version": versions.yandex,
        "chrome_plus_version": versions.chrome_plus,
        "built_by": "Audion Yandex Portable",
        **extra,
    }
    stamp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    context.log(f"[OK] {BUILD_STAMP_FILE}: {stamp}")
    return stamp


def _find_input_build(context: JobContext) -> Path:
    root = _input_root(context)
    if root.name == PORTABLE_NAME and root.is_dir():
        return root
    candidate = root / PORTABLE_NAME
    if candidate.is_dir():
        return candidate
    raise RuntimeError(
        f"{PORTABLE_NAME} was not found in input. Put the build into input\\{PORTABLE_NAME} "
        "or select that folder as the source."
    )


def install_portable_7zip(context: JobContext) -> dict[str, object]:
    before = _seven_zip_version(context)
    if before:
        context.log(f"[OK] Portable 7-Zip already available: {before}")
        return {"installed": False, "version": before, "path": str(_seven_zip_path(context))}

    script = context.paths.root / "install" / "Install-Portable-7Zip.cmd"
    if not script.exists():
        raise RuntimeError(f"Portable 7-Zip installer was not found: {script}")
    context.log(f"[RUN] {script} /NOPAUSE")
    result = subprocess.run(
        [str(script), "/NOPAUSE"],
        cwd=str(context.paths.root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        env=utf8_subprocess_env(),
        **hidden_subprocess_kwargs(),
    )
    for line in result.stdout.splitlines():
        if line.strip():
            context.log(line)
    for line in result.stderr.splitlines():
        if line.strip():
            context.log("[STDERR] " + line)
    if result.returncode != 0:
        raise RuntimeError(f"Portable 7-Zip install failed with exit code {result.returncode}.")
    version = _seven_zip_version(context)
    if not version:
        raise RuntimeError("Portable 7-Zip installer finished, but 7za.exe is not usable.")
    context.log(f"[OK] Portable 7-Zip installed: {version}")
    context.progress(1.0)
    return {"installed": True, "version": version, "path": str(_seven_zip_path(context))}


def check_updates(context: JobContext) -> dict[str, object]:
    """What is published against what the build in input carries. Downloads nothing."""
    available_yandex, resolved = yandex_available_version(
        _param_text(context, "yandex_download_url", YANDEX_FULL_INSTALLER_URL) or YANDEX_FULL_INSTALLER_URL
    )
    context.log(f"[YANDEX] published: {available_yandex or 'unknown'}")
    context.log(f"[URL] {resolved}")
    context.progress(0.4)

    engine = _portable_engine(context)
    plus_version = _published_wrapper_version(context, engine)
    plus_url = ""
    context.progress(0.7)

    try:
        build = _find_input_build(context)
    except RuntimeError as exc:
        context.log(f"[INFO] {exc}")
        context.progress(1.0)
        return {
            "yandex_available": available_yandex,
            "chrome_plus_available": plus_version,
            "build": "",
            "yandex_installed": "",
            "chrome_plus_installed": "",
            "yandex_update": bool(available_yandex),
            "chrome_plus_update": True,
        }

    versions = build_versions(build)
    context.log(f"[BUILD] {build}")
    context.log(f"[BUILD] Yandex: {versions.yandex or 'unknown'}, Chrome++: {versions.chrome_plus or 'unknown'}")
    yandex_update = bool(available_yandex) and not same_version(available_yandex, versions.yandex)
    plus_update = bool(plus_version) and not same_version(plus_version, versions.chrome_plus)
    context.log(
        "[RESULT] Yandex: " + ("update available" if yandex_update else "up to date")
        + "; Chrome++: " + ("update available" if plus_update else "up to date")
    )
    context.progress(1.0)
    return {
        "yandex_available": available_yandex,
        "chrome_plus_available": plus_version,
        "build": str(build),
        "yandex_installed": versions.yandex,
        "chrome_plus_installed": versions.chrome_plus,
        "yandex_update": yandex_update,
        "chrome_plus_update": plus_update,
        "url": resolved,
        "chrome_plus_url": plus_url,
    }


def build_portable(context: JobContext) -> dict[str, object]:
    """Download both parts and assemble a fresh build under output\\Portable."""
    _require_7zip(context)
    keep_temp = _param_bool(context, "keep_temp", False)
    package_archive = _param_bool(context, "package_archive", False)
    wipe_registry = _param_bool(context, "wipe_registry_on_exit", True)
    disable_updater = _param_bool(context, "disable_updater", True)
    guard_defender = _param_bool(context, "guard_defender", True)

    # Chrome++'s version.dll is a routine Defender false positive; the guard keeps
    # the output folder out of Defender's reach for the length of the build and
    # restores it afterwards. It is a no-op where Defender is not running.
    guard = (
        _defender_guard(context, _output_root(context))
        if guard_defender
        else contextlib.nullcontext()
    )
    with guard:
        engine = _portable_engine(context)
        plus_asset, plus_version = _download_wrapper(context, engine, progress_start=0.0, progress_end=0.05)
        context.progress(0.05)
        installer, yandex_version = _download_yandex_installer(context, progress_start=0.05, progress_end=0.5)
        context.progress(0.5)

        portable_dir = _tmp_dir(context) / PORTABLE_NAME
        if portable_dir.exists():
            _remove_tree(portable_dir)
        portable_dir.mkdir(parents=True, exist_ok=True)

        browser_bin = _extract_browser_payload(context, installer.path)
        context.progress(0.7)
        _place_browser(context, portable_dir, browser_bin)
        _place_wrapper(context, portable_dir, engine=engine, asset=plus_asset, wipe_registry=wipe_registry)
        removed = _disable_bundled_updater(context, portable_dir) if disable_updater else []
        _write_launcher(context, portable_dir)
        versions = build_versions(portable_dir)
        _write_build_stamp(
            context,
            portable_dir,
            versions,
            {"mode": "build", "source_url": installer.url, "chrome_plus_release": plus_version},
        )
        context.progress(0.85)

        result_path = (
            _archive_portable_dir(context, portable_dir, PORTABLE_NAME)
            if package_archive
            else _publish_portable_dir(context, portable_dir, PORTABLE_NAME)
        )
        if not keep_temp:
            _remove_tree(_tmp_dir(context))
        context.progress(1.0)
        return {
            "mode": "build",
            "yandex_version": versions.yandex or yandex_version,
            "chrome_plus_version": versions.chrome_plus or plus_version,
            "packaged": package_archive,
            "archive_format": _archive_format(context) if package_archive else "",
            "artifact": str(result_path),
            "updater_removed": removed,
            "registry_wiped_on_exit": wipe_registry,
            "output": str(_portable_root(context)),
        }


def update_portable(context: JobContext) -> dict[str, object]:
    """Refresh App from a new download, keep Data and Cache as they are."""
    _require_7zip(context)
    keep_temp = _param_bool(context, "keep_temp", False)
    package_archive = _param_bool(context, "package_archive", False)
    wipe_registry = _param_bool(context, "wipe_registry_on_exit", True)
    disable_updater = _param_bool(context, "disable_updater", True)
    force = _param_bool(context, "force_update", False)
    guard_defender = _param_bool(context, "guard_defender", True)

    source = _find_input_build(context)
    current = build_versions(source)
    context.log(f"[BUILD] {source}")
    context.log(f"[BUILD] Yandex: {current.yandex or 'unknown'}, Chrome++: {current.chrome_plus or 'unknown'}")

    available, resolved = yandex_available_version(
        _param_text(context, "yandex_download_url", YANDEX_FULL_INSTALLER_URL) or YANDEX_FULL_INSTALLER_URL
    )
    context.log(f"[YANDEX] published: {available or 'unknown'}")
    engine = _portable_engine(context)
    if available and same_version(available, current.yandex) and not force:
        # The browser is current, but the wrapper is what makes the build
        # portable and it is released far more often. 180 KB is not worth a
        # second trip. With no wrapper there is nothing else to compare.
        plus_version = _published_wrapper_version(context, engine)
        if not plus_version or same_version(plus_version, current.chrome_plus):
            context.log("[SKIP] Browser and wrapper are both current. Nothing was downloaded.")
            context.progress(1.0)
            return {
                "mode": "update",
                "updated": False,
                "reason": "already current",
                "yandex_version": current.yandex,
                "chrome_plus_version": current.chrome_plus,
                "source": str(source),
            }
        context.log(f"[INFO] Browser is current; wrapper {current.chrome_plus or 'unknown'} -> {plus_version}.")
        # Delegated before opening a guard here, so its guard is the only one.
        return update_wrapper(context)
    context.progress(0.1)

    # version.dll lands both in the workspace (under output) and in the build the
    # App is copied into, so the guard covers both roots.
    guard = (
        _defender_guard(context, [_output_root(context), source])
        if guard_defender
        else contextlib.nullcontext()
    )
    with guard:
        # Only the new App is staged here. It then replaces the one inside the
        # build the person picked, so the folder they chose is the folder that
        # becomes current; the Target stays reserved for freshly built browsers.
        work = _tmp_dir(context) / PORTABLE_NAME
        if work.exists():
            _remove_tree(work)
        work.mkdir(parents=True, exist_ok=True)

        plus_asset, plus_version = _download_wrapper(context, engine, progress_start=0.1, progress_end=0.15)
        installer, _version = _download_yandex_installer(context, progress_start=0.15, progress_end=0.6)
        context.progress(0.6)

        browser_bin = _extract_browser_payload(context, installer.path)
        context.progress(0.75)
        _place_browser(context, work, browser_bin)
        _place_wrapper(context, work, engine=engine, asset=plus_asset, wipe_registry=wipe_registry)
        removed = _disable_bundled_updater(context, work) if disable_updater else []
        _replace_app_in_place(context, source, work / "App")
        _write_launcher(context, source)
        versions = build_versions(source)
        _write_build_stamp(
            context,
            source,
            versions,
            {
                "mode": "update",
                "previous_yandex_version": current.yandex,
                "source_url": installer.url,
                "chrome_plus_release": plus_version,
            },
        )
        context.progress(0.9)

        result_path = (
            _archive_portable_dir(context, source, f"{PORTABLE_NAME}.updated")
            if package_archive
            else source
        )
        if not keep_temp:
            _remove_tree(_tmp_dir(context))
        context.progress(1.0)
    return {
        "mode": "update",
        "updated": True,
        "source": str(source),
        "previous_yandex_version": current.yandex,
        "yandex_version": versions.yandex,
        "chrome_plus_version": versions.chrome_plus,
        "packaged": package_archive,
        "archive_format": _archive_format(context) if package_archive else "",
        "artifact": str(result_path),
        "updater_removed": removed,
        "registry_wiped_on_exit": wipe_registry,
        "url": resolved,
        "output": str(_portable_root(context)),
    }


def _replace_app_in_place(context: JobContext, target: Path, staged_app: Path) -> None:
    """Swap `App` inside the build the person pointed at, keeping the rest.

    An update belongs where the build already lives: someone picks a folder as
    the Source, presses Update, and expects *that* folder to become current. A
    build published into the Target instead would leave the picked one untouched
    and old, with no hint why - the Target is for new builds.

    `Data` and `Cache` are never moved, and the new `App` is assembled in full
    before anything is touched, so a failed download cannot leave half a browser.
    """
    app_dir = target / "App"
    retired = target / f"App.replaced-{os.getpid()}"
    if app_dir.exists():
        try:
            app_dir.rename(retired)
        except OSError as exc:
            raise RuntimeError(
                f"The build is in use, so App could not be replaced. "
                f"Close the browser and run the update again. ({exc})"
            ) from exc
    try:
        shutil.move(str(staged_app), str(app_dir))
    except OSError:
        if retired.exists():
            retired.rename(app_dir)
        raise
    _remove_tree(retired)
    context.log(f"[UPDATE] App replaced in place: {target}")

def _published_wrapper_version(context: JobContext, engine: str) -> str:
    """What the chosen wrapper publishes today; nothing is downloaded."""
    if engine == "chrome_plus":
        version, name, _url = chrome_plus_release()
        context.log(f"[CHROME++] published: {version} ({name})")
        return version
    version, _url = proxy_library_release()
    context.log(f"[PROXY] published: {version or 'unknown'}")
    return version


def update_proxy_library(context: JobContext) -> dict[str, object]:
    """Replace only the proxy library, leaving the browser untouched."""
    _require_7zip(context)
    keep_temp = _param_bool(context, "keep_temp", False)
    wipe_registry = _param_bool(context, "wipe_registry_on_exit", False)
    guard_defender = _param_bool(context, "guard_defender", True)

    source = _find_input_build(context)
    current = build_versions(source)
    context.log(f"[BUILD] {source}")
    context.log(f"[BUILD] wrapper in the build: {current.chrome_plus or 'unknown'}")

    guard = (
        _defender_guard(context, [_output_root(context), source])
        if guard_defender
        else contextlib.nullcontext()
    )
    with guard:
        asset, version = _download_proxy_library(context, progress_start=0.0, progress_end=0.6)
        context.progress(0.6)
        _place_proxy_library(context, source, asset.path, block_registry=wipe_registry)
        versions = build_versions(source)
        _write_build_stamp(
            context,
            source,
            versions,
            {
                "mode": "proxy_library",
                "portable_engine": "proxy_library",
                "previous_chrome_plus_version": current.chrome_plus,
                "proxy_library_release": version,
            },
        )
        if not keep_temp:
            _remove_tree(_tmp_dir(context))
        context.progress(1.0)
        return {
            "mode": "proxy_library",
            "build": str(source),
            "previous_wrapper_version": current.chrome_plus,
            "wrapper_version": versions.chrome_plus or version,
            "yandex_version": versions.yandex,
        }


def update_wrapper(context: JobContext) -> dict[str, object]:
    """Refresh whichever library the operator picked, browser untouched."""
    engine = _portable_engine(context)
    if engine == "proxy_library":
        return update_proxy_library(context)
    return update_chrome_plus(context)


def update_chrome_plus(context: JobContext) -> dict[str, object]:
    """Replace only the two Chrome++ files, leaving the browser untouched."""
    _require_7zip(context)
    keep_temp = _param_bool(context, "keep_temp", False)
    wipe_registry = _param_bool(context, "wipe_registry_on_exit", True)
    guard_defender = _param_bool(context, "guard_defender", True)

    source = _find_input_build(context)
    current = build_versions(source)
    context.log(f"[BUILD] {source}")
    context.log(f"[BUILD] Chrome++ in the build: {current.chrome_plus or 'unknown'}")

    # version.dll lands both in the workspace (under output) and in the build
    # itself; the guard covers both roots so the Defender false positive cannot
    # break an update the way it breaks a build.
    guard = (
        _defender_guard(context, [_output_root(context), source])
        if guard_defender
        else contextlib.nullcontext()
    )
    with guard:
        plus_asset, plus_version = _download_chrome_plus(context, progress_start=0.0, progress_end=0.6)
        context.progress(0.6)
        _place_chrome_plus(context, source, _chrome_plus_arch_dir(context, plus_asset.path))
        _configure_chrome_plus_ini(context, source, wipe_registry=wipe_registry)
        versions = build_versions(source)
        _write_build_stamp(
            context,
            source,
            versions,
            {"mode": "chrome_plus", "previous_chrome_plus_version": current.chrome_plus, "chrome_plus_release": plus_version},
        )
        if not keep_temp:
            _remove_tree(_tmp_dir(context))
        context.progress(1.0)
    return {
        "mode": "chrome_plus",
        "build": str(source),
        "previous_chrome_plus_version": current.chrome_plus,
        "chrome_plus_version": versions.chrome_plus or plus_version,
        "yandex_version": versions.yandex,
    }
